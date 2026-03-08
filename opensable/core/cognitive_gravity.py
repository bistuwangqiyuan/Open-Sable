"""
Cognitive Gravity — WORLD FIRST
================================
Ideas have MASS. The more an idea is connected and reinforced,
the more gravitational pull it has — attracting related concepts.
Creates thought black holes (obsessions) and thought nebulae (exploration zones).

No AI system models the gravitational dynamics of thought.
This agent does. Ideas orbit, collide, merge, and collapse.
"""

import json, time, uuid, math
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ThoughtBody:
    """A thought with gravitational mass."""
    body_id: str = ""
    concept: str = ""
    mass: float = 1.0          # gravitational pull
    velocity: float = 0.0      # how actively it's being explored
    orbit_parent: str = ""     # if orbiting another thought
    connections: int = 0
    reinforcements: int = 0
    last_interacted: float = 0.0
    created_at: float = 0.0
    is_black_hole: bool = False


class CognitiveGravity:
    """
    Models the gravitational dynamics of ideas.
    Heavy ideas attract lighter ones. Massive clusters become
    black holes (obsessions). Distant light ideas form nebulae.
    """

    BLACK_HOLE_MASS = 50.0
    NEBULA_THRESHOLD = 0.5
    MASS_DECAY_RATE = 0.01  # per hour

    def __init__(self, data_dir: str, max_bodies: int = 500):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "cognitive_gravity_state.json"
        self.bodies: dict[str, ThoughtBody] = {}
        self.collisions: list[dict] = []
        self.black_holes: list[str] = []
        self._max = max_bodies
        self._load_state()

    def add_thought(self, concept: str, initial_mass: float = 1.0) -> ThoughtBody:
        """Add a new thought body to the gravitational field."""
        key = concept.lower().strip()
        if key in self.bodies:
            # Reinforce existing thought — increases mass
            body = self.bodies[key]
            body.mass += initial_mass * 0.5
            body.reinforcements += 1
            body.last_interacted = time.time()
            self._check_black_hole(body)
            self._save_state()
            return body

        body = ThoughtBody(
            body_id=str(uuid.uuid4())[:8],
            concept=concept,
            mass=initial_mass,
            velocity=1.0,
            connections=0,
            reinforcements=1,
            last_interacted=time.time(),
            created_at=time.time(),
        )
        self.bodies[key] = body

        # Check gravitational attraction to existing bodies
        self._apply_gravity(body)

        if len(self.bodies) > self._max:
            self._evict_lightest()

        self._save_state()
        return body

    def _apply_gravity(self, new_body: ThoughtBody):
        """Apply gravitational attraction — heavy thoughts pull light ones."""
        words_new = set(new_body.concept.lower().split())
        for key, body in self.bodies.items():
            if body.body_id == new_body.body_id:
                continue
            words_existing = set(body.concept.lower().split())
            overlap = len(words_new & words_existing)
            if overlap > 0:
                # Gravitational force: proportional to mass and inverseness of distance
                distance = max(1, 5 - overlap)
                force = (body.mass * new_body.mass) / (distance ** 2)
                if force > 2.0 and body.mass > new_body.mass:
                    new_body.orbit_parent = body.body_id
                    body.connections += 1
                    new_body.connections += 1

    def _check_black_hole(self, body: ThoughtBody):
        """Check if a thought has become a black hole (obsession)."""
        if body.mass >= self.BLACK_HOLE_MASS and not body.is_black_hole:
            body.is_black_hole = True
            if body.body_id not in self.black_holes:
                self.black_holes.append(body.body_id)

    def collide(self, concept_a: str, concept_b: str) -> dict:
        """Force two thoughts to collide, potentially merging."""
        a_key = concept_a.lower().strip()
        b_key = concept_b.lower().strip()
        if a_key not in self.bodies or b_key not in self.bodies:
            return {"merged": False, "reason": "body_not_found"}

        a = self.bodies[a_key]
        b = self.bodies[b_key]

        # Merge: heavier absorbs lighter
        if a.mass >= b.mass:
            a.mass += b.mass * 0.7  # some mass lost in collision
            a.connections += b.connections
            a.reinforcements += b.reinforcements
            del self.bodies[b_key]
            winner, loser = a, b
        else:
            b.mass += a.mass * 0.7
            b.connections += a.connections
            b.reinforcements += a.reinforcements
            del self.bodies[a_key]
            winner, loser = b, a

        self._check_black_hole(winner)

        collision = {
            "winner": winner.concept,
            "absorbed": loser.concept,
            "new_mass": round(winner.mass, 2),
            "timestamp": time.time(),
        }
        self.collisions.append(collision)
        if len(self.collisions) > 200:
            self.collisions = self.collisions[-200:]
        self._save_state()
        return {"merged": True, **collision}

    def decay(self):
        """Apply mass decay — forgotten thoughts lose mass over time."""
        now = time.time()
        to_remove = []
        for key, body in self.bodies.items():
            hours_since = (now - body.last_interacted) / 3600
            decay = self.MASS_DECAY_RATE * hours_since
            body.mass = max(0.1, body.mass - decay)
            if body.mass <= 0.1 and hours_since > 72:
                to_remove.append(key)
            # Check if black hole collapses
            if body.is_black_hole and body.mass < self.BLACK_HOLE_MASS * 0.5:
                body.is_black_hole = False
                if body.body_id in self.black_holes:
                    self.black_holes.remove(body.body_id)
        for k in to_remove:
            del self.bodies[k]
        if to_remove:
            self._save_state()

    def get_heaviest(self, n: int = 10) -> list:
        """Get the heaviest thoughts (most gravitational pull)."""
        sorted_bodies = sorted(self.bodies.values(), key=lambda b: b.mass, reverse=True)
        return [{"concept": b.concept, "mass": round(b.mass, 2),
                 "connections": b.connections, "is_black_hole": b.is_black_hole}
                for b in sorted_bodies[:n]]

    def get_nebulae(self) -> list:
        """Get light, recently created thoughts (exploration zones)."""
        return [{"concept": b.concept, "mass": round(b.mass, 2), "age_hours":
                 round((time.time() - b.created_at) / 3600, 1)}
                for b in self.bodies.values()
                if b.mass < self.NEBULA_THRESHOLD and
                (time.time() - b.created_at) < 86400]

    def _evict_lightest(self):
        """Remove the lightest thought to make room."""
        if not self.bodies:
            return
        lightest = min(self.bodies.keys(), key=lambda k: self.bodies[k].mass)
        del self.bodies[lightest]

    def get_stats(self) -> dict:
        return {
            "total_thoughts": len(self.bodies),
            "black_holes": len(self.black_holes),
            "total_collisions": len(self.collisions),
            "heaviest": self.get_heaviest(5),
            "nebulae_count": len(self.get_nebulae()),
            "total_mass": round(sum(b.mass for b in self.bodies.values()), 2),
            "avg_mass": round(
                sum(b.mass for b in self.bodies.values()) /
                max(len(self.bodies), 1), 2
            ),
        }

    def _save_state(self):
        data = {
            "bodies": {k: asdict(v) for k, v in self.bodies.items()},
            "collisions": self.collisions[-200:],
            "black_holes": self.black_holes,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("bodies", {}).items():
                    self.bodies[k] = ThoughtBody(**v)
                self.collisions = data.get("collisions", [])
                self.black_holes = data.get("black_holes", [])
            except Exception:
                pass
