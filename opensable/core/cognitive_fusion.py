"""
Cognitive Fusion Reactor — cross-domain creative pollination.

WORLD FIRST: Takes solutions/patterns from one domain and applies them
to completely unrelated domains. Like biomimicry but for any knowledge.
"How could this database optimization technique help with conversation?"

Persistence: ``cognitive_fusion_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, random
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DomainKnowledge:
    domain: str = ""
    patterns: List[str] = field(default_factory=list)
    principles: List[str] = field(default_factory=list)
    last_updated: float = 0.0


@dataclass
class FusionResult:
    id: str = ""
    source_domain: str = ""
    target_domain: str = ""
    source_principle: str = ""
    fusion_idea: str = ""
    novelty_score: float = 0.0
    applied: bool = False
    timestamp: float = 0.0


class CognitiveFusion:
    """Cross-domain creative pollination engine."""

    def __init__(self, data_dir: Path, fuse_interval: int = 60, max_fusions: int = 300):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.fuse_interval = fuse_interval
        self.max_fusions = max_fusions
        self.domains: Dict[str, DomainKnowledge] = {}
        self.fusions: List[FusionResult] = []
        self.total_fusions: int = 0
        self.total_applied: int = 0
        self._load_state()

    def absorb_knowledge(self, domain: str, pattern: str, principle: str = ""):
        """Absorb knowledge from a domain for future cross-pollination."""
        if domain not in self.domains:
            self.domains[domain] = DomainKnowledge(domain=domain)
        dk = self.domains[domain]
        if pattern and pattern not in dk.patterns:
            dk.patterns.append(pattern[:200])
            if len(dk.patterns) > 50:
                dk.patterns = dk.patterns[-50:]
        if principle and principle not in dk.principles:
            dk.principles.append(principle[:200])
            if len(dk.principles) > 30:
                dk.principles = dk.principles[-30:]
        dk.last_updated = time.time()

    async def fuse(self, llm, target_problem: str = "") -> List[FusionResult]:
        """Cross-pollinate knowledge between random domain pairs."""
        if len(self.domains) < 2:
            return []

        domain_names = list(self.domains.keys())
        results = []

        # Pick 2-3 random domain pairs
        n_pairs = min(3, len(domain_names) * (len(domain_names) - 1) // 2)
        for _ in range(n_pairs):
            d1, d2 = random.sample(domain_names, 2)
            dk1, dk2 = self.domains[d1], self.domains[d2]
            if not dk1.principles and not dk1.patterns:
                continue

            source_items = dk1.principles + dk1.patterns
            source = random.choice(source_items) if source_items else ""
            if not source:
                continue

            try:
                prompt = (
                    "You are a COGNITIVE FUSION REACTOR. Take a principle/pattern from one "
                    "domain and apply it creatively to a completely different domain.\n\n"
                    f"Source domain: {d1}\nSource principle: {source}\n"
                    f"Target domain: {d2}\n"
                    + (f"Target problem: {target_problem}\n" if target_problem else "")
                    + "\nGenerate a creative cross-domain fusion. Respond in JSON:\n"
                    '{"fusion_idea": "...", "novelty_score": 0.0-1.0}'
                )
                resp = await llm.chat_raw(prompt, max_tokens=300)
                text = resp if isinstance(resp, str) else str(resp)
                s = text.find("{")
                e = text.rfind("}") + 1
                if s >= 0 and e > s:
                    data = json.loads(text[s:e])
                    fr = FusionResult(
                        id=f"fusion_{self.total_fusions}_{int(time.time())}",
                        source_domain=d1, target_domain=d2,
                        source_principle=source,
                        fusion_idea=data.get("fusion_idea", ""),
                        novelty_score=float(data.get("novelty_score", 0.5)),
                        timestamp=time.time(),
                    )
                    results.append(fr)
                    self.fusions.append(fr)
                    self.total_fusions += 1
            except Exception as ex:
                logger.debug(f"Fusion failed: {ex}")

        if len(self.fusions) > self.max_fusions:
            self.fusions = self.fusions[-self.max_fusions:]
        self._save_state()
        return results

    def mark_applied(self, fusion_id: str):
        for f in self.fusions:
            if f.id == fusion_id:
                f.applied = True
                self.total_applied += 1
                break
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_domains": len(self.domains),
            "total_fusions": self.total_fusions,
            "total_applied": self.total_applied,
            "domains": list(self.domains.keys()),
            "recent_fusions": [
                {"source": f.source_domain, "target": f.target_domain,
                 "idea": f.fusion_idea[:150], "novelty": f.novelty_score}
                for f in self.fusions[-5:]
            ],
        }

    def _save_state(self):
        try:
            state = {
                "total_fusions": self.total_fusions,
                "total_applied": self.total_applied,
                "domains": {k: asdict(v) for k, v in self.domains.items()},
                "fusions": [asdict(f) for f in self.fusions[-100:]],
            }
            (self.data_dir / "cognitive_fusion_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Cognitive fusion save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "cognitive_fusion_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_fusions = data.get("total_fusions", 0)
                self.total_applied = data.get("total_applied", 0)
                for k, v in data.get("domains", {}).items():
                    self.domains[k] = DomainKnowledge(**{kk: vv for kk, vv in v.items()
                                                         if kk in DomainKnowledge.__dataclass_fields__})
                for fd in data.get("fusions", []):
                    self.fusions.append(FusionResult(**{kk: vv for kk, vv in fd.items()
                                                        if kk in FusionResult.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Cognitive fusion load failed: {e}")
