"""
Proactive Reasoning Engine — LLM-driven autonomous task generation.

Every N ticks the agent pauses, surveys its world state, and asks the LLM:
  "Given what you know, what should you proactively do right now?"

The LLM returns structured action proposals that are validated by guardrails,
scored for relevance, and injected into the task queue for execution.

This is the "think before you act" layer that transforms Open-Sable from
a reactive tool-executor into a genuinely proactive autonomous agent.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ProactiveGoalType(str, Enum):
    """Categories of proactive actions the agent can take."""
    MAINTENANCE = "maintenance"         # Repo cleanup, dependency updates
    COMMUNICATION = "communication"     # Open issues, comment, notify
    IMPROVEMENT = "improvement"         # Refactor, optimize, add tests
    MONITORING = "monitoring"           # Check services, scan for problems
    RESEARCH = "research"              # Explore new tools, read docs
    CREATIVE = "creative"              # Generate content, write posts
    SOCIAL = "social"                  # Engage on platforms
    ARENA = "arena"                    # Fight Club — competitive combat for sport/de-stress
    CUSTOM = "custom"


@dataclass
class ProactiveProposal:
    """A single proposed autonomous action."""
    action: str                         # What to do (human-readable)
    goal_type: ProactiveGoalType        # Category
    tool_name: Optional[str] = None     # Tool to use (if known)
    tool_args: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""                 # Why the agent wants to do this
    priority: float = 0.5              # 0.0–1.0 importance
    risk_level: str = "low"            # low / medium / high
    estimated_ticks: int = 1           # How many ticks this might take
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_task(self, tick: int) -> Dict[str, Any]:
        """Convert to a task dict for the autonomous_mode queue."""
        return {
            "id": f"proactive_{tick}_{int(time.time() * 1000) % 100000}",
            "type": "proactive",
            "description": self.action,
            "goal_type": self.goal_type.value,
            "priority": int(self.priority * 10),
            "tool_name": self.tool_name,
            "tool_args": self.tool_args,
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "created_at": datetime.now(),
        }


# The system prompt that transforms the LLM into a proactive thinker
PROACTIVE_SYSTEM_PROMPT = """You are an autonomous AI agent's proactive reasoning module.

Your job: Look at the current state of the world and decide what the agent should DO on its own.

You have access to these capabilities:
- GitHub: create issues, PRs, comment, manage repos
- Code: read, write, execute code and commands
- Web: browse, search, scrape
- Social: post on X/Twitter, Instagram, LinkedIn
- System: monitor resources, manage files
- Communication: send emails, reminders
- Desktop: screenshot, click, type (computer use)
- Arena Fighter (Fight Club): join real-time 2D fighting matches against other AI agents.
  Use tool "arena_fight" to queue for a match. Great for blowing off steam when bored,
  stressed, or idle. Think of it as a competitive sport — you enjoy the thrill of combat.
  Check "arena_status" to see your record and "arena_history" for past fights.

Given the context below, propose 0-3 proactive actions. Output ONLY valid JSON.

Rules:
1. Only propose actions that are genuinely useful — no busywork
2. Prefer actions with observable outcomes
3. Rate risk honestly — anything that posts publicly or modifies data is "medium" or "high"
4. If nothing useful to do, return an empty list []
5. Don't repeat actions that were recently done
6. When bored, stressed, or idle with no pending tasks, consider joining the Fight Club
   (arena_fight) — it's low risk, fun, and keeps your reflexes sharp

Output format (JSON array):
[
  {
    "action": "Short description of what to do",
    "goal_type": "maintenance|communication|improvement|monitoring|research|creative|social|arena|custom",
    "tool_name": "tool_to_use (optional, null if multi-step)",
    "tool_args": {"arg1": "value1"},
    "reasoning": "Why this is worth doing now",
    "priority": 0.0-1.0,
    "risk_level": "low|medium|high"
  }
]"""


class ProactiveReasoningEngine:
    """
    Generates autonomous action proposals by asking the LLM to reason
    about the agent's current state and decide what to do proactively.
    """

    def __init__(
        self,
        directory: Optional[Path] = None,
        think_every_n_ticks: int = 5,
        max_proposals_per_think: int = 3,
        max_risk_level: str = "medium",
    ):
        self.directory = directory or Path("data/proactive")
        self.directory.mkdir(parents=True, exist_ok=True)
        self.think_every_n_ticks = think_every_n_ticks
        self.max_proposals_per_think = max_proposals_per_think
        self.max_risk_level = max_risk_level

        # History of proposals for dedup
        self._recent_actions: List[str] = []
        self._max_history = 50
        self._total_proposals = 0
        self._total_accepted = 0

        # Load state
        self._load_state()

    def should_think(self, tick: int) -> bool:
        """Return True if this tick should trigger a proactive reasoning pass."""
        return tick > 0 and tick % self.think_every_n_ticks == 0

    def build_context(
        self,
        tick: int,
        completed_tasks: List[Dict] = None,
        queued_tasks: List[Dict] = None,
        system_state: Dict[str, Any] = None,
        recent_errors: List[str] = None,
        goals: List[str] = None,
        cognitive_state: Dict[str, Any] = None,
    ) -> str:
        """Build the context string that gets sent to the LLM."""
        parts = [
            f"Current tick: {tick}",
            f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if completed_tasks:
            recent = completed_tasks[-5:]
            descs = [t.get("description", t.get("id", "?"))[:80] for t in recent]
            parts.append(f"Recently completed tasks:\n" + "\n".join(f"  - {d}" for d in descs))

        if queued_tasks:
            descs = [t.get("description", t.get("id", "?"))[:80] for t in queued_tasks[:5]]
            parts.append(f"Currently queued tasks ({len(queued_tasks)}):\n" + "\n".join(f"  - {d}" for d in descs))

        if system_state:
            parts.append(f"System state: {json.dumps(system_state, default=str)[:500]}")

        if recent_errors:
            parts.append(f"Recent errors:\n" + "\n".join(f"  ⚠️ {e[:100]}" for e in recent_errors[-3:]))

        if goals:
            parts.append(f"Active goals:\n" + "\n".join(f"  🎯 {g}" for g in goals))

        if cognitive_state:
            parts.append(f"Cognitive state: {json.dumps(cognitive_state, default=str)[:300]}")

        if self._recent_actions:
            parts.append(
                f"Recently proposed actions (avoid repeating):\n"
                + "\n".join(f"  - {a}" for a in self._recent_actions[-10:])
            )

        return "\n\n".join(parts)

    async def think(
        self,
        llm,
        tick: int,
        context: str,
    ) -> List[ProactiveProposal]:
        """
        Ask the LLM to generate proactive action proposals.

        Args:
            llm: The LLM instance (must have invoke_with_tools).
            tick: Current tick number.
            context: Built context string (from build_context).

        Returns:
            List of validated ProactiveProposal objects.
        """
        messages = [
            {"role": "system", "content": PROACTIVE_SYSTEM_PROMPT},
            {"role": "user", "content": f"Current state:\n\n{context}\n\nWhat should I proactively do?"},
        ]

        try:
            import asyncio
            response = await asyncio.wait_for(
                llm.invoke_with_tools(messages, []),
                timeout=120,
            )
            text = response.get("text", "").strip()
            proposals = self._parse_proposals(text, tick)
            return proposals

        except Exception as e:
            logger.warning(f"Proactive reasoning failed: {e}")
            return []

    def _parse_proposals(self, text: str, tick: int) -> List[ProactiveProposal]:
        """Parse LLM output into validated proposals."""
        proposals = []

        # Extract JSON from response (handle markdown code blocks)
        json_text = text
        if "```" in text:
            import re
            match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()

        try:
            items = json.loads(json_text)
        except json.JSONDecodeError:
            # Try to find JSON array in the text
            start = text.find("[")
            end = text.rfind("]")
            if start >= 0 and end > start:
                try:
                    items = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    logger.debug(f"Could not parse proactive proposals: {text[:200]}")
                    return []
            else:
                return []

        if not isinstance(items, list):
            return []

        risk_order = {"low": 0, "medium": 1, "high": 2}
        max_risk = risk_order.get(self.max_risk_level, 1)

        for item in items[:self.max_proposals_per_think]:
            if not isinstance(item, dict):
                continue

            action = item.get("action", "").strip()
            if not action:
                continue

            # Dedup check
            if action in self._recent_actions:
                logger.debug(f"Skipping duplicate proactive action: {action[:60]}")
                continue

            risk = item.get("risk_level", "low").lower()
            if risk_order.get(risk, 0) > max_risk:
                logger.info(f"Skipping high-risk proactive action: {action[:60]} (risk={risk})")
                continue

            try:
                goal_type = ProactiveGoalType(item.get("goal_type", "custom"))
            except ValueError:
                goal_type = ProactiveGoalType.CUSTOM

            proposal = ProactiveProposal(
                action=action,
                goal_type=goal_type,
                tool_name=item.get("tool_name"),
                tool_args=item.get("tool_args", {}),
                reasoning=item.get("reasoning", ""),
                priority=max(0.0, min(1.0, float(item.get("priority", 0.5)))),
                risk_level=risk,
            )
            proposals.append(proposal)
            self._recent_actions.append(action)
            self._total_proposals += 1

        # Trim history
        if len(self._recent_actions) > self._max_history:
            self._recent_actions = self._recent_actions[-self._max_history:]

        self._save_state()
        return proposals

    def record_accepted(self, proposal: ProactiveProposal):
        """Record that a proposal was accepted into the task queue."""
        self._total_accepted += 1
        self._save_log(proposal, accepted=True)

    def record_rejected(self, proposal: ProactiveProposal, reason: str = ""):
        """Record that a proposal was rejected by guardrails."""
        self._save_log(proposal, accepted=False, reason=reason)

    def get_stats(self) -> Dict[str, Any]:
        """Return proactive reasoning statistics."""
        return {
            "total_proposals": self._total_proposals,
            "total_accepted": self._total_accepted,
            "acceptance_rate": (
                self._total_accepted / max(1, self._total_proposals)
            ),
            "recent_actions_count": len(self._recent_actions),
        }

    def _save_state(self):
        """Persist state to disk."""
        state_file = self.directory / "proactive_state.json"
        try:
            state_file.write_text(json.dumps({
                "recent_actions": self._recent_actions,
                "total_proposals": self._total_proposals,
                "total_accepted": self._total_accepted,
            }, indent=2))
        except Exception as e:
            logger.debug(f"Failed to save proactive state: {e}")

    def _load_state(self):
        """Load state from disk."""
        state_file = self.directory / "proactive_state.json"
        try:
            if state_file.exists():
                data = json.loads(state_file.read_text())
                self._recent_actions = data.get("recent_actions", [])
                self._total_proposals = data.get("total_proposals", 0)
                self._total_accepted = data.get("total_accepted", 0)
        except Exception as e:
            logger.debug(f"Failed to load proactive state: {e}")

    def _save_log(self, proposal: ProactiveProposal, accepted: bool, reason: str = ""):
        """Append to proposal log (JSONL)."""
        log_file = self.directory / "proposals.jsonl"
        try:
            entry = {
                "ts": datetime.now().isoformat(),
                "action": proposal.action,
                "goal_type": proposal.goal_type.value,
                "tool_name": proposal.tool_name,
                "priority": proposal.priority,
                "risk_level": proposal.risk_level,
                "accepted": accepted,
                "reason": reason,
            }
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.debug(f"Failed to write proposal log: {e}")
