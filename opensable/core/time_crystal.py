"""
Time Crystal Memory,  self-reinforcing temporal patterns.

WORLD FIRST: Discovers recurring cycles in agent and user behavior,
creating "temporal crystals",  periodic patterns that self-reinforce
and predict future states. Like discovering that every Monday the user
asks for reports, so the agent pre-prepares them.

Persistence: ``time_crystal_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class Crystal:
    id: str = ""
    description: str = ""
    period_hours: float = 24.0  # Cycle length
    phase: float = 0.0  # Current phase in cycle (0-1)
    strength: float = 0.5  # How reliable (0-1)
    observations: int = 0
    predicted_events: List[str] = field(default_factory=list)
    actual_hits: int = 0
    misses: int = 0
    last_activated: float = 0.0
    created: float = 0.0


class TimeCrystalMemory:
    """Self-reinforcing temporal patterns that predict the future."""

    def __init__(self, data_dir: Path, max_crystals: int = 50,
                 min_observations: int = 3):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_crystals = max_crystals
        self.min_observations = min_observations

        self.crystals: Dict[str, Crystal] = {}
        self.event_log: List[Dict[str, Any]] = []
        self.pending_predictions: List[Dict[str, Any]] = []

        self._load_state()

    def record_event(self, event_type: str, details: str = ""):
        """Record a timestamped event for pattern detection."""
        now = time.time()
        self.event_log.append({
            "type": event_type, "details": details[:200],
            "timestamp": now,
            "hour": datetime.fromtimestamp(now).hour,
            "weekday": datetime.fromtimestamp(now).weekday(),
        })
        if len(self.event_log) > 1000:
            self.event_log = self.event_log[-1000:]

        self._check_crystal_hits(event_type)

    def detect_patterns(self) -> List[Dict[str, Any]]:
        """Analyze event log to discover temporal crystals."""
        if len(self.event_log) < 10:
            return []

        discovered = []
        # Group by event type
        by_type: Dict[str, List[float]] = {}
        for e in self.event_log:
            t = e["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e["timestamp"])

        for event_type, timestamps in by_type.items():
            if len(timestamps) < self.min_observations:
                continue

            # Detect periodic patterns
            intervals = [timestamps[i+1] - timestamps[i]
                         for i in range(len(timestamps)-1)]
            if not intervals:
                continue

            avg_interval = sum(intervals) / len(intervals)
            interval_hours = avg_interval / 3600

            # Check consistency (low variance = strong crystal)
            if avg_interval > 0:
                variance = sum((i - avg_interval)**2 for i in intervals) / len(intervals)
                consistency = 1.0 / (1.0 + math.sqrt(variance) / avg_interval)
            else:
                consistency = 0

            if consistency >= 0.3 and interval_hours >= 0.5:
                crystal_id = f"crystal_{event_type}_{int(interval_hours)}h"
                if crystal_id not in self.crystals:
                    self.crystals[crystal_id] = Crystal(
                        id=crystal_id,
                        description=f"{event_type} every ~{interval_hours:.1f}h",
                        period_hours=interval_hours,
                        strength=consistency,
                        observations=len(timestamps),
                        created=time.time(),
                    )
                    discovered.append({
                        "type": event_type, "period_hours": round(interval_hours, 1),
                        "strength": round(consistency, 2),
                    })
                    if len(self.crystals) > self.max_crystals:
                        weakest = min(self.crystals.values(), key=lambda c: c.strength)
                        del self.crystals[weakest.id]
                else:
                    c = self.crystals[crystal_id]
                    c.observations = len(timestamps)
                    c.strength = min(0.99, (c.strength + consistency) / 2 + 0.01)

        # Detect day-of-week patterns
        by_weekday: Dict[str, Dict[int, int]] = {}
        for e in self.event_log:
            t = e["type"]
            wd = e["weekday"]
            if t not in by_weekday:
                by_weekday[t] = {}
            by_weekday[t][wd] = by_weekday[t].get(wd, 0) + 1

        for event_type, weekdays in by_weekday.items():
            total = sum(weekdays.values())
            for wd, count in weekdays.items():
                if count >= 3 and count / total >= 0.4:
                    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
                    cid = f"weekly_{event_type}_{days[wd]}"
                    if cid not in self.crystals:
                        self.crystals[cid] = Crystal(
                            id=cid,
                            description=f"{event_type} peaks on {days[wd]}",
                            period_hours=168,  # weekly
                            strength=count / total,
                            observations=count,
                            created=time.time(),
                        )
                        discovered.append({
                            "type": event_type, "day": days[wd],
                            "strength": round(count / total, 2),
                        })

        return discovered

    def predict_next(self, hours_ahead: float = 4.0) -> List[Dict[str, Any]]:
        """Predict what events will happen in the next N hours."""
        predictions = []
        now = time.time()
        for c in self.crystals.values():
            if c.strength < 0.3:
                continue
            period_sec = c.period_hours * 3600
            if c.last_activated > 0:
                time_since = now - c.last_activated
                next_occurrence = c.last_activated + period_sec
                if 0 < (next_occurrence - now) < hours_ahead * 3600:
                    pred = {
                        "crystal": c.id,
                        "event": c.description,
                        "expected_in_hours": round((next_occurrence - now) / 3600, 1),
                        "confidence": round(c.strength, 2),
                    }
                    predictions.append(pred)
                    self.pending_predictions.append({
                        **pred, "expected_time": next_occurrence,
                    })

        if len(self.pending_predictions) > 100:
            self.pending_predictions = self.pending_predictions[-100:]
        return predictions

    def _check_crystal_hits(self, event_type: str):
        """Check if this event was predicted by any crystal."""
        now = time.time()
        window = 3600  # 1 hour tolerance
        for c in self.crystals.values():
            if event_type in c.description or event_type in c.id:
                c.last_activated = now
                # Check pending predictions
                for pred in self.pending_predictions:
                    if pred["crystal"] == c.id:
                        expected = pred.get("expected_time", 0)
                        if abs(now - expected) < window:
                            c.actual_hits += 1
                            c.strength = min(0.99, c.strength + 0.05)

    def get_stats(self) -> Dict[str, Any]:
        active = [c for c in self.crystals.values() if c.strength >= 0.3]
        return {
            "total_crystals": len(self.crystals),
            "active_crystals": len(active),
            "events_logged": len(self.event_log),
            "predictions_pending": len(self.pending_predictions),
            "strongest": [
                {"id": c.id, "description": c.description,
                 "strength": round(c.strength, 2), "period_h": round(c.period_hours, 1),
                 "hits": c.actual_hits}
                for c in sorted(active, key=lambda x: x.strength, reverse=True)[:5]
            ],
        }

    def _save_state(self):
        try:
            state = {
                "crystals": {k: asdict(v) for k, v in self.crystals.items()},
                "event_log": self.event_log[-200:],
            }
            (self.data_dir / "time_crystal_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Time crystal save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "time_crystal_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.event_log = data.get("event_log", [])
                for k, v in data.get("crystals", {}).items():
                    self.crystals[k] = Crystal(
                        **{f: v[f] for f in Crystal.__dataclass_fields__ if f in v})
        except Exception as e:
            logger.debug(f"Time crystal load: {e}")
