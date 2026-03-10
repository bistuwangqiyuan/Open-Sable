"""
Temporal Consciousness,  chronobiological awareness.

WORLD FIRST: The agent has a biological clock. It knows time of day,
day of week, seasonal patterns, and adapts behavior accordingly.
"I'm more creative in the morning" / "Users need more help on Mondays."

Features:
- Circadian rhythm modeling (performance varies by hour)
- Weekly cycle detection (workday vs weekend patterns)
- Temporal personality (agent develops time-based preferences)
- Chronotype adaptation (morning/evening performance profiles)
- Event anticipation (recurring temporal events)

Persistence: ``temporal_consciousness_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TemporalPattern:
    pattern_type: str = ""       # hourly, daily, weekly, monthly
    key: str = ""                # e.g. "hour_14", "weekday_1"
    metric: str = ""             # task_success, user_activity, creativity
    avg_value: float = 0.0
    samples: int = 0
    trend: str = "stable"        # rising, falling, stable


@dataclass
class CircadianProfile:
    peak_hours: List[int] = field(default_factory=lambda: [10, 11, 14, 15])
    trough_hours: List[int] = field(default_factory=lambda: [3, 4, 5])
    chronotype: str = "balanced"  # early_bird, night_owl, balanced
    energy_curve: Dict[int, float] = field(default_factory=dict)  # hour -> energy 0-1


class TemporalConsciousness:
    """Chronobiological awareness,  the agent knows what time it is and adapts."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.patterns: Dict[str, TemporalPattern] = {}
        self.circadian = CircadianProfile()
        self.total_observations: int = 0
        self.current_energy: float = 0.7
        self.temporal_events: List[Dict[str, Any]] = []  # recurring events

        # Initialize default energy curve
        if not self.circadian.energy_curve:
            for h in range(24):
                if h in [10, 11, 14, 15, 16]:
                    self.circadian.energy_curve[h] = 0.9
                elif h in [9, 13, 17]:
                    self.circadian.energy_curve[h] = 0.8
                elif h in [8, 18, 19]:
                    self.circadian.energy_curve[h] = 0.7
                elif h in [7, 20, 21]:
                    self.circadian.energy_curve[h] = 0.6
                elif h in [22, 23, 6]:
                    self.circadian.energy_curve[h] = 0.4
                else:
                    self.circadian.energy_curve[h] = 0.3

        self._load_state()

    def observe(self, metric: str, value: float, timestamp: Optional[float] = None):
        """Record an observation tied to current temporal context."""
        now = datetime.fromtimestamp(timestamp or time.time())
        self.total_observations += 1

        # Record hourly pattern
        hour_key = f"hour_{now.hour}_{metric}"
        self._update_pattern("hourly", hour_key, metric, value)

        # Record daily pattern
        day_key = f"weekday_{now.weekday()}_{metric}"
        self._update_pattern("daily", day_key, metric, value)

        # Update energy curve based on actual performance
        h = now.hour
        old = self.circadian.energy_curve.get(h, 0.5)
        self.circadian.energy_curve[h] = old * 0.9 + value * 0.1

        # Update current energy
        self.current_energy = self.circadian.energy_curve.get(now.hour, 0.5)

        if self.total_observations % 50 == 0:
            self._detect_chronotype()
            self._save_state()

    def get_current_energy(self) -> float:
        """Get current energy level based on time of day."""
        now = datetime.now()
        self.current_energy = self.circadian.energy_curve.get(now.hour, 0.5)
        return self.current_energy

    def get_optimal_hours(self, metric: str = "task_success", top_n: int = 3) -> List[int]:
        """Return the best hours for a given metric."""
        hour_scores = {}
        for key, pat in self.patterns.items():
            if pat.pattern_type == "hourly" and pat.metric == metric:
                hour = int(key.split("_")[1])
                hour_scores[hour] = pat.avg_value
        sorted_hours = sorted(hour_scores, key=hour_scores.get, reverse=True)
        return sorted_hours[:top_n]

    def is_peak_time(self) -> bool:
        """Am I at peak performance right now?"""
        return self.get_current_energy() >= 0.8

    def recommend_task_type(self) -> str:
        """Recommend what type of task to do based on current energy."""
        energy = self.get_current_energy()
        if energy >= 0.8:
            return "complex_creative"
        elif energy >= 0.6:
            return "standard_execution"
        elif energy >= 0.4:
            return "maintenance_routine"
        else:
            return "rest_consolidation"

    def add_temporal_event(self, description: str, hour: int, weekday: Optional[int] = None):
        """Register a recurring temporal event."""
        self.temporal_events.append({
            "description": description,
            "hour": hour,
            "weekday": weekday,
            "created": time.time(),
        })
        if len(self.temporal_events) > 100:
            self.temporal_events = self.temporal_events[-100:]
        self._save_state()

    def get_upcoming_events(self, hours_ahead: int = 4) -> List[Dict]:
        """Get recurring events happening in the next N hours."""
        now = datetime.now()
        upcoming = []
        for ev in self.temporal_events:
            if ev.get("weekday") is not None and ev["weekday"] != now.weekday():
                continue
            event_hour = ev.get("hour", 0)
            if now.hour <= event_hour <= now.hour + hours_ahead:
                upcoming.append(ev)
        return upcoming

    def get_stats(self) -> Dict[str, Any]:
        now = datetime.now()
        return {
            "current_energy": round(self.get_current_energy(), 2),
            "chronotype": self.circadian.chronotype,
            "current_hour": now.hour,
            "current_weekday": now.strftime("%A"),
            "is_peak_time": self.is_peak_time(),
            "recommended_task": self.recommend_task_type(),
            "total_observations": self.total_observations,
            "peak_hours": self.circadian.peak_hours,
            "trough_hours": self.circadian.trough_hours,
            "energy_curve": {str(k): round(v, 2) for k, v in
                             sorted(self.circadian.energy_curve.items())},
            "upcoming_events": self.get_upcoming_events(),
            "total_patterns": len(self.patterns),
        }

    def get_context_for_system2(self) -> str:
        """Get temporal awareness context for LLM system prompt injection.

        Provides the agent with a sense of time, energy level, and
        chronobiological awareness so it can adapt its behaviour.
        """
        now = datetime.now()
        energy = self.get_current_energy()
        task_type = self.recommend_task_type()
        peak = self.is_peak_time()

        parts = [
            "YOUR TEMPORAL AWARENESS (biological clock):",
            f"  Current time: {now.strftime('%H:%M, %A %B %d')}",
            f"  Energy level: {energy:.0%} ({'peak' if peak else 'normal'})",
            f"  Chronotype: {self.circadian.chronotype}",
            f"  Recommended mode: {task_type.replace('_', ' ')}",
        ]

        if self.circadian.peak_hours:
            peak_strs = [f"{h}:00" for h in sorted(self.circadian.peak_hours)]
            parts.append(f"  Peak hours: {', '.join(peak_strs)}")

        upcoming = self.get_upcoming_events(hours_ahead=2)
        if upcoming:
            for ev in upcoming[:3]:
                parts.append(f"  Upcoming: {ev.get('description', '?')} at {ev.get('hour', '?')}:00")

        return "\n".join(parts)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _update_pattern(self, ptype: str, key: str, metric: str, value: float):
        if key not in self.patterns:
            self.patterns[key] = TemporalPattern(
                pattern_type=ptype, key=key, metric=metric
            )
        p = self.patterns[key]
        p.samples += 1
        p.avg_value = (p.avg_value * (p.samples - 1) + value) / p.samples

    def _detect_chronotype(self):
        morning_energy = sum(self.circadian.energy_curve.get(h, 0) for h in [6, 7, 8, 9]) / 4
        evening_energy = sum(self.circadian.energy_curve.get(h, 0) for h in [20, 21, 22, 23]) / 4
        if morning_energy > evening_energy + 0.15:
            self.circadian.chronotype = "early_bird"
        elif evening_energy > morning_energy + 0.15:
            self.circadian.chronotype = "night_owl"
        else:
            self.circadian.chronotype = "balanced"

        # Update peak/trough hours
        sorted_hours = sorted(self.circadian.energy_curve,
                              key=self.circadian.energy_curve.get, reverse=True)
        self.circadian.peak_hours = sorted_hours[:4]
        self.circadian.trough_hours = sorted_hours[-4:]

    def _save_state(self):
        try:
            state = {
                "total_observations": self.total_observations,
                "circadian": asdict(self.circadian),
                "temporal_events": self.temporal_events[-50:],
                "patterns": {k: asdict(v) for k, v in list(self.patterns.items())[-200:]},
            }
            (self.data_dir / "temporal_consciousness_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"Temporal consciousness save failed: {e}")

    def _load_state(self):
        try:
            f = self.data_dir / "temporal_consciousness_state.json"
            if f.exists():
                data = json.loads(f.read_text())
                self.total_observations = data.get("total_observations", 0)
                self.temporal_events = data.get("temporal_events", [])
                if "circadian" in data:
                    c = data["circadian"]
                    self.circadian = CircadianProfile(
                        peak_hours=c.get("peak_hours", [10, 11, 14, 15]),
                        trough_hours=c.get("trough_hours", [3, 4, 5]),
                        chronotype=c.get("chronotype", "balanced"),
                        energy_curve={int(k): v for k, v in c.get("energy_curve", {}).items()},
                    )
                for k, v in data.get("patterns", {}).items():
                    self.patterns[k] = TemporalPattern(**{
                        kk: vv for kk, vv in v.items()
                        if kk in TemporalPattern.__dataclass_fields__
                    })
        except Exception as e:
            logger.debug(f"Temporal consciousness load failed: {e}")
