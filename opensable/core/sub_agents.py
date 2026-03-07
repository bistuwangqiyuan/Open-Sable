"""
Sub-Agent Delegation — Actor-model fire-and-forget sub-agents.

Actor-model fire-and-forget sub-agent delegation.  The main agent can
delegate tasks to specialised sub-agents that run in background as
asyncio tasks.  Results are collected via an inbox.

Usage::

    from opensable.core.sub_agents import SubAgentManager, SubAgentSpec

    manager = SubAgentManager(parent_agent)
    manager.register(SubAgentSpec(
        name="researcher",
        description="Deep research on a topic",
        system_prompt="You are a research specialist...",
        tools=["browser_search", "scrape_url"],
    ))

    task_id = await manager.delegate("researcher", "Find papers on CoALA")
    # ... later ...
    results = manager.check_inbox()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from opensable.core.agent import SableAgent

logger = logging.getLogger(__name__)


@dataclass
class SubAgentSpec:
    """Specification for a sub-agent."""

    name: str
    description: str
    system_prompt: str = ""
    tools: List[str] = field(default_factory=list)  # Tool names to give the sub-agent
    model: str = ""  # Empty = same model as parent
    max_rounds: int = 5
    timeout_s: float = 120.0


@dataclass
class SubAgentResult:
    """Result from a completed sub-agent task."""

    task_id: str
    agent_name: str
    task: str
    result: str
    status: str  # "completed" | "error" | "timeout"
    duration_ms: float
    tool_calls: List[str] = field(default_factory=list)
    error: str = ""
    completed_at: float = field(default_factory=time.time)


class SubAgentManager:
    """Manages sub-agent delegation with actor-model inbox pattern.

    Sub-agents run as asyncio Tasks.  The parent agent delegates via
    ``delegate()`` (fire-and-forget) and later checks ``check_inbox()``
    for completed results.
    """

    def __init__(self, parent_agent: "SableAgent"):
        self.parent = parent_agent
        self._specs: Dict[str, SubAgentSpec] = {}
        self._pending: Dict[str, asyncio.Task] = {}
        self._results: Dict[str, SubAgentResult] = {}
        self._next_id = 0

    def register(self, spec: SubAgentSpec) -> None:
        """Register a sub-agent spec."""
        self._specs[spec.name] = spec
        logger.info(f"Registered sub-agent: {spec.name} — {spec.description}")

    def unregister(self, name: str) -> bool:
        """Unregister a sub-agent spec."""
        if name in self._specs:
            del self._specs[name]
            return True
        return False

    @property
    def registered_agents(self) -> List[str]:
        return list(self._specs.keys())

    # ── Delegation ──────────────────────────────────────────────────────

    async def delegate(
        self,
        agent_name: str,
        task: str,
        *,
        extra_context: str = "",
    ) -> str:
        """Delegate a task to a sub-agent.  Returns immediately with task_id.

        The sub-agent runs in background as an asyncio Task.
        """
        if agent_name not in self._specs:
            raise ValueError(f"Unknown sub-agent: {agent_name}. "
                             f"Available: {list(self._specs.keys())}")

        spec = self._specs[agent_name]
        task_id = f"{agent_name}_{self._next_id}"
        self._next_id += 1

        async def _run():
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    self._run_sub_agent(spec, task, extra_context),
                    timeout=spec.timeout_s,
                )
                elapsed = (time.monotonic() - start) * 1000
                self._results[task_id] = SubAgentResult(
                    task_id=task_id,
                    agent_name=agent_name,
                    task=task,
                    result=result.get("response", ""),
                    status="completed",
                    duration_ms=elapsed,
                    tool_calls=result.get("tools_used", []),
                )
                logger.info(f"Sub-agent {agent_name} completed: {task_id} ({elapsed:.0f}ms)")

            except asyncio.TimeoutError:
                elapsed = (time.monotonic() - start) * 1000
                self._results[task_id] = SubAgentResult(
                    task_id=task_id,
                    agent_name=agent_name,
                    task=task,
                    result="",
                    status="timeout",
                    duration_ms=elapsed,
                    error=f"Timed out after {spec.timeout_s}s",
                )
                logger.warning(f"Sub-agent {agent_name} timed out: {task_id}")

            except Exception as e:
                elapsed = (time.monotonic() - start) * 1000
                self._results[task_id] = SubAgentResult(
                    task_id=task_id,
                    agent_name=agent_name,
                    task=task,
                    result="",
                    status="error",
                    duration_ms=elapsed,
                    error=str(e),
                )
                logger.error(f"Sub-agent {agent_name} failed: {task_id}: {e}")

            finally:
                self._pending.pop(task_id, None)

        self._pending[task_id] = asyncio.create_task(_run())
        logger.info(f"Delegated to {agent_name}: {task_id} — '{task[:80]}'")
        return task_id

    async def _run_sub_agent(
        self,
        spec: SubAgentSpec,
        task: str,
        extra_context: str = "",
    ) -> Dict[str, Any]:
        """Run a sub-agent task using the parent's LLM.

        The sub-agent gets its own system prompt and a filtered set of
        tools.  It runs through the agentic loop for up to max_rounds.
        """
        # Build system prompt
        system_prompt = spec.system_prompt or (
            f"You are {spec.name}, a specialised sub-agent. "
            f"{spec.description}. "
            "Complete the task efficiently. Use tools when needed. "
            "Be concise in your response."
        )

        if extra_context:
            system_prompt += f"\n\nContext from parent agent:\n{extra_context}"

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task},
        ]

        # Get filtered tool schemas
        all_schemas = self.parent.tools.get_tool_schemas()
        if spec.tools:
            tool_schemas = [s for s in all_schemas if s.get("function", {}).get("name") in spec.tools]
        else:
            # Give all tools if none specified
            tool_schemas = all_schemas

        tools_used: List[str] = []

        # Run agentic loop (simplified version)
        for _round in range(spec.max_rounds):
            try:
                response = await asyncio.wait_for(
                    self.parent.llm.invoke_with_tools(
                        messages, tool_schemas if _round < spec.max_rounds - 1 else []
                    ),
                    timeout=60.0,
                )
            except Exception as e:
                return {"response": f"LLM error: {e}", "tools_used": tools_used}

            # Check for tool calls
            all_tool_calls = response.get("tool_calls", [])
            single_tc = response.get("tool_call")
            if single_tc and not all_tool_calls:
                all_tool_calls = [single_tc]

            if not all_tool_calls:
                # No tool calls — the sub-agent is done
                return {
                    "response": response.get("text", ""),
                    "tools_used": tools_used,
                }

            # Execute tools
            for tc in all_tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("arguments", {})
                tools_used.append(tool_name)

                try:
                    result = await self.parent._execute_tool(
                        tool_name, tool_args, user_id="sub_agent"
                    )
                    messages.append({
                        "role": "assistant",
                        "content": f"Called tool: {tool_name}",
                    })
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": str(result)[:4000],
                    })
                except Exception as e:
                    messages.append({
                        "role": "tool",
                        "name": tool_name,
                        "content": f"Error: {e}",
                    })

        # Max rounds reached — synthesise from what we have
        return {
            "response": response.get("text", "Max rounds reached"),
            "tools_used": tools_used,
        }

    # ── Inbox ───────────────────────────────────────────────────────────

    def check_inbox(self) -> Dict[str, SubAgentResult]:
        """Check inbox for completed sub-agent results.

        Returns dict of task_id → SubAgentResult for completed tasks.
        Results persist until clear_inbox() is called.
        """
        return dict(self._results)

    def get_result(self, task_id: str) -> Optional[SubAgentResult]:
        """Get result for a specific task_id."""
        return self._results.get(task_id)

    def clear_inbox(self) -> int:
        """Clear completed results from inbox.  Returns count of cleared items."""
        count = len(self._results)
        self._results.clear()
        return count

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def completed_count(self) -> int:
        return len(self._results)

    # ── Await all ───────────────────────────────────────────────────────

    async def await_all(self, timeout_s: float = 120.0) -> Dict[str, SubAgentResult]:
        """Wait for all pending sub-agents to complete.

        Used at the end of a tick to ensure no leaked tasks.
        """
        if not self._pending:
            return dict(self._results)

        tasks = list(self._pending.values())
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            # Cancel remaining
            for t in tasks:
                if not t.done():
                    t.cancel()
            logger.warning(f"Timed out waiting for {len(tasks)} sub-agent(s)")

        return dict(self._results)

    def get_status(self) -> Dict[str, Any]:
        """Get sub-agent manager status."""
        return {
            "registered_agents": list(self._specs.keys()),
            "pending_tasks": list(self._pending.keys()),
            "completed_results": list(self._results.keys()),
            "specs": {
                name: {
                    "description": spec.description,
                    "tools": spec.tools,
                    "max_rounds": spec.max_rounds,
                    "timeout": spec.timeout_s,
                }
                for name, spec in self._specs.items()
            },
        }


# ── Default sub-agent specs ────────────────────────────────────────────────

DEFAULT_SUB_AGENTS = [
    SubAgentSpec(
        name="researcher",
        description="Deep research on a topic using web search and scraping",
        system_prompt=(
            "You are a research specialist. Use browser_search and scrape_url "
            "to find accurate, up-to-date information. Cite sources. "
            "Return a concise summary with key findings."
        ),
        tools=["browser_search", "scrape_url", "file_read"],
        max_rounds=5,
        timeout_s=120.0,
    ),
    SubAgentSpec(
        name="coder",
        description="Write, review, or debug code",
        system_prompt=(
            "You are a coding specialist. Write clean, tested code. "
            "Use code_execute to test your code before returning it. "
            "Include error handling and type hints."
        ),
        tools=["code_execute", "file_read", "file_write", "execute_command"],
        max_rounds=5,
        timeout_s=90.0,
    ),
    SubAgentSpec(
        name="analyst",
        description="Analyse data, files, and system state",
        system_prompt=(
            "You are an analysis specialist. Examine data thoroughly, "
            "identify patterns and anomalies. Return structured findings "
            "with clear conclusions."
        ),
        tools=["file_read", "execute_command", "code_execute", "system_info"],
        max_rounds=4,
        timeout_s=60.0,
    ),
    SubAgentSpec(
        name="communicator",
        description="Draft messages, emails, and social media posts",
        system_prompt=(
            "You are a communications specialist. Write clear, engaging "
            "messages appropriate for the target platform and audience. "
            "Adapt tone and format to context."
        ),
        tools=["email_send", "email_read"],
        max_rounds=3,
        timeout_s=45.0,
    ),
]
