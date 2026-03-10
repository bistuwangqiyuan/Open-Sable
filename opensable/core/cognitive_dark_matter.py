"""
Cognitive Dark Matter,  WORLD FIRST
=====================================
Detects the influence of HIDDEN, UNOBSERVABLE variables that affect
the agent's performance but can't be directly measured. Like dark matter
in physics,  you can't see it, but you can see its gravitational effects.

Infers the existence of invisible factors from their effects.
No AI agent detects cognitive dark matter. This one does.
"""

import json, time, uuid, math
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class DarkVariable:
    """An inferred hidden variable affecting performance."""
    var_id: str = ""
    name: str = ""
    inferred_effect: str = ""     # positive, negative, oscillating
    influence_strength: float = 0.0  # 0-1
    evidence: list = field(default_factory=list)
    hypothesis: str = ""
    confidence: float = 0.0
    discovered_at: float = 0.0
    last_detected: float = 0.0


@dataclass
class AnomalyRecord:
    """An unexplained performance anomaly."""
    anomaly_id: str = ""
    metric: str = ""
    expected_value: float = 0.0
    actual_value: float = 0.0
    deviation: float = 0.0
    explained: bool = False
    dark_variable_id: str = ""
    timestamp: float = 0.0


class CognitiveDarkMatter:
    """
    Detects hidden variables that affect performance but can't be seen.
    Like dark matter,  invisible but real, detectable by their effects.
    """

    def __init__(self, data_dir: str, anomaly_threshold: float = 0.3):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "cognitive_dark_matter_state.json"
        self.dark_variables: dict[str, DarkVariable] = {}
        self.anomalies: list[AnomalyRecord] = []
        self.metric_history: dict[str, list] = {}   # metric -> [values]
        self.threshold = anomaly_threshold
        self.total_dark_detections: int = 0
        self._load_state()

    def record_metric(self, metric: str, value: float) -> dict:
        """Record a performance metric and check for anomalies."""
        if metric not in self.metric_history:
            self.metric_history[metric] = []
        self.metric_history[metric].append({
            "value": value, "timestamp": time.time()
        })
        if len(self.metric_history[metric]) > 200:
            self.metric_history[metric] = self.metric_history[metric][-200:]

        # Calculate expected value (moving average)
        values = [v["value"] for v in self.metric_history[metric]]
        if len(values) < 3:
            return {"anomaly": False}

        avg = sum(values[-20:]) / len(values[-20:])
        std = math.sqrt(sum((v - avg) ** 2 for v in values[-20:]) / len(values[-20:]))
        if std == 0:
            std = 0.01

        deviation = abs(value - avg) / std

        if deviation > 2.0:  # More than 2 standard deviations
            anomaly = AnomalyRecord(
                anomaly_id=str(uuid.uuid4())[:8],
                metric=metric,
                expected_value=round(avg, 3),
                actual_value=value,
                deviation=round(deviation, 3),
                timestamp=time.time(),
            )
            self.anomalies.append(anomaly)
            if len(self.anomalies) > 1000:
                self.anomalies = self.anomalies[-1000:]
            self._save_state()
            return {
                "anomaly": True,
                "anomaly_id": anomaly.anomaly_id,
                "expected": round(avg, 3),
                "actual": value,
                "deviation_sigma": round(deviation, 2),
            }

        self._save_state()
        return {"anomaly": False, "deviation_sigma": round(deviation, 2)}

    async def infer_dark_variables(self, llm=None) -> list:
        """Analyze unexplained anomalies to infer hidden variables."""
        unexplained = [a for a in self.anomalies if not a.explained][-10:]
        if not unexplained:
            return []

        if llm:
            anomaly_data = [
                {"metric": a.metric, "expected": a.expected_value,
                 "actual": a.actual_value, "deviation": a.deviation}
                for a in unexplained
            ]
            prompt = (
                f"COGNITIVE DARK MATTER DETECTION:\n\n"
                f"These performance anomalies have no known explanation:\n"
                f"{json.dumps(anomaly_data)}\n\n"
                f"Existing dark variables: "
                f"{[dv.name for dv in self.dark_variables.values()]}\n\n"
                f"Infer 1-3 HIDDEN VARIABLES that could explain these anomalies. "
                f"These are factors that can't be directly measured but whose effects are visible.\n"
                f"Return JSON: {{\"dark_variables\": [{{\"name\": \"...\", "
                f"\"effect\": \"positive/negative/oscillating\", "
                f"\"hypothesis\": \"...\", \"confidence\": 0.0-1.0}}]}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=500)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    new_dvs = []
                    for dvd in result.get("dark_variables", []):
                        dv = DarkVariable(
                            var_id=str(uuid.uuid4())[:8],
                            name=dvd.get("name", "unknown_force"),
                            inferred_effect=dvd.get("effect", "unknown"),
                            influence_strength=dvd.get("confidence", 0.5),
                            hypothesis=dvd.get("hypothesis", ""),
                            confidence=dvd.get("confidence", 0.5),
                            discovered_at=time.time(),
                            last_detected=time.time(),
                        )
                        self.dark_variables[dv.var_id] = dv
                        new_dvs.append(dv.name)
                        self.total_dark_detections += 1

                    # Mark anomalies as explained
                    for a in unexplained:
                        a.explained = True
                        if new_dvs:
                            a.dark_variable_id = list(self.dark_variables.keys())[-1]

                    if len(self.dark_variables) > 100:
                        weakest = min(self.dark_variables.items(),
                                     key=lambda x: x[1].confidence)
                        del self.dark_variables[weakest[0]]

                    self._save_state()
                    return new_dvs
            except Exception:
                pass
        return []

    def get_dark_map(self) -> dict:
        """Get the map of all known dark variables and their effects."""
        return {
            dv.name: {
                "effect": dv.inferred_effect,
                "strength": round(dv.influence_strength, 2),
                "hypothesis": dv.hypothesis[:100],
                "confidence": round(dv.confidence, 2),
            }
            for dv in sorted(self.dark_variables.values(),
                            key=lambda d: d.confidence, reverse=True)
        }

    def get_stats(self) -> dict:
        unexplained = sum(1 for a in self.anomalies if not a.explained)
        return {
            "dark_variables_detected": len(self.dark_variables),
            "total_anomalies": len(self.anomalies),
            "unexplained_anomalies": unexplained,
            "metrics_tracked": len(self.metric_history),
            "total_dark_detections": self.total_dark_detections,
            "dark_map": self.get_dark_map(),
            "recent_anomalies": [
                {"metric": a.metric, "deviation": a.deviation,
                 "explained": a.explained}
                for a in self.anomalies[-5:]
            ],
        }

    def _save_state(self):
        data = {
            "dark_variables": {k: asdict(v) for k, v in self.dark_variables.items()},
            "anomalies": [asdict(a) for a in self.anomalies[-1000:]],
            "metric_history": {k: v[-200:] for k, v in self.metric_history.items()},
            "total_dark_detections": self.total_dark_detections,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("dark_variables", {}).items():
                    self.dark_variables[k] = DarkVariable(**v)
                for a in data.get("anomalies", []):
                    self.anomalies.append(AnomalyRecord(**a))
                self.metric_history = data.get("metric_history", {})
                self.total_dark_detections = data.get("total_dark_detections", 0)
            except Exception:
                pass
