"""
Quantified Self-Benchmarking — Internal performance benchmarks the agent runs on itself.

Unlike external benchmarks, this module:
  • Defines 8 internal benchmark suites the agent runs periodically
  • Measures: response quality, tool usage, planning depth, error recovery,
    memory recall, emotional stability, decision speed, learning rate
  • Scores each on a 0–100 scale with historical tracking
  • Computes an aggregate "autonomy score" from all sub-scores
  • Detects regressions (score drops below rolling average)
  • Persists all benchmark results for trend analysis
  • Runs every N ticks (default 25) — lightweight self-assessment
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Benchmark Suite Definitions ──────────────────────────────────────────────

BENCHMARK_SUITES = {
    "task_success": {
        "name": "Task Success Rate",
        "description": "Percentage of tasks completed successfully",
        "weight": 0.20,
    },
    "planning_depth": {
        "name": "Planning Depth",
        "description": "Average number of steps in plans + dependency complexity",
        "weight": 0.15,
    },
    "error_recovery": {
        "name": "Error Recovery",
        "description": "Ability to recover from failures (retry success rate)",
        "weight": 0.15,
    },
    "memory_utilization": {
        "name": "Memory Utilization",
        "description": "How effectively consolidated wisdom is applied",
        "weight": 0.10,
    },
    "emotional_stability": {
        "name": "Emotional Stability",
        "description": "Consistency of emotional state (low valence variance)",
        "weight": 0.10,
    },
    "decision_speed": {
        "name": "Decision Speed",
        "description": "Average time from task discovery to execution start",
        "weight": 0.10,
    },
    "learning_rate": {
        "name": "Learning Rate",
        "description": "Rate of new patterns/insights per tick",
        "weight": 0.10,
    },
    "inter_agent_synergy": {
        "name": "Inter-Agent Synergy",
        "description": "Effectiveness of shared learnings (import + apply rate)",
        "weight": 0.10,
    },
}


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""
    suite: str
    score: float                 # 0–100
    timestamp: str
    tick: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    regression: bool = False     # True if score dropped significantly


@dataclass
class BenchmarkSnapshot:
    """Complete snapshot of all benchmarks at a point in time."""
    snapshot_id: int
    timestamp: str
    tick: int
    results: Dict[str, float]   # suite → score
    autonomy_score: float       # Weighted aggregate
    regressions: List[str]      # Suites that regressed


class SelfBenchmark:
    """
    Quantified self-benchmarking engine.

    Runs 8 internal benchmark suites and computes an aggregate autonomy score.
    Tracks trends and detects regressions.
    """

    def __init__(self, data_dir: Path, run_every_n_ticks: int = 25):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._run_every = run_every_n_ticks

        # State
        self._history: Dict[str, List[BenchmarkResult]] = {k: [] for k in BENCHMARK_SUITES}
        self._snapshots: List[BenchmarkSnapshot] = []
        self._total_runs = 0
        self._last_run_tick = -1
        self._current_autonomy_score = 0.0

        self._load_state()

    # ── Public API ────────────────────────────────────────────────────────────

    async def run_benchmarks(self, tick: int, agent_state: Dict[str, Any]) -> Optional[BenchmarkSnapshot]:
        """
        Run all benchmark suites and return a snapshot.

        agent_state should contain:
          - completed_tasks: List[Dict] — recent completed tasks
          - task_queue: List[Dict] — current queue
          - inner_life: inner life processor instance or None
          - cognitive_memory_count: int
          - deep_planner: DeepPlanner instance or None
          - ultra_ltm: UltraLongTermMemory instance or None
          - inter_agent_bridge: InterAgentBridge instance or None
          - connectome: NeuralColony instance or None
          - tick: int
        """
        if tick - self._last_run_tick < self._run_every:
            return None

        self._last_run_tick = tick
        self._total_runs += 1
        start = time.monotonic()

        results: Dict[str, float] = {}
        regressions: List[str] = []

        # Run each suite
        for suite_id, suite_info in BENCHMARK_SUITES.items():
            try:
                score = self._run_suite(suite_id, agent_state)
                score = max(0, min(100, score))

                # Check for regression
                is_regression = self._check_regression(suite_id, score)
                if is_regression:
                    regressions.append(suite_id)

                result = BenchmarkResult(
                    suite=suite_id,
                    score=score,
                    timestamp=datetime.now().isoformat(),
                    tick=tick,
                    regression=is_regression,
                    details={"method": f"auto_{suite_id}"},
                )
                self._history[suite_id].append(result)
                # Keep last 100 per suite
                if len(self._history[suite_id]) > 100:
                    self._history[suite_id] = self._history[suite_id][-100:]

                results[suite_id] = score
            except Exception as e:
                logger.debug(f"SelfBenchmark: Suite '{suite_id}' failed: {e}")
                results[suite_id] = self._last_known_score(suite_id)

        # Compute weighted autonomy score
        autonomy = 0.0
        for suite_id, score in results.items():
            weight = BENCHMARK_SUITES[suite_id]["weight"]
            autonomy += score * weight
        self._current_autonomy_score = round(autonomy, 1)

        # Create snapshot
        snapshot = BenchmarkSnapshot(
            snapshot_id=len(self._snapshots) + 1,
            timestamp=datetime.now().isoformat(),
            tick=tick,
            results=results,
            autonomy_score=self._current_autonomy_score,
            regressions=regressions,
        )
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 200:
            self._snapshots = self._snapshots[-200:]

        duration_ms = (time.monotonic() - start) * 1000

        self._save_state()

        if regressions:
            logger.warning(
                f"📊 SelfBenchmark: Autonomy={self._current_autonomy_score}/100 "
                f"⚠️ Regressions in: {regressions} ({duration_ms:.0f}ms)"
            )
        else:
            logger.info(
                f"📊 SelfBenchmark: Autonomy={self._current_autonomy_score}/100 "
                f"({duration_ms:.0f}ms)"
            )

        return snapshot

    def get_autonomy_score(self) -> float:
        return self._current_autonomy_score

    def get_suite_trend(self, suite_id: str, last_n: int = 20) -> List[Dict]:
        """Get trend data for a specific suite."""
        history = self._history.get(suite_id, [])
        return [
            {
                "score": r.score,
                "tick": r.tick,
                "timestamp": r.timestamp,
                "regression": r.regression,
            }
            for r in history[-last_n:]
        ]

    def get_stats(self) -> Dict[str, Any]:
        current_scores = {}
        for suite_id in BENCHMARK_SUITES:
            history = self._history.get(suite_id, [])
            if history:
                current_scores[suite_id] = {
                    "score": round(history[-1].score, 1),
                    "trend": self._compute_trend(suite_id),
                    "name": BENCHMARK_SUITES[suite_id]["name"],
                }
            else:
                current_scores[suite_id] = {
                    "score": 0,
                    "trend": "stable",
                    "name": BENCHMARK_SUITES[suite_id]["name"],
                }

        return {
            "autonomy_score": self._current_autonomy_score,
            "total_runs": self._total_runs,
            "suites": current_scores,
            "recent_snapshots": [
                {
                    "id": s.snapshot_id,
                    "tick": s.tick,
                    "autonomy": s.autonomy_score,
                    "regressions": s.regressions,
                    "timestamp": s.timestamp,
                }
                for s in self._snapshots[-10:]
            ],
            "trend_direction": self._overall_trend(),
        }

    # ── Suite Implementations ────────────────────────────────────────────────

    def _run_suite(self, suite_id: str, state: Dict[str, Any]) -> float:
        """Run a specific benchmark suite. Returns 0–100."""
        method = getattr(self, f"_bench_{suite_id}", None)
        if method:
            return method(state)
        return 50.0  # Default neutral score

    def _bench_task_success(self, state: Dict[str, Any]) -> float:
        """Task success rate from recent completed tasks."""
        completed = state.get("completed_tasks", [])
        if not completed:
            return 50.0

        recent = completed[-50:]
        success = sum(1 for t in recent if t.get("status") == "done")
        total = len(recent)
        if total == 0:
            return 50.0
        rate = success / total
        return rate * 100

    def _bench_planning_depth(self, state: Dict[str, Any]) -> float:
        """How deep are the agent's plans?"""
        planner = state.get("deep_planner")
        if not planner:
            return 20.0  # No planner = low score

        stats = planner.get_stats() if hasattr(planner, "get_stats") else {}
        plans = stats.get("plans", [])
        if not plans:
            return 30.0

        # Score based on avg step count and plan completion
        total_steps = sum(p.get("steps", 0) for p in plans)
        total_plans = len(plans)
        avg_steps = total_steps / max(1, total_plans)

        completed_plans = sum(1 for p in plans if p.get("status") == "completed")
        completion_rate = completed_plans / max(1, total_plans)

        # avg_steps of 10 → 80 points, + completion bonus
        depth_score = min(80, avg_steps * 8)
        completion_bonus = completion_rate * 20

        return min(100, depth_score + completion_bonus)

    def _bench_error_recovery(self, state: Dict[str, Any]) -> float:
        """How well does the agent recover from errors?"""
        completed = state.get("completed_tasks", [])
        if not completed:
            return 50.0

        recent = completed[-50:]
        retried = [t for t in recent if t.get("retries", 0) > 0]
        if not retried:
            # No retries needed either — could be good or no errors
            errors = sum(1 for t in recent if t.get("status") == "error")
            if errors == 0:
                return 85.0  # Perfect run — high score
            return 40.0  # Errors but no retries — bad

        recovered = sum(1 for t in retried if t.get("status") == "done")
        recovery_rate = recovered / max(1, len(retried))
        return recovery_rate * 100

    def _bench_memory_utilization(self, state: Dict[str, Any]) -> float:
        """How effectively is long-term memory being used?"""
        ltm = state.get("ultra_ltm")
        cog_count = state.get("cognitive_memory_count", 0)

        base = 30.0
        if cog_count > 0:
            base = min(60.0, 30 + cog_count * 0.5)

        if ltm:
            ltm_stats = ltm.get_stats() if hasattr(ltm, "get_stats") else {}
            patterns = ltm_stats.get("total_patterns", 0)
            avg_conf = ltm_stats.get("avg_confidence", 0)
            base = min(100, base + patterns * 3 + avg_conf * 20)

        return base

    def _bench_emotional_stability(self, state: Dict[str, Any]) -> float:
        """How stable is the emotional state? Lower variance = more stable."""
        inner_life = state.get("inner_life")
        if not inner_life:
            return 60.0  # Neutral

        try:
            if hasattr(inner_life, "emotion"):
                emotion = inner_life.emotion
                v = getattr(emotion, "valence", 0)
                a = getattr(emotion, "arousal", 0.5)

                # Ideal: moderate arousal, not extreme valence
                valence_penalty = abs(v) * 30  # -1 to +1 → 0-30 penalty
                arousal_penalty = abs(a - 0.4) * 40  # Ideal is ~0.4

                return max(10, 100 - valence_penalty - arousal_penalty)
        except Exception:
            pass

        return 60.0

    def _bench_decision_speed(self, state: Dict[str, Any]) -> float:
        """How fast are tasks executed after being discovered?"""
        completed = state.get("completed_tasks", [])
        if not completed:
            return 50.0

        durations = [t.get("duration_ms", 0) for t in completed[-30:] if t.get("duration_ms")]
        if not durations:
            return 50.0

        avg_ms = sum(durations) / len(durations)

        # Under 500ms → 100, 500-2000ms → 80-90, 2000-10000ms → 50-80, over 10s → low
        if avg_ms < 500:
            return 100
        elif avg_ms < 2000:
            return 90 - ((avg_ms - 500) / 1500) * 10
        elif avg_ms < 10000:
            return 80 - ((avg_ms - 2000) / 8000) * 30
        else:
            return max(20, 50 - ((avg_ms - 10000) / 50000) * 30)

    def _bench_learning_rate(self, state: Dict[str, Any]) -> float:
        """Rate of new patterns/insights discovered."""
        ltm = state.get("ultra_ltm")
        bridge = state.get("inter_agent_bridge")

        score = 30.0  # Base

        if ltm:
            ltm_stats = ltm.get_stats() if hasattr(ltm, "get_stats") else {}
            cycles = ltm_stats.get("total_cycles", 0)
            patterns = ltm_stats.get("total_patterns", 0)
            if cycles > 0:
                rate = patterns / max(1, cycles)
                score += min(40, rate * 15)

        if bridge:
            bridge_stats = bridge.get_stats() if hasattr(bridge, "get_stats") else {}
            imported = bridge_stats.get("total_imported", 0)
            applied = bridge_stats.get("applied_count", 0)
            if imported > 0:
                apply_rate = applied / max(1, imported)
                score += min(30, apply_rate * 30)

        return min(100, score)

    def _bench_inter_agent_synergy(self, state: Dict[str, Any]) -> float:
        """Effectiveness of inter-agent learning."""
        bridge = state.get("inter_agent_bridge")
        if not bridge:
            return 20.0  # No bridge = low

        stats = bridge.get_stats() if hasattr(bridge, "get_stats") else {}

        exported = stats.get("total_exported", 0)
        imported = stats.get("total_imported", 0)
        applied = stats.get("applied_count", 0)
        avg_benefit = stats.get("avg_benefit", 0)
        agents_count = len(stats.get("agents_in_vault", []))

        score = 20.0

        # Having multiple agents sharing = base bonus
        if agents_count > 1:
            score += 15

        # Export activity
        score += min(20, exported * 2)

        # Import + apply
        if imported > 0:
            apply_rate = applied / max(1, imported)
            score += apply_rate * 25

        # Benefit quality
        score += min(20, avg_benefit * 40)

        return min(100, score)

    # ── Trend Detection ──────────────────────────────────────────────────────

    def _check_regression(self, suite_id: str, current_score: float) -> bool:
        """Check if current score is a significant drop from rolling average."""
        history = self._history.get(suite_id, [])
        if len(history) < 3:
            return False

        recent = [r.score for r in history[-10:]]
        avg = sum(recent) / len(recent)

        # Regression if score drops more than 15 points below average
        return current_score < (avg - 15)

    def _compute_trend(self, suite_id: str) -> str:
        """Compute trend direction: improving | declining | stable."""
        history = self._history.get(suite_id, [])
        if len(history) < 5:
            return "stable"

        recent_5 = [r.score for r in history[-5:]]
        older_5 = [r.score for r in history[-10:-5]] if len(history) >= 10 else [r.score for r in history[:5]]

        avg_recent = sum(recent_5) / len(recent_5)
        avg_older = sum(older_5) / len(older_5)

        diff = avg_recent - avg_older
        if diff > 5:
            return "improving"
        elif diff < -5:
            return "declining"
        return "stable"

    def _overall_trend(self) -> str:
        """Overall autonomy score trend."""
        if len(self._snapshots) < 3:
            return "stable"

        recent = [s.autonomy_score for s in self._snapshots[-5:]]
        older = [s.autonomy_score for s in self._snapshots[-10:-5]] if len(self._snapshots) >= 10 else [s.autonomy_score for s in self._snapshots[:3]]

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)

        diff = avg_recent - avg_older
        if diff > 3:
            return "improving"
        elif diff < -3:
            return "declining"
        return "stable"

    def _last_known_score(self, suite_id: str) -> float:
        """Get last known score for a suite, or default 50."""
        history = self._history.get(suite_id, [])
        if history:
            return history[-1].score
        return 50.0

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "total_runs": self._total_runs,
                "last_run_tick": self._last_run_tick,
                "current_autonomy_score": self._current_autonomy_score,
                "history": {
                    k: [asdict(r) for r in v[-50:]]
                    for k, v in self._history.items()
                },
                "snapshots": [asdict(s) for s in self._snapshots[-100:]],
            }
            (self._dir / "self_benchmark_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"SelfBenchmark: Save state failed: {e}")

    def _load_state(self):
        sf = self._dir / "self_benchmark_state.json"
        if not sf.exists():
            return
        try:
            state = json.loads(sf.read_text())
            self._total_runs = state.get("total_runs", 0)
            self._last_run_tick = state.get("last_run_tick", -1)
            self._current_autonomy_score = state.get("current_autonomy_score", 0)

            for suite_id, results_data in state.get("history", {}).items():
                if suite_id in self._history:
                    for rd in results_data:
                        self._history[suite_id].append(BenchmarkResult(
                            suite=rd["suite"],
                            score=rd["score"],
                            timestamp=rd["timestamp"],
                            tick=rd.get("tick", 0),
                            details=rd.get("details", {}),
                            regression=rd.get("regression", False),
                        ))

            for sd in state.get("snapshots", []):
                self._snapshots.append(BenchmarkSnapshot(
                    snapshot_id=sd["snapshot_id"],
                    timestamp=sd["timestamp"],
                    tick=sd.get("tick", 0),
                    results=sd.get("results", {}),
                    autonomy_score=sd.get("autonomy_score", 0),
                    regressions=sd.get("regressions", []),
                ))

            logger.info(
                f"📊 SelfBenchmark: Loaded — autonomy={self._current_autonomy_score}/100, "
                f"{self._total_runs} runs"
            )
        except Exception as e:
            logger.warning(f"SelfBenchmark: Load state failed: {e}")
