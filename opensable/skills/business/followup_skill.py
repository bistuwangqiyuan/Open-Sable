"""
Follow-Up Scheduler,  Automated follow-up detection and execution.

Hooks into CRM and Pipeline to:
  - Detect contacts overdue for follow-up
  - Detect deals stalling in a stage
  - Generate follow-up email tasks via email templates
  - Plugs into the proactive reasoning engine as a data source

This is the "glue" between CRM, templates, email, and the autonomous tick loop.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


class FollowUpSkill:
    """
    Scans CRM and pipeline for actionable follow-up opportunities.

    Not a skill with its own DB,  it queries crm_skill and pipeline_skill
    and returns structured recommendations the agent can act on.
    """

    def __init__(self, crm_skill=None, pipeline_skill=None, templates_skill=None):
        self.crm = crm_skill
        self.pipeline = pipeline_skill
        self.templates = templates_skill
        self._initialized = False

    async def initialize(self):
        if self.crm and self.crm.is_ready():
            self._initialized = True
            logger.info("FollowUp skill ready")
        else:
            logger.warning("FollowUp skill: CRM not available")

    def is_ready(self) -> bool:
        return self._initialized

    # ── Detection ─────────────────────────────────────────────────────────

    async def get_overdue_contacts(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get contacts whose follow-up date has passed."""
        if not self.crm or not self.crm.is_ready():
            return []
        return await self.crm.get_overdue_followups(limit=limit)

    async def get_stale_contacts(
        self, days_since_contact: int = 5, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get contacts who were contacted but haven't replied
        and haven't been touched in N days.
        """
        if not self.crm or not self.crm.is_ready():
            return []

        try:
            import aiosqlite
            cutoff = _days_ago(days_since_contact)
            async with aiosqlite.connect(str(self.crm.db_path)) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    """SELECT * FROM contacts
                       WHERE status = 'contacted'
                         AND last_contact IS NOT NULL
                         AND last_contact < ?
                         AND (next_followup IS NULL OR next_followup <= ?)
                       ORDER BY last_contact ASC LIMIT ?""",
                    (cutoff, _now(), limit),
                )
                return [dict(r) for r in await cur.fetchall()]
        except Exception as e:
            logger.error(f"FollowUp stale contacts error: {e}")
            return []

    async def get_stalling_deals(
        self, days_in_stage: int = 7, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get deals that have been in the same stage for too long."""
        if not self.pipeline or not self.pipeline.is_ready():
            return []

        try:
            import aiosqlite
            cutoff = _days_ago(days_in_stage)
            async with aiosqlite.connect(str(self.pipeline.db_path)) as db:
                db.row_factory = aiosqlite.Row
                cur = await db.execute(
                    """SELECT * FROM deals
                       WHERE stage NOT IN ('won', 'lost')
                         AND updated_at < ?
                       ORDER BY updated_at ASC LIMIT ?""",
                    (cutoff, limit),
                )
                return [dict(r) for r in await cur.fetchall()]
        except Exception as e:
            logger.error(f"FollowUp stalling deals error: {e}")
            return []

    # ── Recommendation Engine ─────────────────────────────────────────────

    async def get_followup_recommendations(
        self,
        max_recommendations: int = 10,
        stale_days: int = 5,
        stalling_days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Generate a prioritized list of follow-up recommendations.
        Each recommendation includes: contact/deal info, suggested action,
        template name, and merge fields.

        This is the main entry point for the proactive reasoning engine.
        """
        recommendations: List[Dict[str, Any]] = []

        # 1. Overdue follow-ups (highest priority)
        overdue = await self.get_overdue_contacts(limit=max_recommendations)
        for contact in overdue:
            rec = {
                "type": "overdue_followup",
                "priority": "high",
                "contact_id": contact["id"],
                "contact_name": contact["name"],
                "contact_email": contact["email"],
                "company": contact.get("company", ""),
                "role": contact.get("role", ""),
                "last_contact": contact.get("last_contact", ""),
                "suggested_action": f"Send follow-up email to {contact['name']} at {contact.get('company', 'N/A')}",
                "template": "followup_no_reply",
                "merge_fields": {
                    "name": contact["name"],
                    "company": contact.get("company", ""),
                    "original_subject": f"Partnership Opportunity",
                    "role_context": "buyers" if contact.get("role") == "manufacturer" else "manufacturers",
                },
            }
            recommendations.append(rec)

        # 2. Stale contacts (medium priority)
        if len(recommendations) < max_recommendations:
            stale = await self.get_stale_contacts(
                days_since_contact=stale_days,
                limit=max_recommendations - len(recommendations),
            )
            for contact in stale:
                rec = {
                    "type": "stale_contact",
                    "priority": "medium",
                    "contact_id": contact["id"],
                    "contact_name": contact["name"],
                    "contact_email": contact["email"],
                    "company": contact.get("company", ""),
                    "role": contact.get("role", ""),
                    "last_contact": contact.get("last_contact", ""),
                    "suggested_action": f"Follow up with {contact['name']},  no reply in {stale_days}+ days",
                    "template": "followup_no_reply",
                    "merge_fields": {
                        "name": contact["name"],
                        "company": contact.get("company", ""),
                        "original_subject": "Partnership Opportunity",
                        "role_context": "buyers" if contact.get("role") == "manufacturer" else "manufacturers",
                    },
                }
                recommendations.append(rec)

        # 3. Stalling deals (medium priority)
        if len(recommendations) < max_recommendations:
            stalling = await self.get_stalling_deals(
                days_in_stage=stalling_days,
                limit=max_recommendations - len(recommendations),
            )
            for deal in stalling:
                rec = {
                    "type": "stalling_deal",
                    "priority": "medium",
                    "deal_id": deal["id"],
                    "deal_title": deal["title"],
                    "stage": deal["stage"],
                    "product": deal.get("product", ""),
                    "last_updated": deal.get("updated_at", ""),
                    "suggested_action": f"Deal '{deal['title']}' stuck in '{deal['stage']}' for {stalling_days}+ days,  needs attention",
                    "template": None,
                    "merge_fields": {},
                }
                recommendations.append(rec)

        return recommendations[:max_recommendations]

    # ── Summary for proactive engine ──────────────────────────────────────

    async def get_business_summary(self) -> str:
        """
        Build a human-readable summary of CRM + pipeline state
        for injection into the proactive reasoning context.
        """
        parts = []

        if self.crm and self.crm.is_ready():
            stats = await self.crm.get_stats()
            parts.append(
                f"CRM: {stats['total_contacts']} contacts "
                f"(roles: {stats.get('by_role', {})}; "
                f"statuses: {stats.get('by_status', {})})"
            )

            overdue = await self.get_overdue_contacts(limit=5)
            if overdue:
                names = [f"{c['name']} ({c.get('company', '?')})" for c in overdue]
                parts.append(f"⚠️ Overdue follow-ups: {', '.join(names)}")

        if self.pipeline and self.pipeline.is_ready():
            pstats = await self.pipeline.get_pipeline_stats()
            parts.append(
                f"Pipeline: {pstats['total_deals']} deals "
                f"(stages: {pstats.get('by_stage', {})})"
            )

        recs = await self.get_followup_recommendations(max_recommendations=5)
        if recs:
            actions = [r["suggested_action"] for r in recs[:3]]
            parts.append("Suggested actions:\n" + "\n".join(f"  → {a}" for a in actions))

        return "\n".join(parts) if parts else "No business data yet."
