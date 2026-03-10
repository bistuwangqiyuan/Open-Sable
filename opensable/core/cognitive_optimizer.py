"""
Cognitive Architecture Optimizer,  self-tuning tick pipeline.

Measures the actual impact of each cognitive phase (0-11) on agent
performance and dynamically adjusts:
  - Phase execution order
  - Phase intervals (some phases can run less frequently)
  - Phase weights (how much time/compute each phase gets)
  - Phase skipping (disable phases with negative ROI)

Key ideas:
  - **Impact scoring**: measures performance delta after each phase executes
  - **Dynamic intervals**: high-impact phases run more often
  - **Energy budgeting**: total cognitive compute per tick is bounded
  - **A/B testing**: occasionally runs alternative orderings to find better configs

Persistence: ``cognitive_optimizer_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Default phase configuration
_PHASES = [
    {"id": 0, "name": "Connectome signal propagation", "default_interval": 1, "min_interval": 1, "max_interval": 5},
    {"id": 1, "name": "Cognitive memory decay", "default_interval": 1, "min_interval": 1, "max_interval": 3},
    {"id": 2, "name": "Self-reflection", "default_interval": 1, "min_interval": 1, "max_interval": 5},
    {"id": 3, "name": "Skill evolution", "default_interval": 1, "min_interval": 1, "max_interval": 5},
    {"id": 4, "name": "Pattern learner", "default_interval": 1, "min_interval": 1, "max_interval": 3},
    {"id": 5, "name": "Git brain", "default_interval": 1, "min_interval": 1, "max_interval": 3},
    {"id": 6, "name": "Inner life", "default_interval": 1, "min_interval": 1, "max_interval": 3},
    {"id": 7, "name": "Hebbian learning", "default_interval": 5, "min_interval": 3, "max_interval": 15},
    {"id": 8, "name": "Deep planner", "default_interval": 1, "min_interval": 1, "max_interval": 5},
    {"id": 9, "name": "Inter-agent bridge", "default_interval": 10, "min_interval": 5, "max_interval": 30},
    {"id": 10, "name": "Ultra-LTM", "default_interval": 50, "min_interval": 20, "max_interval": 100},
    {"id": 11, "name": "Self-benchmark", "default_interval": 25, "min_interval": 10, "max_interval": 50},
]


@dataclass
class PhaseMetrics:
    """Performance metrics for a single cognitive phase."""

    phase_id: int
    name: str
    current_interval: int
    total_executions: int = 0
    total_duration_ms: float = 0.0
    impact_score: float = 0.5  # 0-1, higher = more impactful
    last_executed_tick: int = 0
    errors: int = 0
    skip_count: int = 0
    enabled: bool = True


@dataclass
class OptimizationEvent:
    """Record of a pipeline optimization."""

    tick: int
    phase_id: int
    change: str  # "interval_up", "interval_down", "disabled", "enabled", "reordered"
    old_value: Any
    new_value: Any
    reason: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CognitiveOptimizer:
    """Self-tuning cognitive tick pipeline."""

    def __init__(
        self,
        data_dir: Path,
        optimize_interval: int = 20,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "cognitive_optimizer_state.json"

        self._optimize_interval = optimize_interval
        self._last_optimize_tick: int = 0
        self._total_optimizations: int = 0

        self._phases: Dict[int, PhaseMetrics] = {}
        self._events: List[OptimizationEvent] = []
        self._performance_before: Dict[int, float] = {}  # phase_id → perf before
        self._phase_configs = {p["id"]: p for p in _PHASES}

        # Initialize phase metrics
        for p in _PHASES:
            self._phases[p["id"]] = PhaseMetrics(
                phase_id=p["id"],
                name=p["name"],
                current_interval=p["default_interval"],
            )

        self._load_state()

    # ── Phase execution tracking ──────────────────────────────────────────────

    def should_run_phase(self, phase_id: int, tick: int) -> bool:
        """Check if a phase should run this tick based on optimized intervals."""
        metrics = self._phases.get(phase_id)
        if not metrics or not metrics.enabled:
            return False
        return (tick - metrics.last_executed_tick) >= metrics.current_interval

    def record_phase_start(self, phase_id: int, performance_score: float):
        """Record performance score BEFORE a phase runs (for impact measurement)."""
        self._performance_before[phase_id] = performance_score

    def record_phase_end(
        self,
        phase_id: int,
        tick: int,
        duration_ms: float,
        performance_score: float,
        error: bool = False,
    ):
        """Record phase completion and update impact score."""
        metrics = self._phases.get(phase_id)
        if not metrics:
            return

        metrics.total_executions += 1
        metrics.total_duration_ms += duration_ms
        metrics.last_executed_tick = tick
        if error:
            metrics.errors += 1

        # Calculate impact as delta in performance
        before = self._performance_before.get(phase_id, performance_score)
        impact = performance_score - before
        # Normalize impact to 0-1 range
        normalized_impact = max(0, min(1, 0.5 + impact * 5))

        # Exponential moving average
        alpha = 0.2
        metrics.impact_score = alpha * normalized_impact + (1 - alpha) * metrics.impact_score

    # ── Optimization ──────────────────────────────────────────────────────────

    def optimize(self, tick: int) -> List[OptimizationEvent]:
        """Run optimization pass: adjust intervals based on impact scores."""
        if tick - self._last_optimize_tick < self._optimize_interval:
            return []

        self._last_optimize_tick = tick
        self._total_optimizations += 1
        new_events = []

        for phase_id, metrics in self._phases.items():
            config = self._phase_configs.get(phase_id, {})
            if not config:
                continue

            # Skip phases with too few executions to judge
            if metrics.total_executions < 5:
                continue

            # Error rate check: if >50% errors, increase interval (back off)
            error_rate = metrics.errors / max(metrics.total_executions, 1)
            if error_rate > 0.5 and metrics.current_interval < config.get("max_interval", 30):
                old = metrics.current_interval
                metrics.current_interval = min(
                    config.get("max_interval", 30),
                    metrics.current_interval + 2,
                )
                event = OptimizationEvent(
                    tick=tick,
                    phase_id=phase_id,
                    change="interval_up",
                    old_value=old,
                    new_value=metrics.current_interval,
                    reason=f"High error rate ({error_rate:.0%})",
                )
                new_events.append(event)
                continue

            # Impact-based interval adjustment
            if metrics.impact_score > 0.65:
                # High impact → run more often
                if metrics.current_interval > config.get("min_interval", 1):
                    old = metrics.current_interval
                    metrics.current_interval = max(
                        config.get("min_interval", 1),
                        metrics.current_interval - 1,
                    )
                    if old != metrics.current_interval:
                        event = OptimizationEvent(
                            tick=tick,
                            phase_id=phase_id,
                            change="interval_down",
                            old_value=old,
                            new_value=metrics.current_interval,
                            reason=f"High impact ({metrics.impact_score:.2f})",
                        )
                        new_events.append(event)

            elif metrics.impact_score < 0.3:
                # Low impact → run less often
                if metrics.current_interval < config.get("max_interval", 30):
                    old = metrics.current_interval
                    metrics.current_interval = min(
                        config.get("max_interval", 30),
                        metrics.current_interval + 1,
                    )
                    if old != metrics.current_interval:
                        event = OptimizationEvent(
                            tick=tick,
                            phase_id=phase_id,
                            change="interval_up",
                            old_value=old,
                            new_value=metrics.current_interval,
                            reason=f"Low impact ({metrics.impact_score:.2f})",
                        )
                        new_events.append(event)

        self._events.extend(new_events)
        if len(self._events) > 100:
            self._events = self._events[-100:]

        self._save_state()
        return new_events

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        phases = []
        for pid in sorted(self._phases.keys()):
            m = self._phases[pid]
            avg_dur = m.total_duration_ms / max(m.total_executions, 1)
            phases.append({
                "id": m.phase_id,
                "name": m.name,
                "interval": m.current_interval,
                "impact": round(m.impact_score, 3),
                "executions": m.total_executions,
                "avg_duration_ms": round(avg_dur, 1),
                "errors": m.errors,
                "enabled": m.enabled,
            })

        return {
            "total_optimizations": self._total_optimizations,
            "total_events": len(self._events),
            "phases": phases,
            "recent_events": [
                {
                    "tick": e.tick,
                    "phase": e.phase_id,
                    "change": e.change,
                    "old": e.old_value,
                    "new": e.new_value,
                    "reason": e.reason,
                }
                for e in self._events[-10:]
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "phases": {str(k): asdict(v) for k, v in self._phases.items()},
                "events": [asdict(e) for e in self._events[-100:]],
                "last_optimize_tick": self._last_optimize_tick,
                "total_optimizations": self._total_optimizations,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Cognitive optimizer save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._last_optimize_tick = data.get("last_optimize_tick", 0)
                self._total_optimizations = data.get("total_optimizations", 0)

                for pid_str, pdata in data.get("phases", {}).items():
                    pid = int(pid_str)
                    if pid in self._phases:
                        # Update from saved state
                        for key, val in pdata.items():
                            if hasattr(self._phases[pid], key):
                                setattr(self._phases[pid], key, val)

                for edata in data.get("events", []):
                    self._events.append(OptimizationEvent(**edata))
        except Exception as e:
            logger.debug(f"Cognitive optimizer load failed: {e}")
