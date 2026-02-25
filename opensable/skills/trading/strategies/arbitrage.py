"""
Arbitrage Strategy — Cross-exchange price difference detection.

Scans the same asset across multiple exchanges and generates signals
when the spread exceeds a configurable threshold after accounting
for fees and slippage.

Best for: BTC, ETH, and high-volume pairs listed on many exchanges.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..base import OHLCV, PriceTick
from ..strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


class ArbitrageStrategy(Strategy):
    """
    Cross-exchange arbitrage detection.

    Compares prices of the same asset on different exchanges passed via
    context["exchange_prices"] and generates signals when the spread
    is profitable after fees.

    Context required:
        exchange_prices: Dict[str, Decimal]  # exchange_name -> price
        exchange_fees: Dict[str, Decimal]    # optional fee overrides
    """

    name = "arbitrage"
    description = "Cross-exchange arbitrage opportunity detection"
    version = "1.0.0"
    supported_markets = ["crypto"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.run_interval_seconds = self.config.get("interval", 10)  # fast scans
        self.min_spread_pct = Decimal(str(self.config.get("min_spread_pct", "0.3")))
        self.default_fee_pct = Decimal(str(self.config.get("default_fee_pct", "0.1")))
        self.max_slippage_pct = Decimal(str(self.config.get("max_slippage_pct", "0.05")))

    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        if not context or "exchange_prices" not in context:
            return []

        exchange_prices: Dict[str, Decimal] = {
            k: Decimal(str(v)) for k, v in context["exchange_prices"].items()
        }
        exchange_fees: Dict[str, Decimal] = {
            k: Decimal(str(v))
            for k, v in context.get("exchange_fees", {}).items()
        }

        if len(exchange_prices) < 2:
            return []

        # Find best bid (highest sell price) and best ask (lowest buy price)
        sorted_exchanges = sorted(exchange_prices.items(), key=lambda x: x[1])
        cheapest_exchange, cheapest_price = sorted_exchanges[0]
        most_expensive_exchange, highest_price = sorted_exchanges[-1]

        if cheapest_price <= 0:
            return []

        # Calculate gross spread
        gross_spread_pct = ((highest_price - cheapest_price) / cheapest_price) * 100

        # Deduct fees (buy + sell) and slippage
        buy_fee = exchange_fees.get(cheapest_exchange, self.default_fee_pct)
        sell_fee = exchange_fees.get(most_expensive_exchange, self.default_fee_pct)
        total_cost = buy_fee + sell_fee + self.max_slippage_pct
        net_spread_pct = gross_spread_pct - total_cost

        signals: List[Signal] = []

        if net_spread_pct >= self.min_spread_pct:
            confidence = min(float(net_spread_pct) / 2.0, 1.0)  # 2% spread = 100% confidence

            signals.append(Signal(
                symbol=symbol,
                direction=SignalDirection.LONG,
                confidence=round(confidence, 3),
                entry_price=cheapest_price,
                take_profit=highest_price,
                reason=(
                    f"Arb: buy on {cheapest_exchange} @{cheapest_price}, "
                    f"sell on {most_expensive_exchange} @{highest_price}, "
                    f"net spread {net_spread_pct:.2f}%"
                ),
                metadata={
                    "strategy_type": "arbitrage",
                    "buy_exchange": cheapest_exchange,
                    "sell_exchange": most_expensive_exchange,
                    "buy_price": float(cheapest_price),
                    "sell_price": float(highest_price),
                    "gross_spread_pct": float(gross_spread_pct),
                    "net_spread_pct": float(net_spread_pct),
                    "total_fees_pct": float(total_cost),
                    "all_prices": {k: float(v) for k, v in exchange_prices.items()},
                },
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
        # Arb trades should be near-instant, exit quickly if stuck
        if holding_seconds > 120:  # 2 minutes
            return True
        # Any positive P&L is good for arb
        if pnl_pct >= Decimal("0.1"):
            return True
        # Cut losses fast
        if pnl_pct <= Decimal("-0.5"):
            return True
        return False
