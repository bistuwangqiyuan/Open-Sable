"""
Mean Reversion Strategy — Buy oversold, sell overbought.

Uses Bollinger Bands and z-score to identify assets that have
deviated significantly from their mean and are likely to revert.

Best for: stable pairs, commodities, range-bound markets.
"""

from __future__ import annotations

import logging
import statistics
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import OHLCV, PriceTick
from ..strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


def _bollinger_bands(closes: List[float], period: int = 20, num_std: float = 2.0):
    """Compute Bollinger Bands."""
    if len(closes) < period:
        return None, None, None
    window = closes[-period:]
    sma = statistics.mean(window)
    std = statistics.stdev(window) if len(window) > 1 else 0
    upper = sma + num_std * std
    lower = sma - num_std * std
    return sma, upper, lower


def _z_score(closes: List[float], period: int = 20) -> float:
    """Compute z-score of latest price vs rolling mean."""
    if len(closes) < period:
        return 0.0
    window = closes[-period:]
    mean = statistics.mean(window)
    std = statistics.stdev(window) if len(window) > 1 else 1
    return (closes[-1] - mean) / std if std > 0 else 0.0


class MeanReversionStrategy(Strategy):
    """
    Mean reversion: buy when price is significantly below average,
    sell when significantly above.

    Entry (LONG):
    - Price below lower Bollinger Band
    - Z-score < -2.0 (oversold)

    Entry (SHORT / CLOSE):
    - Price above upper Bollinger Band
    - Z-score > 2.0 (overbought)
    """

    name = "mean_reversion"
    description = "Buy oversold / sell overbought using Bollinger Bands and z-score"
    version = "1.0.0"
    supported_markets = ["crypto", "stocks", "commodities"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.bb_period = self.config.get("bb_period", 20)
        self.bb_std = self.config.get("bb_std", 2.0)
        self.z_threshold = self.config.get("z_threshold", 2.0)
        self.take_profit_pct = Decimal(str(self.config.get("take_profit_pct", 3)))
        self.stop_loss_pct = Decimal(str(self.config.get("stop_loss_pct", 2)))
        self.run_interval_seconds = self.config.get("interval", 300)  # 5 min

    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        if len(candles) < self.bb_period + 5:
            return []

        closes = [float(c.close) for c in candles]
        price = float(current_price.price)

        sma, upper_bb, lower_bb = _bollinger_bands(closes, self.bb_period, self.bb_std)
        z = _z_score(closes, self.bb_period)

        if sma is None:
            return []

        signals: List[Signal] = []

        # LONG: oversold (price below lower BB, negative z-score)
        if price < lower_bb and z < -self.z_threshold:
            # Confidence proportional to how far below the band
            deviation = abs(z) / (self.z_threshold * 2)
            confidence = min(0.3 + deviation * 0.5, 0.95)

            tp = Decimal(str(sma))  # Target: revert to mean
            sl = Decimal(str(price)) * (1 - self.stop_loss_pct / 100)

            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=round(confidence, 3),
                entry_price=current_price.price,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"Mean Reversion LONG: price={price:.4f} < lower_BB={lower_bb:.4f}, "
                    f"z-score={z:.2f}, target=SMA({sma:.4f})"
                ),
            ))

        # SHORT: overbought (price above upper BB, positive z-score)
        elif price > upper_bb and z > self.z_threshold:
            deviation = abs(z) / (self.z_threshold * 2)
            confidence = min(0.3 + deviation * 0.5, 0.95)

            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.SHORT,
                confidence=round(confidence, 3),
                entry_price=current_price.price,
                take_profit=Decimal(str(sma)),
                reason=(
                    f"Mean Reversion SHORT: price={price:.4f} > upper_BB={upper_bb:.4f}, "
                    f"z-score={z:.2f}, target=SMA({sma:.4f})"
                ),
            ))

        return signals

    async def should_exit(
        self,
        symbol: str,
        entry_price: Decimal,
        current_price: Decimal,
        pnl_pct: Decimal,
        holding_seconds: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if pnl_pct >= self.take_profit_pct:
            return True
        if pnl_pct <= -self.stop_loss_pct:
            return True
        # Mean reversion trades should resolve quickly (< 4 hours)
        if holding_seconds > 14400 and pnl_pct < Decimal("0.5"):
            return True
        return False
