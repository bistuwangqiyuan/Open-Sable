"""
Durable Execution / Checkpointing,  persist agent state so runs survive crashes.

Saves a JSON checkpoint after every meaningful step (plan created, tool executed,
synthesis complete) so the agent can resume from the exact same point.

Usage:
    from opensable.core.checkpointing import Checkpoint, CheckpointStore

    store = CheckpointStore("/tmp/sable_checkpoints")
    cp = store.load("run-abc") or Checkpoint(run_id="run-abc")
    cp.save_step("plan", plan_data)
    store.save(cp)

    # After crash…
    cp = store.load("run-abc")
    remaining = cp.remaining_plan_steps()
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid as _uuid

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """A single recorded step inside a checkpoint."""
    step_id: str
    step_type: str          # "plan", "tool_call", "tool_result", "synthesis", "error"
    data: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    status: str = "completed"  # "completed", "failed", "skipped"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "step_type": self.step_type,
            "data": self.data,
            "timestamp": self.timestamp,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StepRecord":
        return cls(**d)


@dataclass
class Checkpoint:
    """
    Serializable snapshot of an agent run.

    Captures the full history of steps so the run can be resumed.
    """
    run_id: str = field(default_factory=lambda: str(_uuid.uuid4())[:12])
    user_id: str = "default"
    original_message: str = ""
    plan: List[str] = field(default_factory=list)
    current_step_index: int = 0
    steps: List[StepRecord] = field(default_factory=list)
    messages_history: List[Dict[str, str]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    status: str = "in_progress"  # "in_progress", "completed", "failed", "paused"

    # ── Step recording ───────────────────────────────────────

    def save_step(
        self,
        step_type: str,
        data: Dict[str, Any],
        *,
        status: str = "completed",
    ) -> StepRecord:
        """Record a step and bump the updated timestamp."""
        rec = StepRecord(
            step_id=f"{self.run_id}-s{len(self.steps)}",
            step_type=step_type,
            data=data,
            status=status,
        )
        self.steps.append(rec)
        self.updated_at = time.time()
        return rec

    def record_plan(self, plan_steps: List[str]) -> None:
        """Record the initial plan."""
        self.plan = list(plan_steps)
        self.save_step("plan", {"steps": plan_steps})

    def record_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> None:
        self.save_step("tool_call", {"tool": tool_name, "args": tool_args})

    def record_tool_result(self, tool_name: str, result: Any, *, success: bool = True) -> None:
        self.save_step(
            "tool_result",
            {"tool": tool_name, "result": str(result)[:4000], "success": success},
            status="completed" if success else "failed",
        )

    def record_synthesis(self, response: str) -> None:
        self.save_step("synthesis", {"response": response[:4000]})
        self.status = "completed"

    def record_error(self, error: str) -> None:
        self.save_step("error", {"error": error}, status="failed")
        self.status = "failed"

    def advance_step(self) -> None:
        """Move to the next plan step."""
        self.current_step_index += 1
        self.updated_at = time.time()

    # ── Introspection ────────────────────────────────────────

    def remaining_plan_steps(self) -> List[str]:
        return self.plan[self.current_step_index:]

    @property
    def completed_steps(self) -> List[StepRecord]:
        return [s for s in self.steps if s.status == "completed"]

    @property
    def failed_steps(self) -> List[StepRecord]:
        return [s for s in self.steps if s.status == "failed"]

    @property
    def is_complete(self) -> bool:
        return self.status in ("completed", "failed")

    @property
    def duration_seconds(self) -> float:
        return self.updated_at - self.created_at

    # ── Serialisation ────────────────────────────────────────

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "user_id": self.user_id,
            "original_message": self.original_message,
            "plan": self.plan,
            "current_step_index": self.current_step_index,
            "steps": [s.to_dict() for s in self.steps],
            "messages_history": self.messages_history,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Checkpoint":
        steps = [StepRecord.from_dict(s) for s in d.pop("steps", [])]
        cp = cls(**{k: v for k, v in d.items() if k != "steps"})
        cp.steps = steps
        return cp

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_json(cls, raw: str) -> "Checkpoint":
        return cls.from_dict(json.loads(raw))


class CheckpointStore:
    """
    Persists checkpoints to disk as JSON files.

    Each run gets its own file: ``<directory>/<run_id>.json``.
    """

    def __init__(self, directory: str | Path = "data/checkpoints"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        safe = run_id.replace("/", "_").replace("..", "_")
        return self.directory / f"{safe}.json"

    def save(self, cp: Checkpoint) -> Path:
        """Write the checkpoint to disk. Returns the file path."""
        path = self._path(cp.run_id)
        path.write_text(cp.to_json(), encoding="utf-8")
        logger.debug(f"Checkpoint saved: {path}")
        return path

    def load(self, run_id: str) -> Optional[Checkpoint]:
        """Load a checkpoint from disk, or None if it doesn't exist."""
        path = self._path(run_id)
        if not path.exists():
            return None
        try:
            return Checkpoint.from_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"Failed to load checkpoint {path}: {exc}")
            return None

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def list_runs(self, *, status: Optional[str] = None) -> List[str]:
        """List all run IDs. Optionally filter by status."""
        runs = []
        for f in sorted(self.directory.glob("*.json")):
            if status:
                try:
                    cp = Checkpoint.from_json(f.read_text(encoding="utf-8"))
                    if cp.status == status:
                        runs.append(cp.run_id)
                except Exception:
                    continue
            else:
                runs.append(f.stem)
        return runs

    def list_resumable(self) -> List[str]:
        """Return run IDs that can be resumed (in_progress or paused)."""
        return self.list_runs(status="in_progress") + self.list_runs(status="paused")

    def cleanup(self, *, max_age_hours: float = 72) -> int:
        """Delete checkpoints older than *max_age_hours*."""
        cutoff = time.time() - max_age_hours * 3600
        removed = 0
        for f in self.directory.glob("*.json"):
            try:
                cp = Checkpoint.from_json(f.read_text(encoding="utf-8"))
                if cp.updated_at < cutoff:
                    f.unlink()
                    removed += 1
            except Exception:
                continue
        if removed:
            logger.info(f"Cleaned up {removed} old checkpoint(s)")
        return removed
