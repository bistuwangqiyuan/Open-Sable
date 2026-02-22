"""
Event-Driven Flows — declarative workflow DSL with ``@start``, ``@listen``,
and ``@router`` decorators (inspired by CrewAI Flows).

A *Flow* is a class whose methods are wired together via events.
Each method can emit an event that triggers the next method, enabling
branching, parallelism, and conditional logic without explicit orchestration.

Usage:
    from opensable.core.flows import Flow, start, listen, router

    class AnalysisFlow(Flow):
        @start()
        async def ingest(self):
            data = await load_data()
            return data

        @listen("ingest")
        async def analyse(self, data):
            result = analyse(data)
            return result

        @router("analyse")
        async def route(self, result):
            if result.score > 0.8:
                return "publish"
            return "review"

        @listen("publish")
        async def publish(self, result):
            await send_report(result)

        @listen("review")
        async def review(self, result):
            await request_human_review(result)

    flow = AnalysisFlow()
    await flow.run()
"""

from __future__ import annotations

import asyncio
import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
import time

logger = logging.getLogger(__name__)


# ── Decorators ───────────────────────────────────────────────

def start():
    """Mark a method as the flow's entry point."""
    def decorator(fn: Callable) -> Callable:
        fn._flow_start = True  # type: ignore[attr-defined]
        fn._flow_listens: list[str] = []  # type: ignore[attr-defined]
        fn._flow_router = False  # type: ignore[attr-defined]
        return fn
    return decorator


def listen(*event_names: str):
    """Mark a method as a listener for one or more events (by step name)."""
    def decorator(fn: Callable) -> Callable:
        fn._flow_start = False  # type: ignore[attr-defined]
        fn._flow_listens = list(event_names)  # type: ignore[attr-defined]
        fn._flow_router = False  # type: ignore[attr-defined]
        return fn
    return decorator


def router(*event_names: str):
    """
    Mark a method as a *router*.  A router receives data from upstream
    and returns the **name** of the next step to trigger.
    """
    def decorator(fn: Callable) -> Callable:
        fn._flow_start = False  # type: ignore[attr-defined]
        fn._flow_listens = list(event_names)  # type: ignore[attr-defined]
        fn._flow_router = True  # type: ignore[attr-defined]
        return fn
    return decorator


# ── Data Structures ──────────────────────────────────────────

@dataclass
class FlowEvent:
    """An event flowing through the graph."""
    source: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class StepResult:
    """Record of one step's execution."""
    name: str
    status: str = "pending"  # "pending", "running", "completed", "failed", "skipped"
    output: Any = None
    error: str = ""
    duration: float = 0.0


# ── Flow Base Class ──────────────────────────────────────────

class Flow:
    """
    Base class for event-driven flows.

    Subclass this, decorate methods with ``@start``, ``@listen``, ``@router``,
    then call ``await flow.run()``.
    """

    def __init__(self, **initial_state: Any):
        self.state: Dict[str, Any] = dict(initial_state)
        self._steps: Dict[str, Callable] = {}
        self._listeners: Dict[str, List[str]] = {}  # event_name → [step_names]
        self._routers: Set[str] = set()
        self._start_steps: List[str] = []
        self._results: Dict[str, StepResult] = {}
        self._discover_steps()

    def _discover_steps(self) -> None:
        """Introspect decorated methods and build the event graph."""
        for name in dir(self):
            method = getattr(self, name, None)
            if not callable(method):
                continue
            if getattr(method, "_flow_start", False):
                self._start_steps.append(name)
                self._steps[name] = method
            if getattr(method, "_flow_listens", None):
                self._steps[name] = method
                for event in method._flow_listens:
                    self._listeners.setdefault(event, []).append(name)
            if getattr(method, "_flow_router", False):
                self._routers.add(name)

    async def run(self, **kwargs: Any) -> Dict[str, StepResult]:
        """Execute the flow starting from ``@start`` methods."""
        self.state.update(kwargs)

        if not self._start_steps:
            raise ValueError("Flow has no @start method")

        # Run all @start methods in parallel
        start_tasks = [self._run_step(name, None) for name in self._start_steps]
        await asyncio.gather(*start_tasks)

        return self._results

    async def _run_step(self, name: str, input_data: Any) -> None:
        """Run a single step and propagate its output to listeners."""
        method = self._steps.get(name)
        if not method:
            logger.warning(f"Flow step not found: {name}")
            return

        result = StepResult(name=name, status="running")
        self._results[name] = result
        t0 = time.time()

        try:
            # Call the step method
            sig = inspect.signature(method)
            params = list(sig.parameters.keys())
            if len(params) >= 1 and params[0] != "self":
                # Step expects input data
                output = method(input_data)
            elif len(params) == 0:
                output = method()
            else:
                output = method(input_data) if input_data is not None else method()

            if asyncio.iscoroutine(output):
                output = await output

            result.output = output
            result.status = "completed"
            result.duration = time.time() - t0

            logger.debug(f"Flow step '{name}' completed in {result.duration:.2f}s")

        except Exception as exc:
            result.status = "failed"
            result.error = str(exc)
            result.duration = time.time() - t0
            logger.error(f"Flow step '{name}' failed: {exc}")
            return  # Don't propagate on failure

        # Store the result in shared state
        self.state[name] = output

        # If this is a router, the output is the NAME of the next step
        if name in self._routers:
            next_step_name = str(output)
            listeners = self._listeners.get(next_step_name, [])
            if not listeners:
                # Maybe the router returned the step name directly
                if next_step_name in self._steps:
                    await self._run_step(next_step_name, result.output)
                else:
                    logger.warning(f"Router '{name}' returned unknown target: {next_step_name}")
                return

            tasks = [self._run_step(ln, result.output) for ln in listeners]
            await asyncio.gather(*tasks)
        else:
            # Normal step — trigger all listeners for this step name
            listeners = self._listeners.get(name, [])
            if listeners:
                tasks = [self._run_step(ln, output) for ln in listeners]
                await asyncio.gather(*tasks)

    # ── Introspection ────────────────────────────────────────

    @property
    def graph_description(self) -> str:
        """Human-readable description of the flow graph."""
        lines = [f"Flow: {self.__class__.__name__}", ""]
        for name in self._start_steps:
            lines.append(f"  @start → {name}")
        for event, step_names in self._listeners.items():
            for sn in step_names:
                tag = " (router)" if sn in self._routers else ""
                lines.append(f"  {event} → {sn}{tag}")
        return "\n".join(lines)

    @property
    def completed(self) -> bool:
        return all(r.status in ("completed", "skipped") for r in self._results.values())

    @property
    def failed_steps(self) -> List[str]:
        return [n for n, r in self._results.items() if r.status == "failed"]


# ── Convenience: inline flow builder ─────────────────────────

class FlowBuilder:
    """
    Programmatic flow builder for when you don't want to subclass.

    Usage:
        fb = FlowBuilder("my_flow")
        fb.add_start("fetch", fetch_data)
        fb.add_listener("fetch", "process", process_data)
        fb.add_router("process", "route", route_fn)
        fb.add_listener("publish", "publish", publish_fn)
        flow = fb.build()
        await flow.run()
    """

    def __init__(self, name: str = "inline_flow"):
        self.name = name
        self._start_fns: Dict[str, Callable] = {}
        self._listen_fns: Dict[str, List[tuple[str, Callable]]] = {}
        self._router_fns: Dict[str, tuple[str, Callable]] = {}

    def add_start(self, name: str, fn: Callable) -> "FlowBuilder":
        self._start_fns[name] = fn
        return self

    def add_listener(self, event: str, name: str, fn: Callable) -> "FlowBuilder":
        self._listen_fns.setdefault(event, []).append((name, fn))
        return self

    def add_router(self, event: str, name: str, fn: Callable) -> "FlowBuilder":
        self._router_fns[event] = (name, fn)
        return self

    def build(self) -> Flow:
        """Build a Flow instance from the registered functions."""
        builder = self

        class _DynFlow(Flow):
            pass

        # Add start methods — wrap as staticmethod so getattr() doesn't inject 'self'
        for name, fn in builder._start_fns.items():
            decorated = start()(fn)
            setattr(_DynFlow, name, staticmethod(decorated))

        # Add listeners
        for event, pairs in builder._listen_fns.items():
            for name, fn in pairs:
                decorated = listen(event)(fn)
                setattr(_DynFlow, name, staticmethod(decorated))

        # Add routers
        for event, (name, fn) in builder._router_fns.items():
            decorated = router(event)(fn)
            setattr(_DynFlow, name, staticmethod(decorated))

        return _DynFlow()
