"""
Cognitive Archaeology,  past decision chain reconstruction.

WORLD FIRST: The agent can "excavate" its own past decisions, reconstructing
the full reasoning chain that led to any outcome,  even when the original
reasoning was not explicitly logged. Like an archaeologist piecing together
ancient civilizations from fragments.

Persistence: ``cognitive_archaeology_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionFossil:
    id: str = ""
    action: str = ""
    context: str = ""
    outcome: str = ""
    tick: int = 0
    timestamp: float = 0.0
    parent_id: str = ""  # Chain to previous decision
    tags: List[str] = field(default_factory=list)


@dataclass
class Excavation:
    id: str = ""
    query: str = ""
    chain: List[str] = field(default_factory=list)  # fossil IDs
    reconstruction: str = ""
    depth: int = 0
    created: float = 0.0


class CognitiveArchaeology:
    """Excavates and reconstructs past decision chains."""

    def __init__(self, data_dir: Path, max_fossils: int = 2000,
                 max_chain_depth: int = 20):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_fossils = max_fossils
        self.max_chain_depth = max_chain_depth

        self.fossils: Dict[str, DecisionFossil] = {}
        self.excavations: List[Excavation] = []
        self.current_chain_head: str = ""

        self._load_state()

    def bury(self, action: str, context: str = "", outcome: str = "",
             tick: int = 0, tags: Optional[List[str]] = None):
        """Record a decision as a fossil in the record."""
        fossil_id = uuid.uuid4().hex[:10]
        fossil = DecisionFossil(
            id=fossil_id,
            action=action[:300],
            context=context[:300],
            outcome=outcome[:200],
            tick=tick,
            timestamp=time.time(),
            parent_id=self.current_chain_head,
            tags=tags or [],
        )
        self.fossils[fossil_id] = fossil
        self.current_chain_head = fossil_id

        # Enforce limits
        if len(self.fossils) > self.max_fossils:
            oldest = sorted(self.fossils.values(), key=lambda f: f.timestamp)
            for f in oldest[:100]:
                del self.fossils[f.id]

    def excavate(self, query: str) -> List[Dict[str, Any]]:
        """Find fossils matching a query and reconstruct the chain."""
        query_words = set(query.lower().split())
        matches = []

        for fossil in self.fossils.values():
            fossil_words = set(
                (fossil.action + " " + fossil.context + " " + fossil.outcome).lower().split()
            )
            overlap = len(query_words & fossil_words)
            if overlap >= 2:
                matches.append((fossil, overlap))

        matches.sort(key=lambda x: x[1], reverse=True)

        results = []
        for fossil, score in matches[:5]:
            chain = self._trace_chain(fossil.id)
            results.append({
                "fossil_id": fossil.id,
                "action": fossil.action,
                "outcome": fossil.outcome,
                "tick": fossil.tick,
                "relevance": score,
                "chain_depth": len(chain),
                "chain": [
                    {"action": self.fossils[fid].action[:80],
                     "outcome": self.fossils[fid].outcome[:60]}
                    for fid in chain if fid in self.fossils
                ][:5],
            })

        return results

    async def deep_excavation(self, llm, question: str) -> Dict[str, Any]:
        """LLM-powered deep excavation,  reconstruct WHY something happened."""
        # Find relevant fossils
        raw_results = self.excavate(question)
        if not raw_results:
            return {"reconstruction": "No relevant decision history found.", "fossils": 0}

        # Build the archaeological record
        record = "\n".join(
            f"[Tick {r['tick']}] Action: {r['action']} → Outcome: {r['outcome']}\n"
            f"  Chain: {' → '.join(c['action'] for c in r['chain'])}"
            for r in raw_results[:3]
        )

        prompt = (
            f"As a cognitive archaeologist, reconstruct the full decision history "
            f"that answers: \"{question}\"\n\n"
            f"Archaeological record:\n{record}\n\n"
            f"Reconstruct the COMPLETE story: what decisions led to what, "
            f"and WHY the agent made each choice. Include lessons learned."
        )

        try:
            resp = await llm.chat_raw(prompt, max_tokens=500)
            exc = Excavation(
                id=uuid.uuid4().hex[:10],
                query=question[:200],
                chain=[r["fossil_id"] for r in raw_results],
                reconstruction=resp[:600],
                depth=sum(r["chain_depth"] for r in raw_results),
                created=time.time(),
            )
            self.excavations.append(exc)
            if len(self.excavations) > 50:
                self.excavations = self.excavations[-50:]

            return {
                "reconstruction": resp,
                "fossils_examined": len(raw_results),
                "chain_depth": exc.depth,
            }
        except Exception as e:
            logger.debug(f"Deep excavation failed: {e}")
            return {"reconstruction": record, "fossils": len(raw_results)}

    def _trace_chain(self, fossil_id: str) -> List[str]:
        """Trace back the decision chain from a fossil."""
        chain = []
        current = fossil_id
        depth = 0
        while current and depth < self.max_chain_depth:
            chain.append(current)
            if current in self.fossils:
                current = self.fossils[current].parent_id
            else:
                break
            depth += 1
        return list(reversed(chain))

    def get_timeline(self, last_n: int = 20) -> List[Dict[str, Any]]:
        """Get recent decision timeline."""
        recent = sorted(self.fossils.values(), key=lambda f: f.timestamp)[-last_n:]
        return [
            {"tick": f.tick, "action": f.action[:80], "outcome": f.outcome[:60],
             "tags": f.tags}
            for f in recent
        ]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_fossils": len(self.fossils),
            "excavations": len(self.excavations),
            "chain_head": self.current_chain_head[:10] if self.current_chain_head else None,
            "recent_decisions": self.get_timeline(3),
            "deepest_chain": max(
                (e.depth for e in self.excavations), default=0),
        }

    def _save_state(self):
        try:
            state = {
                "fossils": {k: asdict(v) for k, v in list(self.fossils.items())[-500:]},
                "excavations": [asdict(e) for e in self.excavations[-20:]],
                "current_chain_head": self.current_chain_head,
            }
            (self.data_dir / "cognitive_archaeology_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Cognitive archaeology save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "cognitive_archaeology_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.current_chain_head = data.get("current_chain_head", "")
                for k, v in data.get("fossils", {}).items():
                    self.fossils[k] = DecisionFossil(
                        **{f: v[f] for f in DecisionFossil.__dataclass_fields__ if f in v})
                for ed in data.get("excavations", []):
                    self.excavations.append(Excavation(
                        **{f: ed[f] for f in Excavation.__dataclass_fields__ if f in ed}))
        except Exception as e:
            logger.debug(f"Cognitive archaeology load: {e}")
