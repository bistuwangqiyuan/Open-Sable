"""
Agent Handoffs,  transfer control between specialist agents.

Implements a triage / delegation pattern where a *coordinator* agent can
hand off a sub-task to a *specialist* agent, wait for the result, and
incorporate it into its own response.

Inspired by OpenAI Agents SDK handoff pattern and CrewAI delegation.

Usage:
    from opensable.core.handoffs import Handoff, HandoffRouter

    router = HandoffRouter()
    router.register(
        Handoff(
            name="code_review",
            target_role=AgentRole.REVIEWER,
            description="Reviews code for bugs and style",
            input_schema={"code": str, "language": str},
        )
    )

    # The coordinator calls:
    result = await router.execute("code_review", {"code": src, "language": "python"})
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional
import uuid as _uuid

logger = logging.getLogger(__name__)


class HandoffStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class HandoffResult:
    """Result returned by a specialist agent."""
    handoff_id: str
    status: HandoffStatus
    output: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    agent_role: str = ""


@dataclass
class Handoff:
    """
    A registered handoff,  describes *when* and *to whom* to delegate.

    Attributes:
        name: Unique handoff identifier (e.g. "code_review").
        target_role: Role of the specialist agent (from AgentRole enum).
        description: Human-readable explanation (used by coordinator to decide).
        input_schema: Expected keys in the input dict.
        system_prompt_override: Optional system prompt for the specialist.
        tools_filter: Optional list of tool names the specialist is allowed.
        max_turns: Maximum agentic turns the specialist may take.
    """
    name: str
    target_role: str = "executor"
    description: str = ""
    input_schema: Dict[str, type] = field(default_factory=dict)
    system_prompt_override: Optional[str] = None
    tools_filter: Optional[List[str]] = None
    max_turns: int = 5


@dataclass
class HandoffRequest:
    """An in-flight handoff request."""
    handoff_id: str = field(default_factory=lambda: str(_uuid.uuid4())[:8])
    handoff_name: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    status: HandoffStatus = HandoffStatus.PENDING
    result: Optional[HandoffResult] = None
    source_agent: str = "coordinator"
    target_agent: str = ""


# Callable that runs an agent sub-task.  Signature:
#   (system_prompt, user_message, tools_filter, max_turns) -> str
AgentRunner = Callable[..., Awaitable[str]]


class HandoffRouter:
    """
    Registry + executor for agent handoffs.

    Holds a catalogue of available handoffs and an *agent_runner* callback
    that actually spins up a specialist agent for the sub-task.
    """

    def __init__(self, agent_runner: Optional[AgentRunner] = None):
        self._registry: Dict[str, Handoff] = {}
        self._agent_runner = agent_runner
        self._history: List[HandoffRequest] = []

    # ── Registration ─────────────────────────────────────────

    def register(self, handoff: Handoff) -> None:
        self._registry[handoff.name] = handoff
        logger.debug(f"Registered handoff: {handoff.name} → {handoff.target_role}")

    def unregister(self, name: str) -> None:
        self._registry.pop(name, None)

    def set_agent_runner(self, runner: AgentRunner) -> None:
        """Set the callback that spawns a specialist agent."""
        self._agent_runner = runner

    # ── Catalogue (exposed to coordinator LLM) ───────────────

    def available_handoffs(self) -> List[Dict[str, Any]]:
        """Return a list suitable for injecting into the coordinator system prompt."""
        return [
            {
                "name": h.name,
                "description": h.description,
                "target_role": h.target_role,
                "expected_input": {k: v.__name__ for k, v in h.input_schema.items()},
            }
            for h in self._registry.values()
        ]

    def catalogue_prompt(self) -> str:
        """Return a markdown snippet describing every available handoff."""
        if not self._registry:
            return ""
        lines = ["## Available Specialist Handoffs", ""]
        for h in self._registry.values():
            schema_str = ", ".join(f"{k}: {v.__name__}" for k, v in h.input_schema.items()) or "free-text"
            lines.append(f"- **{h.name}** ({h.target_role}): {h.description}  Input: {schema_str}")
        lines.append("")
        lines.append("To delegate, reply with: `@handoff {name} {json_input}`")
        return "\n".join(lines)

    # ── Execution ────────────────────────────────────────────

    async def execute(
        self,
        handoff_name: str,
        input_data: Dict[str, Any],
        *,
        source_agent: str = "coordinator",
    ) -> HandoffResult:
        """
        Execute a handoff: find the registered Handoff, validate input,
        spin up the specialist via *agent_runner*, return the result.
        """
        handoff = self._registry.get(handoff_name)
        if not handoff:
            return HandoffResult(
                handoff_id="none",
                status=HandoffStatus.FAILED,
                error=f"Unknown handoff: {handoff_name}",
            )

        request = HandoffRequest(
            handoff_name=handoff_name,
            input_data=input_data,
            source_agent=source_agent,
            target_agent=handoff.target_role,
        )

        # Validate input schema
        for key in handoff.input_schema:
            if key not in input_data:
                request.status = HandoffStatus.FAILED
                self._history.append(request)
                return HandoffResult(
                    handoff_id=request.handoff_id,
                    status=HandoffStatus.FAILED,
                    error=f"Missing required input key: {key}",
                )

        if not self._agent_runner:
            request.status = HandoffStatus.FAILED
            self._history.append(request)
            return HandoffResult(
                handoff_id=request.handoff_id,
                status=HandoffStatus.FAILED,
                error="No agent_runner configured,  cannot spawn specialist",
            )

        # Build the specialist prompt
        system_prompt = handoff.system_prompt_override or (
            f"You are a specialist {handoff.target_role} agent. "
            f"Your task: {handoff.description}. "
            f"Reply with ONLY the result,  no preamble."
        )
        user_message = _build_user_message(handoff, input_data)

        request.status = HandoffStatus.IN_PROGRESS
        logger.info(f"🤝 Handoff [{handoff_name}] → {handoff.target_role}")

        try:
            output = await self._agent_runner(
                system_prompt,
                user_message,
                handoff.tools_filter,
                handoff.max_turns,
            )
            request.status = HandoffStatus.COMPLETED
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status=HandoffStatus.COMPLETED,
                output=output,
                agent_role=handoff.target_role,
            )
        except Exception as exc:
            logger.error(f"Handoff [{handoff_name}] failed: {exc}")
            request.status = HandoffStatus.FAILED
            result = HandoffResult(
                handoff_id=request.handoff_id,
                status=HandoffStatus.FAILED,
                error=str(exc),
                agent_role=handoff.target_role,
            )

        request.result = result
        self._history.append(request)
        return result

    # ── Parse coordinator output ─────────────────────────────

    def parse_handoff_command(self, text: str) -> Optional[tuple[str, Dict[str, Any]]]:
        """
        Parse ``@handoff name {"key": "value"}`` from the coordinator's reply.
        Returns (handoff_name, input_data) or None.
        """
        import json as _json
        import re

        m = re.search(r"@handoff\s+(\w+)\s+(\{.*\})", text, re.DOTALL)
        if not m:
            return None
        name = m.group(1)
        try:
            data = _json.loads(m.group(2))
        except _json.JSONDecodeError:
            data = {"input": m.group(2)}
        return name, data

    @property
    def history(self) -> List[HandoffRequest]:
        return list(self._history)


def _build_user_message(handoff: Handoff, data: Dict[str, Any]) -> str:
    """Format input data into a user message for the specialist."""
    parts = [f"## Task: {handoff.name}", ""]
    for k, v in data.items():
        parts.append(f"**{k}:** {v}")
    return "\n".join(parts)


# ── Pre-built handoff catalogue ──────────────────────────────

def default_handoffs() -> List[Handoff]:
    """Return a useful set of pre-configured handoffs."""
    return [
        Handoff(
            name="code_review",
            target_role="reviewer",
            description="Reviews code for bugs, style issues, and security vulnerabilities",
            input_schema={"code": str, "language": str},
            max_turns=3,
        ),
        Handoff(
            name="research",
            target_role="researcher",
            description="Searches the web and knowledge base for factual information",
            input_schema={"query": str},
            max_turns=5,
        ),
        Handoff(
            name="write_code",
            target_role="coder",
            description="Writes or refactors code given a specification",
            input_schema={"spec": str, "language": str},
            max_turns=5,
        ),
        Handoff(
            name="summarize",
            target_role="analyst",
            description="Reads long text and produces a concise summary",
            input_schema={"text": str},
            max_turns=2,
        ),
        Handoff(
            name="translate",
            target_role="writer",
            description="Translates text between languages",
            input_schema={"text": str, "target_language": str},
            max_turns=2,
        ),
    ]
