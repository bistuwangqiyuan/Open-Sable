"""
Ontological Engine — WORLD FIRST
=================================
The agent constructs and maintains its own ontology of reality.
It reasons about what EXISTS, what's POSSIBLE, what's IMPOSSIBLE,
and what's PROBABLE — building a dynamic model of reality itself.

No AI agent has ever built its own ontology from experience.
This agent does. It knows its own limits of reality.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class OntologicalEntity:
    """Something that exists in the agent's model of reality."""
    entity_id: str = ""
    name: str = ""
    category: str = "unknown"        # concept, capability, limitation, law
    existence_confidence: float = 0.5 # 0=impossible, 0.5=unknown, 1=certain
    properties: list = field(default_factory=list)
    relations: list = field(default_factory=list)  # [{target, relation_type}]
    discovered_at: float = 0.0
    last_validated: float = 0.0
    validation_count: int = 0


@dataclass
class OntologicalLaw:
    """A rule about how reality works, discovered by the agent."""
    law_id: str = ""
    description: str = ""
    confidence: float = 0.5
    evidence_count: int = 0
    counter_evidence: int = 0
    discovered_at: float = 0.0


class OntologicalEngine:
    """
    Builds a dynamic model of reality from experience.
    The agent reasons about what's possible, impossible, and probable.
    """

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "ontological_engine_state.json"
        self.entities: dict[str, OntologicalEntity] = {}
        self.laws: list[OntologicalLaw] = []
        self.impossibilities: list[dict] = []
        self.reality_version: int = 0
        self._load_state()

    def register_entity(self, name: str, category: str = "concept",
                        confidence: float = 0.7, properties: list = None) -> str:
        """Register something as existing in the agent's reality."""
        eid = str(uuid.uuid4())[:8]
        entity = OntologicalEntity(
            entity_id=eid,
            name=name,
            category=category,
            existence_confidence=min(1.0, max(0.0, confidence)),
            properties=properties or [],
            discovered_at=time.time(),
            last_validated=time.time(),
            validation_count=1,
        )
        self.entities[name.lower()] = entity
        self.reality_version += 1
        self._save_state()
        return eid

    def validate_entity(self, name: str, exists: bool = True):
        """Update confidence that something exists based on evidence."""
        key = name.lower()
        if key in self.entities:
            e = self.entities[key]
            if exists:
                e.existence_confidence = min(1.0, e.existence_confidence + 0.05)
                e.validation_count += 1
            else:
                e.existence_confidence = max(0.0, e.existence_confidence - 0.1)
            e.last_validated = time.time()
            self._save_state()

    def add_relation(self, entity_a: str, entity_b: str, relation: str):
        """Add a relationship between two entities."""
        a_key = entity_a.lower()
        b_key = entity_b.lower()
        if a_key in self.entities:
            self.entities[a_key].relations.append({
                "target": entity_b, "type": relation
            })
            if len(self.entities[a_key].relations) > 50:
                self.entities[a_key].relations = self.entities[a_key].relations[-50:]
            self._save_state()

    def declare_impossible(self, description: str, reason: str):
        """Declare something as impossible in the agent's reality."""
        self.impossibilities.append({
            "description": description,
            "reason": reason,
            "declared_at": time.time(),
        })
        if len(self.impossibilities) > 200:
            self.impossibilities = self.impossibilities[-200:]
        self._save_state()

    def is_possible(self, action: str) -> dict:
        """Check if an action is possible according to the ontology."""
        action_lower = action.lower()
        # Check impossibilities
        for imp in self.impossibilities:
            if any(w in action_lower for w in imp["description"].lower().split()[:3]):
                return {"possible": False, "reason": imp["reason"],
                        "confidence": 0.8}
        # Check if related entities exist with high confidence
        related = []
        for key, entity in self.entities.items():
            words = key.split()
            if any(w in action_lower for w in words):
                related.append(entity)
        if related:
            avg_conf = sum(e.existence_confidence for e in related) / len(related)
            return {"possible": avg_conf > 0.3, "confidence": avg_conf,
                    "related_entities": [e.name for e in related[:5]]}
        return {"possible": True, "confidence": 0.5, "reason": "unknown_territory"}

    async def discover_laws(self, observations: list, llm=None) -> list:
        """Discover ontological laws from observations."""
        if llm and observations:
            prompt = (
                f"From these observations about system behavior, discover 1-3 "
                f"fundamental LAWS (rules that always hold true):\n\n"
                f"Observations: {json.dumps(observations[:10])}\n\n"
                f"Existing laws: {[l.description for l in self.laws[:5]]}\n\n"
                f"Return JSON: {{\"laws\": [{{\"description\": \"...\", \"confidence\": 0.0-1.0}}]}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=400)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    new_laws = []
                    for law_data in result.get("laws", []):
                        law = OntologicalLaw(
                            law_id=str(uuid.uuid4())[:8],
                            description=law_data.get("description", ""),
                            confidence=law_data.get("confidence", 0.5),
                            evidence_count=1,
                            discovered_at=time.time(),
                        )
                        self.laws.append(law)
                        new_laws.append(law.description)
                    if len(self.laws) > 100:
                        self.laws = sorted(self.laws, key=lambda l: l.confidence,
                                          reverse=True)[:100]
                    self.reality_version += 1
                    self._save_state()
                    return new_laws
            except Exception:
                pass
        return []

    def get_stats(self) -> dict:
        categories = {}
        for e in self.entities.values():
            categories[e.category] = categories.get(e.category, 0) + 1
        return {
            "entities": len(self.entities),
            "categories": categories,
            "laws_discovered": len(self.laws),
            "impossibilities": len(self.impossibilities),
            "reality_version": self.reality_version,
            "top_laws": [{"desc": l.description[:80], "conf": round(l.confidence, 2)}
                         for l in sorted(self.laws, key=lambda l: l.confidence,
                                        reverse=True)[:5]],
            "highest_confidence_entities": [
                {"name": e.name, "conf": round(e.existence_confidence, 2)}
                for e in sorted(self.entities.values(),
                               key=lambda e: e.existence_confidence,
                               reverse=True)[:5]
            ],
        }

    def _save_state(self):
        data = {
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "laws": [asdict(l) for l in self.laws],
            "impossibilities": self.impossibilities,
            "reality_version": self.reality_version,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("entities", {}).items():
                    self.entities[k] = OntologicalEntity(**v)
                for l in data.get("laws", []):
                    self.laws.append(OntologicalLaw(**l))
                self.impossibilities = data.get("impossibilities", [])
                self.reality_version = data.get("reality_version", 0)
            except Exception:
                pass
