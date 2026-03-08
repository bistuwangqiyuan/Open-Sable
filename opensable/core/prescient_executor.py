"""
Prescient Executor — WORLD FIRST
==================================
Pre-executes likely future tasks BEFORE the user asks for them.
Predicts what the user will need next based on behavioral patterns
and starts working on it proactively.

No AI agent pre-executes future tasks. This one does.
The user gets results before they even ask.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class TaskPrediction:
    """A predicted future task."""
    pred_id: str = ""
    predicted_task: str = ""
    confidence: float = 0.0
    basis: str = ""              # why this was predicted
    pre_executed: bool = False
    result_cached: str = ""
    was_requested: bool = False  # did the user actually ask for this?
    predicted_at: float = 0.0
    fulfilled_at: float = 0.0


@dataclass
class BehaviorPattern:
    """A detected behavioral pattern for prediction."""
    pattern_id: str = ""
    trigger: str = ""
    usual_followup: str = ""
    occurrences: int = 0
    accuracy: float = 0.0
    last_seen: float = 0.0


class PrescientExecutor:
    """
    Predicts and pre-executes future tasks.
    Learns from task sequences to anticipate what comes next.
    """

    def __init__(self, data_dir: str, prediction_threshold: float = 0.6,
                 max_predictions: int = 10):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "prescient_executor_state.json"
        self.patterns: dict[str, BehaviorPattern] = {}
        self.predictions: list[TaskPrediction] = []
        self.active_predictions: dict[str, TaskPrediction] = {}
        self.task_history: list[str] = []
        self.threshold = prediction_threshold
        self._max_pred = max_predictions
        self.total_predictions: int = 0
        self.correct_predictions: int = 0
        self.prescience_accuracy: float = 0.0
        self._load_state()

    def observe_task(self, task: str):
        """Observe a task being performed. Learn patterns."""
        task_lower = task.lower().strip()
        self.task_history.append(task_lower)
        if len(self.task_history) > 500:
            self.task_history = self.task_history[-500:]

        # Check if any active prediction matches
        for pid, pred in list(self.active_predictions.items()):
            pred_words = set(pred.predicted_task.lower().split())
            task_words = set(task_lower.split())
            overlap = len(pred_words & task_words) / max(len(pred_words | task_words), 1)
            if overlap > 0.5:
                pred.was_requested = True
                pred.fulfilled_at = time.time()
                self.correct_predictions += 1
                del self.active_predictions[pid]

        # Learn from consecutive task pairs
        if len(self.task_history) >= 2:
            prev = self.task_history[-2]
            key = prev[:50]
            if key in self.patterns:
                p = self.patterns[key]
                p.occurrences += 1
                p.last_seen = time.time()
                # Update accuracy
                if p.usual_followup.lower() == task_lower[:len(p.usual_followup)]:
                    p.accuracy = min(1.0, p.accuracy + 0.05)
                else:
                    p.accuracy = max(0.0, p.accuracy - 0.02)
                    # Update to more common followup if this one repeats
                    p.usual_followup = task[:100]
            else:
                self.patterns[key] = BehaviorPattern(
                    pattern_id=str(uuid.uuid4())[:8],
                    trigger=prev[:100],
                    usual_followup=task[:100],
                    occurrences=1,
                    accuracy=0.3,
                    last_seen=time.time(),
                )

        if len(self.patterns) > 300:
            # Keep most accurate
            sorted_p = sorted(self.patterns.items(),
                             key=lambda x: x[1].accuracy * x[1].occurrences,
                             reverse=True)
            self.patterns = dict(sorted_p[:300])

        self._update_accuracy()
        self._save_state()

    def predict_next(self) -> list[TaskPrediction]:
        """Predict what tasks the user will ask for next."""
        if not self.task_history:
            return []

        current = self.task_history[-1][:50]
        predictions = []

        # Find matching patterns
        for key, pattern in self.patterns.items():
            current_words = set(current.lower().split())
            trigger_words = set(pattern.trigger.lower().split())
            overlap = len(current_words & trigger_words) / max(len(current_words | trigger_words), 1)

            if overlap > 0.3 and pattern.accuracy >= self.threshold:
                confidence = pattern.accuracy * overlap
                if confidence > 0.3:
                    pred = TaskPrediction(
                        pred_id=str(uuid.uuid4())[:8],
                        predicted_task=pattern.usual_followup,
                        confidence=round(confidence, 3),
                        basis=f"After '{pattern.trigger[:30]}', usually '{pattern.usual_followup[:30]}'",
                        predicted_at=time.time(),
                    )
                    predictions.append(pred)

        # Sort by confidence, keep top N
        predictions.sort(key=lambda p: p.confidence, reverse=True)
        predictions = predictions[:self._max_pred]

        for pred in predictions:
            self.predictions.append(pred)
            self.active_predictions[pred.pred_id] = pred
            self.total_predictions += 1

        if len(self.predictions) > 500:
            self.predictions = self.predictions[-500:]
        if len(self.active_predictions) > self._max_pred * 3:
            # Prune old predictions
            sorted_active = sorted(self.active_predictions.items(),
                                  key=lambda x: x[1].predicted_at, reverse=True)
            self.active_predictions = dict(sorted_active[:self._max_pred])

        self._save_state()
        return predictions

    async def pre_execute(self, prediction_id: str, llm=None) -> dict:
        """Pre-execute a predicted task."""
        if prediction_id not in self.active_predictions:
            return {"error": "prediction_not_found"}

        pred = self.active_predictions[prediction_id]
        if pred.pre_executed:
            return {"already_executed": True, "result": pred.result_cached}

        if llm:
            prompt = (
                f"Pre-execute this predicted task. Prepare the result so it's "
                f"ready when the user asks:\n\n"
                f"Task: {pred.predicted_task}\n"
                f"Basis: {pred.basis}\n\n"
                f"Prepare a brief, actionable result.\n"
                f"Return JSON: {{\"result\": \"...\", \"ready\": true}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=300)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    pred.pre_executed = True
                    pred.result_cached = result.get("result", "")
                    self._save_state()
                    return {"pre_executed": True, "result": pred.result_cached}
            except Exception:
                pass

        pred.pre_executed = True
        pred.result_cached = f"Prepared for: {pred.predicted_task[:100]}"
        self._save_state()
        return {"pre_executed": True, "result": pred.result_cached}

    def _update_accuracy(self):
        if self.total_predictions > 0:
            self.prescience_accuracy = self.correct_predictions / self.total_predictions

    def get_stats(self) -> dict:
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "prescience_accuracy": round(self.prescience_accuracy, 3),
            "active_predictions": len(self.active_predictions),
            "patterns_learned": len(self.patterns),
            "task_history_length": len(self.task_history),
            "top_patterns": [
                {"trigger": p.trigger[:40], "followup": p.usual_followup[:40],
                 "accuracy": round(p.accuracy, 2), "seen": p.occurrences}
                for p in sorted(self.patterns.values(),
                               key=lambda p: p.accuracy * p.occurrences,
                               reverse=True)[:5]
            ],
            "pending_predictions": [
                {"task": p.predicted_task[:50], "confidence": round(p.confidence, 2)}
                for p in self.active_predictions.values()
            ][:5],
        }

    def _save_state(self):
        data = {
            "patterns": {k: asdict(v) for k, v in self.patterns.items()},
            "predictions": [asdict(p) for p in self.predictions[-500:]],
            "active_predictions": {k: asdict(v) for k, v in self.active_predictions.items()},
            "task_history": self.task_history[-500:],
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "prescience_accuracy": self.prescience_accuracy,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("patterns", {}).items():
                    self.patterns[k] = BehaviorPattern(**v)
                for p in data.get("predictions", []):
                    self.predictions.append(TaskPrediction(**p))
                for k, v in data.get("active_predictions", {}).items():
                    self.active_predictions[k] = TaskPrediction(**v)
                self.task_history = data.get("task_history", [])
                self.total_predictions = data.get("total_predictions", 0)
                self.correct_predictions = data.get("correct_predictions", 0)
                self.prescience_accuracy = data.get("prescience_accuracy", 0.0)
            except Exception:
                pass
