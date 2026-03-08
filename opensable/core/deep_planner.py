"""
Deep Multi-Step Planner — Plans 10+ steps ahead with dependency graphs.

Unlike simple 1-2 step task queuing, the DeepPlanner:
  • Uses LLM to decompose complex goals into a DAG of ≤15 ordered steps
  • Tracks dependencies between steps (step 4 can't start until 2+3 finish)
  • Re-plans dynamically when steps fail or new information surfaces
  • Caches plan templates for similar goals (template matching)
  • Summarises progress as a completion percentage per active plan
  • Persists plans to disk for restart resilience
"""

import asyncio
import json
import logging
import time
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """A single step inside a plan."""
    step_id: int
    description: str
    depends_on: List[int] = field(default_factory=list)  # step_ids this depends on
    status: str = "pending"       # pending | running | done | failed | skipped
    result: str = ""
    error: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: float = 0.0
    retries: int = 0
    tool_hint: str = ""           # optional: suggested tool name

    def is_ready(self, completed_ids: set) -> bool:
        """True if all dependencies are satisfied."""
        return all(d in completed_ids for d in self.depends_on)


@dataclass
class Plan:
    """A complete multi-step plan for a high-level goal."""
    plan_id: str
    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    status: str = "active"        # active | completed | failed | replanned
    created_at: str = ""
    completed_at: Optional[str] = None
    replan_count: int = 0
    progress: float = 0.0         # 0.0 – 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def update_progress(self):
        total = len(self.steps)
        if total == 0:
            self.progress = 1.0
            return
        done = sum(1 for s in self.steps if s.status in ("done", "skipped"))
        self.progress = done / total

    def completed_ids(self) -> set:
        return {s.step_id for s in self.steps if s.status in ("done", "skipped")}

    def next_ready_steps(self, max_n: int = 3) -> List[PlanStep]:
        """Return up to max_n steps whose dependencies are satisfied."""
        cids = self.completed_ids()
        ready = [s for s in self.steps if s.status == "pending" and s.is_ready(cids)]
        return ready[:max_n]

    def has_failed_blocking(self) -> bool:
        """True if a failed step blocks remaining steps."""
        failed_ids = {s.step_id for s in self.steps if s.status == "failed"}
        for s in self.steps:
            if s.status == "pending" and any(d in failed_ids for d in s.depends_on):
                return True
        return False


# ── LLM Plan Prompt ──────────────────────────────────────────────────────────

_PLAN_SYSTEM = """\
You are a deep-planning engine for an autonomous AI agent.
Given a high-level goal and context, decompose it into 5-15 concrete, sequential steps.
Each step must specify what it does, and which previous step(s) it depends on (by step number).
Steps should be actionable — not vague.  Parallelizable steps should share dependencies, not be chained linearly.

Output ONLY valid JSON: an array of objects, each with:
  {"step": <int 1-N>, "description": "<what to do>", "depends_on": [<int step numbers>], "tool_hint": "<optional tool name>"}

Rules:
- Step 1 always has depends_on: []
- Steps can depend on multiple prior steps (parallel fan-in)
- Keep steps granular but not trivially small
- tool_hint is optional — suggest if you know a tool name
- If the goal is simple, use fewer steps (min 3)
- If complex, use up to 15 steps
"""

_REPLAN_SYSTEM = """\
You are a deep-planning engine. A previous plan partially executed.
Some steps completed, some failed. Review the goal, completed results, and failures.
Produce a NEW plan (steps start from 1) that accounts for what already completed and
works around the failures. Output ONLY valid JSON array of step objects (same format).
"""


class DeepPlanner:
    """
    Deep multi-step planning engine with dependency graphs.

    Plans are persisted to disk so they survive agent restarts.
    """

    def __init__(self, data_dir: Path):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._plans: Dict[str, Plan] = {}
        self._template_cache: Dict[str, dict] = {}  # goal_hash → plan structure
        self._total_plans_created = 0
        self._total_replans = 0
        self._total_steps_executed = 0
        self._load_state()

    # ── Public API ────────────────────────────────────────────────────────────

    async def create_plan(self, goal: str, llm, context: str = "") -> Optional[Plan]:
        """Create a multi-step plan for a goal using LLM decomposition."""
        if not llm:
            logger.warning("DeepPlanner: No LLM available for plan creation")
            return None

        # Check template cache for similar goals
        goal_hash = self._hash_goal(goal)
        cached = self._template_cache.get(goal_hash)

        if cached and (time.time() - cached.get("_ts", 0)) < 86400:
            logger.info(f"📋 DeepPlanner: Using cached plan template for '{goal[:60]}'")
            plan = self._template_to_plan(goal, cached["steps"])
        else:
            # LLM decomposition
            messages = [
                {"role": "system", "content": _PLAN_SYSTEM},
                {"role": "user", "content": (
                    f"Goal: {goal}\n\n"
                    f"Context:\n{context[:2000]}" if context else f"Goal: {goal}"
                )},
            ]
            try:
                response = await llm.invoke_with_tools(messages, [])
                text = response.get("text", "") or ""
                steps_data = self._parse_steps_json(text)
                if not steps_data:
                    logger.warning("DeepPlanner: LLM returned no valid steps")
                    return None
                plan = self._build_plan(goal, steps_data)
                # Cache the template
                self._template_cache[goal_hash] = {
                    "steps": steps_data,
                    "_ts": time.time(),
                }
            except Exception as e:
                logger.error(f"DeepPlanner: Plan creation failed: {e}")
                return None

        self._plans[plan.plan_id] = plan
        self._total_plans_created += 1
        self._save_state()
        logger.info(
            f"📋 DeepPlanner: Created plan '{plan.plan_id}' with {len(plan.steps)} steps "
            f"for goal: {goal[:80]}"
        )
        return plan

    async def replan(self, plan_id: str, llm) -> Optional[Plan]:
        """Re-plan after failures — creates a new plan incorporating completed work."""
        plan = self._plans.get(plan_id)
        if not plan or not llm:
            return None

        completed_summary = "\n".join(
            f"  Step {s.step_id} (DONE): {s.description} → {s.result[:100]}"
            for s in plan.steps if s.status == "done"
        )
        failed_summary = "\n".join(
            f"  Step {s.step_id} (FAILED): {s.description} → Error: {s.error[:100]}"
            for s in plan.steps if s.status == "failed"
        )

        messages = [
            {"role": "system", "content": _REPLAN_SYSTEM},
            {"role": "user", "content": (
                f"Original goal: {plan.goal}\n\n"
                f"Completed steps:\n{completed_summary}\n\n"
                f"Failed steps:\n{failed_summary}\n\n"
                f"Create a new plan that builds on completed work and avoids the failure modes."
            )},
        ]

        try:
            response = await llm.invoke_with_tools(messages, [])
            text = response.get("text", "") or ""
            steps_data = self._parse_steps_json(text)
            if not steps_data:
                return None

            plan.status = "replanned"
            new_plan = self._build_plan(plan.goal, steps_data)
            new_plan.replan_count = plan.replan_count + 1
            new_plan.metadata["original_plan"] = plan_id
            self._plans[new_plan.plan_id] = new_plan
            self._total_replans += 1
            self._save_state()
            logger.info(
                f"🔄 DeepPlanner: Replanned '{plan_id}' → '{new_plan.plan_id}' "
                f"({len(new_plan.steps)} steps, replan #{new_plan.replan_count})"
            )
            return new_plan
        except Exception as e:
            logger.error(f"DeepPlanner: Replan failed: {e}")
            return None

    def mark_step_running(self, plan_id: str, step_id: int):
        plan = self._plans.get(plan_id)
        if not plan:
            return
        for s in plan.steps:
            if s.step_id == step_id:
                s.status = "running"
                s.started_at = datetime.now().isoformat()
                break

    def mark_step_done(self, plan_id: str, step_id: int, result: str = "", duration_ms: float = 0):
        plan = self._plans.get(plan_id)
        if not plan:
            return
        for s in plan.steps:
            if s.step_id == step_id:
                s.status = "done"
                s.result = result[:500]
                s.completed_at = datetime.now().isoformat()
                s.duration_ms = duration_ms
                break
        plan.update_progress()
        self._total_steps_executed += 1
        # Check if plan is complete
        if all(s.status in ("done", "skipped") for s in plan.steps):
            plan.status = "completed"
            plan.completed_at = datetime.now().isoformat()
            logger.info(f"✅ DeepPlanner: Plan '{plan_id}' completed ({len(plan.steps)} steps)")
        self._save_state()

    def mark_step_failed(self, plan_id: str, step_id: int, error: str = ""):
        plan = self._plans.get(plan_id)
        if not plan:
            return
        for s in plan.steps:
            if s.step_id == step_id:
                s.status = "failed"
                s.error = error[:500]
                s.completed_at = datetime.now().isoformat()
                break
        plan.update_progress()

        # Check if plan is blocked
        if plan.has_failed_blocking():
            plan.status = "failed"
            logger.warning(f"❌ DeepPlanner: Plan '{plan_id}' blocked by failed step")
        self._save_state()

    def get_active_plans(self) -> List[Plan]:
        return [p for p in self._plans.values() if p.status == "active"]

    def get_next_steps(self, max_total: int = 3) -> List[Tuple[str, PlanStep]]:
        """Return (plan_id, step) tuples for all ready steps across active plans."""
        result = []
        for plan in self.get_active_plans():
            for step in plan.next_ready_steps(max_n=max_total - len(result)):
                result.append((plan.plan_id, step))
                if len(result) >= max_total:
                    return result
        return result

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        return self._plans.get(plan_id)

    def get_stats(self) -> Dict[str, Any]:
        active = [p for p in self._plans.values() if p.status == "active"]
        return {
            "total_plans": self._total_plans_created,
            "active_plans": len(active),
            "total_replans": self._total_replans,
            "total_steps_executed": self._total_steps_executed,
            "cached_templates": len(self._template_cache),
            "plans": [
                {
                    "plan_id": p.plan_id,
                    "goal": p.goal[:100],
                    "status": p.status,
                    "steps": len(p.steps),
                    "progress": round(p.progress, 2),
                    "replan_count": p.replan_count,
                    "created_at": p.created_at,
                    "step_details": [
                        {
                            "step_id": s.step_id,
                            "description": s.description[:80],
                            "status": s.status,
                            "depends_on": s.depends_on,
                        }
                        for s in p.steps
                    ],
                }
                for p in list(self._plans.values())[-10:]
            ],
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _hash_goal(self, goal: str) -> str:
        """Hash a goal to a short key for template caching."""
        normalised = " ".join(goal.lower().split())
        return hashlib.sha256(normalised.encode()).hexdigest()[:12]

    def _parse_steps_json(self, text: str) -> Optional[List[dict]]:
        """Extract JSON array of steps from LLM response."""
        import re
        # Try to find JSON array in the text
        patterns = [
            r'\[[\s\S]*?\]',
        ]
        for pat in patterns:
            match = re.search(pat, text)
            if match:
                try:
                    data = json.loads(match.group())
                    if isinstance(data, list) and len(data) >= 1:
                        return data
                except json.JSONDecodeError:
                    continue

        # Try raw parse
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

        return None

    def _build_plan(self, goal: str, steps_data: List[dict]) -> Plan:
        """Build a Plan from parsed step data."""
        plan_id = f"plan_{int(time.time())}_{hashlib.sha256(goal.encode()).hexdigest()[:6]}"
        steps = []
        for sd in steps_data:
            step_id = sd.get("step", len(steps) + 1)
            deps = sd.get("depends_on", [])
            if isinstance(deps, int):
                deps = [deps]
            steps.append(PlanStep(
                step_id=step_id,
                description=sd.get("description", f"Step {step_id}"),
                depends_on=deps,
                tool_hint=sd.get("tool_hint", ""),
            ))
        return Plan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            created_at=datetime.now().isoformat(),
        )

    def _template_to_plan(self, goal: str, steps_data: List[dict]) -> Plan:
        """Create a Plan from a cached template."""
        return self._build_plan(goal, steps_data)

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "total_plans_created": self._total_plans_created,
                "total_replans": self._total_replans,
                "total_steps_executed": self._total_steps_executed,
                "plans": {},
                "template_cache": self._template_cache,
            }
            for pid, plan in self._plans.items():
                state["plans"][pid] = {
                    "plan_id": plan.plan_id,
                    "goal": plan.goal,
                    "status": plan.status,
                    "created_at": plan.created_at,
                    "completed_at": plan.completed_at,
                    "replan_count": plan.replan_count,
                    "progress": plan.progress,
                    "metadata": plan.metadata,
                    "steps": [asdict(s) for s in plan.steps],
                }
            (self._dir / "deep_planner_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"DeepPlanner: Save state failed: {e}")

    def _load_state(self):
        sf = self._dir / "deep_planner_state.json"
        if not sf.exists():
            return
        try:
            state = json.loads(sf.read_text())
            self._total_plans_created = state.get("total_plans_created", 0)
            self._total_replans = state.get("total_replans", 0)
            self._total_steps_executed = state.get("total_steps_executed", 0)
            self._template_cache = state.get("template_cache", {})

            for pid, pdata in state.get("plans", {}).items():
                steps = []
                for sd in pdata.get("steps", []):
                    steps.append(PlanStep(
                        step_id=sd["step_id"],
                        description=sd["description"],
                        depends_on=sd.get("depends_on", []),
                        status=sd.get("status", "pending"),
                        result=sd.get("result", ""),
                        error=sd.get("error", ""),
                        started_at=sd.get("started_at"),
                        completed_at=sd.get("completed_at"),
                        duration_ms=sd.get("duration_ms", 0),
                        retries=sd.get("retries", 0),
                        tool_hint=sd.get("tool_hint", ""),
                    ))
                plan = Plan(
                    plan_id=pdata["plan_id"],
                    goal=pdata["goal"],
                    steps=steps,
                    status=pdata.get("status", "active"),
                    created_at=pdata.get("created_at", ""),
                    completed_at=pdata.get("completed_at"),
                    replan_count=pdata.get("replan_count", 0),
                    progress=pdata.get("progress", 0),
                    metadata=pdata.get("metadata", {}),
                )
                self._plans[pid] = plan

            logger.info(
                f"📋 DeepPlanner: Loaded {len(self._plans)} plans, "
                f"{self._total_steps_executed} steps executed historically"
            )
        except Exception as e:
            logger.warning(f"DeepPlanner: Load state failed: {e}")
