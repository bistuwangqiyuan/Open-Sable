"""
Predictive World Model — anticipatory reasoning.

Maintains a lightweight world state model and uses LLM to predict
likely future events, enabling the agent to proactively prepare
instead of being purely reactive.

Key ideas:
  - **State tracking**: maintains key-value world state observations
  - **LLM forecasting**: predicts future events/changes given current state + history
  - **Proactive preparation**: generates preparation tasks for predicted events
  - **Accuracy tracking**: scores past predictions against actual outcomes

Persistence: ``world_predictor_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PREDICT_SYSTEM = """You are a predictive world model for an autonomous AI agent.
Given the agent's current world state observations and recent history,
predict 2-5 events likely to happen in the near future.

Output ONLY valid JSON — an array of objects:
[
  {
    "prediction": "what will likely happen (5-20 words)",
    "timeframe": "next_tick|next_hour|next_day|next_week",
    "confidence": 0.1 to 1.0,
    "category": "system|user|environment|task|social",
    "preparation": "what the agent should do to prepare (optional, 5-20 words)"
  }
]

Rules:
- Be specific and actionable, not vague
- Confidence should reflect actual certainty
- Higher confidence for patterns that repeat regularly
- preparation: only include if the agent can actually do something useful
- If state is too unclear to predict anything, return []"""


@dataclass
class WorldObservation:
    """A key-value observation about world state."""

    key: str
    value: str
    tick: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Prediction:
    """A prediction about a future event."""

    prediction_id: str
    description: str
    timeframe: str
    confidence: float
    category: str
    preparation: str
    tick_created: int
    status: str = "pending"  # pending, correct, incorrect, expired
    actual_outcome: str = ""
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class WorldPredictor:
    """Maintains world state and predicts future events."""

    def __init__(
        self,
        data_dir: Path,
        predict_interval: int = 25,
        max_observations: int = 100,
        max_predictions: int = 200,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "world_predictor_state.json"

        self._predict_interval = predict_interval
        self._max_observations = max_observations
        self._max_predictions = max_predictions

        self._observations: Dict[str, WorldObservation] = {}
        self._predictions: Dict[str, Prediction] = {}
        self._last_predict_tick: int = 0
        self._total_predictions: int = 0
        self._correct_predictions: int = 0
        self._incorrect_predictions: int = 0

        self._load_state()

    # ── Observe ───────────────────────────────────────────────────────────────

    def observe(self, key: str, value: str, tick: int):
        """Record a world state observation."""
        self._observations[key] = WorldObservation(key=key, value=value, tick=tick)

        # Prune old observations
        if len(self._observations) > self._max_observations:
            sorted_obs = sorted(
                self._observations.items(),
                key=lambda x: x[1].tick,
            )
            for old_key, _ in sorted_obs[:len(sorted_obs) - self._max_observations]:
                del self._observations[old_key]

    def observe_from_tasks(self, completed_tasks: List[Dict], tick: int):
        """Extract observations from completed tasks."""
        if not completed_tasks:
            return

        # Task completion rate
        recent = completed_tasks[-20:]
        success = sum(1 for t in recent if t.get("status") == "done")
        total = len(recent)
        self.observe("task_success_rate", f"{success}/{total} ({success/max(total,1)*100:.0f}%)", tick)

        # Common task types
        from collections import Counter
        types = Counter(t.get("type", "unknown") for t in recent)
        self.observe("common_task_types", str(dict(types.most_common(5))), tick)

        # Error patterns
        errors = [t.get("result", "")[:80] for t in recent if t.get("status") == "error"]
        if errors:
            self.observe("recent_errors", "; ".join(errors[:3]), tick)

        # Queue pressure
        self.observe("observation_tick", str(tick), tick)

    # ── Predict ───────────────────────────────────────────────────────────────

    async def predict(
        self,
        llm: Any,
        tick: int,
    ) -> List[Prediction]:
        """Generate predictions about future events."""
        if tick - self._last_predict_tick < self._predict_interval:
            return []

        self._last_predict_tick = tick

        if not self._observations:
            return []

        try:
            # Build world state summary
            state_parts = []
            for obs in sorted(self._observations.values(), key=lambda o: -o.tick)[:30]:
                state_parts.append(f"- {obs.key}: {obs.value}")
            state_text = "\n".join(state_parts)

            # Include recent predictions for context
            recent_preds = []
            for p in sorted(self._predictions.values(), key=lambda x: -x.tick_created)[:5]:
                recent_preds.append(
                    f"- [{p.status}] {p.description} (confidence={p.confidence:.1f})"
                )
            pred_context = "\n".join(recent_preds) if recent_preds else "None yet."

            messages = [
                {"role": "system", "content": _PREDICT_SYSTEM},
                {"role": "user", "content": (
                    f"Current world state:\n{state_text}\n\n"
                    f"Recent predictions:\n{pred_context}"
                )},
            ]

            result = await llm.invoke_with_tools(messages, [])
            text = result.get("text", "") if isinstance(result, dict) else str(result)

            import re
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if m:
                    text = m.group(1).strip()

            start = text.find("[")
            end = text.rfind("]")
            if start < 0 or end < 0:
                return []

            items = json.loads(text[start:end + 1])
            new_predictions = []

            import hashlib
            for item in items:
                if not isinstance(item, dict):
                    continue
                desc = str(item.get("prediction", "")).strip()
                if not desc:
                    continue

                pred_id = f"pred_{hashlib.md5(f'{desc}_{tick}'.encode()).hexdigest()[:8]}"

                pred = Prediction(
                    prediction_id=pred_id,
                    description=desc,
                    timeframe=str(item.get("timeframe", "next_day")),
                    confidence=float(item.get("confidence", 0.5)),
                    category=str(item.get("category", "environment")),
                    preparation=str(item.get("preparation", "")),
                    tick_created=tick,
                )

                self._predictions[pred_id] = pred
                new_predictions.append(pred)
                self._total_predictions += 1

            # Expire old predictions
            self._expire_predictions(tick)

            # Prune
            if len(self._predictions) > self._max_predictions:
                sorted_preds = sorted(
                    self._predictions.items(),
                    key=lambda x: x[1].tick_created,
                )
                for old_key, _ in sorted_preds[:len(sorted_preds) - self._max_predictions]:
                    del self._predictions[old_key]

            self._save_state()
            return new_predictions

        except Exception as e:
            logger.debug(f"Prediction failed: {e}")
            return []

    def _expire_predictions(self, current_tick: int):
        """Expire predictions that have passed their timeframe."""
        timeframe_ticks = {
            "next_tick": 1,
            "next_hour": 60,
            "next_day": 1440,
            "next_week": 10080,
        }

        for pred in self._predictions.values():
            if pred.status != "pending":
                continue
            max_ticks = timeframe_ticks.get(pred.timeframe, 1440)
            if current_tick - pred.tick_created > max_ticks:
                pred.status = "expired"

    def resolve_prediction(self, prediction_id: str, correct: bool, outcome: str = ""):
        """Mark a prediction as correct or incorrect."""
        if prediction_id in self._predictions:
            pred = self._predictions[prediction_id]
            pred.status = "correct" if correct else "incorrect"
            pred.actual_outcome = outcome[:200]
            if correct:
                self._correct_predictions += 1
            else:
                self._incorrect_predictions += 1
            self._save_state()

    def get_pending_preparations(self) -> List[Dict[str, str]]:
        """Return preparation tasks for high-confidence pending predictions."""
        preps = []
        for pred in self._predictions.values():
            if (
                pred.status == "pending"
                and pred.preparation
                and pred.confidence > 0.5
            ):
                preps.append({
                    "prediction": pred.description,
                    "preparation": pred.preparation,
                    "confidence": pred.confidence,
                    "timeframe": pred.timeframe,
                })
        preps.sort(key=lambda p: -p["confidence"])
        return preps[:5]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        total_resolved = self._correct_predictions + self._incorrect_predictions
        accuracy = (
            self._correct_predictions / total_resolved
            if total_resolved > 0
            else 0.0
        )

        pending = [p for p in self._predictions.values() if p.status == "pending"]
        pending.sort(key=lambda p: -p.confidence)

        return {
            "total_observations": len(self._observations),
            "total_predictions": self._total_predictions,
            "correct_predictions": self._correct_predictions,
            "incorrect_predictions": self._incorrect_predictions,
            "accuracy": round(accuracy, 3),
            "pending_predictions": len(pending),
            "top_pending": [
                {
                    "prediction": p.description[:100],
                    "confidence": round(p.confidence, 2),
                    "timeframe": p.timeframe,
                    "category": p.category,
                    "preparation": p.preparation[:80] if p.preparation else "",
                }
                for p in pending[:6]
            ],
            "preparations": self.get_pending_preparations(),
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "observations": {k: asdict(v) for k, v in self._observations.items()},
                "predictions": {k: asdict(v) for k, v in self._predictions.items()},
                "last_predict_tick": self._last_predict_tick,
                "total_predictions": self._total_predictions,
                "correct_predictions": self._correct_predictions,
                "incorrect_predictions": self._incorrect_predictions,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"World predictor save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._last_predict_tick = data.get("last_predict_tick", 0)
                self._total_predictions = data.get("total_predictions", 0)
                self._correct_predictions = data.get("correct_predictions", 0)
                self._incorrect_predictions = data.get("incorrect_predictions", 0)

                for key, odata in data.get("observations", {}).items():
                    self._observations[key] = WorldObservation(**odata)

                for pid, pdata in data.get("predictions", {}).items():
                    self._predictions[pid] = Prediction(**pdata)
        except Exception as e:
            logger.debug(f"World predictor load failed: {e}")
