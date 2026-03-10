"""
Dynamic Skill Factory,  WORLD FIRST
Creates complex multi-step skills from scratch autonomously.
Unlike the existing SkillFactory, this engine can compose entire
skill pipelines, test them, iterate, and deploy,  full autonomous
skill engineering.
"""
import json
import logging
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class SkillBlueprint:
    id: str
    name: str
    description: str
    steps: List[Dict[str, str]] = field(default_factory=list)
    created_at: str = ""
    status: str = "draft"  # draft, testing, validated, deployed, failed
    test_results: List[Dict] = field(default_factory=list)
    iterations: int = 0
    complexity: int = 1  # 1-10
    dependencies: List[str] = field(default_factory=list)
    source_code: str = ""

@dataclass
class SkillTest:
    skill_id: str
    passed: bool
    error: Optional[str] = None
    timestamp: str = ""
    execution_time_ms: float = 0.0

# ── Core Engine ───────────────────────────────────────────────────────

class DynamicSkillFactory:
    """
    Autonomous skill engineering engine.
    Designs, composes, tests, iterates, and deploys complex
    multi-step skills from natural language descriptions.
    """

    MAX_BLUEPRINTS = 100
    MAX_ITERATIONS = 5

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "dynamic_skill_factory_state.json"
        self.skills_dir = self.data_dir / "generated_skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)

        self.blueprints: List[SkillBlueprint] = []
        self.total_created = 0
        self.total_deployed = 0
        self.total_tests = 0
        self.total_failed = 0
        self.total_iterations = 0

        self._load_state()

    async def design_skill(self, need: str, llm=None) -> SkillBlueprint:
        """Design a new skill from a natural language description."""
        skill_id = hashlib.sha256(f"{need}{datetime.now().isoformat()}".encode()).hexdigest()[:12]

        blueprint = SkillBlueprint(
            id=skill_id,
            name=need[:60],
            description=need,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        if llm:
            prompt = f"""Design a multi-step skill for an AI agent.

Need: {need}

Return JSON with:
- "name": short skill name
- "steps": list of {{"action": "...", "tool": "...", "args": "..."}},
- "dependencies": list of required tools/modules
- "complexity": 1-10 rating

Only return valid JSON."""
            try:
                raw = await llm.chat_raw(prompt, max_tokens=800)
                # Try to parse JSON from response
                start = raw.find("{")
                end = raw.rfind("}") + 1
                if start >= 0 and end > start:
                    design = json.loads(raw[start:end])
                    blueprint.name = design.get("name", blueprint.name)
                    blueprint.steps = design.get("steps", [])
                    blueprint.dependencies = design.get("dependencies", [])
                    blueprint.complexity = design.get("complexity", 1)
            except Exception as e:
                logger.debug(f"LLM skill design failed: {e}")
                blueprint.steps = [{"action": "execute", "tool": "llm", "args": need}]

        self.blueprints.append(blueprint)
        self.total_created += 1

        if len(self.blueprints) > self.MAX_BLUEPRINTS:
            self.blueprints = self.blueprints[-self.MAX_BLUEPRINTS:]

        self._save_state()
        return blueprint

    async def generate_code(self, skill_id: str, llm=None) -> Optional[str]:
        """Generate Python source code for a skill blueprint."""
        bp = next((b for b in self.blueprints if b.id == skill_id), None)
        if not bp:
            return None

        if llm:
            steps_desc = "\n".join([f"  {i+1}. {s.get('action', '?')}: {s.get('args', '')}"
                                    for i, s in enumerate(bp.steps)])
            prompt = f"""Generate a Python async function for this skill:

Name: {bp.name}
Description: {bp.description}
Steps:
{steps_desc}

Write a single async function called `execute(agent, **kwargs)` that implements all steps.
Include error handling. Only return Python code, no markdown."""
            try:
                code = await llm.chat_raw(prompt, max_tokens=1500)
                # Clean markdown code blocks if present
                if "```python" in code:
                    code = code.split("```python")[1].split("```")[0]
                elif "```" in code:
                    code = code.split("```")[1].split("```")[0]

                bp.source_code = code.strip()
                bp.status = "testing"
                self._save_state()
                return bp.source_code
            except Exception as e:
                logger.debug(f"Code generation failed: {e}")

        return None

    def test_skill(self, skill_id: str) -> SkillTest:
        """Static test a generated skill (syntax check)."""
        bp = next((b for b in self.blueprints if b.id == skill_id), None)
        if not bp or not bp.source_code:
            return SkillTest(skill_id=skill_id, passed=False, error="No code generated",
                           timestamp=datetime.now(timezone.utc).isoformat())

        self.total_tests += 1
        try:
            compile(bp.source_code, f"skill_{skill_id}.py", "exec")
            test = SkillTest(
                skill_id=skill_id, passed=True,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            bp.test_results.append(asdict(test))
            bp.status = "validated"
        except SyntaxError as e:
            test = SkillTest(
                skill_id=skill_id, passed=False, error=str(e),
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            bp.test_results.append(asdict(test))
            bp.status = "failed"
            bp.iterations += 1
            self.total_failed += 1

        self._save_state()
        return test

    def deploy_skill(self, skill_id: str) -> Dict[str, Any]:
        """Deploy a validated skill to the skills directory."""
        bp = next((b for b in self.blueprints if b.id == skill_id), None)
        if not bp:
            return {"success": False, "error": "Blueprint not found"}
        if bp.status != "validated":
            return {"success": False, "error": f"Skill not validated (status: {bp.status})"}

        try:
            skill_file = self.skills_dir / f"skill_{skill_id}.py"
            skill_file.write_text(bp.source_code)
            bp.status = "deployed"
            self.total_deployed += 1
            self._save_state()
            return {"success": True, "file": str(skill_file), "skill_id": skill_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def iterate_skill(self, skill_id: str, feedback: str, llm=None) -> Optional[str]:
        """Iterate on a skill based on feedback."""
        bp = next((b for b in self.blueprints if b.id == skill_id), None)
        if not bp or not llm:
            return None

        if bp.iterations >= self.MAX_ITERATIONS:
            return None

        prompt = f"""Improve this Python skill based on feedback:

Current code:
{bp.source_code}

Feedback: {feedback}

Return only the improved Python code."""
        try:
            improved = await llm.chat_raw(prompt, max_tokens=1500)
            if "```python" in improved:
                improved = improved.split("```python")[1].split("```")[0]
            elif "```" in improved:
                improved = improved.split("```")[1].split("```")[0]

            bp.source_code = improved.strip()
            bp.iterations += 1
            bp.status = "testing"
            self.total_iterations += 1
            self._save_state()
            return bp.source_code
        except Exception:
            return None

    def get_stats(self) -> Dict[str, Any]:
        deployed = sum(1 for b in self.blueprints if b.status == "deployed")
        return {
            "total_created": self.total_created,
            "total_deployed": self.total_deployed,
            "total_tests": self.total_tests,
            "total_failed": self.total_failed,
            "total_iterations": self.total_iterations,
            "active_blueprints": len(self.blueprints),
            "deployed_skills": deployed,
            "avg_complexity": round(sum(b.complexity for b in self.blueprints) / max(len(self.blueprints), 1), 1),
        }

    def _save_state(self):
        try:
            state = {
                "blueprints": [asdict(b) for b in self.blueprints[-50:]],
                "total_created": self.total_created,
                "total_deployed": self.total_deployed,
                "total_tests": self.total_tests,
                "total_failed": self.total_failed,
                "total_iterations": self.total_iterations,
            }
            self.state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            logger.debug(f"Dynamic skill factory save failed: {e}")

    def _load_state(self):
        try:
            if self.state_file.exists():
                state = json.loads(self.state_file.read_text())
                self.blueprints = [SkillBlueprint(**b) for b in state.get("blueprints", [])]
                self.total_created = state.get("total_created", 0)
                self.total_deployed = state.get("total_deployed", 0)
                self.total_tests = state.get("total_tests", 0)
                self.total_failed = state.get("total_failed", 0)
                self.total_iterations = state.get("total_iterations", 0)
        except Exception as e:
            logger.debug(f"Dynamic skill factory load failed: {e}")
