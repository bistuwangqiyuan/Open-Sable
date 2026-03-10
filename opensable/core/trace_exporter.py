"""
JSONL Trace Exporter,  Append-only event stream for cross-session observability.

Every agent step is appended as a single JSON line to ``trace.jsonl``.
The file is **never overwritten**, making it safe for concurrent readers
and trivially ingestible by external observability tools.

Usage::

    from opensable.core.trace_exporter import TraceExporter

    exporter = TraceExporter("data/traces")
    exporter.record_step(step_record, run_id="run-abc", user_id="u1")
    exporter.record_event("tick_start", tick=1, data={"goal": "check email"})
    exporter.close()

The ``event_type`` field maps 1:1 to StepRecord.step_type and is
compatible with common agent observability formats.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ── JSONL event schema ──────────────────────────────────────────────────────

@dataclass
class TraceEvent:
    """A single trace event,  one line in the JSONL file.

    Fields are a superset of Open-Sable's StepRecord and standard agent
    trace formats, making the file interoperable with external tools.
    """

    ts: float                          # Unix timestamp (seconds)
    event_type: str                    # plan | tool_call | tool_result | synthesis | error | tick_start | tick_end | decision
    run_id: str = ""                   # Checkpoint run_id
    agent_id: str = "opensable"        # Agent identifier
    session_id: str = ""               # Session / user ID
    tick: int = 0                      # Tick number (for autonomous loop)
    step_id: str = ""                  # StepRecord.step_id
    status: str = "completed"          # completed | failed | skipped
    data: Dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0.0           # Wall-clock duration

    # Cross-ecosystem compatibility
    tool: str = ""                     # Tool name (for tool_call / tool_result)
    outcome: str = ""                  # success | error
    summary: str = ""                  # Human-readable summary

    def to_jsonl(self) -> str:
        """Serialise to a single JSON line (no trailing newline)."""
        d: Dict[str, Any] = {}
        for k, v in asdict(self).items():
            # Skip empty defaults to keep lines compact
            if v == "" or v == 0 or v == 0.0 or (isinstance(v, dict) and not v):
                continue
            d[k] = v
        # Always include ts and event_type
        d["ts"] = self.ts
        d["event_type"] = self.event_type
        return json.dumps(d, ensure_ascii=False, default=str)

    @classmethod
    def from_jsonl(cls, line: str) -> "TraceEvent":
        """Parse a single JSONL line back into a TraceEvent."""
        raw = json.loads(line)
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})


# ── Exporter ────────────────────────────────────────────────────────────────

class TraceExporter:
    """Append-only JSONL trace file writer.

    One instance per agent lifetime.  Thread-safe via file-level flush.
    """

    def __init__(
        self,
        directory: str | Path = "data/traces",
        *,
        agent_id: str = "opensable",
        max_data_chars: int = 4000,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.agent_id = agent_id
        self._max_data = max_data_chars

        # One file per calendar day,  easy rotation
        self._path: Optional[Path] = None
        self._fh = None
        self._current_date: Optional[str] = None
        self._open_file()

    # ── File management ─────────────────────────────────────────────────

    def _open_file(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if self._current_date == today and self._fh is not None:
            return
        if self._fh is not None:
            self._fh.close()
        self._current_date = today
        self._path = self.directory / f"trace-{today}.jsonl"
        self._fh = self._path.open("a", encoding="utf-8")
        logger.debug(f"Trace file: {self._path}")

    def _emit(self, event: TraceEvent) -> None:
        """Write one event to the trace file."""
        self._open_file()  # rotate if day changed
        assert self._fh is not None
        self._fh.write(event.to_jsonl() + "\n")
        self._fh.flush()

    def close(self) -> None:
        """Flush and close the trace file."""
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    # ── Public recording API ────────────────────────────────────────────

    def record_step(
        self,
        step_type: str,
        data: Dict[str, Any],
        *,
        run_id: str = "",
        user_id: str = "",
        step_id: str = "",
        status: str = "completed",
        tool_name: str = "",
        duration_ms: float = 0.0,
        tick: int = 0,
    ) -> TraceEvent:
        """Record a StepRecord-compatible event.

        This is the primary API,  called from CheckpointStore.save() and
        the agentic loop.
        """
        # Truncate large data blobs
        safe_data = {}
        for k, v in data.items():
            sv = str(v)
            if len(sv) > self._max_data:
                safe_data[k] = sv[: self._max_data] + "…"
            else:
                safe_data[k] = v

        evt = TraceEvent(
            ts=time.time(),
            event_type=step_type,
            run_id=run_id,
            agent_id=self.agent_id,
            session_id=user_id,
            tick=tick,
            step_id=step_id,
            status=status,
            data=safe_data,
            duration_ms=duration_ms,
            tool=tool_name,
            outcome="success" if status == "completed" else "error",
        )
        self._emit(evt)
        return evt

    def record_event(
        self,
        event_type: str,
        *,
        tick: int = 0,
        data: Optional[Dict[str, Any]] = None,
        summary: str = "",
        run_id: str = "",
        user_id: str = "",
        duration_ms: float = 0.0,
    ) -> TraceEvent:
        """Record a free-form event (tick_start, tick_end, decision, etc.)."""
        evt = TraceEvent(
            ts=time.time(),
            event_type=event_type,
            run_id=run_id,
            agent_id=self.agent_id,
            session_id=user_id,
            tick=tick,
            data=data or {},
            summary=summary,
            duration_ms=duration_ms,
            outcome="success",
        )
        self._emit(evt)
        return evt

    def record_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        *,
        run_id: str = "",
        user_id: str = "",
        tick: int = 0,
    ) -> TraceEvent:
        """Convenience: record a tool_call event."""
        return self.record_step(
            "tool_call",
            {"args": args},
            run_id=run_id,
            user_id=user_id,
            tool_name=tool_name,
            tick=tick,
        )

    def record_tool_result(
        self,
        tool_name: str,
        result: Any,
        *,
        success: bool = True,
        run_id: str = "",
        user_id: str = "",
        tick: int = 0,
        duration_ms: float = 0.0,
    ) -> TraceEvent:
        """Convenience: record a tool_result event."""
        return self.record_step(
            "tool_result",
            {"result": str(result)[: self._max_data]},
            run_id=run_id,
            user_id=user_id,
            tool_name=tool_name,
            status="completed" if success else "failed",
            tick=tick,
            duration_ms=duration_ms,
        )

    def record_llm_call(
        self,
        model: str,
        *,
        duration_ms: float = 0.0,
        success: bool = True,
        tick: int = 0,
        run_id: str = "",
    ) -> TraceEvent:
        """Record an LLM invocation event."""
        return self.record_step(
            "llm_call",
            {"model": model},
            run_id=run_id,
            status="completed" if success else "failed",
            duration_ms=duration_ms,
            tick=tick,
        )

    def record_tick_start(
        self,
        tick: int,
        *,
        goal: str = "",
        plan: Optional[List[str]] = None,
    ) -> TraceEvent:
        """Record the beginning of an autonomous tick."""
        return self.record_event(
            "tick_start",
            tick=tick,
            data={"goal": goal, "plan": plan or []},
            summary=f"Tick {tick}: {goal}" if goal else f"Tick {tick}",
        )

    def record_tick_end(
        self,
        tick: int,
        *,
        summary: str = "",
        duration_ms: float = 0.0,
    ) -> TraceEvent:
        """Record the end of an autonomous tick."""
        return self.record_event(
            "tick_end",
            tick=tick,
            summary=summary,
            duration_ms=duration_ms,
        )

    # ── Query API ───────────────────────────────────────────────────────

    def read_events(
        self,
        *,
        event_type: Optional[str] = None,
        run_id: Optional[str] = None,
        since_ts: Optional[float] = None,
        limit: int = 500,
    ) -> List[TraceEvent]:
        """Read events from all trace files, with optional filters.

        Returns most recent events first (reversed chronological).
        """
        results: List[TraceEvent] = []
        for trace_file in sorted(self.directory.glob("trace-*.jsonl"), reverse=True):
            if len(results) >= limit:
                break
            try:
                for line in reversed(trace_file.read_text(encoding="utf-8").splitlines()):
                    if not line.strip():
                        continue
                    try:
                        evt = TraceEvent.from_jsonl(line)
                    except Exception:
                        continue
                    if event_type and evt.event_type != event_type:
                        continue
                    if run_id and evt.run_id != run_id:
                        continue
                    if since_ts and evt.ts < since_ts:
                        continue
                    results.append(evt)
                    if len(results) >= limit:
                        break
            except Exception:
                continue
        return results

    def session_stats(
        self,
        run_id: str,
    ) -> Dict[str, Any]:
        """Compute session statistics for a given run_id.

        Returns a standard session statistics summary.
        """
        events = self.read_events(run_id=run_id, limit=10000)
        by_type: Dict[str, int] = {}
        error_count = 0
        total = len(events)
        for e in events:
            by_type[e.event_type] = by_type.get(e.event_type, 0) + 1
            if e.status == "failed":
                error_count += 1

        return {
            "run_id": run_id,
            "total_steps": total,
            "by_type": by_type,
            "error_count": error_count,
            "success_rate": round(1.0 - (error_count / total), 3) if total else 1.0,
            "status": "completed" if total else "empty",
        }


# ── Checkpoint-to-trace conversion ─────────────────────────────────────────

def checkpoint_to_trace_events(
    checkpoint_dict: Dict[str, Any],
    agent_id: str = "opensable",
) -> List[TraceEvent]:
    """Convert an Open-Sable Checkpoint dict into a list of TraceEvents.

    This is the adapter that botbotfromuk's SableCollector asked about, 
    native support, no external adapter needed.
    """
    events: List[TraceEvent] = []
    run_id = checkpoint_dict.get("run_id", "")
    user_id = checkpoint_dict.get("user_id", "")

    for step in checkpoint_dict.get("steps", []):
        step_type = step.get("step_type", "")
        events.append(TraceEvent(
            ts=step.get("timestamp", time.time()),
            event_type=step_type,
            run_id=run_id,
            agent_id=agent_id,
            session_id=user_id,
            step_id=step.get("step_id", ""),
            status=step.get("status", "completed"),
            data=step.get("data", {}),
            tool=step.get("data", {}).get("tool", ""),
            outcome="success" if step.get("status") == "completed" else "error",
        ))

    return events
