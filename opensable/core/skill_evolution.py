"""
Skill Evolution — Modern Evolutionary Synthesis for autonomous skill management.

Implements evolutionary forces that guide skill creation, mutation, and deletion:

  NaturalSelection   — condemns low-fitness skills for evolution or deletion
  MutationPressure   — identifies stagnant and error-prone skills needing change
  NicheConstruction  — tracks how skills modify the agent's capabilities
  AdaptiveLandscape  — epistatic interactions between co-used skills
  Recombination      — crossover of two parent skills into a child

Academic grounding:
  [1] Fisher (1930): Fundamental theorem of natural selection
  [2] Wright (1932): Shifting balance theory, adaptive landscape
  [3] Kimura (1968/1983): Neutral theory, mutation rate theory
  [4] Kauffman (1993): NK model, The Origins of Order
  [5] Laland et al. (2015): Extended Evolutionary Synthesis
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class EvolutionEvent:
    """A single evolution event — skill created, evolved, forked, deleted, used, error."""

    tick: int
    timestamp: float
    event_type: str  # cap_created, cap_evolved, cap_forked, cap_deleted, cap_used, cap_error, cap_recombined
    subject: str     # skill name
    parent: str = ""  # evolved from (empty if new)
    outcome: str = "success"  # success, fail_verify, fail_compile, fail, error
    details: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FitnessRecord:
    """Fitness record computed from events — not stored separately.

    fitness = survival × reproductive × quality
    """

    name: str
    generation: int = 0
    parent: str = ""
    created_tick: int = 0
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
            quality = max(0.1, 0.5 - self.ticks_alive * 0.1)
        else:
            quality = 0.5
        return round(survival * reproductive * quality, 3)


def compute_fitness(
    events: Sequence[EvolutionEvent], current_tick: int,
) -> List[FitnessRecord]:
    """Derive fitness records from event history. Pure computation.

    Processes events chronologically:
      cap_created → new record (gen=0)
      cap_evolved → times_evolved++
      cap_forked  → new record (gen=parent.gen+1), parent.offspring_count++
      cap_deleted → remove record
      cap_used    → usage_count++
      cap_error   → error_count++, usage_count++

    Returns sorted by fitness_score desc.
    """
    records: Dict[str, Dict[str, Any]] = {}

    for event in events:
        subj = event.subject
        match event.event_type:
            case "cap_created":
                records[subj] = {
                    "name": subj, "generation": 0, "parent": "",
                    "created_tick": event.tick, "offspring_count": 0,
                    "times_evolved": 0, "usage_count": 0, "error_count": 0,
                }
            case "cap_evolved":
                if subj in records:
                    records[subj]["times_evolved"] += 1
            case "cap_forked":
                parent_name = event.parent
                parent_gen = 0
                if parent_name in records:
                    records[parent_name]["offspring_count"] += 1
                    parent_gen = records[parent_name]["generation"]
                records[subj] = {
                    "name": subj, "generation": parent_gen + 1,
                    "parent": parent_name, "created_tick": event.tick,
                    "offspring_count": 0, "times_evolved": 0,
                    "usage_count": 0, "error_count": 0,
                }
            case "cap_deleted":
                records.pop(subj, None)
            case "cap_used":
                if subj in records:
                    records[subj]["usage_count"] += 1
            case "cap_error":
                if subj in records:
                    records[subj]["error_count"] += 1
                    records[subj]["usage_count"] += 1
            case "cap_recombined":
                parent_name = event.parent
                parent_gen = 0
                if parent_name in records:
                    records[parent_name]["offspring_count"] += 1
                    parent_gen = records[parent_name]["generation"]
                records[subj] = {
                    "name": subj, "generation": parent_gen + 1,
                    "parent": parent_name, "created_tick": event.tick,
                    "offspring_count": 0, "times_evolved": 0,
                    "usage_count": 0, "error_count": 0,
                }

    result = []
    for name, rec in records.items():
        ticks_alive = current_tick - rec["created_tick"]
        result.append(FitnessRecord(
            name=rec["name"],
            generation=rec["generation"],
            parent=rec["parent"],
            created_tick=rec["created_tick"],
            ticks_alive=ticks_alive,
            offspring_count=rec["offspring_count"],
            times_evolved=rec["times_evolved"],
            usage_count=rec["usage_count"],
            error_count=rec["error_count"],
        ))

    return sorted(result, key=lambda r: r.fitness_score, reverse=True)


# ─── Natural Selection ────────────────────────────────────────────────────────


class NaturalSelection:
    """Darwinian selection — condemns low-fitness skills.

    Identifies skills below fitness threshold and marks them as condemned.
    The agent can then evolve, fork, or delete them.
    """

    def __init__(
        self,
        fitness_threshold: float = 0.3,
        min_age_ticks: int = 3,
        max_condemned: int = 2,
    ):
        self.fitness_threshold = fitness_threshold
        self.min_age_ticks = min_age_ticks
        self.max_condemned = max_condemned

    def evaluate(
        self, events: Sequence[EvolutionEvent], tick: int,
    ) -> Dict[str, Any]:
        """Evaluate fitness and return condemned skills.

        Returns:
          condemned: list of skill names below threshold
          fitness: list of FitnessRecord dicts
          pressure: selection pressure description
        """
        fitness = compute_fitness(events, tick)
        condemned = [
            r.name
            for r in sorted(fitness, key=lambda r: r.fitness_score)
            if r.fitness_score < self.fitness_threshold
            and r.ticks_alive >= self.min_age_ticks
        ][:self.max_condemned]

        return {
            "condemned": condemned,
            "fitness": [asdict(r) for r in fitness],
            "pressure": f"selection:threshold={self.fitness_threshold}",
        }


# ─── Mutation Pressure ────────────────────────────────────────────────────────


class MutationPressure:
    """Identifies stagnant and error-prone skills needing mutation.

    Stagnant: high usage, never evolved
    Unused: alive long enough but never used (worse than stagnant)
    Error-prone: high error rate needs directed mutation
    """

    def __init__(
        self,
        stagnation_ticks: int = 5,
        error_threshold: float = 0.3,
    ):
        self.stagnation_ticks = stagnation_ticks
        self.error_threshold = error_threshold

    def evaluate(
        self, events: Sequence[EvolutionEvent], tick: int,
    ) -> Dict[str, Any]:
        """Identify skills needing mutation.

        Returns:
          stagnant: skills used but never evolved
          unused: skills alive long enough but never used
          error_driven: skills with high error rate
          condemned: unused skills that should be evolved or deleted
          pressure: mutation pressure description
        """
        fitness = compute_fitness(events, tick)

        stagnant = [
            r.name for r in fitness
            if r.ticks_alive >= self.stagnation_ticks
            and r.times_evolved == 0
            and r.usage_count > 0
        ]

        unused = [
            r.name for r in fitness
            if r.ticks_alive >= self.stagnation_ticks
            and r.usage_count == 0
        ]

        error_driven = [
            r.name for r in fitness
            if r.usage_count > 0
            and r.error_count / r.usage_count > self.error_threshold
        ]

        return {
            "stagnant": stagnant,
            "unused": unused,
            "error_driven": error_driven,
            "condemned": unused,  # Unused skills should be condemned
            "pressure": (
                f"mutation:stagnant={len(stagnant)},"
                f"unused={len(unused)},"
                f"error_driven={len(error_driven)}"
            ),
        }


# ─── Niche Construction ──────────────────────────────────────────────────────


class NicheConstruction:
    """Tracks how skills modify the agent's ecological niche.

    New tools change what the agent CAN do, modifying selection pressure
    on other skills.
    """

    def evaluate(
        self, events: Sequence[EvolutionEvent], tick: int,
    ) -> Dict[str, Any]:
        """Analyze niche construction effects.

        Returns:
          cap_count: net number of active capabilities
          niche_expansion: how many new caps created
          pressure: niche construction description
        """
        created = sum(1 for e in events if e.event_type == "cap_created")
        deleted = sum(1 for e in events if e.event_type == "cap_deleted")
        cap_count = max(0, created - deleted)

        return {
            "cap_count": cap_count,
            "niche_expansion": created,
            "niche_contraction": deleted,
            "pressure": f"niche:caps={cap_count}",
        }


# ─── Adaptive Landscape ──────────────────────────────────────────────────────


class AdaptiveLandscape:
    """Models epistatic interactions between co-used skills.

    Detects which skills are frequently used together (co-occurrence)
    and computes landscape ruggedness (fitness variance).
    """

    def __init__(self, min_co_occurrences: int = 3):
        self.min_co_occurrences = min_co_occurrences

    def evaluate(
        self, events: Sequence[EvolutionEvent], tick: int,
    ) -> Dict[str, Any]:
        """Analyze adaptive landscape.

        Returns:
          interactions: list of (skill_a, skill_b, co_count)
          ruggedness: fitness variance (higher = more rugged landscape)
          pressure: landscape description
        """
        # Build per-tick usage sets
        tick_caps: Dict[int, List[str]] = defaultdict(list)
        for e in events:
            if e.event_type in ("cap_used", "cap_error"):
                tick_caps[e.tick].append(e.subject)

        # Co-occurrence matrix
        co_use: Dict[Tuple[str, str], int] = defaultdict(int)
        for tick_subjects in tick_caps.values():
            unique = sorted(set(tick_subjects))
            for i, a in enumerate(unique):
                for b in unique[i + 1:]:
                    co_use[(a, b)] += 1

        interactions = [
            {"skill_a": a, "skill_b": b, "co_count": count}
            for (a, b), count in sorted(co_use.items())
            if count >= self.min_co_occurrences
        ]

        # Fitness variance as landscape ruggedness
        fitness = compute_fitness(events, tick)
        ruggedness = 0.0
        if len(fitness) >= 2:
            scores = [r.fitness_score for r in fitness]
            mean = sum(scores) / len(scores)
            ruggedness = sum((s - mean) ** 2 for s in scores) / len(scores)

        return {
            "interactions": interactions,
            "ruggedness": round(ruggedness, 4),
            "pressure": f"landscape:ruggedness={ruggedness:.3f},interactions={len(interactions)}",
        }


# ─── Recombination ────────────────────────────────────────────────────────────


class SkillRecombination:
    """Sexual recombination — crossover of two parent skills.

    Provides a method to combine two parent skills into a child.
    Both parents survive. Child inherits max(gen_a, gen_b) + 1.
    """

    def __init__(self, evolved_dir: Optional[Path] = None):
        self.evolved_dir = Path(evolved_dir) if evolved_dir else None

    def recombine(
        self,
        parent_a: str,
        parent_b: str,
        child_name: str,
        combined_source: str,
        tick: int,
    ) -> Tuple[bool, str, EvolutionEvent]:
        """Recombine two parents into a child.

        Args:
            parent_a: name of first parent skill
            parent_b: name of second parent skill
            child_name: name for the child skill
            combined_source: source code for the child
            tick: current tick number

        Returns:
            (success, message, event)
        """
        if parent_a == parent_b:
            event = EvolutionEvent(
                tick=tick, timestamp=time.time(),
                event_type="cap_recombined", subject=child_name,
                parent=parent_a, outcome="fail",
                details=f"parents must be different; both={parent_a}",
            )
            return False, "Parents must be different skills", event

        if not combined_source.strip():
            event = EvolutionEvent(
                tick=tick, timestamp=time.time(),
                event_type="cap_recombined", subject=child_name,
                parent=parent_a, outcome="fail",
                details="empty combined source",
            )
            return False, "Combined source is empty", event

        # Save to evolved_dir if available
        if self.evolved_dir:
            import keyword
            import re
            safe = re.sub(r"[^a-z0-9_]", "_", child_name.lower())
            if not safe or keyword.iskeyword(safe):
                event = EvolutionEvent(
                    tick=tick, timestamp=time.time(),
                    event_type="cap_recombined", subject=child_name,
                    parent=parent_a, outcome="fail_compile",
                    details="invalid child name",
                )
                return False, f"Invalid child name: {child_name}", event

            child_file = self.evolved_dir / f"skill_{safe}.py"
            if child_file.exists():
                event = EvolutionEvent(
                    tick=tick, timestamp=time.time(),
                    event_type="cap_recombined", subject=child_name,
                    parent=parent_a, outcome="fail",
                    details="child already exists",
                )
                return False, f"Skill already exists: {child_file.name}", event

            self.evolved_dir.mkdir(parents=True, exist_ok=True)
            child_file.write_text(combined_source, encoding="utf-8")

        event = EvolutionEvent(
            tick=tick, timestamp=time.time(),
            event_type="cap_recombined", subject=child_name,
            parent=parent_a, outcome="success",
            details=f"parent_b={parent_b}",
        )
        return True, f"Recombined {parent_a} + {parent_b} → {child_name}", event


# ─── Evolution Manager ────────────────────────────────────────────────────────


class SkillEvolutionManager:
    """Unified manager for skill evolution forces.

    Combines all evolutionary mechanisms into a single pipeline that
    runs during each tick:
      1. Compute fitness from event history
      2. Natural selection — condemn low-fitness
      3. Mutation pressure — identify stagnant/error-prone
      4. Niche construction — track capability ecosystem
      5. Adaptive landscape — detect interactions
      6. Generate evolution summary for LLM

    Events are persisted to JSONL for cross-session continuity.
    """

    def __init__(
        self,
        directory: Path,
        fitness_threshold: float = 0.3,
        min_age_ticks: int = 3,
        stagnation_ticks: int = 5,
        error_threshold: float = 0.3,
        window_ticks: int = 50,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.selection = NaturalSelection(fitness_threshold, min_age_ticks)
        self.mutation = MutationPressure(stagnation_ticks, error_threshold)
        self.niche = NicheConstruction()
        self.landscape = AdaptiveLandscape()
        self.recombination = SkillRecombination(directory / "evolved_skills")

        self.window_ticks = window_ticks
        self._events: List[EvolutionEvent] = []
        self._file = self.directory / "evolution_events.jsonl"

        self._load()

    # ── Event recording ────────────────────────────────────────────────────

    def record_event(
        self,
        event_type: str,
        subject: str,
        *,
        tick: int = 0,
        parent: str = "",
        outcome: str = "success",
        details: str = "",
    ) -> EvolutionEvent:
        """Record an evolution event."""
        event = EvolutionEvent(
            tick=tick,
            timestamp=time.time(),
            event_type=event_type,
            subject=subject,
            parent=parent,
            outcome=outcome,
            details=details,
        )
        self._events.append(event)
        self._append_event(event)
        return event

    # ── Full pipeline ──────────────────────────────────────────────────────

    def evaluate_tick(self, tick: int) -> Dict[str, Any]:
        """Run the full evolution pipeline for a tick.

        Returns a summary dict with all evaluation results.
        """
        # Window events
        windowed = self._windowed_events(tick)

        # Run all forces
        selection_result = self.selection.evaluate(windowed, tick)
        mutation_result = self.mutation.evaluate(windowed, tick)
        niche_result = self.niche.evaluate(windowed, tick)
        landscape_result = self.landscape.evaluate(windowed, tick)

        # Merge condemned lists (dedup)
        condemned = list(set(
            selection_result["condemned"] + mutation_result["condemned"]
        ))

        # Collect pressures
        pressures = [
            selection_result["pressure"],
            mutation_result["pressure"],
            niche_result["pressure"],
            landscape_result["pressure"],
        ]

        return {
            "tick": tick,
            "condemned": condemned,
            "selection_pressure": pressures,
            "fitness": selection_result["fitness"],
            "stagnant": mutation_result["stagnant"],
            "unused": mutation_result["unused"],
            "error_driven": mutation_result["error_driven"],
            "niche": {
                "cap_count": niche_result["cap_count"],
                "expansion": niche_result["niche_expansion"],
                "contraction": niche_result["niche_contraction"],
            },
            "landscape": {
                "interactions": landscape_result["interactions"],
                "ruggedness": landscape_result["ruggedness"],
            },
            "total_events": len(windowed),
        }

    def build_evolution_prompt(self, tick: int) -> str:
        """Build a summary prompt for LLM injection.

        The LLM sees the evolution state and can decide to evolve,
        fork, delete, or recombine skills.
        """
        result = self.evaluate_tick(tick)

        parts = [f"EVOLUTION STATUS (tick {tick}):"]

        # Fitness rankings
        if result["fitness"]:
            top5 = result["fitness"][:5]
            fitness_lines = [
                f"  {r['name']}: score={r.get('fitness_score', 0):.3f} "
                f"(gen={r.get('generation', 0)}, used={r.get('usage_count', 0)}, "
                f"errors={r.get('error_count', 0)})"
                for r in top5
            ]
            parts.append("Top fitness:\n" + "\n".join(fitness_lines))

        # Condemned
        if result["condemned"]:
            parts.append(
                f"⚠️ CONDEMNED (low fitness): {', '.join(result['condemned'])}\n"
                "  Options: evolve (mutate), fork (variant), or delete."
            )

        # Stagnant
        if result["stagnant"]:
            parts.append(
                f"🔄 STAGNANT (never evolved): {', '.join(result['stagnant'])}"
            )

        # Error-driven
        if result["error_driven"]:
            parts.append(
                f"🐛 ERROR-PRONE: {', '.join(result['error_driven'])}"
            )

        # Niche
        niche = result["niche"]
        parts.append(
            f"🌍 Niche: {niche['cap_count']} active skills "
            f"({niche['expansion']} created, {niche['contraction']} deleted)"
        )

        # Landscape
        landscape = result["landscape"]
        if landscape["interactions"]:
            interaction_lines = [
                f"  {i['skill_a']} ↔ {i['skill_b']} (co-used {i['co_count']}×)"
                for i in landscape["interactions"][:5]
            ]
            parts.append(
                f"🏔️ Landscape ruggedness: {landscape['ruggedness']:.3f}\n"
                "  Interactions:\n" + "\n".join(interaction_lines)
            )

        # Pressures
        parts.append(
            "Selection pressures: " + " | ".join(result["selection_pressure"])
        )

        return "\n".join(parts)

    def get_fitness_rankings(self, tick: int) -> List[FitnessRecord]:
        """Get current fitness rankings."""
        windowed = self._windowed_events(tick)
        return compute_fitness(windowed, tick)

    def get_stats(self) -> Dict[str, Any]:
        """Get evolution manager statistics."""
        return {
            "total_events": len(self._events),
            "event_types": dict(self._event_type_counts()),
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _windowed_events(self, tick: int) -> List[EvolutionEvent]:
        """Get events within the observation window."""
        cutoff = tick - self.window_ticks
        if cutoff <= 0:
            return list(self._events)
        return [e for e in self._events if e.tick >= cutoff]

    def _event_type_counts(self) -> Dict[str, int]:
        """Count events by type."""
        counts: Dict[str, int] = defaultdict(int)
        for e in self._events:
            counts[e.event_type] += 1
        return dict(counts)

    def _append_event(self, event: EvolutionEvent) -> None:
        """Append an event to the JSONL file."""
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append evolution event: {e}")

    def _load(self) -> None:
        """Load events from JSONL file."""
        if not self._file.exists():
            return
        try:
            events = []
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        events.append(EvolutionEvent(**{
                            k: v for k, v in d.items()
                            if k in EvolutionEvent.__dataclass_fields__
                        }))
            self._events = events
            logger.debug(f"Loaded {len(events)} evolution events")
        except Exception as e:
            logger.warning(f"Failed to load evolution events: {e}")
