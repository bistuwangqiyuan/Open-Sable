"""
Cognitive Metabolism,  energy budgeting and recovery cycles.

WORLD FIRST: The agent has an "energy" system. Complex tasks consume more
energy, simple tasks less. When energy is low, it switches to maintenance
mode. Prevents cognitive burnout and optimizes for sustained performance.

Persistence: ``cognitive_metabolism_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_TASK_COSTS = {
    "simple": 5, "standard": 15, "complex": 35,
    "creative": 40, "research": 30, "maintenance": 5,
    "llm_call": 10, "tool_use": 8, "planning": 25,
}


@dataclass
class MetabolicEvent:
    tick: int = 0
    action: str = ""
    cost: int = 0
    energy_after: float = 0.0
    timestamp: float = 0.0


class CognitiveMetabolism:
    """Energy system,  prevents cognitive burnout."""

    def __init__(self, data_dir: Path, max_energy: float = 100.0,
                 regen_rate: float = 2.0, burnout_threshold: float = 15.0):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_energy = max_energy
        self.regen_rate = regen_rate  # per tick
        self.burnout_threshold = burnout_threshold

        self.energy: float = max_energy
        self.total_consumed: float = 0.0
        self.total_regenerated: float = 0.0
        self.burnout_count: int = 0
        self.current_mode: str = "normal"  # normal, conservation, recovery, burnout
        self.events: List[MetabolicEvent] = []
        self.tick_costs: List[float] = []

        self._load_state()

    def consume(self, action: str, cost: Optional[int] = None, tick: int = 0) -> bool:
        """Consume energy for an action. Returns False if insufficient energy."""
        actual_cost = cost if cost is not None else _TASK_COSTS.get(action, 10)

        # Conservation mode reduces costs
        if self.current_mode == "conservation":
            actual_cost = int(actual_cost * 0.7)
        elif self.current_mode == "burnout":
            return False  # Can't do anything in burnout

        if self.energy < actual_cost:
            if self.energy < self.burnout_threshold:
                self.current_mode = "burnout"
                self.burnout_count += 1
            return False

        self.energy -= actual_cost
        self.total_consumed += actual_cost
        self.events.append(MetabolicEvent(
            tick=tick, action=action, cost=actual_cost,
            energy_after=self.energy, timestamp=time.time(),
        ))
        if len(self.events) > 500:
            self.events = self.events[-500:]

        self._update_mode()
        return True

    def can_afford(self, action: str) -> bool:
        """Check if we can afford an action without consuming."""
        cost = _TASK_COSTS.get(action, 10)
        return self.energy >= cost and self.current_mode != "burnout"

    def regenerate(self, tick: int = 0, idle: bool = False):
        """Regenerate energy (called every tick)."""
        regen = self.regen_rate
        if idle:
            regen *= 3.0  # Rest is 3x more regenerative
        if self.current_mode == "recovery":
            regen *= 2.0  # Recovery mode is extra regenerative
        if self.current_mode == "burnout":
            regen *= 0.5  # Burnout recovery is slow

        old = self.energy
        self.energy = min(self.max_energy, self.energy + regen)
        self.total_regenerated += (self.energy - old)
        self.tick_costs.append(old - self.energy if self.energy < old else 0)
        if len(self.tick_costs) > 200:
            self.tick_costs = self.tick_costs[-200:]

        self._update_mode()

        if tick % 20 == 0:
            self._save_state()

    def get_energy_percentage(self) -> float:
        return (self.energy / self.max_energy) * 100

    def recommend_action_level(self) -> str:
        """What complexity can we handle right now?"""
        pct = self.get_energy_percentage()
        if pct >= 70:
            return "complex_creative"
        elif pct >= 40:
            return "standard"
        elif pct >= 20:
            return "simple_only"
        else:
            return "rest"

    def get_stats(self) -> Dict[str, Any]:
        return {
            "energy": round(self.energy, 1),
            "max_energy": self.max_energy,
            "energy_pct": round(self.get_energy_percentage(), 1),
            "current_mode": self.current_mode,
            "recommended_level": self.recommend_action_level(),
            "total_consumed": round(self.total_consumed, 1),
            "total_regenerated": round(self.total_regenerated, 1),
            "burnout_count": self.burnout_count,
            "recent_events": [
                {"action": e.action, "cost": e.cost, "energy_after": round(e.energy_after, 1)}
                for e in self.events[-5:]
            ],
        }

    def _update_mode(self):
        pct = self.get_energy_percentage()
        if pct >= 80:
            self.current_mode = "normal"
        elif pct >= 50:
            self.current_mode = "normal"
        elif pct >= 25:
            self.current_mode = "conservation"
        elif pct >= 10:
            self.current_mode = "recovery"
        else:
            if self.current_mode != "burnout":
                self.current_mode = "recovery"

    def _save_state(self):
        try:
            state = {
                "energy": self.energy, "total_consumed": self.total_consumed,
                "total_regenerated": self.total_regenerated,
                "burnout_count": self.burnout_count,
                "current_mode": self.current_mode,
                "events": [asdict(e) for e in self.events[-100:]],
            }
            (self.data_dir / "cognitive_metabolism_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Cognitive metabolism save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "cognitive_metabolism_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.energy = data.get("energy", self.max_energy)
                self.total_consumed = data.get("total_consumed", 0)
                self.total_regenerated = data.get("total_regenerated", 0)
                self.burnout_count = data.get("burnout_count", 0)
                self.current_mode = data.get("current_mode", "normal")
                for ed in data.get("events", []):
                    self.events.append(MetabolicEvent(**{k: v for k, v in ed.items()
                                                         if k in MetabolicEvent.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Cognitive metabolism load failed: {e}")
