"""
Dream Engine — REM-like creative replay during idle time.

WORLD FIRST: No AI agent has biological dreaming. During idle periods,
the agent "dreams" by replaying recent experiences in corrupted/remixed
form, discovering novel solutions and creative connections that pure
logical reasoning would never find.

Inspired by neuroscience research showing REM sleep consolidates memories
and generates creative insight through random recombination of experiences.

Persistence: ``dream_engine_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Dream:
    id: str = ""
    tick: int = 0
    seed_memories: List[str] = field(default_factory=list)
    narrative: str = ""
    insights: List[str] = field(default_factory=list)
    lucidity: float = 0.0          # 0=chaotic, 1=controlled
    emotional_tone: str = "neutral"
    creative_value: float = 0.0    # LLM-scored usefulness
    timestamp: float = 0.0
    applied: bool = False


@dataclass
class DreamCycle:
    cycle_id: int = 0
    phase: str = "idle"            # idle, rem, deep, lucid, wake
    dreams: List[Dream] = field(default_factory=list)
    total_insights: int = 0
    start_time: float = 0.0
    end_time: float = 0.0


class DreamEngine:
    """Biological dreaming for AI agents — creative replay during idle."""

    def __init__(
        self,
        data_dir: Path,
        idle_threshold: int = 5,       # ticks of no tasks → start dreaming
        max_dreams_per_cycle: int = 3,
        corruption_rate: float = 0.3,  # how much to "corrupt" memories
        max_dream_history: int = 200,
    ):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.idle_threshold = idle_threshold
        self.max_dreams_per_cycle = max_dreams_per_cycle
        self.corruption_rate = corruption_rate
        self.max_dream_history = max_dream_history

        self.idle_ticks: int = 0
        self.dreams: List[Dream] = []
        self.cycles: List[DreamCycle] = []
        self.total_insights: int = 0
        self.total_applied: int = 0
        self.current_phase: str = "awake"
        self._experience_buffer: List[str] = []

        self._load_state()

    # ── Public API ────────────────────────────────────────────────────────────

    def record_experience(self, description: str):
        """Feed waking experiences into the dream buffer."""
        self._experience_buffer.append(description[:500])
        if len(self._experience_buffer) > 200:
            self._experience_buffer = self._experience_buffer[-200:]

    def should_dream(self, has_pending_tasks: bool) -> bool:
        """Check if conditions are right for dreaming."""
        if has_pending_tasks:
            self.idle_ticks = 0
            self.current_phase = "awake"
            return False
        self.idle_ticks += 1
        return self.idle_ticks >= self.idle_threshold and len(self._experience_buffer) >= 3

    async def dream_cycle(self, llm) -> DreamCycle:
        """Run a full REM dream cycle — remix experiences for creative insight."""
        cycle = DreamCycle(
            cycle_id=len(self.cycles) + 1,
            phase="rem",
            start_time=time.time(),
        )
        self.current_phase = "rem"

        for i in range(min(self.max_dreams_per_cycle, len(self._experience_buffer) // 2)):
            # Select random seed memories
            n_seeds = random.randint(2, min(5, len(self._experience_buffer)))
            seeds = random.sample(self._experience_buffer, n_seeds)

            # Corrupt/remix them
            corrupted = self._corrupt_memories(seeds)

            dream = await self._generate_dream(llm, seeds, corrupted, cycle.cycle_id, i)
            if dream:
                cycle.dreams.append(dream)
                self.dreams.append(dream)
                cycle.total_insights += len(dream.insights)
                self.total_insights += len(dream.insights)

        cycle.phase = "wake"
        cycle.end_time = time.time()
        self.cycles.append(cycle)
        self.current_phase = "awake"
        self.idle_ticks = 0

        # Trim history
        if len(self.dreams) > self.max_dream_history:
            self.dreams = self.dreams[-self.max_dream_history:]
        if len(self.cycles) > 50:
            self.cycles = self.cycles[-50:]

        self._save_state()
        return cycle

    def get_unapplied_insights(self) -> List[Dict[str, Any]]:
        """Return insights from dreams that haven't been applied yet."""
        results = []
        for d in self.dreams:
            if not d.applied and d.insights and d.creative_value >= 0.5:
                results.append({
                    "dream_id": d.id,
                    "insights": d.insights,
                    "creative_value": d.creative_value,
                    "emotional_tone": d.emotional_tone,
                })
        return results

    def mark_applied(self, dream_id: str):
        """Mark a dream's insights as applied."""
        for d in self.dreams:
            if d.id == dream_id:
                d.applied = True
                self.total_applied += 1
                break
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase,
            "idle_ticks": self.idle_ticks,
            "total_dreams": len(self.dreams),
            "total_cycles": len(self.cycles),
            "total_insights": self.total_insights,
            "total_applied": self.total_applied,
            "experience_buffer_size": len(self._experience_buffer),
            "recent_dreams": [
                {
                    "id": d.id,
                    "narrative": d.narrative[:200],
                    "insights": d.insights[:3],
                    "creative_value": d.creative_value,
                    "emotional_tone": d.emotional_tone,
                    "lucidity": d.lucidity,
                }
                for d in self.dreams[-5:]
            ],
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _corrupt_memories(self, memories: List[str]) -> str:
        """Corrupt and remix memories like biological REM does."""
        # Shuffle words across memories
        words = []
        for m in memories:
            words.extend(m.split())

        n_corrupt = int(len(words) * self.corruption_rate)
        for _ in range(n_corrupt):
            if len(words) > 2:
                i, j = random.sample(range(len(words)), 2)
                words[i], words[j] = words[j], words[i]

        # Insert random "dream logic" connectors
        connectors = ["suddenly", "transformed into", "but actually", "which reminded of",
                       "in a parallel world", "reversing", "merging with"]
        for _ in range(random.randint(1, 3)):
            pos = random.randint(0, max(0, len(words) - 1))
            words.insert(pos, random.choice(connectors))

        return " ".join(words[:150])

    async def _generate_dream(self, llm, seeds, corrupted, cycle_id, dream_idx) -> Optional[Dream]:
        try:
            prompt = (
                "You are a DREAM ENGINE inside an AI agent. The agent is 'dreaming' — "
                "replaying and remixing recent experiences to find creative insights.\n\n"
                f"Original experiences:\n" + "\n".join(f"- {s}" for s in seeds) + "\n\n"
                f"Dream remix (corrupted replay):\n{corrupted}\n\n"
                "Generate a dream narrative and extract creative insights that could help "
                "the agent solve problems in novel ways. Respond in JSON:\n"
                '{"narrative": "...", "insights": ["insight1", "insight2"], '
                '"emotional_tone": "curious|anxious|euphoric|melancholic|neutral", '
                '"creative_value": 0.0-1.0, "lucidity": 0.0-1.0}'
            )
            resp = await llm.chat_raw(prompt, max_tokens=500)
            text = resp if isinstance(resp, str) else str(resp)
            # Extract JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                return Dream(
                    id=f"dream_{cycle_id}_{dream_idx}_{int(time.time())}",
                    tick=0,
                    seed_memories=seeds,
                    narrative=data.get("narrative", ""),
                    insights=data.get("insights", []),
                    lucidity=float(data.get("lucidity", 0.5)),
                    emotional_tone=data.get("emotional_tone", "neutral"),
                    creative_value=float(data.get("creative_value", 0.5)),
                    timestamp=time.time(),
                )
        except Exception as e:
            logger.debug(f"Dream generation failed: {e}")
        return None

    def _save_state(self):
        try:
            state = {
                "idle_ticks": self.idle_ticks,
                "total_insights": self.total_insights,
                "total_applied": self.total_applied,
                "experience_buffer": self._experience_buffer[-100:],
                "dreams": [asdict(d) for d in self.dreams[-50:]],
            }
            (self.data_dir / "dream_engine_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"Dream engine save failed: {e}")

    def _load_state(self):
        try:
            f = self.data_dir / "dream_engine_state.json"
            if f.exists():
                data = json.loads(f.read_text())
                self.idle_ticks = data.get("idle_ticks", 0)
                self.total_insights = data.get("total_insights", 0)
                self.total_applied = data.get("total_applied", 0)
                self._experience_buffer = data.get("experience_buffer", [])
                for dd in data.get("dreams", []):
                    self.dreams.append(Dream(**{k: v for k, v in dd.items()
                                                if k in Dream.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Dream engine load failed: {e}")
