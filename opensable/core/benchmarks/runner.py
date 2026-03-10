"""
Benchmark Runner,  Core evaluation harness for Open-Sable.

Executes benchmark suites against the agent, collects results,
computes metrics, and generates reports.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Data classes ──────────────────────────────────────────────────────────────


class TaskDifficulty(Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    TIMEOUT = "timeout"
    SKIPPED = "skipped"


@dataclass
class BenchmarkTask:
    """A single benchmark task to evaluate."""

    task_id: str
    prompt: str
    expected: str                           # Expected answer / output
    difficulty: TaskDifficulty = TaskDifficulty.MEDIUM
    category: str = ""                      # e.g. "math", "code", "web"
    metadata: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 120                      # seconds
    files: Dict[str, str] = field(default_factory=dict)  # input files


@dataclass
class TaskResult:
    """Result of running a single benchmark task."""

    task_id: str
    status: TaskStatus
    agent_answer: str = ""
    expected: str = ""
    score: float = 0.0                      # 0.0 - 1.0
    duration_ms: int = 0
    error: str = ""
    tool_calls: int = 0
    tokens_used: int = 0
    reasoning_steps: int = 0

    @property
    def passed(self) -> bool:
        return self.status == TaskStatus.PASSED

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "score": self.score,
            "duration_ms": self.duration_ms,
            "agent_answer": self.agent_answer[:200],
            "expected": self.expected[:200],
            "error": self.error,
            "tool_calls": self.tool_calls,
            "tokens_used": self.tokens_used,
        }


@dataclass
class BenchmarkResult:
    """Aggregated results from a benchmark suite run."""

    suite_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    timeouts: int = 0
    skipped: int = 0
    avg_score: float = 0.0
    avg_duration_ms: float = 0.0
    total_duration_ms: int = 0
    tasks: List[TaskResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    model: str = ""
    agent_version: str = ""
    by_difficulty: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    by_category: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        return (self.passed / self.total * 100) if self.total > 0 else 0.0

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"═══ {self.suite_name} Benchmark Results ═══",
            f"Model:      {self.model}",
            f"Total:      {self.total} tasks",
            f"Passed:     {self.passed}/{self.total} ({self.pass_rate:.1f}%)",
            f"Failed:     {self.failed}",
            f"Errors:     {self.errors}",
            f"Timeouts:   {self.timeouts}",
            f"Avg Score:  {self.avg_score:.3f}",
            f"Avg Time:   {self.avg_duration_ms:.0f}ms",
            f"Total Time: {self.total_duration_ms / 1000:.1f}s",
        ]

        if self.by_difficulty:
            lines.append("\nBy Difficulty:")
            for diff, stats in sorted(self.by_difficulty.items()):
                lines.append(f"  {diff}: {stats.get('passed', 0)}/{stats.get('total', 0)} ({stats.get('rate', 0):.1f}%)")

        if self.by_category:
            lines.append("\nBy Category:")
            for cat, stats in sorted(self.by_category.items()):
                lines.append(f"  {cat}: {stats.get('passed', 0)}/{stats.get('total', 0)} ({stats.get('rate', 0):.1f}%)")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "suite": self.suite_name,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "timeouts": self.timeouts,
            "pass_rate": round(self.pass_rate, 2),
            "avg_score": round(self.avg_score, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "total_duration_ms": self.total_duration_ms,
            "model": self.model,
            "agent_version": self.agent_version,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "by_difficulty": self.by_difficulty,
            "by_category": self.by_category,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    def save(self, path: Path):
        """Save results to JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[Benchmark] Results saved to {path}")


# ── Benchmark Suite (abstract) ────────────────────────────────────────────────


class BenchmarkSuite(ABC):
    """Base class for benchmark suites."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Suite name (e.g. 'GAIA', 'SWE-bench')."""
        ...

    @property
    def version(self) -> str:
        return "1.0"

    @abstractmethod
    def load_tasks(self) -> List[BenchmarkTask]:
        """Load all benchmark tasks."""
        ...

    @abstractmethod
    def evaluate(self, task: BenchmarkTask, agent_answer: str) -> float:
        """
        Score the agent's answer against the expected answer.

        Returns:
            float between 0.0 (wrong) and 1.0 (perfect).
        """
        ...


# ── Evaluation helpers ────────────────────────────────────────────────────────


def exact_match(expected: str, actual: str) -> float:
    """Case-insensitive exact match."""
    return 1.0 if expected.strip().lower() == actual.strip().lower() else 0.0


def contains_match(expected: str, actual: str) -> float:
    """Check if expected answer is contained in agent's response."""
    return 1.0 if expected.strip().lower() in actual.strip().lower() else 0.0


def numeric_match(expected: str, actual: str, tolerance: float = 0.01) -> float:
    """Compare numeric answers with tolerance."""
    try:
        exp_num = float(expected.strip())
        act_num = float(actual.strip().replace(",", "").replace("$", "").replace("%", ""))
        if exp_num == 0:
            return 1.0 if abs(act_num) < tolerance else 0.0
        return 1.0 if abs((act_num - exp_num) / exp_num) <= tolerance else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def multi_choice_match(expected: str, actual: str) -> float:
    """Match single-letter multiple choice answers."""
    exp = expected.strip().upper()
    # Extract last single letter (A-E) from agent response
    import re
    matches = re.findall(r'\b([A-E])\b', actual.upper())
    if matches:
        return 1.0 if matches[-1] == exp else 0.0
    return 0.0


# ── Benchmark Runner ──────────────────────────────────────────────────────────


class BenchmarkRunner:
    """
    Runs benchmark suites against an Open-Sable agent.

    Usage:
        runner = BenchmarkRunner(agent)
        result = await runner.run_suite(GAIASuite())
        print(result.summary())
    """

    def __init__(
        self,
        agent=None,
        *,
        concurrency: int = 1,
        results_dir: str = "data/benchmarks",
        progress_callback: Optional[Callable] = None,
    ):
        self.agent = agent
        self.concurrency = concurrency
        self.results_dir = Path(results_dir)
        self.progress_callback = progress_callback

    async def run_suite(
        self,
        suite: BenchmarkSuite,
        *,
        max_tasks: Optional[int] = None,
        categories: Optional[List[str]] = None,
        difficulties: Optional[List[str]] = None,
    ) -> BenchmarkResult:
        """
        Run all tasks in a benchmark suite.

        Args:
            suite: The benchmark suite to run.
            max_tasks: Limit number of tasks (for quick testing).
            categories: Filter by category.
            difficulties: Filter by difficulty.
        """
        started_at = datetime.now().isoformat()
        t0 = time.monotonic()

        # Load and filter tasks
        tasks = suite.load_tasks()

        if categories:
            tasks = [t for t in tasks if t.category in categories]
        if difficulties:
            diff_set = {TaskDifficulty(d) for d in difficulties}
            tasks = [t for t in tasks if t.difficulty in diff_set]
        if max_tasks:
            tasks = tasks[:max_tasks]

        logger.info(f"[Benchmark] Running {suite.name},  {len(tasks)} tasks")

        # Execute tasks
        results: List[TaskResult] = []
        if self.concurrency <= 1:
            for i, task in enumerate(tasks):
                result = await self._run_task(suite, task)
                results.append(result)
                if self.progress_callback:
                    await self.progress_callback(
                        f"[{i + 1}/{len(tasks)}] {task.task_id}: "
                        f"{'✅' if result.passed else '❌'} ({result.duration_ms}ms)"
                    )
        else:
            # Concurrent execution with semaphore
            sem = asyncio.Semaphore(self.concurrency)

            async def _bounded(task):
                async with sem:
                    return await self._run_task(suite, task)

            results = await asyncio.gather(*[_bounded(t) for t in tasks])
            results = list(results)

        # Aggregate results
        total_duration = int((time.monotonic() - t0) * 1000)
        result = self._aggregate(suite.name, results, started_at, total_duration)

        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result.save(self.results_dir / f"{suite.name.lower()}_{timestamp}.json")

        logger.info(f"[Benchmark] {suite.name} complete: {result.pass_rate:.1f}% pass rate")
        return result

    async def _run_task(self, suite: BenchmarkSuite, task: BenchmarkTask) -> TaskResult:
        """Run a single benchmark task."""
        t0 = time.monotonic()

        try:
            if self.agent is None:
                return TaskResult(
                    task_id=task.task_id,
                    status=TaskStatus.SKIPPED,
                    error="No agent configured",
                )

            # Send task prompt to agent
            agent_answer = await asyncio.wait_for(
                self.agent.process_message(
                    user_id=f"benchmark_{task.task_id}",
                    message=task.prompt,
                ),
                timeout=task.timeout,
            )

            duration_ms = int((time.monotonic() - t0) * 1000)

            # Evaluate
            score = suite.evaluate(task, agent_answer)
            status = TaskStatus.PASSED if score >= 0.5 else TaskStatus.FAILED

            return TaskResult(
                task_id=task.task_id,
                status=status,
                agent_answer=agent_answer,
                expected=task.expected,
                score=score,
                duration_ms=duration_ms,
            )

        except asyncio.TimeoutError:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.TIMEOUT,
                expected=task.expected,
                duration_ms=duration_ms,
                error=f"Timed out after {task.timeout}s",
            )
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            logger.warning(f"[Benchmark] Task {task.task_id} error: {e}")
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.ERROR,
                expected=task.expected,
                duration_ms=duration_ms,
                error=str(e),
            )

    def _aggregate(
        self,
        suite_name: str,
        results: List[TaskResult],
        started_at: str,
        total_duration_ms: int,
    ) -> BenchmarkResult:
        """Aggregate individual task results into a BenchmarkResult."""
        passed = sum(1 for r in results if r.status == TaskStatus.PASSED)
        failed = sum(1 for r in results if r.status == TaskStatus.FAILED)
        errors = sum(1 for r in results if r.status == TaskStatus.ERROR)
        timeouts = sum(1 for r in results if r.status == TaskStatus.TIMEOUT)
        skipped = sum(1 for r in results if r.status == TaskStatus.SKIPPED)

        scores = [r.score for r in results if r.status in (TaskStatus.PASSED, TaskStatus.FAILED)]
        durations = [r.duration_ms for r in results if r.duration_ms > 0]

        # Get model info from agent
        model = ""
        version = "1.1.0"
        if self.agent:
            if hasattr(self.agent, "llm") and hasattr(self.agent.llm, "current_model"):
                model = self.agent.llm.current_model or ""

        result = BenchmarkResult(
            suite_name=suite_name,
            total=len(results),
            passed=passed,
            failed=failed,
            errors=errors,
            timeouts=timeouts,
            skipped=skipped,
            avg_score=sum(scores) / len(scores) if scores else 0.0,
            avg_duration_ms=sum(durations) / len(durations) if durations else 0.0,
            total_duration_ms=total_duration_ms,
            tasks=results,
            started_at=started_at,
            finished_at=datetime.now().isoformat(),
            model=model,
            agent_version=version,
        )

        # Breakdown by difficulty / category (using metadata from tasks,  
        # we don't store tasks on TaskResult, so we index by task_id)
        return result

    async def run_quick(self) -> Dict[str, BenchmarkResult]:
        """Run a quick evaluation across all built-in suites (5 tasks each)."""
        from .suites import ReasoningSuite, ToolUseSuite

        results = {}
        for suite_cls in [ReasoningSuite, ToolUseSuite]:
            suite = suite_cls()
            result = await self.run_suite(suite, max_tasks=5)
            results[suite.name] = result

        return results
