"""
Cognitive Memory — multi-tier memory with decay, consolidation, and attention.

Implements a human-inspired memory architecture:

  Working Memory  — top-N most relevant items (Miller's Number: 7 ± 2)
  Short-Term      — recent, decaying rapidly
  Long-Term       — consolidated high-importance memories, slow decay

Core mechanisms:
  MemoryDecay          — exponential time-based importance decay
  MemoryConsolidation  — promotes STM→LTM, forgets low-importance items
  AttentionFilter      — selects top-N for working memory

Academic grounding:
  [1] Miller (1956): The Magical Number Seven — working memory capacity
  [2] Atkinson & Shiffrin (1968): Multi-store model (STM/LTM)
  [3] Park et al., arXiv:2304.03442: Generative Agents — importance × recency
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class CognitiveMemoryItem:
    """A single memory item in the cognitive memory system."""

    content: str
    category: str = "general"              # general, episode, reflection, tick_outcome, etc.
    tier: str = "short_term"               # working, short_term, long_term
    importance_base: float = 0.5           # base importance [0, 1]
    effective_importance: float = 0.5      # computed after decay + boosts
    created_tick: int = 0
    last_accessed_tick: int = 0
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CognitiveMemoryItem":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── Memory Decay ─────────────────────────────────────────────────────────────


class MemoryDecay:
    """Exponential time-based decay on memory importance.

    decay_factor = 0.5^(age / half_life)
    recency_boost = 0.5^(recency / half_life_short)
    effective = base * decay_factor * (0.5 + 0.5 * recency_boost)
    """

    def __init__(
        self,
        half_life_short: int = 10,
        half_life_long: int = 100,
    ):
        self.half_life_short = max(1, half_life_short)
        self.half_life_long = max(1, half_life_long)

    def apply(
        self, memories: List[CognitiveMemoryItem], current_tick: int,
    ) -> List[CognitiveMemoryItem]:
        """Apply decay to all memories, updating effective_importance."""
        result = []
        for mem in memories:
            half_life = (
                self.half_life_long if mem.tier == "long_term"
                else self.half_life_short
            )
            age = max(0, current_tick - mem.created_tick)
            decay_factor = 0.5 ** (age / half_life)

            recency = max(0, current_tick - mem.last_accessed_tick)
            recency_boost = 0.5 ** (recency / self.half_life_short)

            effective = mem.importance_base * decay_factor * (0.5 + 0.5 * recency_boost)
            mem.effective_importance = round(effective, 6)
            result.append(mem)
        return result


# ─── Memory Consolidation ─────────────────────────────────────────────────────


class MemoryConsolidation:
    """Promotes high-importance STM to LTM, forgets low-importance memories.

    STM with effective_importance >= promote_threshold → LTM.
    Any tier with effective_importance < demote_threshold → forgotten (removed).
    """

    def __init__(
        self,
        promote_threshold: float = 0.7,
        demote_threshold: float = 0.1,
    ):
        self.promote_threshold = promote_threshold
        self.demote_threshold = demote_threshold

    def apply(
        self, memories: List[CognitiveMemoryItem],
    ) -> List[CognitiveMemoryItem]:
        """Consolidate memories: promote STM→LTM, forget low-importance."""
        result = []
        promoted = 0
        forgotten = 0
        for mem in memories:
            if mem.effective_importance < self.demote_threshold:
                forgotten += 1
                continue  # Forgotten — removed
            if (
                mem.tier == "short_term"
                and mem.effective_importance >= self.promote_threshold
            ):
                mem.tier = "long_term"
                promoted += 1
            result.append(mem)
        if promoted > 0 or forgotten > 0:
            logger.debug(
                f"Consolidation: {promoted} promoted to LTM, "
                f"{forgotten} forgotten"
            )
        return result


# ─── Attention Filter ─────────────────────────────────────────────────────────


class AttentionFilter:
    """Selects top-N most important memories for working memory.

    Working memory size defaults to 7 (Miller's Number).
    """

    def __init__(self, working_memory_size: int = 7):
        self.working_memory_size = working_memory_size

    def apply(
        self, memories: List[CognitiveMemoryItem],
    ) -> List[CognitiveMemoryItem]:
        """Set top-N memories to 'working' tier, rest keep their tier."""
        sorted_mems = sorted(
            memories,
            key=lambda m: m.effective_importance,
            reverse=True,
        )
        # Mark top-N as working, restore others to their original tier
        for i, mem in enumerate(sorted_mems):
            if i < self.working_memory_size:
                mem.tier = "working"
            elif mem.tier == "working":
                # Demote from working back to original tier
                mem.tier = "short_term"
        return sorted_mems


# ─── Cognitive Memory Manager ─────────────────────────────────────────────────


class CognitiveMemoryManager:
    """Multi-tier memory system with decay, consolidation, and attention.

    Manages the full cognitive memory pipeline:
      1. Memory Decay — apply exponential decay to all items
      2. Consolidation — promote/demote between tiers
      3. Attention — select working memory subset

    Persists memories to a JSONL file for cross-session continuity.
    """

    def __init__(
        self,
        directory: Path,
        half_life_short: int = 10,
        half_life_long: int = 100,
        promote_threshold: float = 0.7,
        demote_threshold: float = 0.1,
        working_memory_size: int = 7,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.decay = MemoryDecay(half_life_short, half_life_long)
        self.consolidation = MemoryConsolidation(promote_threshold, demote_threshold)
        self.attention = AttentionFilter(working_memory_size)

        self._memories: List[CognitiveMemoryItem] = []
        self._file = self.directory / "cognitive_memories.jsonl"

        self._load()

    # ── Core operations ────────────────────────────────────────────────────

    def add_memory(
        self,
        content: str,
        *,
        category: str = "general",
        importance: float = 0.5,
        tick: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CognitiveMemoryItem:
        """Add a new memory to short-term storage."""
        item = CognitiveMemoryItem(
            content=content,
            category=category,
            tier="short_term",
            importance_base=importance,
            effective_importance=importance,
            created_tick=tick,
            last_accessed_tick=tick,
            access_count=0,
            metadata=metadata or {},
        )
        self._memories.append(item)
        self._append_to_file(item)
        return item

    def access_memory(
        self, index: int, tick: int,
    ) -> Optional[CognitiveMemoryItem]:
        """Access a memory by index, boosting its recency."""
        if 0 <= index < len(self._memories):
            mem = self._memories[index]
            mem.last_accessed_tick = tick
            mem.access_count += 1
            return mem
        return None

    def process_tick(self, current_tick: int) -> Dict[str, Any]:
        """Run the full cognitive pipeline on all memories.

        Returns summary statistics.
        """
        count_before = len(self._memories)

        # 1. Apply decay
        self._memories = self.decay.apply(self._memories, current_tick)

        # 2. Consolidation (promote/demote/forget)
        self._memories = self.consolidation.apply(self._memories)

        # 3. Attention filter (select working memory)
        self._memories = self.attention.apply(self._memories)

        count_after = len(self._memories)
        forgotten = count_before - count_after

        # Persist full state
        self._save()

        # Count tiers
        tiers = {"working": 0, "short_term": 0, "long_term": 0}
        for mem in self._memories:
            tiers[mem.tier] = tiers.get(mem.tier, 0) + 1

        return {
            "total": count_after,
            "forgotten": forgotten,
            "tiers": tiers,
            "tick": current_tick,
        }

    def get_working_memory(self) -> List[CognitiveMemoryItem]:
        """Get current working memory items (top-N by importance)."""
        return [m for m in self._memories if m.tier == "working"]

    def get_all_memories(self) -> List[CognitiveMemoryItem]:
        """Get all memories across all tiers."""
        return list(self._memories)

    def get_memories_by_category(
        self, category: str,
    ) -> List[CognitiveMemoryItem]:
        """Get memories filtered by category."""
        return [m for m in self._memories if m.category == category]

    def get_context_prompt(self, max_items: int = 10) -> str:
        """Build a context prompt from working memory for LLM injection."""
        working = self.get_working_memory()
        if not working:
            return ""

        items = working[:max_items]
        parts = ["COGNITIVE WORKING MEMORY (most relevant items):"]
        for i, mem in enumerate(items, 1):
            importance = f"{mem.effective_importance:.2f}"
            parts.append(
                f"  {i}. [{mem.category}] (importance={importance}, "
                f"tier={mem.tier}): {mem.content[:200]}"
            )
        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        tiers = {"working": 0, "short_term": 0, "long_term": 0}
        categories: Dict[str, int] = {}
        for mem in self._memories:
            tiers[mem.tier] = tiers.get(mem.tier, 0) + 1
            categories[mem.category] = categories.get(mem.category, 0) + 1

        avg_importance = 0.0
        if self._memories:
            avg_importance = sum(
                m.effective_importance for m in self._memories
            ) / len(self._memories)

        return {
            "total": len(self._memories),
            "tiers": tiers,
            "categories": categories,
            "avg_importance": round(avg_importance, 4),
        }

    # ── Persistence ────────────────────────────────────────────────────────

    def _append_to_file(self, item: CognitiveMemoryItem) -> None:
        """Append a single memory to the JSONL file."""
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(item.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append cognitive memory: {e}")

    def _save(self) -> None:
        """Overwrite the entire memory file (after consolidation)."""
        try:
            with open(self._file, "w", encoding="utf-8") as f:
                for mem in self._memories:
                    f.write(json.dumps(mem.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save cognitive memories: {e}")

    def _load(self) -> None:
        """Load memories from JSONL file."""
        if not self._file.exists():
            return
        try:
            items = []
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        items.append(CognitiveMemoryItem.from_dict(d))
            self._memories = items
            logger.debug(f"Loaded {len(items)} cognitive memories")
        except Exception as e:
            logger.warning(f"Failed to load cognitive memories: {e}")
