"""
Ultra-Long-Term Memory Consolidation — Weeks/months pattern extraction.

Short-term cognitive memory stores individual events. This module:
  • Periodically scans accumulated memories (cognitive, task outcomes, reflections)
  • Uses LLM to consolidate weeks of activity into high-level patterns
  • Builds a "wisdom library" of durable insights that persist indefinitely
  • Decays raw memories that have been consolidated (saves space)
  • Tracks consolidation cycles with timestamps
  • Feeds consolidated knowledge back into planning & decision-making
  • Runs every N ticks (default 50) but only consolidates if enough raw data exists
"""

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class ConsolidatedMemory:
    """A high-level pattern extracted from many raw memories."""
    memory_id: str
    category: str               # behavioral_pattern | task_strategy | error_pattern
                                # environment_insight | preference | capability_map
    title: str
    insight: str                # The consolidated knowledge
    supporting_count: int = 0   # How many raw memories contributed
    confidence: float = 0.5     # How reliable this insight is (0.0–1.0)
    first_observed: str = ""    # Earliest contributing memory
    last_reinforced: str = ""   # Most recent reinforcement
    reinforcement_count: int = 1
    decay_rate: float = 0.01    # How fast confidence decays without reinforcement
    tags: List[str] = field(default_factory=list)

    def reinforce(self, boost: float = 0.05):
        """Strengthen this memory — it was observed again or found useful."""
        self.confidence = min(1.0, self.confidence + boost)
        self.reinforcement_count += 1
        self.last_reinforced = datetime.now().isoformat()

    def decay(self, ticks_since: int = 1):
        """Diminish confidence over time without reinforcement."""
        self.confidence = max(0.05, self.confidence - self.decay_rate * ticks_since * 0.001)


@dataclass
class ConsolidationCycle:
    """Record of a single consolidation run."""
    cycle_id: int
    timestamp: str
    raw_memories_scanned: int
    patterns_extracted: int
    patterns_reinforced: int
    duration_ms: float = 0.0


# ── LLM Prompts ──────────────────────────────────────────────────────────────

_CONSOLIDATION_PROMPT = """\
You are an AI agent's long-term memory consolidation engine.
You are reviewing a batch of raw memories accumulated over days/weeks of operation.

Your job is to identify HIGH-LEVEL PATTERNS — durable insights that will remain
useful for months. Do NOT repeat individual events. Instead, extract:

Categories:
- behavioral_pattern: "I tend to X when Y happens" (recurring behavior)
- task_strategy: "The best approach for X-type tasks is Y" (winning strategies)
- error_pattern: "X-type errors occur when Y" (failure modes to avoid)
- environment_insight: "The system/user/environment exhibits X pattern" (external observation)
- preference: "The user prefers X over Y" (user behavior model)
- capability_map: "I am strong at X but weak at Y" (self-knowledge)

For each pattern found, output:
  {"category": "...", "title": "short title", "insight": "detailed description",
   "confidence": 0.0-1.0, "tags": ["tag1", "tag2"], "supporting_count": <int>}

Output ONLY a valid JSON array. If no meaningful patterns, return [].
Be selective — only extract patterns supported by multiple data points.
"""

_WISDOM_SUMMARY_PROMPT = """\
You are reviewing an AI agent's accumulated wisdom — long-term patterns extracted
over weeks/months of autonomous operation. Summarize the current state of knowledge
in 3-5 sentences. Focus on: strongest patterns, biggest risks/weaknesses identified,
and most reliable strategies discovered. Be concise and definitive.
"""


class UltraLongTermMemory:
    """
    Ultra-long-term memory consolidation engine.

    Scans raw memories periodically, extracts durable patterns via LLM,
    and maintains a "wisdom library" that enriches future planning.
    """

    def __init__(self, data_dir: Path, consolidate_every_n_ticks: int = 50):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._consolidate_every = consolidate_every_n_ticks

        # State
        self._wisdom: Dict[str, ConsolidatedMemory] = {}
        self._cycles: List[ConsolidationCycle] = []
        self._total_consolidations = 0
        self._total_patterns_found = 0
        self._last_consolidation_tick = -1
        self._wisdom_summary: str = ""

        self._load_state()

    # ── Public API ────────────────────────────────────────────────────────────

    async def consolidate(self, llm, raw_memories: List[str], tick: int = 0) -> int:
        """
        Run a consolidation cycle over raw memories.

        Returns the number of new patterns extracted.
        """
        if tick - self._last_consolidation_tick < self._consolidate_every:
            return 0  # Not time yet

        if len(raw_memories) < 10:
            return 0  # Need enough data to find patterns

        self._last_consolidation_tick = tick
        start = time.monotonic()

        if not llm:
            return 0

        # Prepare memory batch (up to 100 most recent + diverse selection)
        batch = self._select_batch(raw_memories, max_size=100)

        messages = [
            {"role": "system", "content": _CONSOLIDATION_PROMPT},
            {"role": "user", "content": (
                f"Agent tick: {tick}\n"
                f"Memories to consolidate ({len(batch)} items):\n\n"
                + "\n".join(f"- {m[:200]}" for m in batch)
            )},
        ]

        try:
            response = await llm.invoke_with_tools(messages, [])
            text = response.get("text", "") or ""
            patterns = self._parse_json_array(text)
            if not patterns:
                return 0

            new_count = 0
            reinforced_count = 0

            for pd in patterns:
                if not isinstance(pd, dict) or not pd.get("insight"):
                    continue

                title = pd.get("title", "Untitled")[:100]
                insight = pd.get("insight", "")[:500]

                # Check if this reinforces an existing pattern
                existing = self._find_similar(title, insight)
                if existing:
                    existing.reinforce(boost=0.08)
                    existing.supporting_count += pd.get("supporting_count", 1)
                    reinforced_count += 1
                    continue

                # New pattern
                import hashlib
                mid = hashlib.sha256(f"{title}:{insight[:100]}".encode()).hexdigest()[:12]
                mem = ConsolidatedMemory(
                    memory_id=mid,
                    category=pd.get("category", "behavioral_pattern"),
                    title=title,
                    insight=insight,
                    supporting_count=pd.get("supporting_count", 1),
                    confidence=float(pd.get("confidence", 0.6)),
                    first_observed=datetime.now().isoformat(),
                    last_reinforced=datetime.now().isoformat(),
                    tags=pd.get("tags", []),
                )
                self._wisdom[mid] = mem
                new_count += 1

            duration_ms = (time.monotonic() - start) * 1000
            cycle = ConsolidationCycle(
                cycle_id=len(self._cycles) + 1,
                timestamp=datetime.now().isoformat(),
                raw_memories_scanned=len(batch),
                patterns_extracted=new_count,
                patterns_reinforced=reinforced_count,
                duration_ms=duration_ms,
            )
            self._cycles.append(cycle)
            self._total_consolidations += 1
            self._total_patterns_found += new_count

            # Decay all memories slightly (temporal decay)
            for mem in self._wisdom.values():
                mem.decay(ticks_since=self._consolidate_every)

            # Remove very low-confidence patterns (forgotten)
            forgotten = [k for k, v in self._wisdom.items() if v.confidence < 0.05]
            for k in forgotten:
                del self._wisdom[k]

            self._save_state()

            logger.info(
                f"🧠 UltraLTM: Consolidation cycle {cycle.cycle_id} — "
                f"{new_count} new patterns, {reinforced_count} reinforced, "
                f"{len(forgotten)} forgotten ({duration_ms:.0f}ms)"
            )

            return new_count

        except Exception as e:
            logger.warning(f"UltraLTM: Consolidation failed: {e}")
            return 0

    async def generate_wisdom_summary(self, llm) -> str:
        """Generate a concise summary of accumulated wisdom."""
        if not llm or not self._wisdom:
            return self._wisdom_summary or "No consolidated wisdom yet."

        wisdom_text = "\n".join(
            f"- [{m.category}] {m.title} (conf={m.confidence:.2f}, "
            f"reinforced {m.reinforcement_count}x): {m.insight[:200]}"
            for m in sorted(
                self._wisdom.values(),
                key=lambda x: x.confidence,
                reverse=True,
            )[:20]
        )

        messages = [
            {"role": "system", "content": _WISDOM_SUMMARY_PROMPT},
            {"role": "user", "content": f"Accumulated wisdom:\n{wisdom_text}"},
        ]

        try:
            response = await llm.invoke_with_tools(messages, [])
            self._wisdom_summary = response.get("text", "") or ""
            self._save_state()
            return self._wisdom_summary
        except Exception as e:
            logger.debug(f"UltraLTM: Wisdom summary failed: {e}")
            return self._wisdom_summary or ""

    def get_relevant_wisdom(self, context: str = "", top_k: int = 5) -> List[Dict]:
        """Return top-k most confident/relevant wisdom entries."""
        sorted_wisdom = sorted(
            self._wisdom.values(),
            key=lambda x: x.confidence * (x.reinforcement_count ** 0.3),
            reverse=True,
        )

        results = []
        for m in sorted_wisdom[:top_k]:
            results.append({
                "memory_id": m.memory_id,
                "category": m.category,
                "title": m.title,
                "insight": m.insight,
                "confidence": round(m.confidence, 3),
                "reinforcement_count": m.reinforcement_count,
                "supporting_count": m.supporting_count,
                "first_observed": m.first_observed,
                "last_reinforced": m.last_reinforced,
                "tags": m.tags,
            })
        return results

    def reinforce_wisdom(self, memory_id: str, boost: float = 0.05):
        """Manually reinforce a wisdom entry (used when it proves useful)."""
        mem = self._wisdom.get(memory_id)
        if mem:
            mem.reinforce(boost)
            self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        top_5 = sorted(
            self._wisdom.values(),
            key=lambda x: x.confidence,
            reverse=True,
        )[:5]

        return {
            "total_consolidations": self._total_consolidations,
            "total_patterns": len(self._wisdom),
            "total_patterns_found": self._total_patterns_found,
            "avg_confidence": (
                sum(m.confidence for m in self._wisdom.values())
                / max(1, len(self._wisdom))
            ),
            "strongest_patterns": [
                {
                    "title": m.title,
                    "category": m.category,
                    "confidence": round(m.confidence, 3),
                    "reinforcements": m.reinforcement_count,
                    "insight": m.insight[:120],
                }
                for m in top_5
            ],
            "last_consolidation": (
                self._cycles[-1].timestamp if self._cycles else None
            ),
            "total_cycles": len(self._cycles),
            "wisdom_summary": self._wisdom_summary[:300] if self._wisdom_summary else None,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _select_batch(self, memories: List[str], max_size: int = 100) -> List[str]:
        """Select a diverse batch of memories for consolidation."""
        if len(memories) <= max_size:
            return memories

        # Take recent half + random sample from older half
        recent = memories[-max_size // 2:]
        older = memories[:-max_size // 2]

        import random
        sample_size = min(max_size - len(recent), len(older))
        sampled = random.sample(older, sample_size) if sample_size > 0 else []

        return sampled + recent

    def _find_similar(self, title: str, insight: str) -> Optional[ConsolidatedMemory]:
        """Find an existing pattern similar to the new one."""
        title_lower = title.lower()
        insight_words = set(insight.lower().split()[:15])

        for mem in self._wisdom.values():
            # Title overlap
            if title_lower in mem.title.lower() or mem.title.lower() in title_lower:
                return mem
            # Significant word overlap in insight
            mem_words = set(mem.insight.lower().split()[:15])
            overlap = len(insight_words & mem_words)
            if overlap >= 5:
                return mem

        return None

    def _parse_json_array(self, text: str) -> Optional[List[dict]]:
        import re
        match = re.search(r'\[[\s\S]*?\]', text)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "total_consolidations": self._total_consolidations,
                "total_patterns_found": self._total_patterns_found,
                "last_consolidation_tick": self._last_consolidation_tick,
                "wisdom_summary": self._wisdom_summary,
                "wisdom": {
                    k: asdict(v) for k, v in self._wisdom.items()
                },
                "cycles": [asdict(c) for c in self._cycles[-50:]],  # Keep last 50
            }
            (self._dir / "ultra_ltm_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"UltraLTM: Save state failed: {e}")

    def _load_state(self):
        sf = self._dir / "ultra_ltm_state.json"
        if not sf.exists():
            return
        try:
            state = json.loads(sf.read_text())
            self._total_consolidations = state.get("total_consolidations", 0)
            self._total_patterns_found = state.get("total_patterns_found", 0)
            self._last_consolidation_tick = state.get("last_consolidation_tick", -1)
            self._wisdom_summary = state.get("wisdom_summary", "")

            for k, v in state.get("wisdom", {}).items():
                self._wisdom[k] = ConsolidatedMemory(
                    memory_id=v["memory_id"],
                    category=v.get("category", ""),
                    title=v.get("title", ""),
                    insight=v.get("insight", ""),
                    supporting_count=v.get("supporting_count", 0),
                    confidence=v.get("confidence", 0.5),
                    first_observed=v.get("first_observed", ""),
                    last_reinforced=v.get("last_reinforced", ""),
                    reinforcement_count=v.get("reinforcement_count", 1),
                    decay_rate=v.get("decay_rate", 0.01),
                    tags=v.get("tags", []),
                )

            for cd in state.get("cycles", []):
                self._cycles.append(ConsolidationCycle(
                    cycle_id=cd["cycle_id"],
                    timestamp=cd["timestamp"],
                    raw_memories_scanned=cd.get("raw_memories_scanned", 0),
                    patterns_extracted=cd.get("patterns_extracted", 0),
                    patterns_reinforced=cd.get("patterns_reinforced", 0),
                    duration_ms=cd.get("duration_ms", 0),
                ))

            logger.info(
                f"🧠 UltraLTM: Loaded {len(self._wisdom)} patterns, "
                f"{self._total_consolidations} consolidation cycles"
            )
        except Exception as e:
            logger.warning(f"UltraLTM: Load state failed: {e}")
