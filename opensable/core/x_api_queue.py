"""
X API Queue — Intelligent, Self-Adaptive Request Queue

Every X API call goes through this single FIFO queue.
Guarantees:
  1. Only ONE request in-flight at any time
  2. Adaptive cooldown between calls (learns from success/failure)
  3. Requests never lost — they wait in line
  4. Different action types have different base cooldowns
  5. After errors (226, 429) cooldowns increase automatically
  6. After sustained success, cooldowns slowly decrease
  7. Persists learned timings to disk so restarts don't lose knowledge
"""

import asyncio
import json
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════
#  Action categories — grouped by risk level
# ═══════════════════════════════════════════════════════════════════

# Higher risk = needs more cooldown (posting is riskier than browsing)
ACTION_RISK = {
    # Passive — read-only, lowest risk
    "search_tweets":    "passive",
    "get_trends":       "passive",
    "get_user":         "passive",
    "get_user_tweets":  "passive",
    # Active — engagement, medium risk
    "like_tweet":       "active",
    "retweet":          "active",
    "follow_user":      "active",
    "bookmark_tweet":   "active",
    # Aggressive — writing content, highest risk
    "post_tweet":       "aggressive",
    "post_thread":      "aggressive",
    "reply":            "aggressive",
    "quote_tweet":      "aggressive",
    "send_dm":          "aggressive",
    "delete_tweet":     "aggressive",
}

# Base cooldowns per risk category (seconds)
DEFAULT_COOLDOWNS = {
    "passive":    2.0,   # Browsing — 2s between reads
    "active":     4.0,   # Likes/RTs — 4s gap
    "aggressive": 8.0,   # Posts/replies — 8s gap
}

# Absolute limits
MIN_COOLDOWN = 1.0      # Never go below 1s
MAX_COOLDOWN = 120.0     # Never exceed 2min between calls
PERSISTENCE_PATH = Path.home() / ".opensable" / "x_queue_timings.json"


# ═══════════════════════════════════════════════════════════════════
#  Queue Item
# ═══════════════════════════════════════════════════════════════════

@dataclass
class QueueItem:
    """A single pending X API request."""
    method_name: str
    args: tuple
    kwargs: dict
    future: asyncio.Future
    enqueued_at: float = field(default_factory=time.time)
    priority: int = 0  # 0 = normal, higher = processed first (not used yet)


# ═══════════════════════════════════════════════════════════════════
#  Adaptive Cooldown Engine
# ═══════════════════════════════════════════════════════════════════

class AdaptiveCooldown:
    """Self-adjusting cooldown timings that learn from outcomes.
    
    After each API call:
    - Success → slowly shrink cooldown (reward, -5%)
    - Error 226/429 → sharply increase cooldown (penalty, +80%)
    - Other error → moderate increase (+25%)
    - Sustained 10 successes in a row → bonus shrink (-10%)
    
    Tracks per-category stats so "search" can have a faster rhythm
    than "post_tweet" independently.
    """

    def __init__(self):
        # Current learned cooldowns per category
        self.cooldowns: Dict[str, float] = dict(DEFAULT_COOLDOWNS)
        # Success streak per category
        self._streaks: Dict[str, int] = {k: 0 for k in DEFAULT_COOLDOWNS}
        # Total stats for logging
        self._stats = {
            "total_calls": 0,
            "total_successes": 0,
            "total_errors": 0,
            "errors_226": 0,
            "errors_429": 0,
            "last_error_time": 0.0,
        }
        self._load()

    def get_cooldown(self, method_name: str) -> float:
        """Get current cooldown for a method, with human-like jitter."""
        category = ACTION_RISK.get(method_name, "active")
        base = self.cooldowns.get(category, 4.0)
        # Add ±20% random jitter — humans are never exactly on time
        jitter = base * random.uniform(-0.20, 0.20)
        return max(MIN_COOLDOWN, base + jitter)

    def report_success(self, method_name: str):
        """Call after a successful API call — slowly reduce cooldown."""
        category = ACTION_RISK.get(method_name, "active")
        self._stats["total_calls"] += 1
        self._stats["total_successes"] += 1
        self._streaks[category] = self._streaks.get(category, 0) + 1
        streak = self._streaks[category]

        # Slow reward: shrink by 5%
        old = self.cooldowns[category]
        self.cooldowns[category] = max(
            DEFAULT_COOLDOWNS[category] * 0.5,  # Never go below 50% of default
            old * 0.95
        )

        # Bonus: 10 successes in a row → extra shrink
        if streak >= 10 and streak % 10 == 0:
            bonus_old = self.cooldowns[category]
            self.cooldowns[category] = max(
                DEFAULT_COOLDOWNS[category] * 0.5,
                bonus_old * 0.90
            )
            logger.info(
                f"🧠 X Queue [{category}] {streak} successes in a row! "
                f"Cooldown: {bonus_old:.1f}s → {self.cooldowns[category]:.1f}s"
            )

        self._save()

    def report_error(self, method_name: str, error_str: str):
        """Call after a failed API call — increase cooldown based on severity."""
        category = ACTION_RISK.get(method_name, "active")
        self._stats["total_calls"] += 1
        self._stats["total_errors"] += 1
        self._stats["last_error_time"] = time.time()
        self._streaks[category] = 0  # Reset streak

        old = self.cooldowns[category]
        error_lower = error_str.lower()

        if "226" in error_lower or "automated" in error_lower or "spam" in error_lower:
            # CRITICAL — bot detection. Harsh penalty: +80% to ALL categories
            self._stats["errors_226"] += 1
            for cat in self.cooldowns:
                self.cooldowns[cat] = min(MAX_COOLDOWN, self.cooldowns[cat] * 1.80)
            logger.warning(
                f"🚨 X Queue: Error 226 detected! ALL cooldowns increased 80%. "
                f"passive={self.cooldowns['passive']:.1f}s, "
                f"active={self.cooldowns['active']:.1f}s, "
                f"aggressive={self.cooldowns['aggressive']:.1f}s"
            )
        elif "429" in error_lower or "rate" in error_lower:
            # Rate limit — increase this category +60%
            self._stats["errors_429"] += 1
            self.cooldowns[category] = min(MAX_COOLDOWN, old * 1.60)
            logger.warning(
                f"⚠️ X Queue [{category}] Rate limit! "
                f"Cooldown: {old:.1f}s → {self.cooldowns[category]:.1f}s"
            )
        else:
            # Generic error — moderate increase +25%
            self.cooldowns[category] = min(MAX_COOLDOWN, old * 1.25)
            logger.info(
                f"⚠️ X Queue [{category}] Error. "
                f"Cooldown: {old:.1f}s → {self.cooldowns[category]:.1f}s"
            )

        self._save()

    def get_stats(self) -> Dict:
        """Return current state for monitoring."""
        return {
            **self._stats,
            "cooldowns": dict(self.cooldowns),
            "streaks": dict(self._streaks),
        }

    # ── Persistence ───────────────────────────────────────────────

    def _save(self):
        """Persist learned timings to disk."""
        try:
            PERSISTENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cooldowns": self.cooldowns,
                "streaks": self._streaks,
                "stats": self._stats,
            }
            PERSISTENCE_PATH.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.debug(f"Failed to save queue timings: {e}")

    def _load(self):
        """Load previously learned timings."""
        try:
            if PERSISTENCE_PATH.exists():
                data = json.loads(PERSISTENCE_PATH.read_text())
                saved_cooldowns = data.get("cooldowns", {})
                for k in self.cooldowns:
                    if k in saved_cooldowns:
                        self.cooldowns[k] = max(
                            MIN_COOLDOWN,
                            min(MAX_COOLDOWN, float(saved_cooldowns[k]))
                        )
                saved_streaks = data.get("streaks", {})
                for k in self._streaks:
                    if k in saved_streaks:
                        self._streaks[k] = int(saved_streaks[k])
                saved_stats = data.get("stats", {})
                self._stats.update({
                    k: saved_stats[k] for k in saved_stats if k in self._stats
                })
                logger.info(
                    f"🧠 X Queue loaded learned timings: "
                    f"passive={self.cooldowns['passive']:.1f}s, "
                    f"active={self.cooldowns['active']:.1f}s, "
                    f"aggressive={self.cooldowns['aggressive']:.1f}s "
                    f"(from {self._stats['total_calls']} historical calls)"
                )
        except Exception as e:
            logger.debug(f"Failed to load queue timings (using defaults): {e}")


# ═══════════════════════════════════════════════════════════════════
#  The Queue
# ═══════════════════════════════════════════════════════════════════

class XApiQueue:
    """FIFO queue for ALL X API calls. Singleton per process.
    
    Usage:
        queue = XApiQueue.get_instance()
        result = await queue.enqueue("like_tweet", impl.like_tweet, tweet_id)
    
    The queue worker processes items one at a time, sleeping the adaptive
    cooldown between each. If 5 items pile up, they'll all run — just
    sequentially with smart gaps between them.
    """

    _instance: Optional["XApiQueue"] = None

    @classmethod
    def get_instance(cls) -> "XApiQueue":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._queue: deque[QueueItem] = deque()
        self._processing = False
        self._worker_task: Optional[asyncio.Task] = None
        self._cooldown = AdaptiveCooldown()
        self._impl = None  # Set by XSkill when it initializes
        self._last_call_time: float = 0.0
        logger.info("📋 X API Queue initialized (adaptive cooldowns)")

    def set_impl(self, impl):
        """Set the XSkillImpl that has the actual twikit methods."""
        self._impl = impl

    @property
    def cooldown_engine(self) -> AdaptiveCooldown:
        return self._cooldown

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    async def enqueue(self, method_name: str, *args, **kwargs) -> Any:
        """Add a call to the queue and wait for its result.
        
        This is what XSkill calls instead of executing directly.
        Returns the result of the API call (or raises the exception).
        """
        if self._impl is None:
            raise RuntimeError("X not initialized — queue has no impl")

        loop = asyncio.get_event_loop()
        future = loop.create_future()

        item = QueueItem(
            method_name=method_name,
            args=args,
            kwargs=kwargs,
            future=future,
        )

        self._queue.append(item)
        position = len(self._queue)

        if position > 1:
            logger.info(
                f"📋 X Queue: {method_name} queued at position #{position} "
                f"({position - 1} ahead)"
            )

        # Ensure the worker is running
        self._ensure_worker()

        # Wait for our turn — the worker will resolve the future
        return await future

    def _ensure_worker(self):
        """Start the queue worker if not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker())

    async def _worker(self):
        """Process queue items one at a time with adaptive delays."""
        while self._queue:
            item = self._queue.popleft()
            method_name = item.method_name

            # ── Adaptive cooldown before this call ──
            cooldown = self._cooldown.get_cooldown(method_name)
            now = time.time()
            elapsed = now - self._last_call_time

            if elapsed < cooldown and self._last_call_time > 0:
                wait = cooldown - elapsed
                category = ACTION_RISK.get(method_name, "active")
                logger.debug(
                    f"⏱️ X Queue [{category}]: waiting {wait:.1f}s before {method_name} "
                    f"(cooldown={cooldown:.1f}s)"
                )
                await asyncio.sleep(wait)

            # ── Execute the call ──
            queued_for = time.time() - item.enqueued_at
            remaining = len(self._queue)
            logger.info(
                f"▶️ X Queue: executing {method_name} "
                f"(waited {queued_for:.1f}s in queue, {remaining} remaining)"
            )

            try:
                method = getattr(self._impl, method_name)
                result = await method(*item.args, **item.kwargs)

                # ── Success → reward ──
                self._cooldown.report_success(method_name)
                self._last_call_time = time.time()

                if not item.future.done():
                    item.future.set_result(result)

            except Exception as e:
                # ── Error → penalty ──
                error_str = str(e)
                self._cooldown.report_error(method_name, error_str)
                self._last_call_time = time.time()

                if not item.future.done():
                    item.future.set_exception(e)

                # After a 226 error, add extra breathing room before next call
                if "226" in error_str:
                    logger.warning(
                        f"🚨 X Queue: 226 after {method_name}, "
                        f"adding 30s emergency pause before next queued item"
                    )
                    await asyncio.sleep(30)

        logger.debug("📋 X Queue: worker idle (queue empty)")

    def get_status(self) -> Dict:
        """Full status for monitoring/logging."""
        return {
            "queue_size": len(self._queue),
            "queued_methods": [item.method_name for item in self._queue],
            "worker_running": self._worker_task is not None and not self._worker_task.done(),
            "adaptive": self._cooldown.get_stats(),
        }
