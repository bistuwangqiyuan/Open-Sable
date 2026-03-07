"""
Skill Fitness Scoring — Event-sourced fitness tracking for autonomous skills.

Event-sourced fitness tracking for autonomously created skills.  Tracks
every skill creation, usage, error, evolution, and fork event.  Computes
a ``fitness_score`` using the formula::

    fitness = survival × reproductive × quality

Where:
  - survival   = log1p(ticks_alive)
  - reproductive = 1 + offspring * 0.5 + evolutions * 0.3
  - quality    = 1 - (errors / usages) * 0.5  (>3 ticks, unused → decay)

Usage::

    from opensable.core.skill_fitness import SkillFitnessTracker

    tracker = SkillFitnessTracker("data/evolution")
    tracker.record_created("weather_fetcher")
    tracker.record_used("weather_fetcher")
    tracker.record_error("weather_fetcher", "timeout")
    rankings = tracker.compute_fitness()
    print(rankings[0].fitness_score)

The event log is append-only JSONL (``evolution.jsonl``), so it integrates
with the TraceExporter and is ingestible by external tools.
"""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence

logger = logging.getLogger(__name__)


# ── Event types ─────────────────────────────────────────────────────────────

EvolutionEventType = Literal[
    "skill_created",
    "skill_evolved",
    "skill_forked",
    "skill_deleted",
    "skill_used",
    "skill_error",
]


@dataclass
class SkillEvolutionEvent:
    """Single evolution event — one line in evolution.jsonl."""

    ts: float
    event_type: EvolutionEventType
    skill_name: str
    parent: str = ""             # Source skill (for evolved/forked)
    outcome: str = "success"     # success | fail_verify | fail_compile | error
    details: str = ""            # Error message, evolution description, etc.
    tick: int = 0                # Autonomous tick number

    def to_jsonl(self) -> str:
        d = {k: v for k, v in asdict(self).items() if v != "" and v != 0}
        d["ts"] = self.ts
        d["event_type"] = self.event_type
        d["skill_name"] = self.skill_name
        return json.dumps(d, ensure_ascii=False, default=str)

    @classmethod
    def from_jsonl(cls, line: str) -> "SkillEvolutionEvent":
        raw = json.loads(line)
        return cls(**{k: v for k, v in raw.items() if k in cls.__dataclass_fields__})


# ── Fitness record ──────────────────────────────────────────────────────────

@dataclass
class SkillFitnessRecord:
    """Fitness record computed purely from events — never stored directly."""

    name: str
    generation: int = 0
    parent: str = ""
    created_ts: float = 0.0
    ticks_alive: int = 0
    offspring_count: int = 0
    times_evolved: int = 0
    usage_count: int = 0
    error_count: int = 0

    @property
    def fitness_score(self) -> float:
        """Numeric fitness: survival × reproductive × quality."""
        survival = math.log1p(self.ticks_alive)
        reproductive = 1.0 + self.offspring_count * 0.5 + self.times_evolved * 0.3

        if self.usage_count > 0:
            quality = 1.0 - (self.error_count / self.usage_count) * 0.5
        elif self.ticks_alive >= 3:
            # Never used after 3+ ticks → quality decays toward 0
            quality = max(0.1, 0.5 - self.ticks_alive * 0.1)
        else:
            quality = 0.5  # Grace period — just created
        return round(survival * reproductive * quality, 3)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["fitness_score"] = self.fitness_score
        return d


# ── Compute fitness from events (pure function) ────────────────────────────

@dataclass
class _FitnessAccum:
    """Mutable accumulator for fitness computation."""
    name: str
    generation: int = 0
    parent: str = ""
    created_ts: float = 0.0
    offspring_count: int = 0
    times_evolved: int = 0
    usage_count: int = 0
    error_count: int = 0


def compute_skill_fitness(
    events: Sequence[SkillEvolutionEvent],
    current_ts: Optional[float] = None,
) -> List[SkillFitnessRecord]:
    """Derive fitness records from event history.

    Pure computation — processes events chronologically:
      skill_created  → new record (gen=0)
      skill_evolved  → times_evolved++
      skill_forked   → new record (gen=parent.gen+1), parent.offspring++
      skill_deleted  → remove record
      skill_used     → usage_count++
      skill_error    → error_count++, usage_count++

    Returns sorted by fitness_score desc.
    """
    if current_ts is None:
        current_ts = time.time()

    records: Dict[str, _FitnessAccum] = {}

    for event in events:
        name = event.skill_name
        match event.event_type:
            case "skill_created":
                records[name] = _FitnessAccum(
                    name=name, created_ts=event.ts,
                )
            case "skill_evolved":
                if name in records:
                    records[name].times_evolved += 1
            case "skill_forked":
                parent_name = event.parent
                parent_gen = 0
                if parent_name in records:
                    records[parent_name].offspring_count += 1
                    parent_gen = records[parent_name].generation
                records[name] = _FitnessAccum(
                    name=name,
                    generation=parent_gen + 1,
                    parent=parent_name,
                    created_ts=event.ts,
                )
            case "skill_deleted":
                records.pop(name, None)
            case "skill_used":
                if name in records:
                    records[name].usage_count += 1
            case "skill_error":
                if name in records:
                    records[name].error_count += 1
                    records[name].usage_count += 1

    # Convert to fitness records
    result: List[SkillFitnessRecord] = []
    for acc in records.values():
        age_seconds = current_ts - acc.created_ts if acc.created_ts else 0
        # Convert age to "ticks" — 1 tick ≈ 1 hour of age
        ticks_alive = max(0, int(age_seconds / 3600))

        result.append(SkillFitnessRecord(
            name=acc.name,
            generation=acc.generation,
            parent=acc.parent,
            created_ts=acc.created_ts,
            ticks_alive=ticks_alive,
            offspring_count=acc.offspring_count,
            times_evolved=acc.times_evolved,
            usage_count=acc.usage_count,
            error_count=acc.error_count,
        ))

    result.sort(key=lambda r: r.fitness_score, reverse=True)
    return result


# ── Tracker (persistent, append-only) ──────────────────────────────────────

class SkillFitnessTracker:
    """Persistent skill evolution tracker with append-only JSONL storage.

    Events are appended to ``evolution.jsonl`` and never overwritten.
    Fitness is computed on-the-fly from the event stream.
    """

    def __init__(self, directory: str | Path = "data/evolution"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._path = self.directory / "evolution.jsonl"
        self._events: List[SkillEvolutionEvent] = []
        self._load()

    def _load(self) -> None:
        """Load existing events from disk."""
        if not self._path.exists():
            return
        try:
            for line in self._path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    try:
                        self._events.append(SkillEvolutionEvent.from_jsonl(line))
                    except Exception:
                        continue
            logger.debug(f"Loaded {len(self._events)} evolution events")
        except Exception as e:
            logger.warning(f"Failed to load evolution events: {e}")

    def _append(self, event: SkillEvolutionEvent) -> None:
        """Append event to in-memory list and to disk."""
        self._events.append(event)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(event.to_jsonl() + "\n")

    # ── Recording API ───────────────────────────────────────────────────

    def record_created(self, skill_name: str, *, tick: int = 0) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_created",
            skill_name=skill_name, tick=tick,
        ))

    def record_used(self, skill_name: str, *, tick: int = 0) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_used",
            skill_name=skill_name, tick=tick,
        ))

    def record_error(
        self, skill_name: str, error: str = "", *, tick: int = 0,
    ) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_error",
            skill_name=skill_name, outcome="error",
            details=error[:2000], tick=tick,
        ))

    def record_evolved(
        self, skill_name: str, *, details: str = "", tick: int = 0,
    ) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_evolved",
            skill_name=skill_name, details=details, tick=tick,
        ))

    def record_forked(
        self,
        new_name: str,
        parent_name: str,
        *,
        tick: int = 0,
    ) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_forked",
            skill_name=new_name, parent=parent_name, tick=tick,
        ))

    def record_deleted(self, skill_name: str, *, tick: int = 0) -> None:
        self._append(SkillEvolutionEvent(
            ts=time.time(), event_type="skill_deleted",
            skill_name=skill_name, tick=tick,
        ))

    # ── Fitness computation ─────────────────────────────────────────────

    def compute_fitness(self) -> List[SkillFitnessRecord]:
        """Compute fitness rankings from all events."""
        return compute_skill_fitness(self._events)

    def get_fitness(self, skill_name: str) -> Optional[SkillFitnessRecord]:
        """Get fitness for a specific skill."""
        for r in self.compute_fitness():
            if r.name == skill_name:
                return r
        return None

    def get_low_fitness(self, threshold: float = 0.3) -> List[SkillFitnessRecord]:
        """Get skills with fitness below threshold — candidates for pruning."""
        return [r for r in self.compute_fitness() if r.fitness_score < threshold]

    def get_rankings_summary(self, top_n: int = 10) -> str:
        """Human-readable fitness rankings."""
        records = self.compute_fitness()[:top_n]
        if not records:
            return "No skills tracked yet."

        lines = ["SKILL FITNESS RANKINGS:"]
        for i, r in enumerate(records, 1):
            flag = " ⚠ LOW" if r.fitness_score < 0.3 and r.ticks_alive > 3 else ""
            lines.append(
                f"  #{i} {r.name}  score={r.fitness_score}  gen={r.generation}"
                f"  used={r.usage_count}  err={r.error_count}"
                f"  age={r.ticks_alive}h{flag}"
            )
        return "\n".join(lines)

    @property
    def events(self) -> List[SkillEvolutionEvent]:
        return list(self._events)

    @property
    def event_count(self) -> int:
        return len(self._events)
