"""
Adversarial Self-Tester — red-team the agent's own capabilities.

Generates challenging test cases to probe for weaknesses, edge cases,
and failure modes the agent hasn't encountered naturally. Results
feed back into self-improvement and causal reasoning.

Key ideas:
  - **Weakness targeting**: generates tests for weak benchmark suites
  - **LLM-generated edge cases**: creates adversarial inputs
  - **Failure cataloging**: maintains a weakness database
  - **Regression testing**: re-runs past failure cases to confirm fixes

Persistence: ``adversarial_tester_state.json`` in *data_dir*.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ADVERSARIAL_SYSTEM = """You are a red-team testing engine for an autonomous AI agent.
Your job is to find weaknesses. Given the agent's benchmark scores and
known capabilities, generate 2-4 adversarial test scenarios.

Output ONLY valid JSON — an array of objects:
[
  {
    "test_name": "short descriptive name",
    "description": "what to test (1-2 sentences)",
    "category": "reasoning|memory|planning|recovery|robustness|social",
    "difficulty": "easy|medium|hard|extreme",
    "target_weakness": "which weakness this probes",
    "expected_failure_mode": "how the agent might fail"
  }
]

Rules:
- Target the agent's weakest areas (lowest benchmark scores)
- Include both known failure patterns and novel edge cases
- Be specific — vague tests are useless
- Vary difficulty: 1 easy, 1-2 medium, 1 hard
- Focus on things the agent can actually self-test"""


@dataclass
class AdversarialTest:
    """An adversarial test case."""

    test_id: str
    test_name: str
    description: str
    category: str
    difficulty: str
    target_weakness: str
    expected_failure_mode: str
    status: str = "pending"  # pending, passed, failed, error
    result: str = ""
    tick_created: int = 0
    tick_executed: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class Weakness:
    """A cataloged weakness discovered through testing."""

    weakness_id: str
    description: str
    category: str
    severity: float  # 0-1
    confirmed_count: int = 1
    fixed: bool = False
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now


class AdversarialTester:
    """Red-team testing engine for the agent."""

    def __init__(
        self,
        data_dir: Path,
        generate_interval: int = 40,
        max_tests: int = 200,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "adversarial_tester_state.json"

        self._generate_interval = generate_interval
        self._max_tests = max_tests

        self._tests: Dict[str, AdversarialTest] = {}
        self._weaknesses: Dict[str, Weakness] = {}
        self._last_generate_tick: int = 0
        self._total_generated: int = 0
        self._total_passed: int = 0
        self._total_failed: int = 0

        self._load_state()

    async def generate_tests(
        self,
        llm: Any,
        tick: int,
        benchmark_scores: Optional[Dict[str, float]] = None,
        known_weaknesses: Optional[List[str]] = None,
    ) -> List[AdversarialTest]:
        """Generate adversarial test cases targeting weak areas."""
        if tick - self._last_generate_tick < self._generate_interval:
            return []

        self._last_generate_tick = tick

        try:
            context_parts = []

            if benchmark_scores:
                # Sort by score (weakest first)
                sorted_scores = sorted(benchmark_scores.items(), key=lambda x: x[1])
                context_parts.append("Benchmark scores (weakest first):")
                for name, score in sorted_scores:
                    context_parts.append(f"  - {name}: {score}/100")

            if known_weaknesses:
                context_parts.append("Known weaknesses:")
                for w in known_weaknesses[:10]:
                    context_parts.append(f"  - {w}")

            # Include past failure patterns
            failed = [t for t in self._tests.values() if t.status == "failed"]
            if failed:
                context_parts.append("Past failures:")
                for t in failed[-5:]:
                    context_parts.append(f"  - {t.test_name}: {t.result[:100]}")

            context = "\n".join(context_parts) if context_parts else "No benchmark data available."

            messages = [
                {"role": "system", "content": _ADVERSARIAL_SYSTEM},
                {"role": "user", "content": f"Agent analysis:\n{context}"},
            ]

            result = await llm.invoke_with_tools(messages, [])
            text = result.get("text", "") if isinstance(result, dict) else str(result)

            import re
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if m:
                    text = m.group(1).strip()

            start = text.find("[")
            end = text.rfind("]")
            if start < 0 or end < 0:
                return []

            items = json.loads(text[start:end + 1])
            new_tests = []

            for item in items:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("test_name", "")).strip()
                if not name:
                    continue

                test_id = f"adv_{hashlib.md5(f'{name}_{tick}'.encode()).hexdigest()[:8]}"

                test = AdversarialTest(
                    test_id=test_id,
                    test_name=name,
                    description=str(item.get("description", "")),
                    category=str(item.get("category", "robustness")),
                    difficulty=str(item.get("difficulty", "medium")),
                    target_weakness=str(item.get("target_weakness", "")),
                    expected_failure_mode=str(item.get("expected_failure_mode", "")),
                    tick_created=tick,
                )

                self._tests[test_id] = test
                new_tests.append(test)
                self._total_generated += 1

            # Prune old tests
            if len(self._tests) > self._max_tests:
                sorted_tests = sorted(
                    self._tests.items(),
                    key=lambda x: x[1].tick_created,
                )
                for old_key, _ in sorted_tests[:len(sorted_tests) - self._max_tests]:
                    del self._tests[old_key]

            self._save_state()
            return new_tests

        except Exception as e:
            logger.debug(f"Adversarial test generation failed: {e}")
            return []

    def record_result(self, test_id: str, passed: bool, result: str = "", tick: int = 0):
        """Record the result of an adversarial test."""
        if test_id not in self._tests:
            return

        test = self._tests[test_id]
        test.status = "passed" if passed else "failed"
        test.result = result[:500]
        test.tick_executed = tick

        if passed:
            self._total_passed += 1
        else:
            self._total_failed += 1
            # Catalog the weakness
            weakness_id = f"weak_{hashlib.md5(test.target_weakness.encode()).hexdigest()[:8]}"
            if weakness_id in self._weaknesses:
                self._weaknesses[weakness_id].confirmed_count += 1
                self._weaknesses[weakness_id].last_seen = datetime.now().isoformat()
            else:
                self._weaknesses[weakness_id] = Weakness(
                    weakness_id=weakness_id,
                    description=test.target_weakness,
                    category=test.category,
                    severity={"easy": 0.3, "medium": 0.5, "hard": 0.7, "extreme": 0.9}.get(
                        test.difficulty, 0.5
                    ),
                )

        self._save_state()

    def get_pending_tests(self, limit: int = 5) -> List[Dict]:
        """Return pending tests to execute."""
        pending = [t for t in self._tests.values() if t.status == "pending"]
        pending.sort(key=lambda t: t.tick_created)
        return [
            {
                "test_id": t.test_id,
                "name": t.test_name,
                "description": t.description,
                "difficulty": t.difficulty,
            }
            for t in pending[:limit]
        ]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        active_weaknesses = [w for w in self._weaknesses.values() if not w.fixed]
        active_weaknesses.sort(key=lambda w: -w.severity * w.confirmed_count)

        by_category = {}
        for t in self._tests.values():
            if t.status == "failed":
                by_category[t.category] = by_category.get(t.category, 0) + 1

        return {
            "total_generated": self._total_generated,
            "total_passed": self._total_passed,
            "total_failed": self._total_failed,
            "pass_rate": round(
                self._total_passed / max(self._total_passed + self._total_failed, 1), 3
            ),
            "pending_tests": len([t for t in self._tests.values() if t.status == "pending"]),
            "active_weaknesses": len(active_weaknesses),
            "failure_categories": by_category,
            "top_weaknesses": [
                {
                    "description": w.description[:100],
                    "category": w.category,
                    "severity": round(w.severity, 2),
                    "confirmed": w.confirmed_count,
                }
                for w in active_weaknesses[:8]
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "tests": {k: asdict(v) for k, v in self._tests.items()},
                "weaknesses": {k: asdict(v) for k, v in self._weaknesses.items()},
                "last_generate_tick": self._last_generate_tick,
                "total_generated": self._total_generated,
                "total_passed": self._total_passed,
                "total_failed": self._total_failed,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Adversarial tester save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._last_generate_tick = data.get("last_generate_tick", 0)
                self._total_generated = data.get("total_generated", 0)
                self._total_passed = data.get("total_passed", 0)
                self._total_failed = data.get("total_failed", 0)

                for tid, tdata in data.get("tests", {}).items():
                    self._tests[tid] = AdversarialTest(**tdata)

                for wid, wdata in data.get("weaknesses", {}).items():
                    self._weaknesses[wid] = Weakness(**wdata)
        except Exception as e:
            logger.debug(f"Adversarial tester load failed: {e}")
