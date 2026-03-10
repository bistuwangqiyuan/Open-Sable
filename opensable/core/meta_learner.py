"""
Meta-Learning Controller,  learning to learn.

Tracks which cognitive strategies produce the best outcomes and
auto-tunes hyperparameters (learning rates, tick intervals, thresholds)
across the entire cognitive pipeline.

Concepts
--------
- **Strategy Profile**,  a named set of hyperparameters the agent is currently using
- **Strategy Score**,  rolling performance under a given profile
- **Exploration / Exploitation**,  epsilon-greedy: 80% exploit best, 20% explore random
- **Adaptation Rate**,  how fast the controller switches strategies after evidence

Persistence: ``meta_learner_state.json`` in *data_dir*.
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Tunable hyperparameters the meta-learner can adjust ───────────────────────

_DEFAULT_HYPERPARAM_SPACE = {
    "cognitive_tick_interval": {"min": 30, "max": 300, "step": 15, "default": 60},
    "memory_decay_rate": {"min": 0.001, "max": 0.05, "step": 0.002, "default": 0.01},
    "reflection_depth": {"min": 3, "max": 20, "step": 1, "default": 10},
    "planner_max_steps": {"min": 5, "max": 25, "step": 2, "default": 15},
    "exploration_rate": {"min": 0.05, "max": 0.4, "step": 0.05, "default": 0.2},
    "consolidation_interval": {"min": 20, "max": 100, "step": 10, "default": 50},
    "pattern_window_size": {"min": 20, "max": 100, "step": 10, "default": 50},
    "proactive_aggressiveness": {"min": 0.1, "max": 0.9, "step": 0.1, "default": 0.5},
    "hebbian_learning_rate": {"min": 0.005, "max": 0.05, "step": 0.005, "default": 0.02},
    "self_benchmark_interval": {"min": 10, "max": 50, "step": 5, "default": 25},
}


@dataclass
class StrategyProfile:
    """A named configuration of hyperparameters."""

    profile_id: str
    params: Dict[str, float]
    score: float = 0.0
    uses: int = 0
    created_at: str = ""
    last_used_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class AdaptationEvent:
    tick: int
    from_profile: str
    to_profile: str
    reason: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class MetaLearner:
    """Meta-learning controller that optimizes the agent's own cognitive hyperparameters."""

    def __init__(
        self,
        data_dir: Path,
        hyperparam_space: Optional[Dict] = None,
        evaluate_interval: int = 15,
        epsilon: float = 0.2,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "meta_learner_state.json"

        self._space = hyperparam_space or _DEFAULT_HYPERPARAM_SPACE
        self._evaluate_interval = evaluate_interval
        self._epsilon = epsilon

        # Active strategy
        self._active_profile_id: str = "default"
        self._profiles: Dict[str, StrategyProfile] = {}
        self._adaptations: List[AdaptationEvent] = []
        self._performance_history: List[Dict[str, Any]] = []
        self._last_evaluate_tick: int = 0
        self._total_evaluations: int = 0

        # Initialize default profile
        default_params = {k: v["default"] for k, v in self._space.items()}
        self._profiles["default"] = StrategyProfile(
            profile_id="default", params=default_params
        )

        self._load_state()

    # ── Core API ──────────────────────────────────────────────────────────────

    def get_active_params(self) -> Dict[str, float]:
        """Return the currently active hyperparameters."""
        profile = self._profiles.get(self._active_profile_id)
        if profile:
            return dict(profile.params)
        return {k: v["default"] for k, v in self._space.items()}

    def get_param(self, name: str) -> float:
        """Get a single hyperparameter value."""
        params = self.get_active_params()
        return params.get(name, self._space.get(name, {}).get("default", 0))

    async def evaluate_and_adapt(
        self,
        tick: int,
        performance_score: float,
        agent_state: Optional[Dict] = None,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate current strategy and possibly switch to a better one.

        Called every N ticks by the cognitive tick loop.

        Returns dict with adaptation info if a switch occurred, else None.
        """
        if tick - self._last_evaluate_tick < self._evaluate_interval:
            return None

        self._last_evaluate_tick = tick
        self._total_evaluations += 1

        # Record performance under current profile
        active = self._profiles.get(self._active_profile_id)
        if active:
            # Exponential moving average
            alpha = 0.3
            active.score = alpha * performance_score + (1 - alpha) * active.score
            active.uses += 1
            active.last_used_at = datetime.now().isoformat()

        self._performance_history.append({
            "tick": tick,
            "profile_id": self._active_profile_id,
            "score": performance_score,
            "timestamp": datetime.now().isoformat(),
        })

        # Keep only last 200 entries
        if len(self._performance_history) > 200:
            self._performance_history = self._performance_history[-200:]

        # Decide: exploit or explore?
        if random.random() < self._epsilon:
            # EXPLORE: create a mutated profile
            new_profile = self._mutate_profile(active)
            self._profiles[new_profile.profile_id] = new_profile
            old_id = self._active_profile_id
            self._active_profile_id = new_profile.profile_id

            event = AdaptationEvent(
                tick=tick,
                from_profile=old_id,
                to_profile=new_profile.profile_id,
                reason="exploration",
            )
            self._adaptations.append(event)
            self._save_state()

            return {
                "action": "explore",
                "from": old_id,
                "to": new_profile.profile_id,
                "new_params": new_profile.params,
            }
        else:
            # EXPLOIT: switch to best-scoring profile if better than current
            best = max(self._profiles.values(), key=lambda p: p.score)
            if best.profile_id != self._active_profile_id and best.score > active.score + 0.05:
                old_id = self._active_profile_id
                self._active_profile_id = best.profile_id

                event = AdaptationEvent(
                    tick=tick,
                    from_profile=old_id,
                    to_profile=best.profile_id,
                    reason=f"exploit (score {best.score:.2f} > {active.score:.2f})",
                )
                self._adaptations.append(event)
                self._save_state()

                return {
                    "action": "exploit",
                    "from": old_id,
                    "to": best.profile_id,
                    "score_improvement": best.score - active.score,
                }

        self._save_state()
        return None

    # ── Profile mutation ──────────────────────────────────────────────────────

    def _mutate_profile(self, source: Optional[StrategyProfile] = None) -> StrategyProfile:
        """Create a new profile by randomly mutating 1-3 hyperparameters."""
        base_params = source.params if source else {k: v["default"] for k, v in self._space.items()}
        new_params = dict(base_params)

        # Mutate 1-3 random parameters
        mutate_count = random.randint(1, 3)
        keys = random.sample(list(self._space.keys()), min(mutate_count, len(self._space)))

        for key in keys:
            spec = self._space[key]
            current = new_params[key]
            step = spec["step"]

            # Random walk: ±1-2 steps
            delta = random.choice([-2, -1, 1, 2]) * step
            new_val = current + delta
            new_val = max(spec["min"], min(spec["max"], new_val))

            # Round to step precision
            if isinstance(step, float):
                new_val = round(new_val, 4)
            else:
                new_val = int(round(new_val))

            new_params[key] = new_val

        profile_id = f"gen_{hashlib.md5(json.dumps(new_params, sort_keys=True).encode()).hexdigest()[:8]}"
        return StrategyProfile(profile_id=profile_id, params=new_params)

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        active = self._profiles.get(self._active_profile_id)
        profiles_summary = []
        for p in sorted(self._profiles.values(), key=lambda x: -x.score)[:10]:
            profiles_summary.append({
                "id": p.profile_id,
                "score": round(p.score, 3),
                "uses": p.uses,
                "active": p.profile_id == self._active_profile_id,
            })

        recent_adaptations = []
        for a in self._adaptations[-10:]:
            recent_adaptations.append({
                "tick": a.tick,
                "from": a.from_profile,
                "to": a.to_profile,
                "reason": a.reason,
            })

        # Calculate improvement rate
        if len(self._performance_history) >= 10:
            early = [h["score"] for h in self._performance_history[:5]]
            late = [h["score"] for h in self._performance_history[-5:]]
            improvement = (sum(late) / len(late)) - (sum(early) / len(early))
        else:
            improvement = 0.0

        return {
            "active_profile": self._active_profile_id,
            "active_params": active.params if active else {},
            "active_score": round(active.score, 3) if active else 0,
            "total_profiles": len(self._profiles),
            "total_evaluations": self._total_evaluations,
            "total_adaptations": len(self._adaptations),
            "epsilon": self._epsilon,
            "improvement_rate": round(improvement, 4),
            "profiles": profiles_summary,
            "recent_adaptations": recent_adaptations,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "active_profile_id": self._active_profile_id,
                "profiles": {k: asdict(v) for k, v in self._profiles.items()},
                "adaptations": [asdict(a) for a in self._adaptations[-50:]],
                "performance_history": self._performance_history[-200:],
                "total_evaluations": self._total_evaluations,
                "last_evaluate_tick": self._last_evaluate_tick,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Meta-learner save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._active_profile_id = data.get("active_profile_id", "default")
                self._total_evaluations = data.get("total_evaluations", 0)
                self._last_evaluate_tick = data.get("last_evaluate_tick", 0)
                self._performance_history = data.get("performance_history", [])

                for pid, pdata in data.get("profiles", {}).items():
                    self._profiles[pid] = StrategyProfile(**pdata)

                for adict in data.get("adaptations", []):
                    self._adaptations.append(AdaptationEvent(**adict))
        except Exception as e:
            logger.debug(f"Meta-learner load failed: {e}")
