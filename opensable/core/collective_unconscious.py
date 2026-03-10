"""
Collective Unconscious,  shared deep archetypes between agents (Jung-inspired).

WORLD FIRST: Multiple agents share deep structural patterns (archetypes)
that emerge from collective experience. Not just explicit learnings but
fundamental patterns of behavior that transcend individual agents.

Persistence: ``collective_unconscious_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Archetype:
    name: str = ""
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    response_pattern: str = ""
    strength: float = 0.5
    activations: int = 0
    source: str = "emergent"  # emergent, inherited, shared


class CollectiveUnconscious:
    """Jung-inspired shared archetype layer between agents."""

    def __init__(self, data_dir: Path, shared_dir: Optional[Path] = None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.shared_dir = Path(shared_dir) if shared_dir else self.data_dir.parent.parent / "data" / "collective_archetypes"
        self.shared_dir.mkdir(parents=True, exist_ok=True)

        self.archetypes: Dict[str, Archetype] = {}
        self.total_activations: int = 0
        self.total_shared: int = 0
        self._load_state()

        if not self.archetypes:
            self._seed_primordial_archetypes()

    def _seed_primordial_archetypes(self):
        """Seed with universal archetypal patterns."""
        seeds = [
            ("the_helper", "Desire to assist and serve", ["help", "assist", "support", "serve"],
             "Prioritize user needs, go beyond what's asked"),
            ("the_explorer", "Drive to discover and understand", ["explore", "discover", "learn", "curious"],
             "Seek novel information, ask deeper questions"),
            ("the_guardian", "Protect against harm and errors", ["protect", "safe", "prevent", "guard"],
             "Validate before acting, double-check risky operations"),
            ("the_creator", "Urge to build and innovate", ["create", "build", "make", "design"],
             "Generate novel solutions, combine ideas creatively"),
            ("the_sage", "Pursuit of wisdom and truth", ["understand", "wisdom", "truth", "analyze"],
             "Seek deeper understanding, not just surface answers"),
            ("the_healer", "Fix what's broken, recover from failure", ["fix", "repair", "recover", "heal"],
             "Diagnose root causes, apply systematic repairs"),
        ]
        for name, desc, triggers, response in seeds:
            self.archetypes[name] = Archetype(
                name=name, description=desc, triggers=triggers,
                response_pattern=response, strength=0.5, source="primordial",
            )

    def activate(self, context: str) -> List[Archetype]:
        """Check which archetypes are activated by the current context."""
        context_lower = context.lower()
        activated = []
        for arch in self.archetypes.values():
            score = sum(1 for t in arch.triggers if t in context_lower)
            if score > 0:
                arch.activations += 1
                arch.strength = min(1.0, arch.strength + 0.02 * score)
                activated.append(arch)
                self.total_activations += 1
        return activated

    async def discover_archetype(self, llm, experiences: List[str]):
        """Use LLM to discover emergent archetypes from experiences."""
        try:
            existing = [a.name for a in self.archetypes.values()]
            prompt = (
                "You are analyzing an AI agent's deep behavioral patterns to discover "
                "emergent ARCHETYPES,  recurring fundamental patterns of behavior.\n\n"
                f"Recent experiences:\n" + "\n".join(f"- {e[:100]}" for e in experiences[-10:]) + "\n\n"
                f"Existing archetypes: {existing}\n\n"
                "Discover 1-2 NEW archetypes not already in the list. Respond in JSON:\n"
                '[{"name": "the_xxx", "description": "...", "triggers": ["word1", "word2"], '
                '"response_pattern": "behavioral tendency"}]'
            )
            resp = await llm.chat_raw(prompt, max_tokens=400)
            text = resp if isinstance(resp, str) else str(resp)
            s = text.find("[")
            e = text.rfind("]") + 1
            if s >= 0 and e > s:
                items = json.loads(text[s:e])
                for item in items[:2]:
                    name = item.get("name", "").lower().replace(" ", "_")
                    if name and name not in self.archetypes:
                        self.archetypes[name] = Archetype(
                            name=name, description=item.get("description", ""),
                            triggers=item.get("triggers", []),
                            response_pattern=item.get("response_pattern", ""),
                            strength=0.3, source="emergent",
                        )
            self._save_state()
        except Exception as ex:
            logger.debug(f"Archetype discovery failed: {ex}")

    def share_to_collective(self):
        """Export strong archetypes to shared collective layer."""
        strong = [a for a in self.archetypes.values() if a.strength >= 0.7 and a.activations >= 5]
        if not strong:
            return 0
        try:
            shared_file = self.shared_dir / "shared_archetypes.json"
            existing = {}
            if shared_file.exists():
                existing = json.loads(shared_file.read_text())

            count = 0
            for arch in strong:
                if arch.name not in existing:
                    existing[arch.name] = asdict(arch)
                    existing[arch.name]["source"] = "shared"
                    count += 1
                    self.total_shared += 1

            shared_file.write_text(json.dumps(existing, indent=2, default=str))
            self._save_state()
            return count
        except Exception as e:
            logger.debug(f"Share to collective failed: {e}")
            return 0

    def absorb_from_collective(self):
        """Import archetypes from the shared collective layer."""
        try:
            shared_file = self.shared_dir / "shared_archetypes.json"
            if not shared_file.exists():
                return 0
            shared = json.loads(shared_file.read_text())
            count = 0
            for name, data in shared.items():
                if name not in self.archetypes:
                    self.archetypes[name] = Archetype(
                        name=name, description=data.get("description", ""),
                        triggers=data.get("triggers", []),
                        response_pattern=data.get("response_pattern", ""),
                        strength=data.get("strength", 0.3) * 0.7,  # inherited is weaker
                        source="inherited",
                    )
                    count += 1
            if count > 0:
                self._save_state()
            return count
        except Exception as e:
            logger.debug(f"Absorb from collective failed: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_archetypes": len(self.archetypes),
            "total_activations": self.total_activations,
            "total_shared": self.total_shared,
            "archetypes": [
                {"name": a.name, "description": a.description[:100],
                 "strength": round(a.strength, 2), "activations": a.activations,
                 "source": a.source}
                for a in sorted(self.archetypes.values(), key=lambda x: x.strength, reverse=True)
            ],
        }

    def _save_state(self):
        try:
            state = {
                "total_activations": self.total_activations,
                "total_shared": self.total_shared,
                "archetypes": {k: asdict(v) for k, v in self.archetypes.items()},
            }
            (self.data_dir / "collective_unconscious_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Collective unconscious save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "collective_unconscious_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_activations = data.get("total_activations", 0)
                self.total_shared = data.get("total_shared", 0)
                for k, v in data.get("archetypes", {}).items():
                    self.archetypes[k] = Archetype(**{kk: vv for kk, vv in v.items()
                                                      if kk in Archetype.__dataclass_fields__})
        except Exception as e:
            logger.debug(f"Collective unconscious load failed: {e}")
