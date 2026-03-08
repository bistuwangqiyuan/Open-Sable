"""
Curiosity Drive — intrinsic motivation and boredom detection.

WORLD FIRST: The agent gets "bored" with repetitive tasks and actively
seeks novel challenges. Drives self-directed exploration and prevents
stagnation through information-theoretic novelty scoring.

Persistence: ``curiosity_drive_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib, math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CuriosityProbe:
    question: str = ""
    domain: str = ""
    novelty_score: float = 0.0
    explored: bool = False
    result: str = ""
    timestamp: float = 0.0


class CuriosityDrive:
    """Intrinsic motivation — boredom detection and novelty seeking."""

    def __init__(self, data_dir: Path, boredom_threshold: int = 5,
                 novelty_decay: float = 0.02, max_probes: int = 200):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.boredom_threshold = boredom_threshold
        self.novelty_decay = novelty_decay
        self.max_probes = max_probes

        self.task_history: List[str] = []
        self.repetition_count: Dict[str, int] = {}
        self.boredom_level: float = 0.0
        self.curiosity_level: float = 0.5
        self.probes: List[CuriosityProbe] = []
        self.total_explorations: int = 0
        self.domains_explored: Dict[str, int] = {}
        self.novelty_scores: List[float] = []

        self._load_state()

    def observe_task(self, task_description: str) -> float:
        """Observe a task and update boredom/curiosity levels."""
        fingerprint = self._fingerprint(task_description)
        self.task_history.append(fingerprint)
        self.repetition_count[fingerprint] = self.repetition_count.get(fingerprint, 0) + 1

        # Calculate novelty (inverse of familiarity)
        familiarity = min(self.repetition_count[fingerprint] / 10.0, 1.0)
        novelty = 1.0 - familiarity
        self.novelty_scores.append(novelty)
        if len(self.novelty_scores) > 100:
            self.novelty_scores = self.novelty_scores[-100:]

        # Update boredom — increases with repetition
        if self.repetition_count[fingerprint] >= self.boredom_threshold:
            self.boredom_level = min(1.0, self.boredom_level + 0.1)
        else:
            self.boredom_level = max(0.0, self.boredom_level - 0.05)

        # Update curiosity — increases with boredom, decreases with novelty
        self.curiosity_level = 0.3 + 0.4 * self.boredom_level + 0.3 * (1.0 - self._avg_novelty())

        if len(self.task_history) > 500:
            self.task_history = self.task_history[-500:]

        return novelty

    def is_bored(self) -> bool:
        return self.boredom_level >= 0.6

    def get_curiosity_level(self) -> float:
        return self.curiosity_level

    async def generate_curiosity_probes(self, llm, context: str = "") -> List[CuriosityProbe]:
        """Generate questions the agent is curious about."""
        try:
            explored = list(self.domains_explored.keys())[:10]
            prompt = (
                "You are an AI agent's CURIOSITY DRIVE. The agent is getting bored with "
                "repetitive tasks and needs novel challenges to explore.\n\n"
                f"Boredom level: {self.boredom_level:.2f}\n"
                f"Already explored domains: {explored}\n"
                f"Context: {context[:300]}\n\n"
                "Generate 3 curiosity probes — novel questions or challenges the agent "
                "should explore to learn something new. Respond in JSON:\n"
                '[{"question": "...", "domain": "...", "novelty_score": 0.0-1.0}]'
            )
            resp = await llm.chat_raw(prompt, max_tokens=400)
            text = resp if isinstance(resp, str) else str(resp)
            s = text.find("[")
            e = text.rfind("]") + 1
            if s >= 0 and e > s:
                items = json.loads(text[s:e])
                probes = []
                for item in items[:3]:
                    probe = CuriosityProbe(
                        question=item.get("question", ""),
                        domain=item.get("domain", "general"),
                        novelty_score=float(item.get("novelty_score", 0.7)),
                        timestamp=time.time(),
                    )
                    probes.append(probe)
                    self.probes.append(probe)
                    self.total_explorations += 1
                if len(self.probes) > self.max_probes:
                    self.probes = self.probes[-self.max_probes:]
                self._save_state()
                return probes
        except Exception as e:
            logger.debug(f"Curiosity probe generation failed: {e}")
        return []

    def record_exploration(self, probe_question: str, domain: str, result: str):
        """Record the result of exploring a curiosity probe."""
        self.domains_explored[domain] = self.domains_explored.get(domain, 0) + 1
        # Satisfy curiosity — reduce boredom
        self.boredom_level = max(0.0, self.boredom_level - 0.15)
        for p in self.probes:
            if p.question == probe_question:
                p.explored = True
                p.result = result[:300]
                break
        self._save_state()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "boredom_level": round(self.boredom_level, 2),
            "curiosity_level": round(self.curiosity_level, 2),
            "is_bored": self.is_bored(),
            "avg_novelty": round(self._avg_novelty(), 2),
            "total_explorations": self.total_explorations,
            "unique_tasks": len(self.repetition_count),
            "domains_explored": self.domains_explored,
            "recent_probes": [
                {"question": p.question[:100], "domain": p.domain,
                 "novelty": p.novelty_score, "explored": p.explored}
                for p in self.probes[-5:]
            ],
        }

    def _fingerprint(self, text: str) -> str:
        words = sorted(set(text.lower().split()))[:10]
        return hashlib.md5(" ".join(words).encode()).hexdigest()[:8]

    def _avg_novelty(self) -> float:
        if not self.novelty_scores:
            return 0.5
        return sum(self.novelty_scores[-20:]) / len(self.novelty_scores[-20:])

    def _save_state(self):
        try:
            state = {
                "boredom_level": self.boredom_level,
                "curiosity_level": self.curiosity_level,
                "total_explorations": self.total_explorations,
                "repetition_count": dict(list(self.repetition_count.items())[-200:]),
                "domains_explored": self.domains_explored,
                "novelty_scores": self.novelty_scores[-50:],
                "probes": [asdict(p) for p in self.probes[-50:]],
            }
            (self.data_dir / "curiosity_drive_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Curiosity drive save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "curiosity_drive_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.boredom_level = data.get("boredom_level", 0.0)
                self.curiosity_level = data.get("curiosity_level", 0.5)
                self.total_explorations = data.get("total_explorations", 0)
                self.repetition_count = data.get("repetition_count", {})
                self.domains_explored = data.get("domains_explored", {})
                self.novelty_scores = data.get("novelty_scores", [])
                for pd in data.get("probes", []):
                    self.probes.append(CuriosityProbe(**{k: v for k, v in pd.items()
                                                         if k in CuriosityProbe.__dataclass_fields__}))
        except Exception as e:
            logger.debug(f"Curiosity drive load failed: {e}")
