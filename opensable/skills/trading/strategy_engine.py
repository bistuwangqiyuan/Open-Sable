"""
Strategy Engine — Framework for running trading strategies.

Strategies produce Signals, which are evaluated by the engine and
(if approved) turned into orders. The engine manages strategy lifecycle,
scheduling, and signal aggregation.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .base import OHLCV, OrderSide, OrderType, PriceTick

logger = logging.getLogger(__name__)


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"     # Close existing position
    NEUTRAL = "neutral"  # No action


@dataclass
class Signal:
    """A trading signal produced by a strategy."""
    symbol: str
    direction: SignalDirection
    confidence: float  # 0.0 to 1.0
    strategy: str = ""
    exchange: str = ""  # Preferred exchange, empty = any
    entry_price: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    quantity_pct: float = 1.0  # % of allowed allocation
    order_type: OrderType = OrderType.MARKET
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def side(self) -> OrderSide:
        return OrderSide.BUY if self.direction == SignalDirection.LONG else OrderSide.SELL


class Strategy(ABC):
    """
    Abstract base class for all trading strategies.

    Subclasses must implement:
    - analyze(): examine market data and return signals
    - should_exit(): decide whether to close a position

    Optionally override:
    - on_start(): called when strategy is activated
    - on_stop(): called when strategy is deactivated
    """

    name: str = "base_strategy"
    description: str = ""
    version: str = "1.0.0"
    supported_markets: List[str] = []  # e.g. ["crypto", "stocks", "prediction"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enabled = True
        self._last_run: Optional[datetime] = None
        self.run_interval_seconds: int = 60  # Default: run every 60s

    @abstractmethod
    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        """
        Analyze market data for a symbol and return trading signals.

        Args:
            symbol: The trading pair/asset
            candles: Historical OHLCV data
            current_price: Latest price tick
            context: Additional context (news, sentiment, etc.)

        Returns:
            List of Signal objects (usually 0 or 1)
        """
        ...

    async def should_exit(
        self,
        symbol: str,
        entry_price: Decimal,
        current_price: Decimal,
        pnl_pct: Decimal,
        holding_seconds: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if an existing position should be closed."""
        # Default: exit on 5% profit or 2% loss
        if pnl_pct >= Decimal("5"):
            return True
        if pnl_pct <= Decimal("-2"):
            return True
        return False

    async def on_start(self) -> None:
        """Called when the strategy is activated."""
        pass

    async def on_stop(self) -> None:
        """Called when the strategy is deactivated."""
        pass

    def should_run(self) -> bool:
        """Check if enough time has passed since last run."""
        if not self._last_run:
            return True
        elapsed = (datetime.utcnow() - self._last_run).total_seconds()
        return elapsed >= self.run_interval_seconds

    def mark_run(self) -> None:
        self._last_run = datetime.utcnow()


class StrategyEngine:
    """
    Manages multiple strategies and aggregates their signals.

    Responsibilities:
    - Register/unregister strategies
    - Run strategies on schedule
    - Aggregate and deduplicate signals
    - Provide strategy status and history
    """

    def __init__(self):
        self._strategies: Dict[str, Strategy] = {}
        self._signal_history: List[Signal] = []
        self._running = False

    def register(self, strategy: Strategy) -> None:
        """Register a strategy."""
        self._strategies[strategy.name] = strategy
        logger.info(f"Registered strategy: {strategy.name}")

    def unregister(self, name: str) -> None:
        """Unregister a strategy."""
        self._strategies.pop(name, None)

    def get_strategy(self, name: str) -> Optional[Strategy]:
        return self._strategies.get(name)

    @property
    def strategies(self) -> Dict[str, Strategy]:
        return dict(self._strategies)

    async def scan_symbol(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        """Run all enabled strategies on a single symbol."""
        all_signals: List[Signal] = []

        for name, strategy in self._strategies.items():
            if not strategy.enabled:
                continue
            if not strategy.should_run():
                continue

            try:
                signals = await strategy.analyze(symbol, candles, current_price, context)
                for s in signals:
                    s.strategy = name
                all_signals.extend(signals)
                strategy.mark_run()
            except Exception as e:
                logger.error(f"Strategy {name} failed on {symbol}: {e}")

        # Store signal history
        self._signal_history.extend(all_signals)
        if len(self._signal_history) > 1000:
            self._signal_history = self._signal_history[-500:]

        return all_signals

    async def scan_multiple(
        self,
        symbols_data: Dict[str, Dict[str, Any]],
    ) -> List[Signal]:
        """
        Run strategies across multiple symbols.

        Args:
            symbols_data: {symbol: {"candles": [...], "price": PriceTick, "context": {...}}}
        """
        all_signals: List[Signal] = []
        for symbol, data in symbols_data.items():
            signals = await self.scan_symbol(
                symbol,
                data.get("candles", []),
                data.get("price"),
                data.get("context"),
            )
            all_signals.extend(signals)
        return all_signals

    def get_recent_signals(self, limit: int = 20, min_confidence: float = 0.0) -> List[Signal]:
        """Get recent signals, optionally filtered by confidence."""
        signals = [s for s in self._signal_history if s.confidence >= min_confidence]
        return signals[-limit:]

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get stats for all registered strategies."""
        stats = {}
        for name, strategy in self._strategies.items():
            strat_signals = [s for s in self._signal_history if s.strategy == name]
            stats[name] = {
                "enabled": strategy.enabled,
                "description": strategy.description,
                "last_run": strategy._last_run.isoformat() if strategy._last_run else None,
                "total_signals": len(strat_signals),
                "avg_confidence": (
                    sum(s.confidence for s in strat_signals) / len(strat_signals)
                    if strat_signals else 0
                ),
            }
        return stats
