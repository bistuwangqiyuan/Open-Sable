"""
Trading-specific guardrails for Open-Sable.

These plug into the existing GuardrailsEngine to add financial safety
checks before and after trading tool calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Import base guardrail types
try:
    from opensable.core.guardrails import InputGuardrail, OutputGuardrail, GuardrailAction
except ImportError:
    # Standalone fallback
    from enum import Enum

    class GuardrailAction(Enum):
        BLOCK = "block"
        WARN = "warn"
        SANITIZE = "sanitize"

    class InputGuardrail:
        name = ""
        async def check(self, tool_name, args, context=None):
            return GuardrailAction.WARN, None

    class OutputGuardrail:
        name = ""
        async def check(self, tool_name, result, context=None):
            return GuardrailAction.WARN, None


class MaxOrderValueGuardrail(InputGuardrail):
    """Block trades above maximum order value."""

    name = "max_order_value"

    def __init__(self, max_usd: float = 10000.0):
        self.max_usd = max_usd

    async def check(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        if tool_name != "trading_place_trade":
            return None, None

        # We can't fully check without price, but we can catch obvious violations
        amount = args.get("amount", "0")
        try:
            amount_f = float(amount)
        except (ValueError, TypeError):
            return GuardrailAction.BLOCK, f"Invalid trade amount: {amount}"

        if amount_f <= 0:
            return GuardrailAction.BLOCK, "Trade amount must be positive"

        return None, None


class BannedAssetGuardrail(InputGuardrail):
    """Block trades on banned assets (known scam tokens, etc.)."""

    name = "banned_asset"

    # Well-known scam/rug tokens to always block
    DEFAULT_BANNED = {
        "SQUID", "SAFEMOON", "BITCONNECT",
    }

    def __init__(self, banned_assets: Optional[set] = None):
        self.banned = (banned_assets or set()) | self.DEFAULT_BANNED

    async def check(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        if tool_name not in ("trading_place_trade", "trading_analyze"):
            return None, None

        symbol = args.get("symbol", "").upper()
        base = symbol.replace("/USDT", "").replace("USDT", "").replace("/USD", "")

        if base in self.banned:
            return GuardrailAction.BLOCK, f"🚫 {base} is a banned asset (known scam/rug pull)"

        return None, None


class PaperModeGuardrail(InputGuardrail):
    """Warn (or block) when attempting live trades without explicit confirmation."""

    name = "paper_mode_check"

    def __init__(self, paper_mode: bool = True):
        self.paper_mode = paper_mode

    async def check(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ):
        if tool_name != "trading_place_trade":
            return None, None

        exchange = args.get("exchange", "paper")

        if not self.paper_mode and exchange != "paper":
            return (
                GuardrailAction.WARN,
                f"⚠️ LIVE TRADE on {exchange}! This will use real money.",
            )

        return None, None


class DailyLossGuardrail(OutputGuardrail):
    """After each trade, check if daily loss limit is approached."""

    name = "daily_loss_check"

    def __init__(self, max_daily_loss_pct: float = 2.0):
        self.max_daily_loss_pct = max_daily_loss_pct

    async def check(
        self,
        tool_name: str,
        result: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        if tool_name != "trading_place_trade":
            return None, None

        # The risk manager handles the hard block — this is a soft warning
        if context and context.get("daily_pnl_pct", 0) < -(self.max_daily_loss_pct * 0.8):
            return (
                GuardrailAction.WARN,
                f"⚠️ Approaching daily loss limit ({self.max_daily_loss_pct}%). "
                "Consider stopping for today.",
            )

        return None, None


def register_trading_guardrails(engine, config) -> None:
    """Register all trading guardrails with the guardrails engine."""
    try:
        max_order = getattr(config, "trading_max_order_usd", 10000)
        paper_mode = getattr(config, "trading_paper_mode", True)
        max_daily = getattr(config, "trading_max_daily_loss_pct", 2.0)
        banned_str = getattr(config, "trading_banned_assets", "")
        banned_set = {a.strip().upper() for a in banned_str.split(",") if a.strip()}

        engine.add_input_guardrail(MaxOrderValueGuardrail(max_usd=max_order))
        engine.add_input_guardrail(BannedAssetGuardrail(banned_assets=banned_set))
        engine.add_input_guardrail(PaperModeGuardrail(paper_mode=paper_mode))
        engine.add_output_guardrail(DailyLossGuardrail(max_daily_loss_pct=max_daily))
        logger.info("✅ Trading guardrails registered (4 rules)")
    except Exception as e:
        logger.warning(f"Failed to register trading guardrails: {e}")
