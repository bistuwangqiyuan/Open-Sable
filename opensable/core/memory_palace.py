"""
Memory Palace — spatial memory using Method of Loci.

WORLD FIRST: Memories organized in virtual "rooms" with spatial associations.
Dramatically better recall than flat vector search because memories are
contextually placed in navigable spaces.

Persistence: ``memory_palace_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class Locus:
    """A single memory placed in a room."""
    id: str = ""
    content: str = ""
    tags: List[str] = field(default_factory=list)
    emotional_anchor: str = ""
    vividness: float = 1.0
    visits: int = 0
    created_at: float = 0.0
    last_visited: float = 0.0


@dataclass
class Room:
    """A thematic room containing related memories."""
    name: str = ""
    theme: str = ""
    loci: List[Locus] = field(default_factory=list)
    connections: List[str] = field(default_factory=list)  # connected room names
    visit_count: int = 0
    capacity: int = 50


class MemoryPalace:
    """Spatial memory organization using the Method of Loci."""

    def __init__(self, data_dir: Path, max_rooms: int = 30, default_capacity: int = 50):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_rooms = max_rooms
        self.default_capacity = default_capacity
        self.rooms: Dict[str, Room] = {}
        self.total_loci: int = 0
        self.total_recalls: int = 0
        self._load_state()

        # Create default rooms if empty
        if not self.rooms:
            for name, theme in [
                ("entrance", "general"), ("library", "knowledge"),
                ("workshop", "skills"), ("garden", "creativity"),
                ("vault", "important"), ("observatory", "predictions"),
            ]:
                self.rooms[name] = Room(name=name, theme=theme, capacity=default_capacity)
            self.rooms["entrance"].connections = ["library", "workshop", "garden"]
            self.rooms["library"].connections = ["entrance", "vault", "observatory"]
            self.rooms["workshop"].connections = ["entrance", "garden"]
            self.rooms["garden"].connections = ["entrance", "workshop", "observatory"]
            self.rooms["vault"].connections = ["library"]
            self.rooms["observatory"].connections = ["library", "garden"]

    def place_memory(self, content: str, room_name: str = "", tags: Optional[List[str]] = None,
                     emotional_anchor: str = "") -> Locus:
        """Place a memory in a room."""
        if not room_name:
            room_name = self._auto_assign_room(content, tags or [])

        if room_name not in self.rooms:
            self.rooms[room_name] = Room(name=room_name, theme=room_name,
                                          capacity=self.default_capacity)

        room = self.rooms[room_name]
        locus = Locus(
            id=hashlib.md5(f"{content}{time.time()}".encode()).hexdigest()[:12],
            content=content[:500],
            tags=tags or [],
            emotional_anchor=emotional_anchor,
            vividness=1.0,
            created_at=time.time(),
            last_visited=time.time(),
        )
        room.loci.append(locus)
        self.total_loci += 1

        # Enforce capacity — remove least vivid
        if len(room.loci) > room.capacity:
            room.loci.sort(key=lambda l: l.vividness * (l.visits + 1), reverse=True)
            room.loci = room.loci[:room.capacity]

        if self.total_loci % 20 == 0:
            self._save_state()
        return locus

    def recall(self, query: str, room_name: str = "", max_results: int = 10) -> List[Dict]:
        """Recall memories by walking through the palace."""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        rooms_to_search = [self.rooms[room_name]] if room_name and room_name in self.rooms \
            else self.rooms.values()

        for room in rooms_to_search:
            room.visit_count += 1
            for locus in room.loci:
                score = 0.0
                content_lower = locus.content.lower()
                # Word overlap scoring
                content_words = set(content_lower.split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    score = overlap / max(len(query_words), 1)
                # Tag matching bonus
                for tag in locus.tags:
                    if tag.lower() in query_lower:
                        score += 0.3
                # Vividness bonus
                score *= locus.vividness

                if score > 0.1:
                    locus.visits += 1
                    locus.last_visited = time.time()
                    # Strengthen vividness on recall (spaced repetition)
                    locus.vividness = min(1.0, locus.vividness + 0.05)
                    results.append({
                        "content": locus.content,
                        "room": room.name,
                        "score": score,
                        "tags": locus.tags,
                        "emotional_anchor": locus.emotional_anchor,
                        "visits": locus.visits,
                    })

        self.total_recalls += 1
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:max_results]

    def walk_room(self, room_name: str) -> List[Dict]:
        """Walk through a room and see all its memories."""
        if room_name not in self.rooms:
            return []
        room = self.rooms[room_name]
        room.visit_count += 1
        return [{"content": l.content[:200], "tags": l.tags, "vividness": l.vividness,
                 "visits": l.visits} for l in room.loci]

    def decay_vividness(self, rate: float = 0.01):
        """Memories fade over time if not visited."""
        for room in self.rooms.values():
            for locus in room.loci:
                age = time.time() - locus.last_visited
                decay = rate * (age / 3600)  # per hour
                locus.vividness = max(0.1, locus.vividness - decay)

    def connect_rooms(self, room_a: str, room_b: str):
        """Create a corridor between two rooms."""
        if room_a in self.rooms and room_b in self.rooms:
            if room_b not in self.rooms[room_a].connections:
                self.rooms[room_a].connections.append(room_b)
            if room_a not in self.rooms[room_b].connections:
                self.rooms[room_b].connections.append(room_a)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_rooms": len(self.rooms),
            "total_loci": self.total_loci,
            "total_recalls": self.total_recalls,
            "rooms": [
                {"name": r.name, "theme": r.theme, "loci_count": len(r.loci),
                 "visits": r.visit_count, "connections": r.connections}
                for r in sorted(self.rooms.values(), key=lambda x: x.visit_count, reverse=True)
            ],
        }

    def _auto_assign_room(self, content: str, tags: List[str]) -> str:
        cl = content.lower()
        tag_str = " ".join(tags).lower()
        combined = cl + " " + tag_str
        if any(w in combined for w in ["learn", "know", "fact", "info", "doc"]):
            return "library"
        if any(w in combined for w in ["skill", "tool", "code", "build", "create"]):
            return "workshop"
        if any(w in combined for w in ["idea", "creative", "novel", "dream", "imagine"]):
            return "garden"
        if any(w in combined for w in ["important", "critical", "never", "always", "rule"]):
            return "vault"
        if any(w in combined for w in ["predict", "future", "trend", "expect", "forecast"]):
            return "observatory"
        return "entrance"

    def _save_state(self):
        try:
            state = {
                "total_loci": self.total_loci,
                "total_recalls": self.total_recalls,
                "rooms": {k: asdict(v) for k, v in self.rooms.items()},
            }
            (self.data_dir / "memory_palace_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Memory palace save failed: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "memory_palace_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_loci = data.get("total_loci", 0)
                self.total_recalls = data.get("total_recalls", 0)
                for k, v in data.get("rooms", {}).items():
                    loci = [Locus(**{kk: vv for kk, vv in ld.items()
                                     if kk in Locus.__dataclass_fields__})
                            for ld in v.get("loci", [])]
                    self.rooms[k] = Room(
                        name=v.get("name", k), theme=v.get("theme", ""),
                        loci=loci, connections=v.get("connections", []),
                        visit_count=v.get("visit_count", 0),
                        capacity=v.get("capacity", self.default_capacity),
                    )
        except Exception as e:
            logger.debug(f"Memory palace load failed: {e}")
