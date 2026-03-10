"""
CRM Skill,  SQLite-backed contact & lead management.

Tables:
  contacts  ,  companies and individuals (name, email, company, country, role, etc.)
  activities,  timestamped log of every interaction (email sent, reply received, note)

Designed for the textile brokerage use-case but generic enough for any B2B workflow.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import aiosqlite
    AIOSQLITE = True
except ImportError:
    AIOSQLITE = False

DB_NAME = "crm.db"

# ── Schema ────────────────────────────────────────────────────────────────────

_CREATE_CONTACTS = """
CREATE TABLE IF NOT EXISTS contacts (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT,
    phone       TEXT,
    company     TEXT,
    country     TEXT,
    city        TEXT,
    role        TEXT DEFAULT 'prospect',   -- manufacturer | buyer | supplier | partner | prospect
    industry    TEXT,
    products    TEXT,                       -- comma-separated product categories
    status      TEXT DEFAULT 'new',        -- new | contacted | replied | qualified | inactive | blacklisted
    source      TEXT,                      -- web_search | referral | inbound | linkedin | manual
    tags        TEXT,                      -- comma-separated free-form tags
    notes       TEXT,
    website     TEXT,
    score       INTEGER DEFAULT 0,         -- lead score 0-100
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    last_contact TEXT,
    next_followup TEXT
);
"""

_CREATE_ACTIVITIES = """
CREATE TABLE IF NOT EXISTS activities (
    id          TEXT PRIMARY KEY,
    contact_id  TEXT NOT NULL,
    type        TEXT NOT NULL,             -- email_sent | email_received | note | call | meeting | status_change
    subject     TEXT,
    body        TEXT,
    metadata    TEXT,                      -- JSON blob for extra data
    created_at  TEXT NOT NULL,
    FOREIGN KEY (contact_id) REFERENCES contacts(id)
);
"""

_CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email);",
    "CREATE INDEX IF NOT EXISTS idx_contacts_status ON contacts(status);",
    "CREATE INDEX IF NOT EXISTS idx_contacts_role ON contacts(role);",
    "CREATE INDEX IF NOT EXISTS idx_contacts_country ON contacts(country);",
    "CREATE INDEX IF NOT EXISTS idx_activities_contact ON activities(contact_id);",
    "CREATE INDEX IF NOT EXISTS idx_contacts_next_followup ON contacts(next_followup);",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


# ── Skill ─────────────────────────────────────────────────────────────────────

class CRMSkill:
    """SQLite-backed CRM for contact & lead management."""

    def __init__(self, data_dir: str = "./data"):
        self.db_path = Path(data_dir) / DB_NAME
        self._initialized = False

    async def initialize(self):
        if not AIOSQLITE:
            logger.warning("aiosqlite not installed,  CRM skill disabled. pip install aiosqlite")
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(_CREATE_CONTACTS)
            await db.execute(_CREATE_ACTIVITIES)
            for idx in _CREATE_IDX:
                await db.execute(idx)
            await db.commit()
        self._initialized = True
        logger.info(f"CRM skill ready (db: {self.db_path})")

    def is_ready(self) -> bool:
        return self._initialized and AIOSQLITE

    # ── Contacts CRUD ─────────────────────────────────────────────────────

    async def add_contact(
        self,
        name: str,
        email: str = "",
        phone: str = "",
        company: str = "",
        country: str = "",
        city: str = "",
        role: str = "prospect",
        industry: str = "",
        products: str = "",
        source: str = "manual",
        tags: str = "",
        notes: str = "",
        website: str = "",
        score: int = 0,
    ) -> Dict[str, Any]:
        """Add a new contact. Returns the created contact dict."""
        cid = _uuid()
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO contacts
                   (id, name, email, phone, company, country, city, role, industry,
                    products, status, source, tags, notes, website, score, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, name, email, phone, company, country, city, role, industry,
                 products, "new", source, tags, notes, website, score, now, now),
            )
            await db.commit()
        return {"id": cid, "name": name, "email": email, "company": company, "status": "new"}

    async def update_contact(self, contact_id: str, **fields) -> Dict[str, Any]:
        """Update one or more fields on a contact."""
        allowed = {
            "name", "email", "phone", "company", "country", "city", "role",
            "industry", "products", "status", "source", "tags", "notes",
            "website", "score", "last_contact", "next_followup",
        }
        updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not updates:
            return {"error": "No valid fields to update"}
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [contact_id]
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
            await db.commit()
        return {"updated": contact_id, "fields": list(updates.keys())}

    async def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """Get a single contact by ID."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,))
            row = await cur.fetchone()
            return dict(row) if row else None

    async def search_contacts(
        self,
        query: str = "",
        role: str = "",
        status: str = "",
        country: str = "",
        tags: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Search contacts with filters. `query` matches name/email/company."""
        clauses: List[str] = []
        params: List[Any] = []
        if query:
            clauses.append("(name LIKE ? OR email LIKE ? OR company LIKE ?)")
            q = f"%{query}%"
            params.extend([q, q, q])
        if role:
            clauses.append("role = ?")
            params.append(role)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if country:
            clauses.append("country LIKE ?")
            params.append(f"%{country}%")
        if tags:
            clauses.append("tags LIKE ?")
            params.append(f"%{tags}%")

        where = " AND ".join(clauses) if clauses else "1"
        sql = f"SELECT * FROM contacts WHERE {where} ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a contact and its activities."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute("DELETE FROM activities WHERE contact_id = ?", (contact_id,))
            cur = await db.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
            await db.commit()
            return {"deleted": contact_id, "rows": cur.rowcount}

    # ── Activities ────────────────────────────────────────────────────────

    async def log_activity(
        self,
        contact_id: str,
        activity_type: str,
        subject: str = "",
        body: str = "",
        metadata: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Log an interaction with a contact."""
        aid = _uuid()
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(
                """INSERT INTO activities (id, contact_id, type, subject, body, metadata, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (aid, contact_id, activity_type, subject, body,
                 json.dumps(metadata or {}), now),
            )
            # Update last_contact on the contact
            await db.execute(
                "UPDATE contacts SET last_contact = ?, updated_at = ? WHERE id = ?",
                (now, now, contact_id),
            )
            await db.commit()
        return {"id": aid, "contact_id": contact_id, "type": activity_type}

    async def get_activities(
        self, contact_id: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get activity history for a contact."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM activities WHERE contact_id = ? ORDER BY created_at DESC LIMIT ?",
                (contact_id, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    # ── Bulk / Analytics ──────────────────────────────────────────────────

    async def get_stats(self) -> Dict[str, Any]:
        """Get CRM statistics: counts by role, status, country."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row

            total = (await (await db.execute("SELECT COUNT(*) as c FROM contacts")).fetchone())["c"]

            role_rows = await (await db.execute(
                "SELECT role, COUNT(*) as c FROM contacts GROUP BY role"
            )).fetchall()

            status_rows = await (await db.execute(
                "SELECT status, COUNT(*) as c FROM contacts GROUP BY status"
            )).fetchall()

            country_rows = await (await db.execute(
                "SELECT country, COUNT(*) as c FROM contacts GROUP BY country ORDER BY c DESC LIMIT 10"
            )).fetchall()

            return {
                "total_contacts": total,
                "by_role": {r["role"]: r["c"] for r in role_rows},
                "by_status": {r["status"]: r["c"] for r in status_rows},
                "top_countries": {r["country"]: r["c"] for r in country_rows},
            }

    async def get_overdue_followups(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contacts whose next_followup date has passed."""
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                """SELECT * FROM contacts
                   WHERE next_followup IS NOT NULL
                     AND next_followup <= ?
                     AND status NOT IN ('inactive', 'blacklisted')
                   ORDER BY next_followup ASC LIMIT ?""",
                (now, limit),
            )
            return [dict(r) for r in await cur.fetchall()]

    async def bulk_import(self, contacts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Import multiple contacts at once. Returns count of imported."""
        imported = 0
        errors = 0
        for c in contacts:
            try:
                await self.add_contact(**c)
                imported += 1
            except Exception as e:
                logger.warning(f"CRM bulk import error: {e}")
                errors += 1
        return {"imported": imported, "errors": errors}
