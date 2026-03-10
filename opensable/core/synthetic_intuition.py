"""
Synthetic Intuition,  fast gut-feel pattern matching.

WORLD FIRST: The agent develops "hunches" by building compressed pattern
signatures from past experiences. Instead of full reasoning chains, it
can make instant probabilistic judgments,  System 1 thinking for AI.

Persistence: ``synthetic_intuition_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Hunch:
    id: str = ""
    pattern: str = ""
    prediction: str = ""
    confidence: float = 0.5
    times_right: int = 0
    times_wrong: int = 0
    created_tick: int = 0
    last_used: float = 0.0


class SyntheticIntuition:
    """Fast gut-feel pattern matching,  System 1 for AI."""

    def __init__(self, data_dir: Path, max_hunches: int = 300,
                 confidence_threshold: float = 0.6):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_hunches = max_hunches
        self.confidence_threshold = confidence_threshold

        self.hunches: Dict[str, Hunch] = {}
        self.gut_feelings: List[Dict[str, Any]] = []
        self.accuracy_history: List[float] = []
        self.total_snap_judgments: int = 0
        self.total_correct: int = 0

        self._load_state()

    def learn_pattern(self, situation: str, outcome: str, tick: int = 0):
        """Create or reinforce a hunch from observed pattern."""
        sig = self._signature(situation)
        if sig in self.hunches:
            h = self.hunches[sig]
            if outcome == h.prediction:
                h.times_right += 1
                h.confidence = min(0.99, h.confidence + 0.05)
            else:
                h.times_wrong += 1
                h.confidence = max(0.1, h.confidence - 0.08)
            h.last_used = time.time()
        else:
            self.hunches[sig] = Hunch(
                id=sig, pattern=situation[:200], prediction=outcome[:200],
                confidence=0.5, times_right=1, times_wrong=0,
                created_tick=tick, last_used=time.time(),
            )
            if len(self.hunches) > self.max_hunches:
                worst = min(self.hunches.values(), key=lambda h: h.confidence)
                del self.hunches[worst.id]

    def consult(self, situation: str) -> Optional[Dict[str, Any]]:
        """Ask gut feeling about a situation. Returns prediction or None."""
        sig = self._signature(situation)
        if sig in self.hunches:
            h = self.hunches[sig]
            if h.confidence >= self.confidence_threshold:
                self.total_snap_judgments += 1
                h.last_used = time.time()
                feeling = {
                    "prediction": h.prediction,
                    "confidence": h.confidence,
                    "basis": f"Seen {h.times_right + h.times_wrong} similar situations",
                }
                self.gut_feelings.append(feeling)
                if len(self.gut_feelings) > 100:
                    self.gut_feelings = self.gut_feelings[-100:]
                return feeling

        # Fuzzy matching,  check partial overlaps
        words = set(situation.lower().split())
        best_match = None
        best_overlap = 0
        for h in self.hunches.values():
            pattern_words = set(h.pattern.lower().split())
            overlap = len(words & pattern_words)
            if overlap > best_overlap and overlap >= 3 and h.confidence >= self.confidence_threshold:
                best_match = h
                best_overlap = overlap

        if best_match:
            self.total_snap_judgments += 1
            best_match.last_used = time.time()
            feeling = {
                "prediction": best_match.prediction,
                "confidence": best_match.confidence * 0.7,  # Lower for fuzzy
                "basis": f"Similar to: {best_match.pattern[:80]}",
            }
            self.gut_feelings.append(feeling)
            return feeling

        return None

    async def develop_intuition(self, llm, experiences: List[str], tick: int = 0):
        """LLM develops new hunches from a batch of experiences."""
        if not experiences:
            return
        exp_text = "\n".join(f"- {e}" for e in experiences[:10])
        prompt = (
            f"Analyze these experiences and extract 3 reusable 'gut feelings',  "
            f"quick pattern→outcome rules that could apply in future:\n{exp_text}\n\n"
            f"Return JSON array: [{{\"pattern\": \"...\", \"prediction\": \"...\", \"confidence\": 0.X}}]"
        )
        try:
            resp = await llm.chat_raw(prompt, max_tokens=500)
            import re
            m = re.search(r'\[.*\]', resp, re.DOTALL)
            if m:
                items = json.loads(m.group())
                for item in items[:3]:
                    self.learn_pattern(item["pattern"], item["prediction"], tick)
        except Exception as e:
            logger.debug(f"Intuition development failed: {e}")

    def feedback(self, situation: str, was_correct: bool):
        """Record whether a snap judgment was correct."""
        sig = self._signature(situation)
        if sig in self.hunches:
            h = self.hunches[sig]
            if was_correct:
                h.times_right += 1
                h.confidence = min(0.99, h.confidence + 0.03)
                self.total_correct += 1
            else:
                h.times_wrong += 1
                h.confidence = max(0.1, h.confidence - 0.05)
        if self.total_snap_judgments > 0:
            self.accuracy_history.append(self.total_correct / self.total_snap_judgments)
            if len(self.accuracy_history) > 100:
                self.accuracy_history = self.accuracy_history[-100:]

    def get_stats(self) -> Dict[str, Any]:
        high_conf = [h for h in self.hunches.values() if h.confidence >= 0.7]
        return {
            "total_hunches": len(self.hunches),
            "high_confidence": len(high_conf),
            "snap_judgments": self.total_snap_judgments,
            "accuracy": round(self.total_correct / max(1, self.total_snap_judgments), 3),
            "recent_feelings": self.gut_feelings[-3:],
            "strongest_hunches": sorted(
                [{"pattern": h.pattern[:60], "confidence": round(h.confidence, 2)}
                 for h in self.hunches.values()],
                key=lambda x: x["confidence"], reverse=True
            )[:5],
        }

    def _signature(self, text: str) -> str:
        normalized = " ".join(sorted(text.lower().split()))
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _save_state(self):
        try:
            state = {
                "hunches": {k: asdict(v) for k, v in self.hunches.items()},
                "total_snap_judgments": self.total_snap_judgments,
                "total_correct": self.total_correct,
                "accuracy_history": self.accuracy_history[-50:],
            }
            (self.data_dir / "synthetic_intuition_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Synthetic intuition save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "synthetic_intuition_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_snap_judgments = data.get("total_snap_judgments", 0)
                self.total_correct = data.get("total_correct", 0)
                self.accuracy_history = data.get("accuracy_history", [])
                for k, v in data.get("hunches", {}).items():
                    self.hunches[k] = Hunch(**{f: v[f] for f in Hunch.__dataclass_fields__ if f in v})
        except Exception as e:
            logger.debug(f"Synthetic intuition load failed: {e}")
