"""
Momentum Strategy,  Trend-following using RSI, MACD, and volume.

Buys when momentum is strong and rising, sells when it weakens.
Best for: crypto, memecoins, trending assets.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import OHLCV, PriceTick
from ..strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


def _compute_rsi(closes: List[float], period: int = 14) -> float:
    """Compute RSI (Relative Strength Index)."""
    if len(closes) < period + 1:
        return 50.0  # Neutral if not enough data

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _compute_ema(values: List[float], period: int) -> List[float]:
    """Compute Exponential Moving Average."""
    if not values:
        return []
    ema = [values[0]]
    multiplier = 2 / (period + 1)
    for v in values[1:]:
        ema.append(v * multiplier + ema[-1] * (1 - multiplier))
    return ema


def _compute_macd(closes: List[float], fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute MACD line, signal line, and histogram."""
    if len(closes) < slow:
        return 0, 0, 0

    fast_ema = _compute_ema(closes, fast)
    slow_ema = _compute_ema(closes, slow)
    macd_line = [f - s for f, s in zip(fast_ema, slow_ema)]
    signal_line = _compute_ema(macd_line, signal)

    if not macd_line or not signal_line:
        return 0, 0, 0

    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    histogram = macd_val - signal_val
    return macd_val, signal_val, histogram


def _compute_volume_ratio(volumes: List[float], period: int = 20) -> float:
    """Current volume vs average volume ratio."""
    if len(volumes) < period:
        return 1.0
    avg = sum(volumes[-period:]) / period
    return volumes[-1] / avg if avg > 0 else 1.0


class MomentumStrategy(Strategy):
    """
    Trend-following momentum strategy.

    Entry conditions (LONG):
    - RSI > 50 and rising (momentum is positive)
    - MACD histogram positive and growing
    - Volume above average (confirms trend)
    - Price above 20-period EMA

    Exit conditions:
    - RSI < 40 (momentum weakening)
    - MACD histogram turns negative
    - 5% take profit or 2% stop loss
    """

    name = "momentum"
    description = "Trend-following using RSI, MACD, and volume breakouts"
    version = "1.0.0"
    supported_markets = ["crypto", "stocks", "commodities"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.rsi_period = self.config.get("rsi_period", 14)
        self.rsi_buy_threshold = self.config.get("rsi_buy_threshold", 55)
        self.rsi_sell_threshold = self.config.get("rsi_sell_threshold", 40)
        self.rsi_overbought = self.config.get("rsi_overbought", 80)
        self.volume_threshold = self.config.get("volume_threshold", 1.5)
        self.take_profit_pct = Decimal(str(self.config.get("take_profit_pct", 5)))
        self.stop_loss_pct = Decimal(str(self.config.get("stop_loss_pct", 2)))
        self.run_interval_seconds = self.config.get("interval", 60)

    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        if len(candles) < 30:
            return []

        closes = [float(c.close) for c in candles]
        volumes = [float(c.volume) for c in candles]
        price = float(current_price.price)

        # Compute indicators
        rsi = _compute_rsi(closes, self.rsi_period)
        macd_val, signal_val, histogram = _compute_macd(closes)
        volume_ratio = _compute_volume_ratio(volumes)
        ema20 = _compute_ema(closes, 20)[-1] if len(closes) >= 20 else price

        # Score components (0-1)
        rsi_score = 0.0
        if rsi > self.rsi_buy_threshold and rsi < self.rsi_overbought:
            rsi_score = min((rsi - 50) / 30, 1.0)  # Higher RSI = stronger momentum
        elif rsi >= self.rsi_overbought:
            rsi_score = -0.5  # Overbought,  potential reversal

        macd_score = 0.0
        if histogram > 0:
            macd_score = min(histogram / (abs(macd_val) + 0.001), 1.0)

        volume_score = min((volume_ratio - 1.0) / 2.0, 1.0) if volume_ratio > 1.0 else 0.0

        trend_score = 1.0 if price > ema20 else -0.5

        # Combined confidence
        confidence = (rsi_score * 0.3 + macd_score * 0.3 + volume_score * 0.2 + trend_score * 0.2)
        confidence = max(0.0, min(1.0, confidence))

        signals: List[Signal] = []

        # LONG signal
        if (
            rsi > self.rsi_buy_threshold
            and rsi < self.rsi_overbought
            and histogram > 0
            and price > ema20
            and confidence >= 0.4
        ):
            tp = Decimal(str(price)) * (1 + self.take_profit_pct / 100)
            sl = Decimal(str(price)) * (1 - self.stop_loss_pct / 100)

            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=round(confidence, 3),
                entry_price=current_price.price,
                stop_loss=sl,
                take_profit=tp,
                reason=(
                    f"Momentum LONG: RSI={rsi:.1f}, MACD hist={histogram:.4f}, "
                    f"Vol ratio={volume_ratio:.1f}x, Price>EMA20"
                ),
            ))

        # SHORT signal (for assets that support shorting)
        elif (
            rsi < self.rsi_sell_threshold
            and histogram < 0
            and price < ema20
            and abs(confidence) >= 0.4
        ):
            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.SHORT,
                confidence=round(abs(confidence), 3),
                entry_price=current_price.price,
                reason=f"Momentum SHORT: RSI={rsi:.1f}, MACD hist={histogram:.4f}, Price<EMA20",
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
        # Take profit
        if pnl_pct >= self.take_profit_pct:
            return True
        # Stop loss
        if pnl_pct <= -self.stop_loss_pct:
            return True
        # Time-based exit: if holding >24h with minimal profit
        if holding_seconds > 86400 and pnl_pct < Decimal("0.5"):
            return True
        return False
