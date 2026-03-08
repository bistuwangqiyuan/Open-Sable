"""
Predictive Empathy — pre-emptive user frustration detection.

WORLD FIRST: The agent predicts when the user is ABOUT to get frustrated
BEFORE it happens, and proactively adjusts its behavior. It learns
frustration patterns: response time, repeated clarifications, tone shifts,
and intervenes before the user has to complain.

Persistence: ``predictive_empathy_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_FRUSTRATION_SIGNALS = {
    "repeated_request": 0.3,
    "short_response": 0.15,
    "question_marks_multiple": 0.2,
    "caps_usage": 0.25,
    "negative_tone": 0.35,
    "clarification_needed": 0.2,
    "long_wait": 0.15,
    "error_reported": 0.3,
    "task_repetition": 0.25,
}


@dataclass
class UserState:
    frustration_level: float = 0.0
    patience_estimate: float = 0.7
    satisfaction_trend: float = 0.5
    interaction_count: int = 0
    last_interaction: float = 0.0
    preferred_style: str = "balanced"  # concise, detailed, balanced
    known_triggers: List[str] = field(default_factory=list)


class PredictiveEmpathy:
    """Predicts user frustration before it happens."""

    def __init__(self, data_dir: Path, alert_threshold: float = 0.6,
                 decay_rate: float = 0.05):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.alert_threshold = alert_threshold
        self.decay_rate = decay_rate

        self.user_state = UserState()
        self.signal_history: List[Dict[str, Any]] = []
        self.interventions: List[Dict[str, Any]] = []
        self.predictions: List[Dict[str, Any]] = []
        self.accuracy: float = 0.5

        self._load_state()

    def observe_interaction(self, user_message: str, response_time_sec: float = 0.0):
        """Observe a user interaction and update frustration prediction."""
        signals_detected = []

        # Detect frustration signals
        msg = user_message.strip()
        if len(msg) < 10 and "?" in msg:
            signals_detected.append("short_response")
        if msg.count("?") >= 2:
            signals_detected.append("question_marks_multiple")
        if sum(1 for c in msg if c.isupper()) / max(len(msg), 1) > 0.5 and len(msg) > 5:
            signals_detected.append("caps_usage")
        if response_time_sec > 30:
            signals_detected.append("long_wait")

        # Check for negative tone words
        neg_words = {"error", "wrong", "broken", "fail", "bad", "slow",
                     "again", "still", "not working", "frustrated", "annoyed"}
        if any(w in msg.lower() for w in neg_words):
            signals_detected.append("negative_tone")

        # Check for repeated requests
        if self.signal_history:
            last = self.signal_history[-1]
            if last.get("message_hash") == hash(msg.lower()[:50]):
                signals_detected.append("repeated_request")

        # Update frustration level
        delta = sum(_FRUSTRATION_SIGNALS.get(s, 0.1) for s in signals_detected)
        self.user_state.frustration_level = min(1.0,
            self.user_state.frustration_level + delta)

        # Natural decay
        time_since = time.time() - self.user_state.last_interaction if self.user_state.last_interaction else 0
        if time_since > 60:  # More than a minute since last interaction
            self.user_state.frustration_level = max(0,
                self.user_state.frustration_level - self.decay_rate * (time_since / 60))

        self.user_state.interaction_count += 1
        self.user_state.last_interaction = time.time()

        self.signal_history.append({
            "signals": signals_detected,
            "frustration": round(self.user_state.frustration_level, 3),
            "message_hash": hash(msg.lower()[:50]),
            "timestamp": time.time(),
        })
        if len(self.signal_history) > 200:
            self.signal_history = self.signal_history[-200:]

        if self.user_state.frustration_level >= self.alert_threshold:
            self._generate_intervention()

        return {
            "frustration": round(self.user_state.frustration_level, 3),
            "signals": signals_detected,
            "alert": self.user_state.frustration_level >= self.alert_threshold,
        }

    def predict_frustration(self) -> Dict[str, Any]:
        """Predict whether user will be frustrated soon."""
        # Trend analysis
        if len(self.signal_history) >= 3:
            recent = [s["frustration"] for s in self.signal_history[-5:]]
            trend = (recent[-1] - recent[0]) / max(len(recent), 1)
            predicted = self.user_state.frustration_level + trend * 3  # Project 3 interactions ahead

            prediction = {
                "current": round(self.user_state.frustration_level, 3),
                "predicted_next": round(min(1.0, max(0, predicted)), 3),
                "trend": "rising" if trend > 0.02 else "falling" if trend < -0.02 else "stable",
                "will_alert": predicted >= self.alert_threshold,
                "recommended_action": self._recommend_action(predicted),
            }
            self.predictions.append(prediction)
            if len(self.predictions) > 100:
                self.predictions = self.predictions[-100:]
            return prediction

        return {
            "current": round(self.user_state.frustration_level, 3),
            "predicted_next": round(self.user_state.frustration_level, 3),
            "trend": "insufficient_data",
            "will_alert": False,
            "recommended_action": "continue_normally",
        }

    def _recommend_action(self, predicted_frustration: float) -> str:
        if predicted_frustration >= 0.8:
            return "apologize_and_simplify"
        elif predicted_frustration >= 0.6:
            return "be_more_concise"
        elif predicted_frustration >= 0.4:
            return "clarify_proactively"
        elif predicted_frustration >= 0.2:
            return "maintain_quality"
        return "continue_normally"

    def _generate_intervention(self):
        """Generate a proactive intervention when frustration is high."""
        intervention = {
            "type": "frustration_prevention",
            "frustration_level": round(self.user_state.frustration_level, 3),
            "action": self._recommend_action(self.user_state.frustration_level),
            "timestamp": time.time(),
        }
        self.interventions.append(intervention)
        if len(self.interventions) > 100:
            self.interventions = self.interventions[-100:]

    def get_communication_style(self) -> Dict[str, Any]:
        """Get recommended communication adjustments based on user state."""
        f = self.user_state.frustration_level
        return {
            "verbosity": "concise" if f > 0.5 else "normal",
            "formality": "high" if f > 0.6 else "normal",
            "explanations": "minimal" if f > 0.7 else "moderate" if f > 0.3 else "detailed",
            "proactive_help": f < 0.3,
            "apology_appropriate": f > 0.6,
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "frustration_level": round(self.user_state.frustration_level, 3),
            "patience_estimate": round(self.user_state.patience_estimate, 2),
            "satisfaction_trend": round(self.user_state.satisfaction_trend, 2),
            "interactions": self.user_state.interaction_count,
            "interventions_made": len(self.interventions),
            "current_prediction": self.predict_frustration(),
            "communication_style": self.get_communication_style(),
        }

    def _save_state(self):
        try:
            state = {
                "user_state": asdict(self.user_state),
                "signal_history": self.signal_history[-50:],
                "interventions": self.interventions[-30:],
                "accuracy": self.accuracy,
            }
            (self.data_dir / "predictive_empathy_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Predictive empathy save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "predictive_empathy_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.accuracy = data.get("accuracy", 0.5)
                self.signal_history = data.get("signal_history", [])
                self.interventions = data.get("interventions", [])
                us = data.get("user_state", {})
                self.user_state = UserState(
                    **{f: us[f] for f in UserState.__dataclass_fields__ if f in us})
        except Exception as e:
            logger.debug(f"Predictive empathy load: {e}")
