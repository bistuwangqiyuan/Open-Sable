"""
Self-Reflection,  cognitive pattern analysis and stagnation detection.

Analyzes recent tick outcomes and goals to prepare structured reflection
context for the LLM.  All intelligence comes from the LLM; this module
only aggregates data and formats prompts.

Core capabilities:
  ReflectionEngine  ,  detects stagnation, failure loops, success patterns
  ReflectionPrompt  ,  builds a structured prompt for LLM self-analysis

Academic grounding:
  [1] Schacter & Addis (2007): Constructive memory,  reflection drives planning
  [2] Park et al., arXiv:2304.03442: Generative Agents,  reflective architecture
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ReflectionEntry:
    """A single reflection produced by the LLM or the system."""

    tick: int
    timestamp: float = 0.0
    reflection_type: str = "general"      # general, stagnation, success, failure, strategy
    content: str = ""
    conclusions: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReflectionEntry":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class TickOutcome:
    """Summary of a single tick's outcome for reflection analysis."""

    tick: int
    success: bool = True
    summary: str = ""
    tools_used: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    goals_progressed: List[str] = field(default_factory=list)


class ReflectionEngine:
    """Self-reflection engine that analyzes patterns and generates prompts.

    Tracks tick outcomes and goals, detects patterns like:
      - Stagnation: same actions repeated without progress
      - Failure loops: repeated errors on the same task
      - Success patterns: what worked well
      - Stale goals: goals with no progress for N ticks

    Generates structured reflection prompts that the LLM processes
    to produce actual insights.
    """

    def __init__(
        self,
        directory: Path,
        min_outcomes: int = 3,
        stale_goal_ticks: int = 5,
        reflection_interval: int = 5,
        max_history: int = 100,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.min_outcomes = min_outcomes
        self.stale_goal_ticks = stale_goal_ticks
        self.reflection_interval = reflection_interval
        self.max_history = max_history

        self._outcomes: List[TickOutcome] = []
        self._reflections: List[ReflectionEntry] = []
        self._file = self.directory / "reflections.jsonl"
        self._outcomes_file = self.directory / "tick_outcomes.jsonl"

        self._load()

    # ── Record outcomes ────────────────────────────────────────────────────

    def record_outcome(self, outcome: TickOutcome) -> None:
        """Record a tick outcome for pattern analysis."""
        self._outcomes.append(outcome)
        # Trim old outcomes
        if len(self._outcomes) > self.max_history:
            self._outcomes = self._outcomes[-self.max_history:]
        self._save_outcomes()

    def record_reflection(self, entry: ReflectionEntry) -> None:
        """Record a reflection (from LLM or system analysis)."""
        if not entry.timestamp:
            entry.timestamp = time.time()
        self._reflections.append(entry)
        self._append_reflection(entry)

    # ── Analysis ───────────────────────────────────────────────────────────

    def should_reflect(self, tick: int) -> bool:
        """Check if it's time for a reflection cycle."""
        if len(self._outcomes) < self.min_outcomes:
            return False
        if self.reflection_interval <= 0:
            return True
        return tick % self.reflection_interval == 0

    def detect_patterns(self, tick: int) -> Dict[str, Any]:
        """Detect patterns in recent tick outcomes.

        Returns a dict with detected patterns:
          - stagnation: True if same tools used repeatedly with no progress
          - failure_rate: fraction of recent ticks that failed
          - repeated_errors: error messages that appear multiple times
          - success_streak: number of consecutive successful ticks
          - stale_actions: actions repeated without new results
        """
        if not self._outcomes:
            return {"patterns_found": False}

        recent = self._outcomes[-self.min_outcomes:]

        # Failure rate
        failures = sum(1 for o in recent if not o.success)
        failure_rate = failures / len(recent)

        # Repeated errors
        all_errors: Dict[str, int] = {}
        for o in recent:
            for err in o.errors:
                short = err[:80]
                all_errors[short] = all_errors.get(short, 0) + 1
        repeated_errors = {k: v for k, v in all_errors.items() if v >= 2}

        # Tool usage repetition (stagnation detection)
        tool_sets = [frozenset(o.tools_used) for o in recent if o.tools_used]
        stagnation = False
        if len(tool_sets) >= 3:
            # If the last 3 ticks used the exact same tools → stagnation
            stagnation = len(set(tool_sets[-3:])) == 1

        # Success streak
        success_streak = 0
        for o in reversed(self._outcomes):
            if o.success:
                success_streak += 1
            else:
                break

        # Goals progressed
        all_goals_progressed: Dict[str, int] = {}
        for o in recent:
            for g in o.goals_progressed:
                all_goals_progressed[g] = all_goals_progressed.get(g, 0) + 1

        return {
            "patterns_found": True,
            "failure_rate": round(failure_rate, 2),
            "repeated_errors": repeated_errors,
            "stagnation": stagnation,
            "success_streak": success_streak,
            "goals_progressed": all_goals_progressed,
            "recent_outcomes": len(recent),
        }

    def detect_stale_goals(
        self, goals: List[Dict[str, Any]], tick: int,
    ) -> List[Dict[str, Any]]:
        """Detect goals with no progress for stale_goal_ticks.

        Each goal dict should have: name, status, progress, created_tick.
        """
        stale = []
        for goal in goals:
            if goal.get("status") != "active":
                continue
            goal_age = tick - goal.get("created_tick", tick)
            progress = goal.get("progress", 0)
            if goal_age >= self.stale_goal_ticks and progress < 0.1:
                stale.append({
                    "name": goal.get("name", "unknown"),
                    "age_ticks": goal_age,
                    "progress": progress,
                })
        return stale

    # ── Prompt generation ──────────────────────────────────────────────────

    def build_reflection_prompt(
        self,
        tick: int,
        goals: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Build a structured reflection prompt for the LLM.

        Returns a prompt string that should be injected as a system message
        when self-reflection is triggered.
        """
        patterns = self.detect_patterns(tick)
        recent = self._outcomes[-self.min_outcomes:]

        parts = []

        # Recent outcomes
        outcome_lines = []
        for o in recent:
            status = "✅" if o.success else "❌"
            outcome_lines.append(
                f"  - tick {o.tick}: {status} {o.summary[:100]}"
            )
        parts.append(
            f"Recent outcomes (last {len(recent)} ticks):\n"
            + "\n".join(outcome_lines)
        )

        # Detected patterns
        if patterns.get("stagnation"):
            parts.append(
                "⚠️ STAGNATION DETECTED: Same tools used repeatedly "
                "without new results."
            )

        if patterns.get("failure_rate", 0) > 0.5:
            parts.append(
                f"⚠️ HIGH FAILURE RATE: {patterns['failure_rate']:.0%} "
                "of recent ticks failed."
            )

        if patterns.get("repeated_errors"):
            error_lines = [
                f"  - \"{err}\" (×{count})"
                for err, count in patterns["repeated_errors"].items()
            ]
            parts.append(
                "⚠️ REPEATED ERRORS:\n" + "\n".join(error_lines)
            )

        if patterns.get("success_streak", 0) >= 3:
            parts.append(
                f"✅ Success streak: {patterns['success_streak']} consecutive "
                "successful ticks! Identify what's working."
            )

        # Stale goals
        if goals:
            stale = self.detect_stale_goals(goals, tick)
            if stale:
                stale_lines = [
                    f"  - \"{g['name']}\" ({g['age_ticks']} ticks, "
                    f"{g['progress']:.0%} progress)"
                    for g in stale
                ]
                parts.append(
                    "⚠️ STALE GOALS (no progress):\n"
                    + "\n".join(stale_lines)
                )

        # Reflection questions
        parts.append(
            "\nREFLECTION TIME. Analyze honestly:"
            "\n- Am I repeating the same actions every tick? What should I change?"
            "\n- What WORKED and what DIDN'T? Double down on what works."
            "\n- Are there stale goals I should abandon or reprioritize?"
            "\n- Am I making real progress or just staying busy?"
            "\n- What's the highest-leverage action I could take next?"
            "\n\nSave a brief 'reflection' with your conclusions."
        )

        return "\n\n".join(parts)

    def get_recent_reflections(
        self, last_n: int = 5,
    ) -> List[ReflectionEntry]:
        """Get the N most recent reflections."""
        return self._reflections[-last_n:]

    def get_stats(self) -> Dict[str, Any]:
        """Get reflection engine statistics."""
        total_outcomes = len(self._outcomes)
        total_reflections = len(self._reflections)
        recent_success_rate = 0.0
        if total_outcomes > 0:
            recent = self._outcomes[-10:]
            recent_success_rate = sum(
                1 for o in recent if o.success
            ) / len(recent)

        return {
            "total_outcomes": total_outcomes,
            "total_reflections": total_reflections,
            "recent_success_rate": round(recent_success_rate, 2),
        }

    # ── Persistence ────────────────────────────────────────────────────────

    def _save_outcomes(self) -> None:
        """Save all tick outcomes."""
        try:
            with open(self._outcomes_file, "w", encoding="utf-8") as f:
                for o in self._outcomes:
                    f.write(json.dumps(asdict(o), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to save tick outcomes: {e}")

    def _append_reflection(self, entry: ReflectionEntry) -> None:
        """Append a reflection to the JSONL file."""
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append reflection: {e}")

    def _load(self) -> None:
        """Load tick outcomes and reflections from disk."""
        # Load outcomes
        if self._outcomes_file.exists():
            try:
                with open(self._outcomes_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            d = json.loads(line)
                            self._outcomes.append(TickOutcome(**{
                                k: v for k, v in d.items()
                                if k in TickOutcome.__dataclass_fields__
                            }))
            except Exception as e:
                logger.warning(f"Failed to load tick outcomes: {e}")

        # Load reflections
        if self._file.exists():
            try:
                with open(self._file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            d = json.loads(line)
                            self._reflections.append(
                                ReflectionEntry.from_dict(d)
                            )
            except Exception as e:
                logger.warning(f"Failed to load reflections: {e}")
