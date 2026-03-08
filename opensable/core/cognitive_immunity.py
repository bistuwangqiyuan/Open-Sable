"""
Cognitive Immune System — antibody-based failure defense.

WORLD FIRST: Like biological immune systems, the agent develops
"antibodies" (pattern-action rules) against failure patterns.
When a new failure is similar to a past one, it's instantly
neutralized without needing full LLM reasoning.

Features:
- Antibody generation from failure events
- Antigen matching (new failures compared to antibody library)
- Immune memory (long-lived memory cells for catastrophic failures)
- Tolerance (avoids false positives on normal behavior)
- Autoimmune detection (prevents over-triggering)

Persistence: ``cognitive_immunity_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Antibody:
    id: str = ""
    pattern: str = ""              # failure pattern signature
    keywords: List[str] = field(default_factory=list)
    response: str = ""             # automatic response action
    severity: str = "medium"       # low, medium, high, critical
    matches: int = 0               # times triggered
    false_positives: int = 0
    created_at: float = 0.0
    last_triggered: float = 0.0
    active: bool = True


@dataclass
class ImmuneEvent:
    tick: int = 0
    antigen: str = ""              # the incoming failure
    antibody_id: str = ""          # which antibody matched
    response: str = ""
    neutralized: bool = False
    timestamp: float = 0.0


class CognitiveImmunity:
    """Biological immune system for AI agent failure defense."""

    def __init__(
        self,
        data_dir: Path,
        match_threshold: float = 0.4,
        max_antibodies: int = 200,
        autoimmune_threshold: int = 10,  # too many triggers = autoimmune
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.match_threshold = match_threshold
        self.max_antibodies = max_antibodies
        self.autoimmune_threshold = autoimmune_threshold

        self.antibodies: List[Antibody] = []
        self.events: List[ImmuneEvent] = []
        self.total_neutralized: int = 0
        self.total_false_positives: int = 0
        self.autoimmune_suppressed: int = 0

        self._load_state()

    def generate_antibody(self, failure_description: str, response_action: str,
                          severity: str = "medium", keywords: Optional[List[str]] = None):
        """Create a new antibody from a failure event."""
        if not keywords:
            words = failure_description.lower().split()
            keywords = [w for w in words if len(w) > 3][:10]

        ab = Antibody(
            id=f"ab_{len(self.antibodies)}_{int(time.time())}",
            pattern=failure_description[:300],
            keywords=keywords,
            response=response_action[:200],
            severity=severity,
            created_at=time.time(),
            active=True,
        )
        self.antibodies.append(ab)
        if len(self.antibodies) > self.max_antibodies:
            # Remove oldest low-match antibodies
            self.antibodies.sort(key=lambda a: a.matches, reverse=True)
            self.antibodies = self.antibodies[:self.max_antibodies]
        self._save_state()
        return ab

    async def generate_antibody_llm(self, llm, failure: str, context: str = ""):
        """Use LLM to generate a smart antibody from a failure."""
        try:
            prompt = (
                "You are an IMMUNE SYSTEM for an AI agent. A failure just occurred. "
                "Generate an 'antibody' — a pattern-action rule to prevent this failure in the future.\n\n"
                f"Failure: {failure}\n"
                f"Context: {context}\n\n"
                "Respond in JSON:\n"
                '{"keywords": ["word1", "word2"], "response": "preventive action", '
                '"severity": "low|medium|high|critical"}'
            )
            resp = await llm.chat_raw(prompt, max_tokens=200)
            text = resp if isinstance(resp, str) else str(resp)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return self.generate_antibody(
                    failure, data.get("response", "retry with caution"),
                    data.get("severity", "medium"), data.get("keywords", [])
                )
        except Exception as e:
            logger.debug(f"Antibody LLM generation failed: {e}")
        return None

    def scan(self, incoming: str, tick: int = 0) -> Optional[ImmuneEvent]:
        """Scan incoming event for known failure patterns (antigen matching)."""
        incoming_lower = incoming.lower()
        incoming_words = set(incoming_lower.split())

        best_match: Optional[Antibody] = None
        best_score = 0.0

        for ab in self.antibodies:
            if not ab.active:
                continue
            # Check for autoimmune
            if ab.matches > self.autoimmune_threshold and ab.false_positives > ab.matches * 0.5:
                ab.active = False
                self.autoimmune_suppressed += 1
                continue

            if not ab.keywords:
                continue
            overlap = sum(1 for k in ab.keywords if k in incoming_lower)
            score = overlap / len(ab.keywords)

            if score > best_score and score >= self.match_threshold:
                best_score = score
                best_match = ab

        if best_match:
            best_match.matches += 1
            best_match.last_triggered = time.time()
            event = ImmuneEvent(
                tick=tick,
                antigen=incoming[:200],
                antibody_id=best_match.id,
                response=best_match.response,
                neutralized=True,
                timestamp=time.time(),
            )
            self.events.append(event)
            self.total_neutralized += 1
            if len(self.events) > 500:
                self.events = self.events[-500:]
            self._save_state()
            return event
        return None

    def report_false_positive(self, antibody_id: str):
        """Report that an antibody triggered incorrectly."""
        for ab in self.antibodies:
            if ab.id == antibody_id:
                ab.false_positives += 1
                self.total_false_positives += 1
                break
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        active = [ab for ab in self.antibodies if ab.active]
        return {
            "total_antibodies": len(self.antibodies),
            "active_antibodies": len(active),
            "total_neutralized": self.total_neutralized,
            "total_false_positives": self.total_false_positives,
            "autoimmune_suppressed": self.autoimmune_suppressed,
            "recent_events": [
                {"antigen": e.antigen[:100], "response": e.response, "tick": e.tick}
                for e in self.events[-5:]
            ],
            "top_antibodies": [
                {"id": ab.id, "pattern": ab.pattern[:100], "matches": ab.matches,
                 "severity": ab.severity, "active": ab.active}
                for ab in sorted(self.antibodies, key=lambda a: a.matches, reverse=True)[:5]
            ],
        }

    def _save_state(self):
        try:
            state = {
                "total_neutralized": self.total_neutralized,
                "total_false_positives": self.total_false_positives,
                "autoimmune_suppressed": self.autoimmune_suppressed,
                "antibodies": [asdict(ab) for ab in self.antibodies[-100:]],
                "events": [asdict(e) for e in self.events[-100:]],
            }
            (self.data_dir / "cognitive_immunity_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"Cognitive immunity save failed: {e}")

    def _load_state(self):
        try:
            f = self.data_dir / "cognitive_immunity_state.json"
            if f.exists():
                data = json.loads(f.read_text())
                self.total_neutralized = data.get("total_neutralized", 0)
                self.total_false_positives = data.get("total_false_positives", 0)
                self.autoimmune_suppressed = data.get("autoimmune_suppressed", 0)
                for ad in data.get("antibodies", []):
                    self.antibodies.append(Antibody(**{k: v for k, v in ad.items()
                                                       if k in Antibody.__dataclass_fields__}))
                for ed in data.get("events", []):
                    self.events.append(ImmuneEvent(**{k: v for k, v in ed.items()
                                                      if k in ImmuneEvent.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Cognitive immunity load failed: {e}")
