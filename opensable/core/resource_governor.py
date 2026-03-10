"""
Resource Governor,  autonomous token, memory and compute management.

Tracks LLM token consumption, memory pressure, and compute time,
then enforces budgets and triggers efficiency optimizations when
resources are constrained.

Key ideas:
  - **Token budget**: tracks tokens per tick and total lifetime usage
  - **Memory pressure**: monitors cognitive memory sizes and triggers cleanup
  - **Compute budget**: tracks CPU time per tick and throttles if over budget
  - **Adaptive throttling**: reduces LLM call frequency under pressure
  - **Cost estimation**: estimates API cost based on token usage

Persistence: ``resource_governor_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Token consumption tracking for a single tick."""

    tick: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class ResourceSnapshot:
    """Snapshot of resource utilization."""

    tick: int
    token_usage: int
    memory_items: int
    compute_ms: float
    throttle_level: int  # 0=none, 1=light, 2=moderate, 3=heavy
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ResourceGovernor:
    """Manages and throttles agent resource consumption."""

    def __init__(
        self,
        data_dir: Path,
        token_budget_per_tick: int = 8000,
        token_budget_daily: int = 500000,
        max_llm_calls_per_tick: int = 10,
        max_compute_ms_per_tick: float = 30000.0,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "resource_governor_state.json"

        self._token_budget_tick = token_budget_per_tick
        self._token_budget_daily = token_budget_daily
        self._max_llm_calls = max_llm_calls_per_tick
        self._max_compute_ms = max_compute_ms_per_tick

        # Current tick tracking
        self._current_tick: int = 0
        self._tick_tokens: int = 0
        self._tick_llm_calls: int = 0
        self._tick_compute_start: float = 0.0
        self._throttle_level: int = 0  # 0-3

        # Lifetime tracking
        self._total_tokens: int = 0
        self._total_llm_calls: int = 0
        self._daily_tokens: int = 0
        self._daily_reset_date: str = ""
        self._total_ticks_governed: int = 0

        # History
        self._snapshots: List[ResourceSnapshot] = []
        self._tick_usages: List[TokenUsage] = []

        self._load_state()

    # ── Tick lifecycle ────────────────────────────────────────────────────────

    def tick_start(self, tick: int):
        """Call at the beginning of each tick."""
        self._current_tick = tick
        self._tick_tokens = 0
        self._tick_llm_calls = 0
        self._tick_compute_start = time.monotonic()

        # Reset daily counter if new day
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self._daily_reset_date:
            self._daily_tokens = 0
            self._daily_reset_date = today

    def tick_end(self, tick: int, memory_items: int = 0):
        """Call at the end of each tick. Records snapshot and adjusts throttle."""
        compute_ms = (time.monotonic() - self._tick_compute_start) * 1000

        usage = TokenUsage(
            tick=tick,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=self._tick_tokens,
            llm_calls=self._tick_llm_calls,
        )
        self._tick_usages.append(usage)
        if len(self._tick_usages) > 200:
            self._tick_usages = self._tick_usages[-200:]

        # Calculate throttle level
        self._update_throttle(compute_ms, memory_items)

        snapshot = ResourceSnapshot(
            tick=tick,
            token_usage=self._tick_tokens,
            memory_items=memory_items,
            compute_ms=round(compute_ms, 1),
            throttle_level=self._throttle_level,
        )
        self._snapshots.append(snapshot)
        if len(self._snapshots) > 200:
            self._snapshots = self._snapshots[-200:]

        self._total_ticks_governed += 1
        self._save_state()

    # ── Resource tracking ─────────────────────────────────────────────────────

    def record_tokens(self, prompt: int = 0, completion: int = 0):
        """Record token consumption for the current tick."""
        total = prompt + completion
        self._tick_tokens += total
        self._total_tokens += total
        self._daily_tokens += total
        self._tick_llm_calls += 1
        self._total_llm_calls += 1

    def can_call_llm(self) -> bool:
        """Check if the agent is allowed to make another LLM call this tick."""
        if self._throttle_level >= 3:
            return False
        if self._tick_llm_calls >= self._max_llm_calls:
            return False
        if self._tick_tokens >= self._token_budget_tick * (1.5 if self._throttle_level == 0 else 1.0):
            return False
        if self._daily_tokens >= self._token_budget_daily:
            return False
        return True

    def get_throttle_level(self) -> int:
        """Return current throttle level (0=none, 1=light, 2=moderate, 3=heavy)."""
        return self._throttle_level

    def get_remaining_budget(self) -> Dict[str, Any]:
        """Return remaining resource budgets."""
        return {
            "tick_tokens_remaining": max(0, self._token_budget_tick - self._tick_tokens),
            "daily_tokens_remaining": max(0, self._token_budget_daily - self._daily_tokens),
            "llm_calls_remaining": max(0, self._max_llm_calls - self._tick_llm_calls),
            "throttle_level": self._throttle_level,
        }

    # ── Throttle calculation ──────────────────────────────────────────────────

    def _update_throttle(self, compute_ms: float, memory_items: int):
        """Calculate throttle level based on resource usage."""
        level = 0

        # Token usage pressure
        tick_ratio = self._tick_tokens / max(self._token_budget_tick, 1)
        daily_ratio = self._daily_tokens / max(self._token_budget_daily, 1)

        if tick_ratio > 1.5 or daily_ratio > 0.9:
            level = max(level, 3)
        elif tick_ratio > 1.0 or daily_ratio > 0.7:
            level = max(level, 2)
        elif tick_ratio > 0.8 or daily_ratio > 0.5:
            level = max(level, 1)

        # Compute time pressure
        if compute_ms > self._max_compute_ms * 1.5:
            level = max(level, 3)
        elif compute_ms > self._max_compute_ms:
            level = max(level, 2)
        elif compute_ms > self._max_compute_ms * 0.8:
            level = max(level, 1)

        # Memory pressure (soft signal)
        if memory_items > 10000:
            level = max(level, 2)
        elif memory_items > 5000:
            level = max(level, 1)

        old = self._throttle_level
        self._throttle_level = level

        if level != old:
            labels = {0: "none", 1: "light", 2: "moderate", 3: "heavy"}
            logger.info(
                f"⚡ Resource governor: throttle {labels.get(old, old)} → {labels.get(level, level)}"
            )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        # Compute average tokens per tick
        if self._tick_usages:
            recent = self._tick_usages[-20:]
            avg_tokens = sum(u.total_tokens for u in recent) / len(recent)
            avg_calls = sum(u.llm_calls for u in recent) / len(recent)
        else:
            avg_tokens = 0
            avg_calls = 0

        return {
            "throttle_level": self._throttle_level,
            "throttle_label": {0: "none", 1: "light", 2: "moderate", 3: "heavy"}.get(
                self._throttle_level, "unknown"
            ),
            "total_tokens": self._total_tokens,
            "daily_tokens": self._daily_tokens,
            "daily_budget": self._token_budget_daily,
            "daily_usage_pct": round(
                self._daily_tokens / max(self._token_budget_daily, 1) * 100, 1
            ),
            "total_llm_calls": self._total_llm_calls,
            "avg_tokens_per_tick": round(avg_tokens, 0),
            "avg_llm_calls_per_tick": round(avg_calls, 1),
            "total_ticks_governed": self._total_ticks_governed,
            "tick_budget": self._token_budget_tick,
            "current_tick_tokens": self._tick_tokens,
            "current_tick_calls": self._tick_llm_calls,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "total_tokens": self._total_tokens,
                "total_llm_calls": self._total_llm_calls,
                "daily_tokens": self._daily_tokens,
                "daily_reset_date": self._daily_reset_date,
                "total_ticks_governed": self._total_ticks_governed,
                "throttle_level": self._throttle_level,
                "snapshots": [asdict(s) for s in self._snapshots[-200:]],
                "tick_usages": [asdict(u) for u in self._tick_usages[-200:]],
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Resource governor save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._total_tokens = data.get("total_tokens", 0)
                self._total_llm_calls = data.get("total_llm_calls", 0)
                self._daily_tokens = data.get("daily_tokens", 0)
                self._daily_reset_date = data.get("daily_reset_date", "")
                self._total_ticks_governed = data.get("total_ticks_governed", 0)
                self._throttle_level = data.get("throttle_level", 0)

                for sdata in data.get("snapshots", []):
                    self._snapshots.append(ResourceSnapshot(**sdata))

                for udata in data.get("tick_usages", []):
                    self._tick_usages.append(TokenUsage(**udata))
        except Exception as e:
            logger.debug(f"Resource governor load failed: {e}")
