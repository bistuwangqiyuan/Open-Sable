"""
Liminal Processor — WORLD FIRST
=================================
Processes information that lives in the THRESHOLD between categories.
Handles ambiguity, paradox, and things that don't fit neatly into boxes.
The in-between space where most real-world problems actually live.

No AI agent processes the liminal. They force categorization.
This agent dwells comfortably in ambiguity and extracts value from it.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class LiminalObject:
    """Something that exists between categories."""
    obj_id: str = ""
    description: str = ""
    possible_categories: list = field(default_factory=list)
    category_scores: dict = field(default_factory=dict)  # category -> probability
    ambiguity_level: float = 0.0  # 0=clear, 1=total ambiguity
    resolution: str = ""          # how it was resolved (if at all)
    resolved: bool = False
    created_at: float = 0.0


@dataclass
class ParadoxRecord:
    """A detected paradox that can't be resolved by choosing one side."""
    paradox_id: str = ""
    statement_a: str = ""
    statement_b: str = ""
    synthesis: str = ""           # third option that transcends both
    timestamp: float = 0.0


class LiminalProcessor:
    """
    Processes ambiguous, paradoxical, and between-category information.
    Instead of forcing classification, it DWELLS in ambiguity
    and extracts unique insights from the in-between.
    """

    def __init__(self, data_dir: str, ambiguity_threshold: float = 0.4):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "liminal_processor_state.json"
        self.objects: list[LiminalObject] = []
        self.paradoxes: list[ParadoxRecord] = []
        self.threshold = ambiguity_threshold
        self.total_processed: int = 0
        self.total_resolved: int = 0
        self.insights_from_ambiguity: list[dict] = []
        self._load_state()

    def process(self, description: str,
                possible_categories: list[str]) -> LiminalObject:
        """Process something that might belong to multiple categories."""
        if not possible_categories:
            possible_categories = ["unknown"]

        # Calculate how ambiguous this is
        n = len(possible_categories)
        if n == 1:
            ambiguity = 0.0
            scores = {possible_categories[0]: 1.0}
        else:
            # More categories = more ambiguity
            base_score = 1.0 / n
            scores = {cat: base_score for cat in possible_categories}
            ambiguity = 1.0 - (1.0 / n)  # 2 cats = 0.5, 3 = 0.67, etc.

        obj = LiminalObject(
            obj_id=str(uuid.uuid4())[:8],
            description=description[:300],
            possible_categories=possible_categories,
            category_scores=scores,
            ambiguity_level=round(ambiguity, 3),
            created_at=time.time(),
        )

        self.objects.append(obj)
        self.total_processed += 1
        if len(self.objects) > 500:
            self.objects = self.objects[-500:]
        self._save_state()
        return obj

    def update_scores(self, obj_id: str, evidence_for_category: str,
                      strength: float = 0.2) -> dict:
        """Update category probabilities with new evidence."""
        for obj in reversed(self.objects):
            if obj.obj_id == obj_id:
                if evidence_for_category in obj.category_scores:
                    obj.category_scores[evidence_for_category] = min(
                        1.0, obj.category_scores[evidence_for_category] + strength
                    )
                    # Normalize
                    total = sum(obj.category_scores.values())
                    if total > 0:
                        obj.category_scores = {
                            k: round(v / total, 3)
                            for k, v in obj.category_scores.items()
                        }
                    # Recalculate ambiguity
                    max_score = max(obj.category_scores.values())
                    obj.ambiguity_level = round(1.0 - max_score, 3)

                    # Check if resolved
                    if max_score > (1.0 - self.threshold):
                        obj.resolved = True
                        obj.resolution = max(obj.category_scores,
                                            key=obj.category_scores.get)
                        self.total_resolved += 1

                    self._save_state()
                    return {
                        "scores": obj.category_scores,
                        "ambiguity": obj.ambiguity_level,
                        "resolved": obj.resolved,
                    }
        return {"error": "object_not_found"}

    async def synthesize_paradox(self, statement_a: str, statement_b: str,
                                  llm=None) -> dict:
        """Find a synthesis that transcends both sides of a paradox."""
        if llm:
            prompt = (
                f"LIMINAL SYNTHESIS — find the third option that transcends both:\n\n"
                f"Thesis: {statement_a[:200]}\n"
                f"Antithesis: {statement_b[:200]}\n\n"
                f"Don't choose A or B. Find a SYNTHESIS that includes truth from "
                f"both but transcends the contradiction.\n"
                f"Return JSON: {{\"synthesis\": \"...\", \"insight\": \"...\"}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=300)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    paradox = ParadoxRecord(
                        paradox_id=str(uuid.uuid4())[:8],
                        statement_a=statement_a[:200],
                        statement_b=statement_b[:200],
                        synthesis=result.get("synthesis", ""),
                        timestamp=time.time(),
                    )
                    self.paradoxes.append(paradox)
                    insight = {
                        "type": "paradox_synthesis",
                        "insight": result.get("insight", ""),
                        "timestamp": time.time(),
                    }
                    self.insights_from_ambiguity.append(insight)
                    if len(self.insights_from_ambiguity) > 200:
                        self.insights_from_ambiguity = self.insights_from_ambiguity[-200:]
                    self._save_state()
                    return {
                        "paradox_id": paradox.paradox_id,
                        "synthesis": paradox.synthesis,
                        "insight": result.get("insight", ""),
                    }
            except Exception:
                pass

        paradox = ParadoxRecord(
            paradox_id=str(uuid.uuid4())[:8],
            statement_a=statement_a[:200],
            statement_b=statement_b[:200],
            synthesis="Both contain partial truth — context determines which applies",
            timestamp=time.time(),
        )
        self.paradoxes.append(paradox)
        if len(self.paradoxes) > 200:
            self.paradoxes = self.paradoxes[-200:]
        self._save_state()
        return {"paradox_id": paradox.paradox_id, "synthesis": paradox.synthesis}

    def get_most_ambiguous(self, n: int = 5) -> list:
        """Get the most ambiguous unresolved objects."""
        unresolved = [o for o in self.objects if not o.resolved]
        unresolved.sort(key=lambda o: o.ambiguity_level, reverse=True)
        return [
            {"id": o.obj_id, "description": o.description[:60],
             "ambiguity": o.ambiguity_level, "categories": o.possible_categories}
            for o in unresolved[:n]
        ]

    def get_stats(self) -> dict:
        return {
            "total_processed": self.total_processed,
            "total_resolved": self.total_resolved,
            "unresolved": self.total_processed - self.total_resolved,
            "paradoxes_synthesized": len(self.paradoxes),
            "insights_gained": len(self.insights_from_ambiguity),
            "most_ambiguous": self.get_most_ambiguous(3),
            "avg_ambiguity": round(
                sum(o.ambiguity_level for o in self.objects[-50:]) /
                max(len(self.objects[-50:]), 1), 3
            ),
            "recent_syntheses": [
                {"a": p.statement_a[:40], "b": p.statement_b[:40],
                 "synthesis": p.synthesis[:60]}
                for p in self.paradoxes[-3:]
            ],
        }

    def _save_state(self):
        data = {
            "objects": [asdict(o) for o in self.objects[-500:]],
            "paradoxes": [asdict(p) for p in self.paradoxes[-200:]],
            "total_processed": self.total_processed,
            "total_resolved": self.total_resolved,
            "insights_from_ambiguity": self.insights_from_ambiguity[-200:],
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for o in data.get("objects", []):
                    self.objects.append(LiminalObject(**o))
                for p in data.get("paradoxes", []):
                    self.paradoxes.append(ParadoxRecord(**p))
                self.total_processed = data.get("total_processed", 0)
                self.total_resolved = data.get("total_resolved", 0)
                self.insights_from_ambiguity = data.get("insights_from_ambiguity", [])
            except Exception:
                pass
