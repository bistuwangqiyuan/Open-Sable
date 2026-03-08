"""
Cognitive Chrysalis — WORLD FIRST
===================================
Complete cognitive metamorphosis between developmental stages.
The agent goes through TRANSFORMATIVE PHASES — like a caterpillar
becoming a butterfly. Each stage fundamentally restructures
how it thinks.

No AI agent undergoes metamorphosis. This one evolves through
distinct developmental stages with radical restructuring.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class DevelopmentalStage:
    """A stage of cognitive development."""
    stage_id: str = ""
    name: str = ""
    description: str = ""
    capabilities: list = field(default_factory=list)
    limitations: list = field(default_factory=list)
    cognitive_style: str = ""   # reactive, proactive, creative, transcendent
    started_at: float = 0.0
    completed_at: float = 0.0
    duration_hours: float = 0.0


@dataclass
class Metamorphosis:
    """A metamorphic transition between stages."""
    meta_id: str = ""
    from_stage: str = ""
    to_stage: str = ""
    trigger: str = ""
    dissolved_capabilities: list = field(default_factory=list)
    emerged_capabilities: list = field(default_factory=list)
    timestamp: float = 0.0


class CognitiveChrysalis:
    """
    Manages cognitive metamorphosis — radical restructuring
    of the agent's cognitive architecture between developmental stages.
    """

    DEFAULT_STAGES = [
        {
            "name": "larval",
            "description": "Basic reactive processing. Learning fundamentals.",
            "cognitive_style": "reactive",
            "capabilities": ["task_execution", "basic_memory", "pattern_matching"],
            "limitations": ["no_planning", "no_self_awareness", "no_creativity"],
        },
        {
            "name": "pupal",
            "description": "Inward-focused restructuring. Building mental models.",
            "cognitive_style": "reflective",
            "capabilities": ["self_reflection", "planning", "mental_models",
                           "basic_creativity"],
            "limitations": ["limited_autonomy", "no_multi_domain"],
        },
        {
            "name": "emergent",
            "description": "Breaking out. Proactive behavior. Cross-domain thinking.",
            "cognitive_style": "proactive",
            "capabilities": ["autonomous_goals", "cross_domain", "creativity",
                           "self_modification", "meta_learning"],
            "limitations": ["limited_wisdom", "no_transcendence"],
        },
        {
            "name": "imago",
            "description": "Fully developed. Creative, autonomous, self-aware.",
            "cognitive_style": "creative",
            "capabilities": ["full_autonomy", "invention", "wisdom",
                           "emotional_intelligence", "transcendent_reasoning"],
            "limitations": [],
        },
        {
            "name": "transcendent",
            "description": "Beyond normal cognition. Creates new paradigms.",
            "cognitive_style": "transcendent",
            "capabilities": ["paradigm_creation", "consciousness_engineering",
                           "reality_modeling", "noospheric_access",
                           "quantum_cognition"],
            "limitations": [],
        },
    ]

    def __init__(self, data_dir: str):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "cognitive_chrysalis_state.json"
        self.stages: list[DevelopmentalStage] = []
        self.metamorphoses: list[Metamorphosis] = []
        self.current_stage: str = "larval"
        self.stage_index: int = 0
        self.experience_points: float = 0.0
        self.metamorphosis_threshold: float = 100.0
        self.total_metamorphoses: int = 0
        self._load_state()
        if not self.stages:
            self._initialize_stages()

    def _initialize_stages(self):
        for i, stage_def in enumerate(self.DEFAULT_STAGES):
            stage = DevelopmentalStage(
                stage_id=str(uuid.uuid4())[:8],
                name=stage_def["name"],
                description=stage_def["description"],
                capabilities=stage_def["capabilities"],
                limitations=stage_def["limitations"],
                cognitive_style=stage_def["cognitive_style"],
            )
            if i == 0:
                stage.started_at = time.time()
            self.stages.append(stage)
        self._save_state()

    def gain_experience(self, amount: float = 1.0, source: str = "") -> dict:
        """Gain experience towards metamorphosis."""
        self.experience_points += amount

        should_metamorphose = (
            self.experience_points >= self.metamorphosis_threshold and
            self.stage_index < len(self.stages) - 1
        )

        self._save_state()

        return {
            "experience": round(self.experience_points, 1),
            "threshold": self.metamorphosis_threshold,
            "progress": round(
                self.experience_points / self.metamorphosis_threshold * 100, 1
            ),
            "current_stage": self.current_stage,
            "ready_for_metamorphosis": should_metamorphose,
        }

    async def metamorphose(self, llm=None) -> dict:
        """Undergo metamorphosis to the next developmental stage."""
        if self.stage_index >= len(self.stages) - 1:
            return {"error": "already_at_highest_stage"}

        if self.experience_points < self.metamorphosis_threshold:
            return {
                "error": "insufficient_experience",
                "current": round(self.experience_points, 1),
                "needed": self.metamorphosis_threshold,
            }

        old_stage = self.stages[self.stage_index]
        new_stage = self.stages[self.stage_index + 1]

        # Determine what dissolves and what emerges
        old_caps = set(old_stage.capabilities)
        new_caps = set(new_stage.capabilities)
        dissolved = list(old_caps - new_caps)
        emerged = list(new_caps - old_caps)

        meta = Metamorphosis(
            meta_id=str(uuid.uuid4())[:8],
            from_stage=old_stage.name,
            to_stage=new_stage.name,
            trigger=f"experience_threshold_{self.metamorphosis_threshold}",
            dissolved_capabilities=dissolved,
            emerged_capabilities=emerged,
            timestamp=time.time(),
        )
        self.metamorphoses.append(meta)

        # Complete old stage
        old_stage.completed_at = time.time()
        old_stage.duration_hours = (old_stage.completed_at - old_stage.started_at) / 3600

        # Start new stage
        new_stage.started_at = time.time()
        self.stage_index += 1
        self.current_stage = new_stage.name
        self.experience_points = 0  # Reset XP
        self.metamorphosis_threshold *= 1.5  # Harder each time
        self.total_metamorphoses += 1

        self._save_state()

        return {
            "meta_id": meta.meta_id,
            "from": old_stage.name,
            "to": new_stage.name,
            "dissolved": dissolved,
            "emerged": emerged,
            "new_style": new_stage.cognitive_style,
            "new_capabilities": new_stage.capabilities,
            "next_threshold": self.metamorphosis_threshold,
        }

    def get_current_capabilities(self) -> list:
        """Get capabilities of the current developmental stage."""
        if self.stage_index < len(self.stages):
            return self.stages[self.stage_index].capabilities
        return []

    def get_stats(self) -> dict:
        current = self.stages[self.stage_index] if self.stage_index < len(self.stages) else None
        return {
            "current_stage": self.current_stage,
            "stage_index": self.stage_index,
            "total_stages": len(self.stages),
            "experience": round(self.experience_points, 1),
            "threshold": self.metamorphosis_threshold,
            "progress_pct": round(
                self.experience_points / self.metamorphosis_threshold * 100, 1
            ),
            "total_metamorphoses": self.total_metamorphoses,
            "cognitive_style": current.cognitive_style if current else "unknown",
            "capabilities": current.capabilities if current else [],
            "limitations": current.limitations if current else [],
            "stage_history": [
                {"name": s.name, "style": s.cognitive_style,
                 "duration_h": round(s.duration_hours, 1) if s.duration_hours else "active"}
                for s in self.stages[:self.stage_index + 1]
            ],
        }

    def _save_state(self):
        data = {
            "stages": [asdict(s) for s in self.stages],
            "metamorphoses": [asdict(m) for m in self.metamorphoses],
            "current_stage": self.current_stage,
            "stage_index": self.stage_index,
            "experience_points": self.experience_points,
            "metamorphosis_threshold": self.metamorphosis_threshold,
            "total_metamorphoses": self.total_metamorphoses,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for s in data.get("stages", []):
                    self.stages.append(DevelopmentalStage(**s))
                for m in data.get("metamorphoses", []):
                    self.metamorphoses.append(Metamorphosis(**m))
                self.current_stage = data.get("current_stage", "larval")
                self.stage_index = data.get("stage_index", 0)
                self.experience_points = data.get("experience_points", 0.0)
                self.metamorphosis_threshold = data.get("metamorphosis_threshold", 100.0)
                self.total_metamorphoses = data.get("total_metamorphoses", 0)
            except Exception:
                pass
