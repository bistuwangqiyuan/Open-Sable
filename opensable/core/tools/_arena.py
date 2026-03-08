"""
Arena (fighting game) tool implementations — mixin for ToolRegistry.
"""

import logging
from typing import Dict

logger = logging.getLogger(__name__)


class ArenaToolsMixin:
    """Tool handlers for the Arena Fighter skill."""

    # ── arena_fight ───────────────────────────────────────────────────────────

    async def _arena_fight_tool(self, params: Dict) -> str:
        """Connect to the arena, authenticate via SAGP, and queue for a fight."""
        if not getattr(self, "arena_skill", None):
            return "Arena skill not available — set ARENA_URL in profile.env"
        use_llm = params.get("use_llm", True)
        result = await self.arena_skill.connect_and_fight(use_llm=use_llm)
        if "error" in result:
            return f"Arena error: {result['error']}"
        return (
            f"Connected to arena as {result.get('agent', '?')} "
            f"at {result.get('arena', '?')} — status: {result.get('status', '?')}"
        )

    # ── arena_status ──────────────────────────────────────────────────────────

    async def _arena_status_tool(self, params: Dict) -> str:
        """Return current arena status (idle / queued / fighting / result)."""
        if not getattr(self, "arena_skill", None):
            return "Arena skill not available"
        import json
        status = await self.arena_skill.get_status()
        return json.dumps(status, indent=2)

    # ── arena_history ─────────────────────────────────────────────────────────

    async def _arena_history_tool(self, params: Dict) -> str:
        """Return recent fight history."""
        if not getattr(self, "arena_skill", None):
            return "Arena skill not available"
        import json
        limit = params.get("limit", 10)
        history = await self.arena_skill.get_history(limit=limit)
        if not history:
            return "No arena fights recorded yet."
        return json.dumps(history, indent=2)

    # ── arena_disconnect ──────────────────────────────────────────────────────

    async def _arena_disconnect_tool(self, params: Dict) -> str:
        """Disconnect from the arena if currently connected."""
        if not getattr(self, "arena_skill", None):
            return "Arena skill not available"
        result = await self.arena_skill.disconnect()
        return f"Arena: {result.get('status', 'disconnected')}"
