"""
Runner — The one-liner entry point for Open-Sable.

Inspired by the OpenAI Agents SDK ``Runner.run_sync()`` pattern, but with
Open-Sable's full power underneath (planning, parallel tools, guardrails,
HITL, checkpointing, streaming).

Usage:
    from opensable import Agent, Runner

    agent = Agent(name="Sable")
    result = Runner.run_sync(agent, "What is the capital of France?")
    print(result.text)

    # With custom tools:
    from opensable import function_tool

    @function_tool
    async def get_weather(city: str) -> str:
        '''Get weather for a city.'''
        return f"Sunny in {city}"

    agent = Agent(name="WeatherBot", tools=[get_weather])
    result = Runner.run_sync(agent, "What's the weather in Tokyo?")

    # Streaming:
    async for event in Runner.run_streamed(agent, "Search for Python news"):
        print(event)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from .function_tool import FunctionTool

logger = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Result of a single agent run."""
    text: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text

    def __repr__(self) -> str:
        preview = self.text[:80] + "..." if len(self.text) > 80 else self.text
        return f'RunResult("{preview}")'


@dataclass
class StreamEvent:
    """A single event from a streamed agent run."""
    type: str  # "progress" | "token" | "response"
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.text


class Agent:
    """
    Lightweight agent configuration object.

    This is the public-facing Agent — not to be confused with the internal
    ``SableAgent``.  It wraps SableAgent with a clean SDK surface.

    Args:
        name:         Display name for the agent.
        instructions: System prompt / personality (optional).
        tools:        List of @function_tool-decorated callables.
        model:        Override the default LLM model.
        config:       Full OpenSableConfig (advanced).
    """

    def __init__(
        self,
        name: str = "Sable",
        *,
        instructions: str | None = None,
        tools: List[FunctionTool] | None = None,
        model: str | None = None,
        config: Any | None = None,
    ):
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        self.model = model
        self._config = config
        self._core_agent = None  # lazy

    async def _ensure_initialised(self) -> Any:
        """Lazily initialise the underlying SableAgent."""
        if self._core_agent is not None:
            return self._core_agent

        from .config import OpenSableConfig
        from .agent import SableAgent

        cfg = self._config or OpenSableConfig()

        if self.instructions:
            cfg.agent_personality = "__custom__"
            cfg._custom_personality = self.instructions

        if self.model:
            cfg.default_model = self.model

        core = SableAgent(cfg)
        await core.initialize()

        # Register @function_tool tools into the ToolRegistry
        if self.tools:
            for ft in self.tools:
                if isinstance(ft, FunctionTool):
                    # Register handler and schema
                    core.tools.register(ft.name, ft.execute)
                    core.tools._custom_schemas.append(ft.schema)

        # Patch personality if custom instructions
        if self.instructions:
            original_fn = core._get_personality_prompt

            def _custom_personality(_self=None):
                return self.instructions

            core._get_personality_prompt = _custom_personality

        self._core_agent = core
        return core


class Runner:
    """
    Static methods to run an Agent.

    Handles all the async lifecycle so the user never has to.
    """

    @staticmethod
    async def run(
        agent: Agent,
        message: str,
        *,
        user_id: str = "default_user",
        history: List[dict] | None = None,
    ) -> RunResult:
        """
        Run the agent asynchronously and return the result.

        Args:
            agent:   An ``Agent`` instance.
            message: The user message.
            user_id: User identifier for memory & HITL.
            history: Optional conversation history.
        """
        core = await agent._ensure_initialised()
        text = await core.process_message(user_id, message, history)
        return RunResult(text=text, metadata={"agent": agent.name, "user_id": user_id})

    @staticmethod
    def run_sync(
        agent: Agent,
        message: str,
        *,
        user_id: str = "default_user",
        history: List[dict] | None = None,
    ) -> RunResult:
        """
        Synchronous convenience wrapper — creates/reuses an event loop.

        Perfect for scripts, notebooks, and one-liners:
            result = Runner.run_sync(Agent(), "Hello!")
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = Runner.run(agent, message, user_id=user_id, history=history)

        if loop and loop.is_running():
            # Already in an async context (Jupyter, etc.)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    @staticmethod
    async def run_streamed(
        agent: Agent,
        message: str,
        *,
        user_id: str = "default_user",
        history: List[dict] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        """
        Stream progress events and the final response.

        Usage:
            async for event in Runner.run_streamed(agent, "search python"):
                if event.type == "progress":
                    print(f"  ⏳ {event.text}")
                elif event.type == "response":
                    print(f"  ✅ {event.text}")
        """
        core = await agent._ensure_initialised()
        async for ev in core.stream(message, user_id=user_id, history=history):
            yield StreamEvent(
                type=ev.get("type", "progress"),
                text=ev.get("text", ""),
                metadata={"agent": agent.name},
            )
