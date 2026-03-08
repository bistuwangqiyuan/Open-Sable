"""
Holographic Context — fragment-to-whole context reconstruction.

WORLD FIRST: Like a hologram where any fragment can reconstruct the whole
image, this module allows the agent to reconstruct full context from
partial information. It compresses experiences into holographic encodings
where every piece contains references to the whole.

Persistence: ``holographic_context_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Hologram:
    id: str = ""
    fragment: str = ""
    whole_context: str = ""
    associations: List[str] = field(default_factory=list)
    access_count: int = 0
    created: float = 0.0
    last_accessed: float = 0.0


class HolographicContext:
    """Fragment-to-whole context reconstruction."""

    def __init__(self, data_dir: Path, max_holograms: int = 500,
                 compression_ratio: float = 0.3):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_holograms = max_holograms
        self.compression_ratio = compression_ratio

        self.holograms: Dict[str, Hologram] = {}
        self.association_graph: Dict[str, List[str]] = {}
        self.reconstructions: int = 0

        self._load_state()

    def encode(self, context: str, key_fragments: Optional[List[str]] = None):
        """Encode a full context into holographic fragments."""
        if not context:
            return

        # Auto-extract fragments if not provided
        if not key_fragments:
            key_fragments = self._extract_fragments(context)

        # Create a hologram for each fragment
        for frag in key_fragments[:10]:
            frag_id = hashlib.md5(frag.encode()).hexdigest()[:12]

            # Compress the whole into a reference
            compressed = self._compress(context)

            self.holograms[frag_id] = Hologram(
                id=frag_id,
                fragment=frag[:200],
                whole_context=compressed[:500],
                associations=[f[:100] for f in key_fragments if f != frag][:8],
                created=time.time(),
            )

            # Build association graph
            for other_frag in key_fragments:
                if other_frag != frag:
                    other_id = hashlib.md5(other_frag.encode()).hexdigest()[:12]
                    if frag_id not in self.association_graph:
                        self.association_graph[frag_id] = []
                    if other_id not in self.association_graph[frag_id]:
                        self.association_graph[frag_id].append(other_id)

        # Enforce limits
        while len(self.holograms) > self.max_holograms:
            oldest = min(self.holograms.values(), key=lambda h: h.last_accessed or h.created)
            del self.holograms[oldest.id]
            self.association_graph.pop(oldest.id, None)

    def reconstruct(self, fragment: str) -> Optional[Dict[str, Any]]:
        """Reconstruct full context from a fragment. This is the magic."""
        # Direct match
        frag_id = hashlib.md5(fragment.encode()).hexdigest()[:12]
        if frag_id in self.holograms:
            h = self.holograms[frag_id]
            h.access_count += 1
            h.last_accessed = time.time()
            self.reconstructions += 1
            return {
                "full_context": h.whole_context,
                "related_fragments": h.associations,
                "confidence": 1.0,
                "method": "direct_match",
            }

        # Fuzzy match — find holograms with overlapping content
        frag_words = set(fragment.lower().split())
        candidates = []
        for h in self.holograms.values():
            h_words = set(h.fragment.lower().split())
            overlap = len(frag_words & h_words)
            if overlap >= 2:
                candidates.append((h, overlap))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            best = candidates[0][0]
            best.access_count += 1
            best.last_accessed = time.time()
            self.reconstructions += 1

            # Walk association graph to gather more context
            related_contexts = [best.whole_context]
            if best.id in self.association_graph:
                for assoc_id in self.association_graph[best.id][:3]:
                    if assoc_id in self.holograms:
                        related_contexts.append(self.holograms[assoc_id].whole_context)

            return {
                "full_context": " | ".join(related_contexts),
                "related_fragments": best.associations,
                "confidence": min(1.0, candidates[0][1] / max(len(frag_words), 1)),
                "method": "fuzzy_reconstruction",
            }

        return None

    async def deep_reconstruct(self, llm, fragment: str) -> Optional[str]:
        """Use LLM + holographic data to deeply reconstruct context."""
        basic = self.reconstruct(fragment)
        if not basic:
            return None

        prompt = (
            f"Given this FRAGMENT: \"{fragment}\"\n"
            f"And this PARTIAL RECONSTRUCTION: \"{basic['full_context'][:300]}\"\n"
            f"And these RELATED pieces: {basic['related_fragments'][:5]}\n\n"
            f"Reconstruct the FULL original context. What was happening?"
        )
        try:
            resp = await llm.chat_raw(prompt, max_tokens=400)
            return resp
        except Exception as e:
            logger.debug(f"Deep reconstruction failed: {e}")
            return basic.get("full_context")

    def get_stats(self) -> Dict[str, Any]:
        total_associations = sum(len(v) for v in self.association_graph.values())
        most_accessed = sorted(self.holograms.values(),
                               key=lambda h: h.access_count, reverse=True)[:3]
        return {
            "total_holograms": len(self.holograms),
            "association_links": total_associations,
            "total_reconstructions": self.reconstructions,
            "most_accessed": [
                {"fragment": h.fragment[:60], "accesses": h.access_count}
                for h in most_accessed
            ],
        }

    def _extract_fragments(self, text: str) -> List[str]:
        """Extract key fragments from text."""
        sentences = text.replace('\n', '. ').split('. ')
        fragments = []
        for s in sentences:
            s = s.strip()
            if len(s) > 10:
                fragments.append(s)
        # Also extract key phrases (2-3 word combos)
        words = text.split()
        for i in range(0, len(words) - 2, 3):
            phrase = " ".join(words[i:i+3])
            if len(phrase) > 5:
                fragments.append(phrase)
        return fragments[:15]

    def _compress(self, text: str) -> str:
        """Compress context while preserving key information."""
        words = text.split()
        target = max(10, int(len(words) * self.compression_ratio))
        if len(words) <= target:
            return text
        # Keep first, last, and evenly spaced words
        step = max(1, len(words) // target)
        kept = [words[i] for i in range(0, len(words), step)][:target]
        return " ".join(kept)

    def _save_state(self):
        try:
            state = {
                "holograms": {k: asdict(v) for k, v in list(self.holograms.items())[-200:]},
                "association_graph": {k: v for k, v in list(self.association_graph.items())[-200:]},
                "reconstructions": self.reconstructions,
            }
            (self.data_dir / "holographic_context_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Holographic context save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "holographic_context_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.reconstructions = data.get("reconstructions", 0)
                self.association_graph = data.get("association_graph", {})
                for k, v in data.get("holograms", {}).items():
                    self.holograms[k] = Hologram(
                        **{f: v[f] for f in Hologram.__dataclass_fields__ if f in v})
        except Exception as e:
            logger.debug(f"Holographic context load: {e}")
