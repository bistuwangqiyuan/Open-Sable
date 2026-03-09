"""
Pipeline Skill — Deal / opportunity tracking for B2B workflows.

Tables:
  deals        — links a buyer contact to manufacturer contact(s) with product/qty/stage
  deal_events  — audit trail of every stage change, message, etc.

Pipeline stages:
  prospect → qualified → proposal → negotiation → won | lost
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import aiosqlite
    AIOSQLITE = True
except ImportError:
    AIOSQLITE = False

DB_NAME = "crm.db"  # Same DB as CRM — co-located for JOIN efficiency

STAGES = ["prospect", "qualified", "proposal", "negotiation", "won", "lost"]

_CREATE_DEALS = """
CREATE TABLE IF NOT EXISTS deals (
    id               TEXT PRIMARY KEY,
    title            TEXT NOT NULL,
    buyer_id         TEXT,                  -- FK → contacts.id
    manufacturer_id  TEXT,                  -- FK → contacts.id
    product          TEXT,
    quantity          TEXT,
    unit             TEXT DEFAULT 'meters',
    quality_requirements TEXT,
    delivery_date    TEXT,
    price_range      TEXT,
    currency         TEXT DEFAULT 'EUR',
    stage            TEXT DEFAULT 'prospect',
    priority         TEXT DEFAULT 'medium',  -- low | medium | high | urgent
    notes            TEXT,
    value_estimate   REAL DEFAULT 0,         -- estimated deal value (EUR)
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL,
    closed_at        TEXT
);
"""

_CREATE_DEAL_EVENTS = """
CREATE TABLE IF NOT EXISTS deal_events (
    id          TEXT PRIMARY KEY,
    deal_id     TEXT NOT NULL,
    type        TEXT NOT NULL,               -- stage_change | note | email | requirement_update
    from_stage  TEXT,
    to_stage    TEXT,
    description TEXT,
    metadata    TEXT,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (deal_id) REFERENCES deals(id)
);
"""

_CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS idx_deals_stage ON deals(stage);",
    "CREATE INDEX IF NOT EXISTS idx_deals_buyer ON deals(buyer_id);",
    "CREATE INDEX IF NOT EXISTS idx_deals_mfr ON deals(manufacturer_id);",
    "CREATE INDEX IF NOT EXISTS idx_deal_events_deal ON deal_events(deal_id);",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class PipelineSkill:
    """B2B deal pipeline management backed by SQLite."""

    def __init__(self, data_dir: str = "./data"):
        self.db_path = Path(data_dir) / DB_NAME
        self._initialized = False

    async def initialize(self):
        if not AIOSQLITE:
            logger.warning("aiosqlite not installed — Pipeline skill disabled.")
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(_CREATE_DEALS)
            await db.execute(_CREATE_DEAL_EVENTS)
            for idx in _CREATE_IDX:
                await db.execute(idx)
            await db.commit()
        self._initialized = True
        logger.info("Pipeline skill ready")

    def is_ready(self) -> bool:
        return self._initialized and AIOSQLITE

    # ── Deal CRUD ─────────────────────────────────────────────────────────

    async def create_deal(
        self,
        title: str,
        buyer_id: str = "",
        manufacturer_id: str = "",
        product: str = "",
        quantity: str = "",
        unit: str = "meters",
        quality_requirements: str = "",
        delivery_date: str = "",
        price_range: str = "",
        currency: str = "EUR",
        priority: str = "medium",
        notes: str = "",
        value_estimate: float = 0,
    ) -> Dict[str, Any]:
        """Create a new deal in the pipeline."""
        did = _uuid()
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO deals
                   (id, title, buyer_id, manufacturer_id, product, quantity, unit,
                    quality_requirements, delivery_date, price_range, currency,
                    stage, priority, notes, value_estimate, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (did, title, buyer_id, manufacturer_id, product, quantity, unit,
                 quality_requirements, delivery_date, price_range, currency,
                 "prospect", priority, notes, value_estimate, now, now),
            )
            await db.execute(
                """INSERT INTO deal_events (id, deal_id, type, to_stage, description, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (_uuid(), did, "stage_change", "prospect", "Deal created", now),
            )
            await db.commit()
        return {"id": did, "title": title, "stage": "prospect"}

    async def update_deal(self, deal_id: str, **fields) -> Dict[str, Any]:
        """Update deal fields (not stage — use advance_deal for that)."""
        allowed = {
            "title", "buyer_id", "manufacturer_id", "product", "quantity",
            "unit", "quality_requirements", "delivery_date", "price_range",
            "currency", "priority", "notes", "value_estimate",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return {"error": "No valid fields to update"}
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [deal_id]
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(f"UPDATE deals SET {set_clause} WHERE id = ?", values)
            await db.commit()
        return {"updated": deal_id, "fields": list(updates.keys())}

    async def advance_deal(
        self, deal_id: str, new_stage: str, reason: str = ""
    ) -> Dict[str, Any]:
        """Move a deal to a new pipeline stage."""
        if new_stage not in STAGES:
            return {"error": f"Invalid stage '{new_stage}'. Valid: {STAGES}"}
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT stage FROM deals WHERE id = ?", (deal_id,))
            row = await cur.fetchone()
            if not row:
                return {"error": f"Deal {deal_id} not found"}
            old_stage = row["stage"]
            closed = now if new_stage in ("won", "lost") else None
            await db.execute(
                "UPDATE deals SET stage = ?, updated_at = ?, closed_at = COALESCE(?, closed_at) WHERE id = ?",
                (new_stage, now, closed, deal_id),
            )
            await db.execute(
                """INSERT INTO deal_events
                   (id, deal_id, type, from_stage, to_stage, description, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (_uuid(), deal_id, "stage_change", old_stage, new_stage, reason, now),
            )
            await db.commit()
        return {"deal_id": deal_id, "from": old_stage, "to": new_stage}

    async def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Get a deal by ID."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_deals(
        self,
        stage: str = "",
        buyer_id: str = "",
        manufacturer_id: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List deals, optionally filtered by stage or participant."""
        clauses: List[str] = []
        params: List[Any] = []
        if stage:
            clauses.append("stage = ?")
            params.append(stage)
        if buyer_id:
            clauses.append("buyer_id = ?")
            params.append(buyer_id)
        if manufacturer_id:
            clauses.append("manufacturer_id = ?")
            params.append(manufacturer_id)
        where = " AND ".join(clauses) if clauses else "1"
        sql = f"SELECT * FROM deals WHERE {where} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            return [dict(r) for r in await cur.fetchall()]

    async def get_deal_history(self, deal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """Get event history for a deal."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM deal_events WHERE deal_id = ? ORDER BY created_at DESC LIMIT ?",
                (deal_id, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get pipeline analytics: deals per stage, total value, etc."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            stage_rows = await (await db.execute(
                "SELECT stage, COUNT(*) as c, SUM(value_estimate) as v FROM deals GROUP BY stage"
            )).fetchall()
            total = (await (await db.execute("SELECT COUNT(*) as c FROM deals")).fetchone())["c"]
            return {
                "total_deals": total,
                "by_stage": {
                    r["stage"]: {"count": r["c"], "value": r["v"] or 0}
                    for r in stage_rows
                },
            }

    async def match_buyer_manufacturers(
        self, deal_id: str
    ) -> Dict[str, Any]:
        """
        Get a deal with its buyer and manufacturer contact details
        for matching purposes. Returns enriched deal info.
        """
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            deal_cur = await db.execute("SELECT * FROM deals WHERE id = ?", (deal_id,))
            deal = await deal_cur.fetchone()
            if not deal:
                return {"error": "Deal not found"}
            deal = dict(deal)

            buyer = manufacturer = None
            if deal.get("buyer_id"):
                cur = await db.execute("SELECT * FROM contacts WHERE id = ?", (deal["buyer_id"],))
                row = await cur.fetchone()
                if row:
                    buyer = dict(row)
            if deal.get("manufacturer_id"):
                cur = await db.execute("SELECT * FROM contacts WHERE id = ?", (deal["manufacturer_id"],))
                row = await cur.fetchone()
                if row:
                    manufacturer = dict(row)

            return {"deal": deal, "buyer": buyer, "manufacturer": manufacturer}
