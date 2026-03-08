"""
Cognitive Scar Tissue — permanent catastrophic failure markers.

WORLD FIRST: Unlike normal learning (which decays), cognitive scars are
PERMANENT markers from catastrophic failures. They never fade and create
hard boundaries the agent will never cross again. Like touching a hot stove —
you learn once and never forget.

Persistence: ``cognitive_scar_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Scar:
    id: str = ""
    description: str = ""
    original_action: str = ""
    consequence: str = ""
    severity: float = 1.0  # Always high — these are serious
    keywords: List[str] = field(default_factory=list)
    created: float = 0.0
    times_prevented: int = 0  # How many disasters we've prevented
    last_triggered: float = 0.0


class CognitiveScar:
    """Permanent markers from catastrophic failures — never decay."""

    def __init__(self, data_dir: Path, pain_threshold: float = 0.8):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pain_threshold = pain_threshold

        self.scars: Dict[str, Scar] = {}
        self.near_misses: List[Dict[str, Any]] = []
        self.total_prevented: int = 0

        self._load_state()

    def burn(self, action: str, consequence: str, severity: float = 1.0,
             keywords: Optional[List[str]] = None):
        """Create a permanent scar from a catastrophic failure."""
        if severity < self.pain_threshold:
            return  # Not severe enough to scar

        scar_id = hashlib.md5(f"{action}:{consequence}".encode()).hexdigest()[:12]
        kw = keywords or self._extract_keywords(action + " " + consequence)

        self.scars[scar_id] = Scar(
            id=scar_id,
            description=f"NEVER: {action[:100]} → caused: {consequence[:100]}",
            original_action=action[:300],
            consequence=consequence[:300],
            severity=severity,
            keywords=kw,
            created=time.time(),
        )
        logger.warning(f"Cognitive scar formed: {action[:60]} → {consequence[:60]}")
        self._save_state()

    def check(self, proposed_action: str) -> Optional[Dict[str, Any]]:
        """Check if a proposed action would trigger any scar.
        Returns warning dict or None if safe."""
        action_words = set(proposed_action.lower().split())

        for scar in self.scars.values():
            scar_words = set(scar.keywords)
            overlap = action_words & scar_words
            if len(overlap) >= 2 or (len(overlap) >= 1 and len(scar_words) <= 3):
                scar.times_prevented += 1
                scar.last_triggered = time.time()
                self.total_prevented += 1
                return {
                    "blocked": True,
                    "scar_id": scar.id,
                    "warning": scar.description,
                    "original_consequence": scar.consequence,
                    "times_this_saved_us": scar.times_prevented,
                }

        return None

    def check_batch(self, actions: List[str]) -> List[Dict[str, Any]]:
        """Check multiple actions, return all warnings."""
        warnings = []
        for a in actions:
            w = self.check(a)
            if w:
                warnings.append(w)
        return warnings

    def record_near_miss(self, action: str, what_almost_happened: str):
        """Record something that almost went wrong (might become a scar)."""
        self.near_misses.append({
            "action": action[:200],
            "risk": what_almost_happened[:200],
            "timestamp": time.time(),
        })
        if len(self.near_misses) > 50:
            self.near_misses = self.near_misses[-50:]

    async def analyze_near_misses(self, llm) -> List[str]:
        """LLM reviews near misses and recommends which should become scars."""
        if len(self.near_misses) < 3:
            return []
        nm_text = "\n".join(
            f"- Action: {nm['action']} → Risk: {nm['risk']}"
            for nm in self.near_misses[-10:]
        )
        prompt = (
            f"Review these near-miss incidents:\n{nm_text}\n\n"
            f"Which of these are severe enough to CREATE A PERMANENT RULE "
            f"(cognitive scar) the agent should NEVER violate? "
            f"Return JSON: [{{\"action\": \"...\", \"rule\": \"NEVER ...\"}}]"
        )
        try:
            resp = await llm.chat_raw(prompt, max_tokens=400)
            import re
            m = re.search(r'\[.*\]', resp, re.DOTALL)
            if m:
                items = json.loads(m.group())
                rules = []
                for item in items:
                    self.burn(item.get("action", ""), item.get("rule", ""), 0.9)
                    rules.append(item.get("rule", ""))
                return rules
        except Exception as e:
            logger.debug(f"Near miss analysis failed: {e}")
        return []

    def get_all_rules(self) -> List[str]:
        """Get all permanent rules (for system prompt injection)."""
        return [s.description for s in self.scars.values()]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_scars": len(self.scars),
            "total_prevented": self.total_prevented,
            "near_misses": len(self.near_misses),
            "scars": [
                {"id": s.id, "rule": s.description[:80],
                 "prevented": s.times_prevented, "severity": s.severity}
                for s in sorted(self.scars.values(),
                                key=lambda x: x.times_prevented, reverse=True)[:5]
            ],
            "most_protective": max(
                (s.times_prevented for s in self.scars.values()), default=0),
        }

    def _extract_keywords(self, text: str) -> List[str]:
        stop = {"the", "a", "an", "is", "was", "to", "of", "in", "for", "and", "or"}
        words = [w.lower().strip(".,!?:;") for w in text.split() if len(w) > 2]
        return list(set(w for w in words if w not in stop))[:15]

    def _save_state(self):
        try:
            state = {
                "scars": {k: asdict(v) for k, v in self.scars.items()},
                "near_misses": self.near_misses[-30:],
                "total_prevented": self.total_prevented,
            }
            (self.data_dir / "cognitive_scar_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Cognitive scar save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "cognitive_scar_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_prevented = data.get("total_prevented", 0)
                self.near_misses = data.get("near_misses", [])
                for k, v in data.get("scars", {}).items():
                    self.scars[k] = Scar(**{f: v[f] for f in Scar.__dataclass_fields__ if f in v})
        except Exception as e:
            logger.debug(f"Cognitive scar load: {e}")
