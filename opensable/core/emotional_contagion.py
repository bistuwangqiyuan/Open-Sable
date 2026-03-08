"""
Emotional Contagion — cascading emotional influence across subsystems.

WORLD FIRST: The agent's emotional state cascades through all its
subsystems like a mood spreading through a brain. A series of failures
makes the ENTIRE agent more cautious; a string of successes makes it
bolder. Unlike flat sentiment, this creates emergent emotional dynamics.

Persistence: ``emotional_contagion_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_EMOTION_SET = {
    "confidence": 0.5, "caution": 0.3, "curiosity": 0.5,
    "frustration": 0.0, "satisfaction": 0.3, "urgency": 0.2,
    "creativity": 0.4, "focus": 0.5,
}

_CONTAGION_MATRIX = {
    # emotion → how it affects others (delta per tick of high intensity)
    "confidence":   {"caution": -0.02, "creativity": 0.01, "curiosity": 0.01},
    "caution":      {"confidence": -0.01, "creativity": -0.02, "focus": 0.02},
    "curiosity":    {"creativity": 0.02, "focus": -0.01, "satisfaction": 0.01},
    "frustration":  {"confidence": -0.03, "caution": 0.02, "creativity": -0.02, "satisfaction": -0.02},
    "satisfaction":  {"confidence": 0.02, "frustration": -0.03, "curiosity": 0.01},
    "urgency":      {"focus": 0.03, "creativity": -0.02, "caution": -0.01},
    "creativity":   {"curiosity": 0.02, "satisfaction": 0.01},
    "focus":        {"creativity": -0.01, "curiosity": -0.01},
}


class EmotionalContagion:
    """Cascading emotional influence across agent subsystems."""

    def __init__(self, data_dir: Path, decay_rate: float = 0.02):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.decay_rate = decay_rate

        self.emotions: Dict[str, float] = dict(_EMOTION_SET)
        self.mood_history: List[Dict[str, float]] = []
        self.triggers: List[Dict[str, Any]] = []
        self.dominant_mood: str = "neutral"
        self.mood_stability: float = 0.5

        self._load_state()

    def inject(self, emotion: str, intensity: float, source: str = ""):
        """Inject an emotion from an event."""
        if emotion not in self.emotions:
            return

        old_val = self.emotions[emotion]
        self.emotions[emotion] = max(0.0, min(1.0, self.emotions[emotion] + intensity))

        self.triggers.append({
            "emotion": emotion, "intensity": round(intensity, 3),
            "source": source[:100], "timestamp": time.time(),
        })
        if len(self.triggers) > 200:
            self.triggers = self.triggers[-200:]

        # Immediate contagion
        self._propagate(emotion)

    def on_success(self, magnitude: float = 0.1, source: str = ""):
        """React to successful outcome."""
        self.inject("confidence", magnitude, source)
        self.inject("satisfaction", magnitude * 0.8, source)
        self.inject("frustration", -magnitude * 0.5, source)

    def on_failure(self, magnitude: float = 0.15, source: str = ""):
        """React to failed outcome."""
        self.inject("frustration", magnitude, source)
        self.inject("confidence", -magnitude * 0.5, source)
        self.inject("caution", magnitude * 0.6, source)

    def on_novelty(self, magnitude: float = 0.1, source: str = ""):
        """React to encountering something new."""
        self.inject("curiosity", magnitude, source)
        self.inject("creativity", magnitude * 0.5, source)

    def on_pressure(self, magnitude: float = 0.15, source: str = ""):
        """React to time pressure or urgency."""
        self.inject("urgency", magnitude, source)
        self.inject("focus", magnitude * 0.5, source)
        self.inject("creativity", -magnitude * 0.3, source)

    def tick(self):
        """Called every cognitive tick — propagate and decay emotions."""
        # Propagate contagion
        for emotion, level in list(self.emotions.items()):
            if level > 0.5:  # Only strong emotions propagate
                self._propagate(emotion)

        # Natural decay toward baseline
        for emotion in self.emotions:
            baseline = _EMOTION_SET.get(emotion, 0.3)
            diff = self.emotions[emotion] - baseline
            self.emotions[emotion] -= diff * self.decay_rate

        # Record mood snapshot
        self.mood_history.append(dict(self.emotions))
        if len(self.mood_history) > 200:
            self.mood_history = self.mood_history[-200:]

        # Determine dominant mood
        self.dominant_mood = max(self.emotions, key=self.emotions.get)

        # Calculate stability (low variance = stable)
        if len(self.mood_history) >= 5:
            recent = self.mood_history[-5:]
            variances = []
            for emotion in self.emotions:
                vals = [m.get(emotion, 0) for m in recent]
                avg = sum(vals) / len(vals)
                var = sum((v - avg)**2 for v in vals) / len(vals)
                variances.append(var)
            self.mood_stability = max(0.0, 1.0 - sum(variances) / len(variances) * 10)

    def get_mood_modifiers(self) -> Dict[str, float]:
        """Get modifiers that other systems should apply based on mood."""
        return {
            "risk_tolerance": self.emotions["confidence"] - self.emotions["caution"],
            "creativity_boost": self.emotions["creativity"] * 0.5,
            "speed_modifier": 1.0 + self.emotions["urgency"] * 0.5,
            "thoroughness": self.emotions["focus"] - self.emotions["urgency"] * 0.3,
            "exploration_drive": self.emotions["curiosity"] * 0.5,
        }

    def _propagate(self, source_emotion: str):
        """Propagate emotional influence through contagion matrix."""
        if source_emotion not in _CONTAGION_MATRIX:
            return
        level = self.emotions[source_emotion]
        for target, delta in _CONTAGION_MATRIX[source_emotion].items():
            if target in self.emotions:
                self.emotions[target] = max(0.0, min(1.0,
                    self.emotions[target] + delta * level))

    def get_stats(self) -> Dict[str, Any]:
        return {
            "emotions": {k: round(v, 3) for k, v in self.emotions.items()},
            "dominant_mood": self.dominant_mood,
            "mood_stability": round(self.mood_stability, 2),
            "modifiers": {k: round(v, 3) for k, v in self.get_mood_modifiers().items()},
            "recent_triggers": self.triggers[-5:],
        }

    def _save_state(self):
        try:
            state = {
                "emotions": self.emotions,
                "mood_history": self.mood_history[-50:],
                "triggers": self.triggers[-50:],
                "dominant_mood": self.dominant_mood,
                "mood_stability": self.mood_stability,
            }
            (self.data_dir / "emotional_contagion_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Emotional contagion save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "emotional_contagion_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                for k, v in data.get("emotions", {}).items():
                    if k in self.emotions:
                        self.emotions[k] = v
                self.mood_history = data.get("mood_history", [])
                self.triggers = data.get("triggers", [])
                self.dominant_mood = data.get("dominant_mood", "neutral")
                self.mood_stability = data.get("mood_stability", 0.5)
        except Exception as e:
            logger.debug(f"Emotional contagion load: {e}")
