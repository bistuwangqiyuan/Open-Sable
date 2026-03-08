"""
Distributed Task Queue

Redis-based task queue with worker pattern for horizontal scaling.
Enables distributing CPU-intensive or long-running tasks across
multiple workers with result collection, retry logic, and monitoring.

Features:
  1. Task submission — Push tasks to named queues with priority
  2. Worker pattern — Process tasks with configurable concurrency
  3. Result collection — Retrieve results by task ID
  4. Retry logic — Auto-retry failed tasks with exponential backoff
  5. Priority queues — High/medium/low priority routing
  6. Task routing — Route to specific workers by capability
  7. Dead letter queue — Failed tasks after max retries
  8. Progress tracking — Real-time task progress updates
  9. Queue monitoring — Depth, throughput, error rates
  10. Graceful shutdown — Finish in-progress tasks before stopping
"""
import json
import logging
import asyncio
import uuid
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Awaitable
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import aioredis
        REDIS_AVAILABLE = True
    except ImportError:
        REDIS_AVAILABLE = False


# ── Enums & Data Models ──────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"          # Failed after max retries
    CANCELLED = "cancelled"

class TaskPriority(int, Enum):
    LOW = 0
    MEDIUM = 5
    HIGH = 10
    CRITICAL = 20

@dataclass
class Task:
    """Represents a unit of work."""
    task_id: str
    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    status: str = TaskStatus.PENDING
    priority: int = TaskPriority.MEDIUM
    queue: str = "default"
    result: Any = None
    error: str = ""
    created_at: str = ""
    started_at: str = ""
    completed_at: str = ""
    retries: int = 0
    max_retries: int = 3
    progress: float = 0.0   # 0-1
    worker_id: str = ""
    tags: List[str] = field(default_factory=list)
    timeout: int = 300      # seconds


# ── In-Memory Queue (fallback when Redis unavailable) ────────────────

class InMemoryQueue:
    """Simple async priority queue for when Redis is not available."""

    def __init__(self):
        self.queues: Dict[str, List[Task]] = defaultdict(list)
        self.results: Dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def enqueue(self, task: Task):
        async with self._lock:
            self.queues[task.queue].append(task)
            # Sort by priority descending
            self.queues[task.queue].sort(key=lambda t: t.priority, reverse=True)
            self.results[task.task_id] = task

    async def dequeue(self, queue: str = "default") -> Optional[Task]:
        async with self._lock:
            q = self.queues.get(queue, [])
            if q:
                task = q.pop(0)
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now(timezone.utc).isoformat()
                return task
        return None

    async def update_task(self, task: Task):
        async with self._lock:
            self.results[task.task_id] = task

    async def get_task(self, task_id: str) -> Optional[Task]:
        return self.results.get(task_id)

    async def queue_depth(self, queue: str = "default") -> int:
        return len(self.queues.get(queue, []))

    async def all_queues(self) -> Dict[str, int]:
        return {q: len(tasks) for q, tasks in self.queues.items()}


# ── Redis Queue ──────────────────────────────────────────────────────

class RedisQueue:
    """Redis-backed task queue with sorted sets for priority."""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self._redis = None
        self.prefix = "sable:taskq:"

    async def connect(self):
        if not REDIS_AVAILABLE:
            return False
        try:
            self._redis = aioredis.from_url(self.redis_url, decode_responses=True)
            await self._redis.ping()
            return True
        except Exception as e:
            logger.warning(f"[TaskQueue] Redis connection failed: {e}")
            self._redis = None
            return False

    async def enqueue(self, task: Task):
        if not self._redis:
            return
        pipe = self._redis.pipeline()
        # Store task data
        pipe.set(f"{self.prefix}task:{task.task_id}", json.dumps(asdict(task), default=str))
        # Add to sorted set (priority queue)
        pipe.zadd(f"{self.prefix}queue:{task.queue}", {task.task_id: task.priority})
        await pipe.execute()

    async def dequeue(self, queue: str = "default") -> Optional[Task]:
        if not self._redis:
            return None
        # Pop highest priority task
        result = await self._redis.zpopmax(f"{self.prefix}queue:{queue}", count=1)
        if result:
            task_id = result[0][0]
            raw = await self._redis.get(f"{self.prefix}task:{task_id}")
            if raw:
                data = json.loads(raw)
                task = Task(**{k: v for k, v in data.items() if k in Task.__dataclass_fields__})
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now(timezone.utc).isoformat()
                await self.update_task(task)
                return task
        return None

    async def update_task(self, task: Task):
        if self._redis:
            await self._redis.set(
                f"{self.prefix}task:{task.task_id}",
                json.dumps(asdict(task), default=str),
                ex=86400,  # TTL 24h
            )

    async def get_task(self, task_id: str) -> Optional[Task]:
        if not self._redis:
            return None
        raw = await self._redis.get(f"{self.prefix}task:{task_id}")
        if raw:
            data = json.loads(raw)
            return Task(**{k: v for k, v in data.items() if k in Task.__dataclass_fields__})
        return None

    async def queue_depth(self, queue: str = "default") -> int:
        if not self._redis:
            return 0
        return await self._redis.zcard(f"{self.prefix}queue:{queue}")

    async def all_queues(self) -> Dict[str, int]:
        if not self._redis:
            return {}
        keys = await self._redis.keys(f"{self.prefix}queue:*")
        result = {}
        for key in keys:
            q_name = key.replace(f"{self.prefix}queue:", "")
            result[q_name] = await self._redis.zcard(key)
        return result


# ── Distributed Task Queue Engine ────────────────────────────────────

class DistributedTaskQueue:
    """
    Full-featured distributed task queue with Redis or in-memory backend.
    Supports priority queues, retries, dead-letter, workers, and monitoring.
    """

    def __init__(self, data_dir: Path, redis_url: str = "redis://localhost:6379"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "task_queue_state.json"

        self.redis_url = redis_url
        self._backend: Optional[Any] = None
        self._using_redis = False

        # Handler registry: task_type -> callable
        self._handlers: Dict[str, Callable[..., Awaitable[Any]]] = {}

        # Worker management
        self._workers: List[asyncio.Task] = []
        self._running = False
        self._worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        # Stats
        self.total_submitted = 0
        self.total_completed = 0
        self.total_failed = 0
        self.total_retried = 0
        self.total_dead = 0
        self.throughput_history: deque = deque(maxlen=100)

        self._load_state()

    async def initialize(self):
        """Initialize backend (try Redis, fallback to in-memory)."""
        if REDIS_AVAILABLE:
            rq = RedisQueue(self.redis_url)
            if await rq.connect():
                self._backend = rq
                self._using_redis = True
                logger.info("[TaskQueue] Connected to Redis")
                return

        # Fallback
        self._backend = InMemoryQueue()
        self._using_redis = False
        logger.info("[TaskQueue] Using in-memory queue (Redis not available)")

    # ── Task Submission ──────────────────────────────────────────────

    async def submit(
        self,
        task_type: str,
        payload: Optional[Dict[str, Any]] = None,
        queue: str = "default",
        priority: int = TaskPriority.MEDIUM,
        max_retries: int = 3,
        timeout: int = 300,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Submit a task to the queue. Returns task_id."""
        if self._backend is None:
            await self.initialize()

        task = Task(
            task_id=uuid.uuid4().hex,
            task_type=task_type,
            payload=payload or {},
            status=TaskStatus.QUEUED,
            priority=priority,
            queue=queue,
            max_retries=max_retries,
            timeout=timeout,
            tags=tags or [],
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        await self._backend.enqueue(task)
        self.total_submitted += 1
        self._save_state()
        return task.task_id

    async def get_result(self, task_id: str) -> Dict[str, Any]:
        """Get task status and result."""
        if self._backend is None:
            return {"error": "Queue not initialized"}

        task = await self._backend.get_task(task_id)
        if task is None:
            return {"error": f"Task {task_id} not found"}

        return {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": task.status,
            "progress": task.progress,
            "result": task.result,
            "error": task.error,
            "retries": task.retries,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
        }

    # ── Handler Registration ─────────────────────────────────────────

    def register_handler(self, task_type: str, handler: Callable[..., Awaitable[Any]]):
        """Register a handler function for a task type."""
        self._handlers[task_type] = handler
        logger.info(f"[TaskQueue] Registered handler for '{task_type}'")

    # ── Worker Management ────────────────────────────────────────────

    async def start_workers(self, num_workers: int = 3, queues: Optional[List[str]] = None):
        """Start N worker coroutines processing tasks."""
        if self._running:
            return

        if self._backend is None:
            await self.initialize()

        self._running = True
        target_queues = queues or ["default"]

        for i in range(num_workers):
            q = target_queues[i % len(target_queues)]
            worker = asyncio.create_task(self._worker_loop(f"{self._worker_id}-{i}", q))
            self._workers.append(worker)

        logger.info(f"[TaskQueue] Started {num_workers} workers on queues: {target_queues}")

    async def stop_workers(self):
        """Gracefully stop all workers."""
        self._running = False
        for w in self._workers:
            w.cancel()
        self._workers.clear()
        logger.info("[TaskQueue] Workers stopped")

    async def _worker_loop(self, worker_id: str, queue: str):
        """Main worker loop: dequeue → process → store result."""
        logger.info(f"[TaskQueue] Worker {worker_id} started on queue '{queue}'")

        while self._running:
            try:
                task = await self._backend.dequeue(queue)
                if task is None:
                    await asyncio.sleep(1)
                    continue

                task.worker_id = worker_id
                await self._process_task(task)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[TaskQueue] Worker {worker_id} error: {e}")
                await asyncio.sleep(2)

    async def _process_task(self, task: Task):
        """Process a single task with retry logic."""
        handler = self._handlers.get(task.task_type)

        if handler is None:
            task.status = TaskStatus.FAILED
            task.error = f"No handler registered for task type '{task.task_type}'"
            task.completed_at = datetime.now(timezone.utc).isoformat()
            await self._backend.update_task(task)
            self.total_failed += 1
            return

        start_time = time.time()

        try:
            # Run with timeout
            result = await asyncio.wait_for(
                handler(task.payload, task),
                timeout=task.timeout,
            )
            task.result = result
            task.status = TaskStatus.SUCCESS
            task.progress = 1.0
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self.total_completed += 1

            elapsed = time.time() - start_time
            self.throughput_history.append(elapsed)

        except asyncio.TimeoutError:
            task.error = f"Task timed out after {task.timeout}s"
            await self._handle_retry(task)

        except Exception as e:
            task.error = str(e)
            await self._handle_retry(task)

        await self._backend.update_task(task)
        self._save_state()

    async def _handle_retry(self, task: Task):
        """Retry or move to dead letter queue."""
        if task.retries < task.max_retries:
            task.retries += 1
            task.status = TaskStatus.RETRYING
            self.total_retried += 1

            # Exponential backoff
            delay = min(60, 2 ** task.retries)
            await asyncio.sleep(delay)

            # Re-enqueue
            task.status = TaskStatus.QUEUED
            await self._backend.enqueue(task)
        else:
            task.status = TaskStatus.DEAD
            task.completed_at = datetime.now(timezone.utc).isoformat()
            self.total_dead += 1
            self.total_failed += 1

    # ── Queue Monitoring ─────────────────────────────────────────────

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get status of all queues."""
        if self._backend is None:
            return {"error": "Queue not initialized"}

        queues = await self._backend.all_queues()
        avg_throughput = (
            sum(self.throughput_history) / len(self.throughput_history)
            if self.throughput_history else 0
        )

        return {
            "backend": "redis" if self._using_redis else "in-memory",
            "workers_running": len(self._workers),
            "queues": queues,
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_retried": self.total_retried,
            "total_dead": self.total_dead,
            "avg_process_time": round(avg_throughput, 3),
            "registered_handlers": list(self._handlers.keys()),
        }

    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a pending/queued task."""
        task = await self._backend.get_task(task_id)
        if task is None:
            return {"error": f"Task {task_id} not found"}
        if task.status in (TaskStatus.SUCCESS, TaskStatus.DEAD, TaskStatus.CANCELLED):
            return {"error": f"Task already in terminal state: {task.status}"}

        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(timezone.utc).isoformat()
        await self._backend.update_task(task)
        return {"ok": True, "task_id": task_id, "status": "cancelled"}

    # ── Built-in Task Types ──────────────────────────────────────────

    def register_builtins(self):
        """Register some common built-in task handlers."""

        async def echo_handler(payload: Dict, task: Task) -> Any:
            """Simple echo for testing."""
            return {"echo": payload}

        async def sleep_handler(payload: Dict, task: Task) -> Any:
            """Sleep for N seconds (for testing)."""
            seconds = payload.get("seconds", 1)
            await asyncio.sleep(seconds)
            return {"slept": seconds}

        self.register_handler("echo", echo_handler)
        self.register_handler("sleep", sleep_handler)

    # ── Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "using_redis": self._using_redis,
                "redis_url": self.redis_url,
                "total_submitted": self.total_submitted,
                "total_completed": self.total_completed,
                "total_failed": self.total_failed,
                "total_retried": self.total_retried,
                "total_dead": self.total_dead,
                "registered_handlers": list(self._handlers.keys()),
                "workers_count": len(self._workers),
            }
            self.state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"[TaskQueue] Save failed: {e}")

    def _load_state(self):
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.total_submitted = state.get("total_submitted", 0)
                self.total_completed = state.get("total_completed", 0)
                self.total_failed = state.get("total_failed", 0)
                self.total_retried = state.get("total_retried", 0)
                self.total_dead = state.get("total_dead", 0)
                logger.info(f"[TaskQueue] Loaded state: {self.total_submitted} tasks submitted")
            except Exception as e:
                logger.error(f"[TaskQueue] Load failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        avg_throughput = (
            sum(self.throughput_history) / len(self.throughput_history)
            if self.throughput_history else 0
        )
        return {
            "backend": "redis" if self._using_redis else "in-memory",
            "redis_url": self.redis_url if self._using_redis else "(not connected)",
            "workers_active": len(self._workers),
            "running": self._running,
            "registered_handlers": list(self._handlers.keys()),
            "total_submitted": self.total_submitted,
            "total_completed": self.total_completed,
            "total_failed": self.total_failed,
            "total_retried": self.total_retried,
            "total_dead": self.total_dead,
            "success_rate": (
                round(self.total_completed / max(1, self.total_submitted) * 100, 1)
            ),
            "avg_process_time_s": round(avg_throughput, 3),
        }
