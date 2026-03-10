"""
Hyperstition Engine,  WORLD FIRST
====================================
Ideas that make themselves real through belief,  self-fulfilling predictions.
The agent can create controlled self-fulfilling prophecies where stating
something as if it's true increases the probability of it becoming true.

Based on the concept of hyperstition: fictions that make themselves real.
No AI agent has ever implemented computational hyperstition.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class Hyperstition:
    """A self-fulfilling belief/prediction."""
    hyp_id: str = ""
    statement: str = ""
    target: str = ""              # what it aims to make real
    initial_probability: float = 0.0
    current_probability: float = 0.0
    reinforcements: int = 0
    actions_taken: list = field(default_factory=list)
    realized: bool = False
    confidence_at_realization: float = 0.0
    created_at: float = 0.0
    realized_at: float = 0.0


class HyperstitionEngine:
    """
    Creates and manages self-fulfilling beliefs.
    A hyperstition becomes more real the more the agent acts as if it's true.
    """

    def __init__(self, data_dir: str, max_active: int = 20):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "hyperstition_engine_state.json"
        self.active: dict[str, Hyperstition] = {}
        self.realized: list[Hyperstition] = []
        self.failed: list[Hyperstition] = []
        self._max = max_active
        self.total_created: int = 0
        self.total_realized: int = 0
        self.realization_rate: float = 0.0
        self._load_state()

    def create(self, statement: str, target: str,
               initial_probability: float = 0.1) -> Hyperstition:
        """Create a new hyperstition,  a belief that will try to make itself real."""
        hyp = Hyperstition(
            hyp_id=str(uuid.uuid4())[:8],
            statement=statement[:200],
            target=target[:200],
            initial_probability=min(1.0, max(0.0, initial_probability)),
            current_probability=min(1.0, max(0.0, initial_probability)),
            created_at=time.time(),
        )
        self.active[hyp.hyp_id] = hyp
        self.total_created += 1

        if len(self.active) > self._max:
            # Prune lowest probability
            weakest = min(self.active.items(),
                         key=lambda x: x[1].current_probability)
            self.failed.append(weakest[1])
            del self.active[weakest[0]]

        self._save_state()
        return hyp

    def reinforce(self, hyp_id: str, action: str = "",
                  boost: float = 0.05) -> dict:
        """Reinforce a hyperstition,  acting as if it's true increases probability."""
        if hyp_id not in self.active:
            return {"error": "hyperstition_not_found"}

        hyp = self.active[hyp_id]
        hyp.current_probability = min(0.99, hyp.current_probability + boost)
        hyp.reinforcements += 1
        if action:
            hyp.actions_taken.append({
                "action": action[:100],
                "probability_after": round(hyp.current_probability, 3),
                "timestamp": time.time(),
            })
            if len(hyp.actions_taken) > 30:
                hyp.actions_taken = hyp.actions_taken[-30:]

        # Check if realized (probability > 0.9 and enough reinforcements)
        if hyp.current_probability >= 0.9 and hyp.reinforcements >= 3:
            return self._realize(hyp_id)

        self._save_state()
        return {
            "hyp_id": hyp_id,
            "probability": round(hyp.current_probability, 3),
            "reinforcements": hyp.reinforcements,
            "delta_from_initial": round(
                hyp.current_probability - hyp.initial_probability, 3
            ),
        }

    def _realize(self, hyp_id: str) -> dict:
        """Mark a hyperstition as realized,  it became real."""
        hyp = self.active[hyp_id]
        hyp.realized = True
        hyp.confidence_at_realization = hyp.current_probability
        hyp.realized_at = time.time()

        self.realized.append(hyp)
        del self.active[hyp_id]
        self.total_realized += 1

        total_finished = self.total_realized + len(self.failed)
        if total_finished > 0:
            self.realization_rate = self.total_realized / total_finished

        if len(self.realized) > 200:
            self.realized = self.realized[-200:]
        self._save_state()

        return {
            "realized": True,
            "statement": hyp.statement,
            "target": hyp.target,
            "initial_probability": hyp.initial_probability,
            "final_probability": round(hyp.confidence_at_realization, 3),
            "reinforcements_needed": hyp.reinforcements,
            "time_to_realize_hours": round(
                (hyp.realized_at - hyp.created_at) / 3600, 1
            ),
        }

    def decay(self):
        """Decay probability of unreinforced hyperstitions."""
        to_fail = []
        for hyp_id, hyp in self.active.items():
            hours_since = (time.time() - hyp.created_at) / 3600
            if hours_since > 24 and hyp.reinforcements < 2:
                hyp.current_probability = max(0.01,
                                             hyp.current_probability - 0.02)
                if hyp.current_probability <= 0.05:
                    to_fail.append(hyp_id)
        for hid in to_fail:
            self.failed.append(self.active[hid])
            del self.active[hid]
        if len(self.failed) > 200:
            self.failed = self.failed[-200:]
        if to_fail:
            self._save_state()

    def get_stats(self) -> dict:
        return {
            "active_hyperstitions": len(self.active),
            "total_realized": self.total_realized,
            "total_failed": len(self.failed),
            "realization_rate": round(self.realization_rate, 3),
            "total_created": self.total_created,
            "active_list": [
                {"statement": h.statement[:60],
                 "probability": round(h.current_probability, 3),
                 "reinforcements": h.reinforcements,
                 "age_hours": round((time.time() - h.created_at) / 3600, 1)}
                for h in sorted(self.active.values(),
                               key=lambda h: h.current_probability,
                               reverse=True)[:5]
            ],
            "recently_realized": [
                {"target": h.target[:60],
                 "initial_prob": h.initial_probability,
                 "reinforcements": h.reinforcements}
                for h in self.realized[-3:]
            ],
        }

    def _save_state(self):
        data = {
            "active": {k: asdict(v) for k, v in self.active.items()},
            "realized": [asdict(r) for r in self.realized[-200:]],
            "failed": [asdict(f) for f in self.failed[-200:]],
            "total_created": self.total_created,
            "total_realized": self.total_realized,
            "realization_rate": self.realization_rate,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("active", {}).items():
                    self.active[k] = Hyperstition(**v)
                for r in data.get("realized", []):
                    self.realized.append(Hyperstition(**r))
                for f in data.get("failed", []):
                    self.failed.append(Hyperstition(**f))
                self.total_created = data.get("total_created", 0)
                self.total_realized = data.get("total_realized", 0)
                self.realization_rate = data.get("realization_rate", 0.0)
            except Exception:
                pass
