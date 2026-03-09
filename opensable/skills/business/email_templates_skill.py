"""
Email Templates Skill — Named templates with merge fields.

Templates are stored in SQLite (same crm.db) and support merge fields:
  {{name}}, {{company}}, {{product}}, {{country}}, {{quantity}}, etc.

Includes built-in starter templates for B2B outreach workflows.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import re

logger = logging.getLogger(__name__)

try:
    import aiosqlite
    AIOSQLITE = True
except ImportError:
    AIOSQLITE = False

DB_NAME = "crm.db"

_CREATE_TEMPLATES = """
CREATE TABLE IF NOT EXISTS email_templates (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    subject     TEXT NOT NULL,
    body        TEXT NOT NULL,
    category    TEXT DEFAULT 'outreach',   -- outreach | followup | inquiry | proposal | notification
    language    TEXT DEFAULT 'en',
    tags        TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""

# ── Built-in starter templates ────────────────────────────────────────────────

STARTER_TEMPLATES = [
    {
        "name": "manufacturer_introduction",
        "subject": "Partnership Opportunity — {{my_company}}",
        "body": """Dear {{name}},

I am writing on behalf of {{my_company}}, a textile brokerage firm that connects quality manufacturers in Turkey with established buyers across Europe.

We came across {{company}} and were impressed by your {{products}} production capabilities. We are actively seeking reliable manufacturing partners for our European client base.

Our clients typically require:
• Consistent quality standards (EU compliance)
• Competitive pricing for bulk orders
• Reliable delivery timelines (4-8 weeks)

Would you be open to a brief call or email exchange to explore a potential partnership?

I'd be happy to provide more details about our current buyer requirements and how we work with our manufacturing partners.

Best regards,
{{my_name}}
{{my_company}}
{{my_email}}""",
        "category": "outreach",
    },
    {
        "name": "buyer_introduction",
        "subject": "Quality Turkish Textile Supply — {{my_company}}",
        "body": """Dear {{name}},

I'm reaching out from {{my_company}}. We specialize in sourcing high-quality textile products directly from vetted manufacturers in Turkey.

We noticed {{company}} is active in the {{industry}} sector and thought our sourcing capabilities could be valuable to your supply chain.

What we offer:
• Direct access to 50+ verified Turkish textile manufacturers
• Products: denim, cotton, linen, synthetic blends, home textiles
• Quality assurance and factory audits
• Competitive pricing with transparent margins
• Flexible MOQs and delivery scheduling

Could you share your current textile sourcing needs? We'd love to prepare a tailored proposal.

Best regards,
{{my_name}}
{{my_company}}
{{my_email}}""",
        "category": "outreach",
    },
    {
        "name": "followup_no_reply",
        "subject": "Re: {{original_subject}} — Quick follow-up",
        "body": """Dear {{name}},

I wanted to follow up on my previous email regarding a potential partnership between {{company}} and {{my_company}}.

I understand how busy things can get, so I'll keep this brief — we have several active {{role_context}} looking for partners, and I believe there could be a strong fit.

Would you have 10 minutes this week for a quick call? Or if you prefer, just reply with your current needs and I'll put together relevant options.

Best regards,
{{my_name}}
{{my_company}}""",
        "category": "followup",
    },
    {
        "name": "followup_second",
        "subject": "Re: {{original_subject}} — Last check-in",
        "body": """Dear {{name}},

This is my final follow-up regarding our potential collaboration. I completely understand if the timing isn't right.

If your needs change in the future, please don't hesitate to reach out. We're always happy to help {{company}} with textile sourcing from Turkey.

Wishing you continued success.

Best regards,
{{my_name}}
{{my_company}}
{{my_email}}""",
        "category": "followup",
    },
    {
        "name": "buyer_inquiry_to_manufacturer",
        "subject": "Buyer Inquiry — {{product}} ({{quantity}} {{unit}})",
        "body": """Dear {{name}},

We have a buyer inquiry that matches your production capabilities:

Product: {{product}}
Quantity: {{quantity}} {{unit}}
Quality: {{quality_requirements}}
Delivery: {{delivery_date}}
Destination: {{buyer_country}}

Could you please provide:
1. Unit price for this quantity
2. Available delivery timeline
3. Sample availability
4. Minimum order quantity for this product

Our buyer is ready to proceed quickly once terms are agreed.

Best regards,
{{my_name}}
{{my_company}}""",
        "category": "inquiry",
    },
    {
        "name": "proposal_to_buyer",
        "subject": "Sourcing Proposal — {{product}} from Turkey",
        "body": """Dear {{name}},

Following your requirements, we've identified {{match_count}} suitable manufacturers for your needs:

Product: {{product}}
Quantity: {{quantity}} {{unit}}
Quality: {{quality_requirements}}

Manufacturer options:
{{manufacturer_details}}

Next steps:
1. Let us know which option(s) interest you
2. We can arrange samples within 5-7 business days
3. Once approved, production lead time is typically {{lead_time}}

We handle all logistics, quality checks, and documentation.

Looking forward to your feedback.

Best regards,
{{my_name}}
{{my_company}}""",
        "category": "proposal",
    },
]

_MERGE_RE = re.compile(r"\{\{(\w+)\}\}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uuid() -> str:
    return uuid.uuid4().hex[:12]


class EmailTemplatesSkill:
    """Manage and render email templates with merge fields."""

    def __init__(self, data_dir: str = "./data"):
        self.db_path = Path(data_dir) / DB_NAME
        self._initialized = False

    async def initialize(self):
        if not AIOSQLITE:
            logger.warning("aiosqlite not installed — EmailTemplates skill disabled.")
            return
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(str(self.db_path)) as db:
            await db.execute(_CREATE_TEMPLATES)
            await db.commit()

            # Seed starter templates if table is empty
            cur = await db.execute("SELECT COUNT(*) as c FROM email_templates")
            row = await cur.fetchone()
            if row[0] == 0:
                now = _now()
                for t in STARTER_TEMPLATES:
                    await db.execute(
                        """INSERT OR IGNORE INTO email_templates
                           (id, name, subject, body, category, created_at, updated_at)
                           VALUES (?,?,?,?,?,?,?)""",
                        (_uuid(), t["name"], t["subject"], t["body"],
                         t.get("category", "outreach"), now, now),
                    )
                await db.commit()
                logger.info(f"Seeded {len(STARTER_TEMPLATES)} starter email templates")

        self._initialized = True
        logger.info("EmailTemplates skill ready")

    def is_ready(self) -> bool:
        return self._initialized and AIOSQLITE

    # ── Template CRUD ─────────────────────────────────────────────────────

    async def list_templates(self, category: str = "") -> List[Dict[str, Any]]:
        """List all templates, optionally filtered by category."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            if category:
                cur = await db.execute(
                    "SELECT id, name, subject, category, language FROM email_templates WHERE category = ? ORDER BY name",
                    (category,),
                )
            else:
                cur = await db.execute(
                    "SELECT id, name, subject, category, language FROM email_templates ORDER BY name"
                )
            return [dict(r) for r in await cur.fetchall()]

    async def get_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a template by name."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM email_templates WHERE name = ?", (name,)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

    async def save_template(
        self,
        name: str,
        subject: str,
        body: str,
        category: str = "outreach",
        language: str = "en",
        tags: str = "",
    ) -> Dict[str, Any]:
        """Create or update a template."""
        now = _now()
        async with aiosqlite.connect(str(self.db_path)) as db:
            # Upsert
            cur = await db.execute(
                "SELECT id FROM email_templates WHERE name = ?", (name,)
            )
            existing = await cur.fetchone()
            if existing:
                await db.execute(
                    """UPDATE email_templates
                       SET subject = ?, body = ?, category = ?, language = ?, tags = ?, updated_at = ?
                       WHERE name = ?""",
                    (subject, body, category, language, tags, now, name),
                )
            else:
                await db.execute(
                    """INSERT INTO email_templates
                       (id, name, subject, body, category, language, tags, created_at, updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (_uuid(), name, subject, body, category, language, tags, now, now),
                )
            await db.commit()
        return {"name": name, "action": "updated" if existing else "created"}

    async def delete_template(self, name: str) -> Dict[str, Any]:
        """Delete a template by name."""
        async with aiosqlite.connect(str(self.db_path)) as db:
            cur = await db.execute(
                "DELETE FROM email_templates WHERE name = ?", (name,)
            )
            await db.commit()
            return {"deleted": name, "rows": cur.rowcount}

    # ── Rendering ─────────────────────────────────────────────────────────

    async def render_template(
        self, name: str, fields: Dict[str, str]
    ) -> Optional[Dict[str, str]]:
        """
        Render a template with merge fields.
        Returns {"subject": "...", "body": "..."} or None if template not found.
        """
        tpl = await self.get_template(name)
        if not tpl:
            return None

        def _replace(text: str) -> str:
            def _sub(m):
                key = m.group(1)
                return fields.get(key, m.group(0))  # keep {{key}} if not provided
            return _MERGE_RE.sub(_sub, text)

        return {
            "subject": _replace(tpl["subject"]),
            "body": _replace(tpl["body"]),
        }

    async def preview_merge_fields(self, name: str) -> List[str]:
        """List all merge fields in a template (e.g. ['name', 'company', ...])."""
        tpl = await self.get_template(name)
        if not tpl:
            return []
        all_text = tpl["subject"] + " " + tpl["body"]
        return sorted(set(_MERGE_RE.findall(all_text)))
