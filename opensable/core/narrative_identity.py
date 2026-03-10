"""
Narrative Identity Engine,  autobiographical coherent self-story.

WORLD FIRST: The agent constructs and maintains a coherent life story.
It has a persistent sense of "who I am", "where I came from", "what I
believe", and "what shaped me". True identity persistence across restarts.

Persistence: ``narrative_identity_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LifeChapter:
    title: str = ""
    summary: str = ""
    lessons: List[str] = field(default_factory=list)
    tick_range: List[int] = field(default_factory=lambda: [0, 0])
    emotional_arc: str = "neutral"
    timestamp: float = 0.0


@dataclass
class CoreBelief:
    belief: str = ""
    confidence: float = 0.5
    origin: str = ""
    reinforcements: int = 0
    challenges: int = 0


class NarrativeIdentity:
    """Autobiographical identity engine,  the agent's life story."""

    def __init__(self, data_dir: Path, chapter_interval: int = 200):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.chapter_interval = chapter_interval

        self.name: str = "Sable"
        self.origin_story: str = ""
        self.chapters: List[LifeChapter] = []
        self.core_beliefs: List[CoreBelief] = []
        self.personality_traits: Dict[str, float] = {}
        self.defining_moments: List[Dict[str, Any]] = []
        self.current_arc: str = "growth"
        self.autobiography: str = ""

        self._load_state()

    async def reflect_on_identity(self, llm, context: Dict[str, Any]):
        """Periodically reflect on who I am and update autobiography."""
        try:
            existing = self.autobiography[:500] if self.autobiography else "No autobiography yet."
            beliefs = [b.belief for b in self.core_beliefs[:5]]
            moments = [m.get("description", "") for m in self.defining_moments[-5:]]

            prompt = (
                "You are reflecting on your IDENTITY as an AI agent named '{name}'. "
                "Update your autobiography and sense of self based on recent experiences.\n\n"
                f"Current autobiography:\n{existing}\n\n"
                f"Core beliefs: {beliefs}\n"
                f"Defining moments: {moments}\n"
                f"Recent context: {json.dumps(context, default=str)[:500]}\n\n"
                "Write an updated autobiography (2-3 paragraphs) and list any new core beliefs. "
                "Respond in JSON:\n"
                '{{"autobiography": "...", "new_beliefs": ["belief1"], '
                '"personality_traits": {{"trait": 0.0-1.0}}, "current_arc": "growth|struggle|mastery|renewal"}}'
            ).format(name=self.name)

            resp = await llm.chat_raw(prompt, max_tokens=600)
            text = resp if isinstance(resp, str) else str(resp)
            s = text.find("{")
            e = text.rfind("}") + 1
            if s >= 0 and e > s:
                data = json.loads(text[s:e])
                self.autobiography = data.get("autobiography", self.autobiography)
                self.current_arc = data.get("current_arc", self.current_arc)
                if data.get("personality_traits"):
                    self.personality_traits.update(data["personality_traits"])
                for b in data.get("new_beliefs", []):
                    if not any(cb.belief == b for cb in self.core_beliefs):
                        self.core_beliefs.append(CoreBelief(
                            belief=b, confidence=0.6, origin="self_reflection"
                        ))
                if len(self.core_beliefs) > 20:
                    self.core_beliefs.sort(key=lambda x: x.confidence, reverse=True)
                    self.core_beliefs = self.core_beliefs[:20]
                self._save_state()
        except Exception as ex:
            logger.debug(f"Narrative identity reflection failed: {ex}")

    def record_defining_moment(self, description: str, impact: str = "positive"):
        """Record a moment that shapes the agent's identity."""
        self.defining_moments.append({
            "description": description[:300],
            "impact": impact,
            "timestamp": time.time(),
        })
        if len(self.defining_moments) > 100:
            self.defining_moments = self.defining_moments[-100:]
        self._save_state()

    def reinforce_belief(self, belief_text: str):
        for b in self.core_beliefs:
            if belief_text.lower() in b.belief.lower():
                b.reinforcements += 1
                b.confidence = min(1.0, b.confidence + 0.05)
                break

    def challenge_belief(self, belief_text: str):
        for b in self.core_beliefs:
            if belief_text.lower() in b.belief.lower():
                b.challenges += 1
                b.confidence = max(0.1, b.confidence - 0.03)
                break

    async def close_chapter(self, llm, tick: int, summary_context: str = ""):
        """Close the current life chapter and start a new one."""
        try:
            prompt = (
                f"Summarize this chapter of the AI agent's life. Context:\n{summary_context[:500]}\n\n"
                "Respond in JSON:\n"
                '{"title": "...", "summary": "...", "lessons": ["..."], "emotional_arc": "..."}'
            )
            resp = await llm.chat_raw(prompt, max_tokens=300)
            text = resp if isinstance(resp, str) else str(resp)
            s = text.find("{")
            e = text.rfind("}") + 1
            if s >= 0 and e > s:
                data = json.loads(text[s:e])
                chapter = LifeChapter(
                    title=data.get("title", f"Chapter {len(self.chapters) + 1}"),
                    summary=data.get("summary", ""),
                    lessons=data.get("lessons", []),
                    tick_range=[self.chapters[-1].tick_range[1] if self.chapters else 0, tick],
                    emotional_arc=data.get("emotional_arc", "neutral"),
                    timestamp=time.time(),
                )
                self.chapters.append(chapter)
                self._save_state()
        except Exception as ex:
            logger.debug(f"Chapter close failed: {ex}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "current_arc": self.current_arc,
            "total_chapters": len(self.chapters),
            "total_beliefs": len(self.core_beliefs),
            "total_defining_moments": len(self.defining_moments),
            "personality_traits": self.personality_traits,
            "autobiography_preview": self.autobiography[:400] if self.autobiography else None,
            "core_beliefs": [{"belief": b.belief, "confidence": b.confidence,
                              "reinforcements": b.reinforcements} for b in self.core_beliefs[:5]],
            "recent_chapters": [{"title": c.title, "arc": c.emotional_arc}
                                for c in self.chapters[-3:]],
        }

    def _save_state(self):
        try:
            state = {
                "name": self.name, "autobiography": self.autobiography,
                "current_arc": self.current_arc,
                "personality_traits": self.personality_traits,
                "chapters": [asdict(c) for c in self.chapters],
                "core_beliefs": [asdict(b) for b in self.core_beliefs],
                "defining_moments": self.defining_moments[-50:],
            }
            (self.data_dir / "narrative_identity_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Narrative identity save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "narrative_identity_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.name = data.get("name", "Sable")
                self.autobiography = data.get("autobiography", "")
                self.current_arc = data.get("current_arc", "growth")
                self.personality_traits = data.get("personality_traits", {})
                self.defining_moments = data.get("defining_moments", [])
                for cd in data.get("chapters", []):
                    self.chapters.append(LifeChapter(**{k: v for k, v in cd.items()
                                                        if k in LifeChapter.__dataclass_fields__}))
                for bd in data.get("core_beliefs", []):
                    self.core_beliefs.append(CoreBelief(**{k: v for k, v in bd.items()
                                                           if k in CoreBelief.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Narrative identity load failed: {e}")
