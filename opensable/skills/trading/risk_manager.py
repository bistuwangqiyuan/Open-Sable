"""
Risk Manager — Enforces hard safety limits before any trade executes.

Every order passes through RiskManager.check_trade() BEFORE hitting
the exchange.  If the risk check fails, the trade is blocked.  This
is the final safety net — no override is possible without changing
code (by design).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import Order, OrderSide, Position

logger = logging.getLogger(__name__)


class RiskAction(str, Enum):
    ALLOW = "allow"
    REDUCE = "reduce"     # Allowed if quantity is reduced
    REJECT = "reject"     # Hard block


@dataclass
class RiskDecision:
    """Result of a risk check."""
    action: RiskAction
    reason: str = ""
    max_allowed_quantity: Optional[Decimal] = None  # Set if action == REDUCE
    warnings: List[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.action in (RiskAction.ALLOW, RiskAction.REDUCE)


@dataclass
class DailyStats:
    """Intraday P&L tracking."""
    date: str = ""  # YYYY-MM-DD
    realized_pnl: Decimal = Decimal("0")
    trades_count: int = 0
    volume_usd: Decimal = Decimal("0")
    peak_equity: Decimal = Decimal("0")
    current_equity: Decimal = Decimal("0")


class RiskManager:
    """
    Pre-trade risk engine.  Every order MUST pass through check_trade()
    before being sent to an exchange.

    Hard limits (configurable):
    - max_position_size_pct: max % of portfolio in one position
    - max_daily_loss_pct: max daily loss before halt
    - max_drawdown_pct: max drawdown before emergency halt
    - max_open_positions: max number of simultaneous positions
    - max_order_value_usd: max single order $ value
    - min_liquidity_usd: reject illiquid markets
    - banned_assets: blacklisted tokens / scam coins
    - require_approval_above_usd: HITL threshold
    """

    def __init__(
        self,
        *,
        max_position_size_pct: float = 5.0,
        max_daily_loss_pct: float = 2.0,
        max_drawdown_pct: float = 10.0,
        max_open_positions: int = 10,
        max_order_value_usd: float = 10_000.0,
        min_liquidity_usd: float = 10_000.0,
        require_approval_above_usd: float = 100.0,
        banned_assets: Optional[List[str]] = None,
        allowed_exchanges: Optional[List[str]] = None,
    ):
        self.max_position_size_pct = max_position_size_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_open_positions = max_open_positions
        self.max_order_value_usd = Decimal(str(max_order_value_usd))
        self.min_liquidity_usd = Decimal(str(min_liquidity_usd))
        self.require_approval_above_usd = Decimal(str(require_approval_above_usd))
        self.banned_assets = set(a.upper() for a in (banned_assets or []))
        self.allowed_exchanges = set(allowed_exchanges) if allowed_exchanges else None

        self._daily_stats = DailyStats(date=datetime.utcnow().strftime("%Y-%m-%d"))
        self._halt = False
        self._halt_reason = ""

    # ── Main check ──

    async def check_trade(
        self,
        order: Order,
        portfolio_value_usd: Decimal,
        current_positions: List[Position],
        current_price: Decimal,
        volume_24h_usd: Optional[Decimal] = None,
    ) -> RiskDecision:
        """
        Evaluate a proposed order against all risk rules.

        Returns RiskDecision with action = ALLOW, REDUCE, or REJECT.
        """
        warnings: List[str] = []

        # 0. Emergency halt
        if self._halt:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason=f"Trading HALTED: {self._halt_reason}",
            )

        # 1. Check banned assets
        symbol_upper = order.symbol.upper()
        for banned in self.banned_assets:
            if banned in symbol_upper:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=f"Asset {order.symbol} is banned: {banned}",
                )

        # 2. Check allowed exchanges
        if self.allowed_exchanges and order.exchange not in self.allowed_exchanges:
            return RiskDecision(
                action=RiskAction.REJECT,
                reason=f"Exchange '{order.exchange}' is not in allowed list",
            )

        # 3. Calculate order notional value
        order_price = order.price or current_price
        order_value = order.quantity * order_price

        # 4. Max single order value
        if order_value > self.max_order_value_usd:
            max_qty = self.max_order_value_usd / order_price if order_price > 0 else Decimal("0")
            return RiskDecision(
                action=RiskAction.REDUCE,
                reason=f"Order value ${order_value} exceeds max ${self.max_order_value_usd}",
                max_allowed_quantity=max_qty,
            )

        # 5. Max position size (% of portfolio)
        if portfolio_value_usd > 0:
            position_pct = float(order_value / portfolio_value_usd) * 100
            # Also include existing position in same symbol
            existing = [p for p in current_positions if p.symbol == order.symbol]
            existing_value = sum(p.notional_value for p in existing)
            total_exposure_pct = float((order_value + existing_value) / portfolio_value_usd) * 100

            if total_exposure_pct > self.max_position_size_pct:
                max_additional = (
                    portfolio_value_usd * Decimal(str(self.max_position_size_pct / 100))
                    - existing_value
                )
                max_qty = max(max_additional / order_price, Decimal("0")) if order_price > 0 else Decimal("0")
                return RiskDecision(
                    action=RiskAction.REDUCE,
                    reason=f"Position would be {total_exposure_pct:.1f}% of portfolio "
                           f"(max {self.max_position_size_pct}%)",
                    max_allowed_quantity=max_qty,
                )

        # 6. Max open positions
        if order.side == OrderSide.BUY:
            unique_symbols = set(p.symbol for p in current_positions)
            if order.symbol not in unique_symbols and len(unique_symbols) >= self.max_open_positions:
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=f"Max open positions ({self.max_open_positions}) reached",
                )

        # 7. Daily loss limit
        self._refresh_daily_stats()
        if portfolio_value_usd > 0:
            daily_loss_pct = float(
                abs(min(self._daily_stats.realized_pnl, Decimal("0"))) / portfolio_value_usd
            ) * 100
            if daily_loss_pct >= self.max_daily_loss_pct:
                self._halt = True
                self._halt_reason = f"Daily loss limit hit: {daily_loss_pct:.1f}%"
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=self._halt_reason,
                )
            if daily_loss_pct >= self.max_daily_loss_pct * 0.8:
                warnings.append(
                    f"⚠️ Approaching daily loss limit: {daily_loss_pct:.1f}% "
                    f"(max {self.max_daily_loss_pct}%)"
                )

        # 8. Max drawdown
        if self._daily_stats.peak_equity > 0:
            dd = float(
                (self._daily_stats.peak_equity - self._daily_stats.current_equity)
                / self._daily_stats.peak_equity
            ) * 100
            if dd >= self.max_drawdown_pct:
                self._halt = True
                self._halt_reason = f"Max drawdown hit: {dd:.1f}%"
                return RiskDecision(
                    action=RiskAction.REJECT,
                    reason=self._halt_reason,
                )
            if dd >= self.max_drawdown_pct * 0.7:
                warnings.append(f"⚠️ Drawdown at {dd:.1f}% (halt at {self.max_drawdown_pct}%)")

        # 9. Liquidity check
        if volume_24h_usd is not None and volume_24h_usd < self.min_liquidity_usd:
            warnings.append(
                f"⚠️ Low liquidity: 24h volume ${volume_24h_usd} "
                f"< min ${self.min_liquidity_usd}"
            )
            # Don't reject, just warn — some memecoins have low volume

        # 10. All checks passed
        return RiskDecision(
            action=RiskAction.ALLOW,
            reason="All risk checks passed",
            warnings=warnings,
        )

    # ── HITL threshold ──

    def needs_approval(self, order_value_usd: Decimal) -> bool:
        """Check if this order value triggers human-in-the-loop approval."""
        return order_value_usd >= self.require_approval_above_usd

    # ── Daily tracking ──

    def record_trade_pnl(self, pnl: Decimal, volume: Decimal = Decimal("0")) -> None:
        """Update daily P&L tracking after a trade closes."""
        self._refresh_daily_stats()
        self._daily_stats.realized_pnl += pnl
        self._daily_stats.trades_count += 1
        self._daily_stats.volume_usd += volume

    def update_equity(self, equity: Decimal) -> None:
        """Update current equity for drawdown tracking."""
        self._daily_stats.current_equity = equity
        if equity > self._daily_stats.peak_equity:
            self._daily_stats.peak_equity = equity

    def _refresh_daily_stats(self) -> None:
        """Reset daily stats if we rolled into a new day."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if self._daily_stats.date != today:
            self._daily_stats = DailyStats(date=today)

    # ── Emergency controls ──

    def halt_trading(self, reason: str = "Manual halt") -> None:
        """Emergency halt — no more trades until resumed."""
        self._halt = True
        self._halt_reason = reason
        logger.warning(f"🚨 TRADING HALTED: {reason}")

    def resume_trading(self) -> None:
        """Resume trading after a halt."""
        self._halt = False
        self._halt_reason = ""
        logger.info("✅ Trading resumed")

    @property
    def is_halted(self) -> bool:
        return self._halt

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        """Return current risk manager status."""
        self._refresh_daily_stats()
        return {
            "halted": self._halt,
            "halt_reason": self._halt_reason,
            "daily_pnl": str(self._daily_stats.realized_pnl),
            "daily_trades": self._daily_stats.trades_count,
            "daily_volume": str(self._daily_stats.volume_usd),
            "limits": {
                "max_position_size_pct": self.max_position_size_pct,
                "max_daily_loss_pct": self.max_daily_loss_pct,
                "max_drawdown_pct": self.max_drawdown_pct,
                "max_open_positions": self.max_open_positions,
                "max_order_value_usd": str(self.max_order_value_usd),
                "require_approval_above_usd": str(self.require_approval_above_usd),
            },
            "banned_assets": list(self.banned_assets),
        }
