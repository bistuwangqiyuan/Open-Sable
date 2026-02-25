"""
Sentiment Strategy — LLM-powered news and social media analysis.

This is Open-Sable's unique edge over traditional bots: it uses the
LLM to read news articles, tweets, and Reddit posts, then generates
a sentiment score that drives trading decisions.

Best for: memecoins, event-driven markets, breaking news.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Callable, Coroutine, Dict, List, Optional

from ..base import OHLCV, PriceTick
from ..strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


class SentimentStrategy(Strategy):
    """
    LLM-powered sentiment analysis strategy.

    1. Fetches news headlines and social posts about the asset
    2. Asks the LLM to score sentiment from -1.0 to +1.0
    3. Generates BUY signal on strong positive, SELL on strong negative
    4. Combines sentiment with basic momentum for confirmation

    Requires:
    - An LLM invoke function (injected at init)
    - Optionally, a web search function and X/Twitter search function
    """

    name = "sentiment"
    description = "LLM-powered news and social media sentiment analysis"
    version = "1.0.0"
    supported_markets = ["crypto", "stocks", "prediction", "memecoins"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)
        self.run_interval_seconds = self.config.get("interval", 300)  # 5 min
        self.sentiment_threshold = self.config.get("sentiment_threshold", 0.6)
        self.max_news_age_hours = self.config.get("max_news_age_hours", 4)

        # Injected callbacks — set these after construction
        self._llm_invoke: Optional[Callable[..., Coroutine]] = None
        self._web_search: Optional[Callable[..., Coroutine]] = None
        self._x_search: Optional[Callable[..., Coroutine]] = None

    def set_llm(self, llm_invoke: Callable[..., Coroutine]) -> None:
        """Inject the LLM invoke function (from SableAgent.llm)."""
        self._llm_invoke = llm_invoke

    def set_web_search(self, search_fn: Callable[..., Coroutine]) -> None:
        """Inject web search function (from BrowserSkill)."""
        self._web_search = search_fn

    def set_x_search(self, search_fn: Callable[..., Coroutine]) -> None:
        """Inject X/Twitter search function."""
        self._x_search = search_fn

    async def analyze(
        self,
        symbol: str,
        candles: List[OHLCV],
        current_price: PriceTick,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Signal]:
        if not self._llm_invoke:
            logger.warning("SentimentStrategy: no LLM configured, skipping")
            return []

        # Gather intelligence
        intel_parts: List[str] = []

        # 1. Web search for recent news
        if self._web_search:
            try:
                base_symbol = symbol.upper().replace("USDT", "").replace("/USDT", "").replace("USD", "")
                news = await self._web_search(f"{base_symbol} price news last {self.max_news_age_hours} hours")
                if news:
                    intel_parts.append(f"Recent news:\n{news[:2000]}")
            except Exception as e:
                logger.debug(f"Web search failed for {symbol}: {e}")

        # 2. X/Twitter sentiment
        if self._x_search:
            try:
                base_symbol = symbol.upper().replace("USDT", "").replace("/USDT", "").replace("USD", "")
                tweets = await self._x_search(f"${base_symbol}")
                if tweets:
                    intel_parts.append(f"Social media posts:\n{tweets[:2000]}")
            except Exception as e:
                logger.debug(f"X search failed for {symbol}: {e}")

        # 3. Price context
        if candles:
            recent = candles[-10:]
            price_change = ((float(current_price.price) / float(recent[0].close)) - 1) * 100
            intel_parts.append(
                f"Price data: current=${current_price.price}, "
                f"change over last 10 candles: {price_change:+.2f}%"
            )

        # 4. Any additional context passed in
        if context:
            for key, val in context.items():
                if isinstance(val, str) and val:
                    intel_parts.append(f"{key}: {val[:500]}")

        if not intel_parts:
            return []

        # Ask LLM to score sentiment
        intel_text = "\n\n".join(intel_parts)
        prompt = f"""Analyze the market sentiment for {symbol} based on the following data.

{intel_text}

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "score": <float from -1.0 (very bearish) to 1.0 (very bullish)>,
  "confidence": <float from 0.0 to 1.0>,
  "summary": "<one sentence explanation>",
  "key_factors": ["<factor1>", "<factor2>"]
}}"""

        try:
            response = await self._llm_invoke(prompt)
            import json
            # Try to parse JSON from response
            text = response if isinstance(response, str) else str(response)
            # Extract JSON from possible markdown code blocks
            if "```" in text:
                text = text.split("```")[1].replace("json", "").strip()
            data = json.loads(text)

            score = float(data.get("score", 0))
            confidence = float(data.get("confidence", 0.5))
            summary = data.get("summary", "")

        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM sentiment response: {e}")
            return []

        signals: List[Signal] = []

        # Generate signal if sentiment is strong enough
        if abs(score) >= self.sentiment_threshold and confidence >= 0.4:
            direction = SignalDirection.LONG if score > 0 else SignalDirection.SHORT
            combined_conf = min(abs(score) * confidence, 1.0)

            signals.append(Signal(
                symbol=symbol,
                direction=direction,
                confidence=round(combined_conf, 3),
                entry_price=current_price.price,
                reason=f"Sentiment {direction.value}: score={score:.2f}, {summary}",
                metadata={
                    "sentiment_score": score,
                    "llm_confidence": confidence,
                    "key_factors": data.get("key_factors", []),
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
        # Standard profit/loss exits
        if pnl_pct >= Decimal("5"):
            return True
        if pnl_pct <= Decimal("-3"):
            return True
        # Sentiment trades should resolve in hours, not days
        if holding_seconds > 21600 and pnl_pct < Decimal("1"):  # 6 hours
            return True
        return False
