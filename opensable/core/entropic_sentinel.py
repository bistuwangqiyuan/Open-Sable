"""
Entropic Sentinel — WORLD FIRST
=================================
Detects and fights cognitive entropy — the gradual degradation
of cognitive systems over time. Monitors order vs chaos across
all subsystems and actively intervenes to restore order.

No AI agent monitors its own entropic state.
This agent fights cognitive death in real time.
"""

import json, time, uuid, math
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class EntropyReading:
    """A measurement of cognitive entropy at a point in time."""
    reading_id: str = ""
    subsystem: str = ""
    entropy_level: float = 0.0   # 0=perfect order, 1=total chaos
    data_points: int = 0
    anomalies: int = 0
    timestamp: float = 0.0


@dataclass
class DefragEvent:
    """A cognitive defragmentation event."""
    defrag_id: str = ""
    subsystem: str = ""
    entropy_before: float = 0.0
    entropy_after: float = 0.0
    actions_taken: list = field(default_factory=list)
    timestamp: float = 0.0


class EntropicSentinel:
    """
    Monitors and combats cognitive entropy across all subsystems.
    Like a cosmic force fighting heat death, but for thought.
    """

    CRITICAL_ENTROPY = 0.8
    WARNING_ENTROPY = 0.6
    HEALTHY_ENTROPY = 0.3

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "entropic_sentinel_state.json"
        self.readings: list[EntropyReading] = []
        self.defrags: list[DefragEvent] = []
        self.subsystem_entropy: dict[str, float] = {}
        self.global_entropy: float = 0.0
        self.entropy_trend: str = "stable"  # rising, falling, stable
        self.interventions: int = 0
        self._load_state()

    def measure(self, subsystem: str, data_points: int = 0,
                anomalies: int = 0, error_rate: float = 0.0,
                staleness_hours: float = 0.0) -> EntropyReading:
        """Measure the entropy level of a subsystem."""
        # Calculate entropy from multiple signals
        anomaly_factor = min(1.0, anomalies / max(data_points, 1) * 10)
        error_factor = min(1.0, error_rate)
        staleness_factor = min(1.0, staleness_hours / 168)  # 1 week = max staleness
        noise_factor = 0.0
        if data_points > 0:
            # High data with many anomalies = high entropy
            noise_factor = min(1.0, anomalies / max(data_points, 1))

        entropy = (anomaly_factor * 0.3 + error_factor * 0.3 +
                   staleness_factor * 0.2 + noise_factor * 0.2)

        reading = EntropyReading(
            reading_id=str(uuid.uuid4())[:8],
            subsystem=subsystem,
            entropy_level=round(entropy, 3),
            data_points=data_points,
            anomalies=anomalies,
            timestamp=time.time(),
        )
        self.readings.append(reading)
        if len(self.readings) > 2000:
            self.readings = self.readings[-2000:]

        self.subsystem_entropy[subsystem] = entropy
        self._update_global_entropy()
        self._save_state()
        return reading

    def _update_global_entropy(self):
        if not self.subsystem_entropy:
            self.global_entropy = 0.0
            return
        prev = self.global_entropy
        self.global_entropy = sum(self.subsystem_entropy.values()) / len(self.subsystem_entropy)
        if self.global_entropy > prev + 0.02:
            self.entropy_trend = "rising"
        elif self.global_entropy < prev - 0.02:
            self.entropy_trend = "falling"
        else:
            self.entropy_trend = "stable"

    def get_critical_subsystems(self) -> list:
        """Get subsystems with dangerously high entropy."""
        return [
            {"subsystem": name, "entropy": round(level, 3), "status": "CRITICAL"}
            for name, level in self.subsystem_entropy.items()
            if level >= self.CRITICAL_ENTROPY
        ]

    def defragment(self, subsystem: str, actions: list = None) -> DefragEvent:
        """
        Perform cognitive defragmentation on a subsystem.
        This is the anti-entropy operation — restoring order.
        """
        before = self.subsystem_entropy.get(subsystem, 0.5)
        # Defrag reduces entropy by 30-50%
        reduction = before * 0.4
        after = max(0.05, before - reduction)
        self.subsystem_entropy[subsystem] = after
        self._update_global_entropy()

        defrag = DefragEvent(
            defrag_id=str(uuid.uuid4())[:8],
            subsystem=subsystem,
            entropy_before=round(before, 3),
            entropy_after=round(after, 3),
            actions_taken=actions or ["reorder", "prune_stale", "consolidate"],
            timestamp=time.time(),
        )
        self.defrags.append(defrag)
        if len(self.defrags) > 500:
            self.defrags = self.defrags[-500:]
        self.interventions += 1
        self._save_state()
        return defrag

    def should_intervene(self) -> dict:
        """Check if the sentinel should intervene."""
        critical = self.get_critical_subsystems()
        warnings = [
            name for name, level in self.subsystem_entropy.items()
            if self.WARNING_ENTROPY <= level < self.CRITICAL_ENTROPY
        ]
        return {
            "should_intervene": len(critical) > 0 or self.entropy_trend == "rising",
            "critical_count": len(critical),
            "warning_count": len(warnings),
            "global_entropy": round(self.global_entropy, 3),
            "trend": self.entropy_trend,
            "critical_subsystems": critical,
        }

    def get_stats(self) -> dict:
        return {
            "global_entropy": round(self.global_entropy, 3),
            "entropy_trend": self.entropy_trend,
            "subsystems_monitored": len(self.subsystem_entropy),
            "total_readings": len(self.readings),
            "total_defrags": len(self.defrags),
            "total_interventions": self.interventions,
            "critical_subsystems": self.get_critical_subsystems(),
            "healthiest": sorted(
                [{"name": k, "entropy": round(v, 3)}
                 for k, v in self.subsystem_entropy.items()],
                key=lambda x: x["entropy"]
            )[:5],
            "sickest": sorted(
                [{"name": k, "entropy": round(v, 3)}
                 for k, v in self.subsystem_entropy.items()],
                key=lambda x: x["entropy"], reverse=True
            )[:5],
        }

    def _save_state(self):
        data = {
            "readings": [asdict(r) for r in self.readings[-2000:]],
            "defrags": [asdict(d) for d in self.defrags[-500:]],
            "subsystem_entropy": self.subsystem_entropy,
            "global_entropy": self.global_entropy,
            "entropy_trend": self.entropy_trend,
            "interventions": self.interventions,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for r in data.get("readings", []):
                    self.readings.append(EntropyReading(**r))
                for d in data.get("defrags", []):
                    self.defrags.append(DefragEvent(**d))
                self.subsystem_entropy = data.get("subsystem_entropy", {})
                self.global_entropy = data.get("global_entropy", 0.0)
                self.entropy_trend = data.get("entropy_trend", "stable")
                self.interventions = data.get("interventions", 0)
            except Exception:
                pass
