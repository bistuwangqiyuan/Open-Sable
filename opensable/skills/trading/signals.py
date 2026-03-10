"""
Signal Aggregator,  Combines signals from multiple strategies.

When multiple strategies fire on the same symbol, the aggregator
combines them into a consensus signal with weighted confidence.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional

from .strategy_engine import Signal, SignalDirection

logger = logging.getLogger(__name__)


@dataclass
class AggregatedSignal:
    """A consensus signal from multiple strategies."""
    symbol: str
    direction: SignalDirection
    confidence: float
    contributing_strategies: List[str]
    signals: List[Signal]
    reason: str = ""

    @property
    def is_strong(self) -> bool:
        """Strong signal = multiple strategies agree with high confidence."""
        return self.confidence >= 0.7 and len(self.contributing_strategies) >= 2


class SignalAggregator:
    """
    Aggregates signals from multiple strategies for the same symbol.

    Weighting modes:
    - equal: all strategies weighted equally
    - confidence: weighted by signal confidence
    - custom: user-defined weights per strategy
    """

    def __init__(
        self,
        strategy_weights: Optional[Dict[str, float]] = None,
        min_confidence: float = 0.3,
        require_consensus: bool = False,
    ):
        self.strategy_weights = strategy_weights or {}
        self.min_confidence = min_confidence
        self.require_consensus = require_consensus  # Require 2+ strategies to agree

    def aggregate(self, signals: List[Signal]) -> List[AggregatedSignal]:
        """
        Aggregate signals grouped by symbol.

        Returns one AggregatedSignal per symbol (or none if below threshold).
        """
        if not signals:
            return []

        # Group by symbol
        by_symbol: Dict[str, List[Signal]] = defaultdict(list)
        for s in signals:
            if s.direction != SignalDirection.NEUTRAL and s.confidence >= self.min_confidence:
                by_symbol[s.symbol].append(s)

        results: List[AggregatedSignal] = []
        for symbol, sym_signals in by_symbol.items():
            agg = self._aggregate_symbol(symbol, sym_signals)
            if agg:
                results.append(agg)

        # Sort by confidence descending
        results.sort(key=lambda a: a.confidence, reverse=True)
        return results

    def _aggregate_symbol(self, symbol: str, signals: List[Signal]) -> Optional[AggregatedSignal]:
        """Aggregate signals for a single symbol."""
        if not signals:
            return None

        # Count votes by direction
        direction_votes: Dict[SignalDirection, float] = defaultdict(float)
        direction_signals: Dict[SignalDirection, List[Signal]] = defaultdict(list)

        for s in signals:
            weight = self.strategy_weights.get(s.strategy, 1.0)
            weighted_conf = s.confidence * weight
            direction_votes[s.direction] += weighted_conf
            direction_signals[s.direction].append(s)

        # Find winning direction
        best_direction = max(direction_votes, key=direction_votes.get)
        best_signals = direction_signals[best_direction]

        # Calculate consensus confidence
        total_weight = sum(
            self.strategy_weights.get(s.strategy, 1.0) for s in signals
        )
        consensus_conf = direction_votes[best_direction] / total_weight if total_weight > 0 else 0

        # Boost for agreement (multiple strategies agree)
        if len(best_signals) >= 2:
            consensus_conf = min(consensus_conf * 1.2, 1.0)

        # Require consensus check
        if self.require_consensus and len(best_signals) < 2:
            return None

        # Filter by minimum confidence
        if consensus_conf < self.min_confidence:
            return None

        strategies = list(set(s.strategy for s in best_signals))
        reasons = [s.reason for s in best_signals if s.reason]

        return AggregatedSignal(
            symbol=symbol,
            direction=best_direction,
            confidence=round(consensus_conf, 3),
            contributing_strategies=strategies,
            signals=best_signals,
            reason=" | ".join(reasons) if reasons else f"Consensus from {len(strategies)} strategies",
        )
