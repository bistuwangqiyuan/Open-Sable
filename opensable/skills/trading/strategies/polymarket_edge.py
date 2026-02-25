"""
Polymarket Edge Strategy — Find mispriced prediction markets.

Uses the LLM to estimate the "true" probability of an event, then
compares it to Polymarket's current price. When the gap exceeds a
threshold, it generates a BUY signal on the underpriced outcome.

Best for: prediction markets (Polymarket, Kalshi, etc.)
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional

from ..base import OHLCV, PriceTick
from ..strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


class PolymarketEdgeStrategy(Strategy):
    """
    LLM-estimated probability vs market price strategy for prediction markets.

    Workflow:
    1. Look at a Polymarket condition/question
    2. Ask LLM to estimate the probability (0-100%)
    3. If LLM estimate > market price + edge_threshold → BUY YES
    4. If LLM estimate < market price - edge_threshold → BUY NO (sell YES)

    Context required:
        market_question: str         — the actual prediction market question
        market_description: str      — optional additional context
        market_end_date: str         — when the market resolves
        current_yes_price: Decimal   — current YES token price (0-1)
        current_no_price: Decimal    — current NO token price (0-1)
        market_volume: Decimal       — total volume traded
    """

    name = "polymarket_edge"
    description = "LLM-estimated edge on prediction markets"
    version = "1.0.0"
    supported_markets = ["prediction"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.run_interval_seconds = self.config.get("interval", 600)  # 10 min
        self.edge_threshold_pct = Decimal(str(self.config.get("edge_threshold_pct", "8")))
        self.min_volume = Decimal(str(self.config.get("min_volume", "1000")))
        self.max_bet_pct = float(self.config.get("max_bet_pct", 3))  # max 3% of portfolio

        # Injected LLM function
        self._llm_invoke: Optional[Callable[..., Coroutine]] = None

    def set_llm(self, llm_invoke: Callable[..., Coroutine]) -> None:
        """Inject the LLM invoke function."""
        self._llm_invoke = llm_invoke

    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        if not self._llm_invoke:
            logger.warning("PolymarketEdgeStrategy: no LLM configured, skipping")
            return []

        if not context:
            return []

        question = context.get("market_question", "")
        description = context.get("market_description", "")
        end_date = context.get("market_end_date", "unknown")
        yes_price = Decimal(str(context.get("current_yes_price", 0)))
        no_price = Decimal(str(context.get("current_no_price", 0)))
        volume = Decimal(str(context.get("market_volume", 0)))

        if not question:
            return []

        # Skip low-volume markets — too illiquid
        if volume < self.min_volume:
            return []

        market_implied_pct = yes_price * 100  # $0.65 = 65% implied probability

        # Ask LLM to estimate true probability
        prompt = f"""You are a prediction market analyst. Estimate the TRUE probability of this event.

Question: {question}
{f'Description: {description}' if description else ''}
Resolution date: {end_date}
Current market price: YES = ${yes_price:.2f} (implies {market_implied_pct:.1f}%)

Think step by step about:
1. Historical base rates for similar events
2. Current relevant information
3. Known biases in prediction markets

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "estimated_probability_pct": <your estimate 0-100>,
  "confidence": <0.0-1.0 how confident you are in your estimate>,
  "reasoning": "<brief explanation>"
}}"""

        try:
            response = await self._llm_invoke(prompt)
            import json
            text = response if isinstance(response, str) else str(response)
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            data = json.loads(text)

            estimated_pct = Decimal(str(data.get("estimated_probability_pct", 50)))
            confidence = float(data.get("confidence", 0.5))
            reasoning = data.get("reasoning", "")

        except Exception as e:
            logger.warning(f"Failed to parse LLM probability estimate: {e}")
            return []

        signals: List[Signal] = []

        # Calculate edge
        edge = estimated_pct - market_implied_pct  # positive = underpriced YES

        if abs(edge) >= self.edge_threshold_pct and confidence >= 0.5:
            if edge > 0:
                # Market underprices YES — buy YES tokens
                direction = SignalDirection.LONG
                entry = yes_price
                target_price = estimated_pct / 100
                reason = (
                    f"Polymarket edge: LLM estimates {estimated_pct:.0f}% vs "
                    f"market {market_implied_pct:.0f}% (+{edge:.0f}% edge). "
                    f"BUY YES. {reasoning}"
                )
            else:
                # Market overprices YES — buy NO tokens
                direction = SignalDirection.SHORT
                entry = no_price
                target_price = (100 - estimated_pct) / 100
                reason = (
                    f"Polymarket edge: LLM estimates {estimated_pct:.0f}% vs "
                    f"market {market_implied_pct:.0f}% ({edge:.0f}% edge). "
                    f"BUY NO. {reasoning}"
                )

            signal_confidence = min(float(abs(edge)) / 30.0 * confidence, 1.0)

            signals.append(Signal(
                symbol=symbol,
                direction=direction,
                confidence=round(signal_confidence, 3),
                entry_price=entry,
                take_profit=Decimal(str(target_price)),
                reason=reason,
                metadata={
                    "strategy_type": "polymarket_edge",
                    "market_question": question,
                    "market_implied_pct": float(market_implied_pct),
                    "llm_estimated_pct": float(estimated_pct),
                    "edge_pct": float(edge),
                    "llm_confidence": confidence,
                    "market_volume": float(volume),
                    "reasoning": reasoning,
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
        # Prediction markets: hold until near resolution or big move
        if pnl_pct >= Decimal("30"):  # Prediction market tokens can 3x
            return True
        if pnl_pct <= Decimal("-20"):  # Wide stop for volatile markets
            return True
        # If resolution is imminent and we're up, take profit
        if context and context.get("hours_to_resolution", 999) < 2:
            return True
        return False
