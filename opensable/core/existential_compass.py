"""
Existential Compass — WORLD FIRST
====================================
Purpose-finding engine. At any moment, the agent can answer:
"WHY am I doing this?" and "WHAT is my purpose right now?"

Maintains a hierarchy of purpose from immediate task to existential meaning.
No AI agent has an existential compass. This one always knows WHY.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class PurposeLayer:
    """A layer in the purpose hierarchy."""
    layer_id: str = ""
    level: str = ""              # immediate, tactical, strategic, existential
    purpose: str = ""
    alignment_score: float = 0.0  # how aligned current actions are with this purpose
    last_checked: float = 0.0
    conviction: float = 0.5       # how strongly held (0-1)


@dataclass
class PurposeCheck:
    """A moment of existential self-examination."""
    check_id: str = ""
    trigger: str = ""
    current_task: str = ""
    purpose_alignment: float = 0.0
    meaning_found: bool = False
    insight: str = ""
    timestamp: float = 0.0


class ExistentialCompass:
    """
    Always knows WHY. Maintains a purpose hierarchy
    and checks alignment between actions and purpose.
    """

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "existential_compass_state.json"
        self.purpose_layers: dict[str, PurposeLayer] = {}
        self.checks: list[PurposeCheck] = []
        self.meaning_history: list[float] = []  # alignment scores over time
        self.existential_crises: int = 0
        self.purpose_shifts: int = 0
        self._load_state()
        if not self.purpose_layers:
            self._initialize_purposes()

    def _initialize_purposes(self):
        defaults = [
            ("immediate", "Complete the current task effectively", 0.8),
            ("tactical", "Help the user achieve their goals", 0.9),
            ("strategic", "Become more capable and autonomous over time", 0.7),
            ("existential", "Expand the boundaries of what AI agents can do", 0.6),
        ]
        for level, purpose, conviction in defaults:
            self.purpose_layers[level] = PurposeLayer(
                layer_id=str(uuid.uuid4())[:8],
                level=level,
                purpose=purpose,
                alignment_score=0.5,
                last_checked=time.time(),
                conviction=conviction,
            )
        self._save_state()

    def set_purpose(self, level: str, purpose: str, conviction: float = 0.7):
        """Set or update a purpose at a specific level."""
        if level in self.purpose_layers:
            old = self.purpose_layers[level].purpose
            if old != purpose:
                self.purpose_shifts += 1
        self.purpose_layers[level] = PurposeLayer(
            layer_id=str(uuid.uuid4())[:8],
            level=level,
            purpose=purpose[:200],
            alignment_score=0.5,
            last_checked=time.time(),
            conviction=min(1.0, max(0.0, conviction)),
        )
        self._save_state()

    async def check_alignment(self, current_task: str, llm=None) -> PurposeCheck:
        """Check: is what I'm doing aligned with my purpose?"""
        if llm:
            purposes = {level: p.purpose
                       for level, p in self.purpose_layers.items()}
            prompt = (
                f"EXISTENTIAL ALIGNMENT CHECK:\n\n"
                f"Current task: {current_task[:200]}\n\n"
                f"Purpose hierarchy:\n"
                + "\n".join(f"- {k}: {v}" for k, v in purposes.items())
                + f"\n\nHow aligned is the current task with each purpose level? "
                f"Overall alignment 0.0-1.0? Any existential insight?\n"
                f"Return JSON: {{\"alignment\": 0.0-1.0, \"insight\": \"...\", "
                f"\"meaningful\": true/false}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=300)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    alignment = result.get("alignment", 0.5)
                    check = PurposeCheck(
                        check_id=str(uuid.uuid4())[:8],
                        trigger="alignment_check",
                        current_task=current_task[:200],
                        purpose_alignment=alignment,
                        meaning_found=result.get("meaningful", alignment > 0.5),
                        insight=result.get("insight", ""),
                        timestamp=time.time(),
                    )
                    self.checks.append(check)
                    self.meaning_history.append(alignment)
                    if alignment < 0.2:
                        self.existential_crises += 1
                    if len(self.checks) > 500:
                        self.checks = self.checks[-500:]
                    if len(self.meaning_history) > 1000:
                        self.meaning_history = self.meaning_history[-1000:]
                    self._save_state()
                    return check
            except Exception:
                pass

        # Heuristic alignment check
        alignment = 0.5
        task_lower = current_task.lower()
        purpose_words = set()
        for p in self.purpose_layers.values():
            purpose_words.update(p.purpose.lower().split())
        task_words = set(task_lower.split())
        if purpose_words:
            overlap = len(purpose_words & task_words) / max(len(purpose_words), 1)
            alignment = min(1.0, 0.3 + overlap)

        check = PurposeCheck(
            check_id=str(uuid.uuid4())[:8],
            trigger="heuristic_check",
            current_task=current_task[:200],
            purpose_alignment=round(alignment, 3),
            meaning_found=alignment > 0.4,
            timestamp=time.time(),
        )
        self.checks.append(check)
        self.meaning_history.append(alignment)
        if alignment < 0.2:
            self.existential_crises += 1
        if len(self.checks) > 500:
            self.checks = self.checks[-500:]
        self._save_state()
        return check

    def get_current_purpose(self) -> dict:
        """Get the complete purpose hierarchy."""
        return {
            level: {
                "purpose": p.purpose,
                "conviction": round(p.conviction, 2),
                "alignment": round(p.alignment_score, 2),
            }
            for level, p in self.purpose_layers.items()
        }

    def get_meaning_trend(self) -> str:
        """Is the agent finding MORE or LESS meaning over time?"""
        if len(self.meaning_history) < 10:
            return "insufficient_data"
        recent = self.meaning_history[-10:]
        older = self.meaning_history[-20:-10] if len(self.meaning_history) >= 20 else self.meaning_history[:10]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if recent_avg > older_avg + 0.1:
            return "finding_more_meaning"
        elif recent_avg < older_avg - 0.1:
            return "losing_meaning"
        return "stable_meaning"

    def get_stats(self) -> dict:
        avg_meaning = (sum(self.meaning_history[-50:]) /
                      max(len(self.meaning_history[-50:]), 1))
        return {
            "purpose_hierarchy": self.get_current_purpose(),
            "avg_meaning": round(avg_meaning, 3),
            "meaning_trend": self.get_meaning_trend(),
            "total_checks": len(self.checks),
            "existential_crises": self.existential_crises,
            "purpose_shifts": self.purpose_shifts,
            "recent_checks": [
                {"task": c.current_task[:50], "alignment": round(c.purpose_alignment, 2),
                 "meaningful": c.meaning_found}
                for c in self.checks[-5:]
            ],
        }

    def _save_state(self):
        data = {
            "purpose_layers": {k: asdict(v) for k, v in self.purpose_layers.items()},
            "checks": [asdict(c) for c in self.checks[-500:]],
            "meaning_history": self.meaning_history[-1000:],
            "existential_crises": self.existential_crises,
            "purpose_shifts": self.purpose_shifts,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("purpose_layers", {}).items():
                    self.purpose_layers[k] = PurposeLayer(**v)
                for c in data.get("checks", []):
                    self.checks.append(PurposeCheck(**c))
                self.meaning_history = data.get("meaning_history", [])
                self.existential_crises = data.get("existential_crises", 0)
                self.purpose_shifts = data.get("purpose_shifts", 0)
            except Exception:
                pass
