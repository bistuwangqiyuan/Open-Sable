"""
Pattern Learner,  LLM-driven pattern detection + institutional learning.

Detects evolution patterns from event history and converts high-confidence
patterns into permanent verification rules (institutional learning).

Components:
  PatternDetector    ,  aggregates event data for LLM analysis
  InstitutionalLearner,  converts patterns → permanent verification rules
  HistoryWindow      ,  bounds event history to prevent O(n) growth
  FitnessSnapshotter ,  periodic fitness snapshots for trend analysis

All pattern DETECTION is done by the LLM.  This module only aggregates
data, provides tools/prompts, and converts results into persistent rules.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class EvolutionPattern:
    """A pattern detected by the LLM from evolution event analysis."""

    name: str
    description: str
    confidence: float = 0.5         # 0.0–1.0
    pattern_type: str = "general"   # failure_mode, synergy, generation_trend, stagnation
    source_ticks: List[int] = field(default_factory=list)
    detected_tick: int = 0
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvolutionPattern":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class VerifyRule:
    """A permanent verification rule learned from evolution patterns.

    Institutional learning: failures become permanent algebraic invariants
    that future skills must satisfy.
    """

    name: str
    condition: str                  # human-readable condition description
    severity: str = "warning"       # warning, error
    source_tick: int = 0
    source_pattern: str = ""        # pattern that spawned this rule
    created_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VerifyRule":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class FitnessSnapshot:
    """Periodic snapshot of fitness rankings for trend analysis."""

    tick: int
    timestamp: float = 0.0
    rankings: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Pattern Detector ─────────────────────────────────────────────────────────


class PatternDetector:
    """Aggregates evolution event data for LLM-driven pattern analysis.

    Builds event summaries and provides a prompt for the LLM to detect
    patterns.  User calls `report_pattern()` with LLM-detected patterns.
    """

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self._patterns: List[EvolutionPattern] = []
        self._file = self.directory / "patterns.jsonl"

        self._load()

    def report_pattern(
        self,
        name: str,
        description: str,
        *,
        confidence: float = 0.5,
        pattern_type: str = "general",
        tick: int = 0,
        source_ticks: Optional[List[int]] = None,
    ) -> EvolutionPattern:
        """Report a pattern detected by the LLM.

        Returns the created pattern, or the existing one if name exists.
        """
        # Dedup by name
        for p in self._patterns:
            if p.name == name:
                return p

        pattern = EvolutionPattern(
            name=name,
            description=description,
            confidence=max(0.0, min(1.0, confidence)),
            pattern_type=pattern_type,
            source_ticks=source_ticks or [],
            detected_tick=tick,
            timestamp=time.time(),
        )
        self._patterns.append(pattern)
        self._append(pattern)
        return pattern

    def build_event_summary(
        self,
        events: Sequence[Any],
    ) -> str:
        """Build a structured event summary for LLM analysis.

        Each event should have: tick, event_type, subject, parent, outcome, details.
        """
        if not events:
            return "No events recorded."

        parts: List[str] = []
        subject_counts: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        for e in events:
            tick = getattr(e, "tick", 0)
            event_type = getattr(e, "event_type", "unknown")
            subject = getattr(e, "subject", "unknown")
            parent = getattr(e, "parent", "")

            line = f"- tick {tick}: {event_type} \"{subject}\""
            if parent:
                line += f" (parent: {parent})"
            parts.append(line)
            subject_counts[subject][event_type] += 1

        summary = "Events:\n" + "\n".join(parts)

        # Aggregated counts
        agg_parts = []
        for subj, counts in sorted(subject_counts.items()):
            count_strs = [
                f"{count} {etype}"
                for etype, count in sorted(counts.items())
            ]
            agg_parts.append(f"- {subj}: {', '.join(count_strs)}")

        if agg_parts:
            summary += "\n\nAggregated:\n" + "\n".join(agg_parts)

        return summary

    def build_analysis_prompt(
        self,
        events: Sequence[Any],
    ) -> str:
        """Build a prompt for the LLM to detect evolution patterns.

        Returns a prompt to be injected as a system message.
        """
        summary = self.build_event_summary(events)

        # Include previously detected patterns for context
        prev_patterns = ""
        if self._patterns:
            prev_lines = [
                f"- {p.name} ({p.pattern_type}, confidence={p.confidence:.1f}): "
                f"{p.description}"
                for p in self._patterns[-5:]
            ]
            prev_patterns = (
                "\n\nPreviously detected patterns:\n"
                + "\n".join(prev_lines)
            )

        return (
            f"EVOLUTION EVENTS:\n{summary}{prev_patterns}"
            "\n\nIf you detect patterns (repeated failures, synergies "
            "between skills, generation trends, stagnation loops), "
            "use report_evolution_pattern to record them."
        )

    def get_patterns(self) -> List[EvolutionPattern]:
        """Get all detected patterns."""
        return list(self._patterns)

    def get_high_confidence_patterns(
        self, min_confidence: float = 0.5,
    ) -> List[EvolutionPattern]:
        """Get patterns above a confidence threshold."""
        return [
            p for p in self._patterns
            if p.confidence >= min_confidence
        ]

    # ── Persistence ────────────────────────────────────────────────────────

    def _append(self, pattern: EvolutionPattern) -> None:
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(pattern.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append pattern: {e}")

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            patterns = []
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        patterns.append(EvolutionPattern.from_dict(d))
            self._patterns = patterns
        except Exception as e:
            logger.warning(f"Failed to load patterns: {e}")


# ─── Institutional Learner ────────────────────────────────────────────────────


class InstitutionalLearner:
    """Converts high-confidence patterns into permanent verification rules.

    Institutional learning: failures become permanent algebraic invariants.
    Future skills are checked against these rules before deployment.
    """

    def __init__(
        self,
        directory: Path,
        min_confidence: float = 0.5,
        max_rules_per_tick: int = 2,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.min_confidence = min_confidence
        self.max_rules_per_tick = max_rules_per_tick

        self._rules: List[VerifyRule] = []
        self._file = self.directory / "verify_rules.jsonl"

        self._load()

    def learn_from_patterns(
        self,
        patterns: List[EvolutionPattern],
        tick: int,
    ) -> List[VerifyRule]:
        """Convert high-confidence patterns into verification rules.

        Returns newly created rules.
        """
        existing_names = {r.name for r in self._rules}
        new_rules = []

        for pattern in patterns:
            if pattern.confidence < self.min_confidence:
                continue
            if pattern.name in existing_names:
                continue
            if len(new_rules) >= self.max_rules_per_tick:
                break

            if pattern.pattern_type == "failure_mode":
                subject = pattern.name.removeprefix("failure:")
                rule = VerifyRule(
                    name=pattern.name,
                    condition=pattern.description,
                    severity="warning",
                    source_tick=tick,
                    source_pattern=pattern.name,
                    created_at=time.time(),
                )
                new_rules.append(rule)
                self._rules.append(rule)
                self._append(rule)

            elif pattern.pattern_type == "stagnation":
                rule = VerifyRule(
                    name=f"stagnation:{pattern.name}",
                    condition=f"Stagnation detected: {pattern.description}",
                    severity="warning",
                    source_tick=tick,
                    source_pattern=pattern.name,
                    created_at=time.time(),
                )
                new_rules.append(rule)
                self._rules.append(rule)
                self._append(rule)

        if new_rules:
            logger.info(
                f"Institutional learning: {len(new_rules)} new rules "
                f"from patterns at tick {tick}"
            )

        return new_rules

    def check_against_rules(
        self, skill_name: str, skill_source: str = "",
    ) -> List[Dict[str, str]]:
        """Check a skill against all verification rules.

        Returns list of violations (rule name + condition).
        Currently returns all applicable rules as warnings;
        actual verification logic is delegated to the LLM.
        """
        violations = []
        for rule in self._rules:
            # Check if the rule's source pattern is related to this skill
            if skill_name in rule.condition or skill_name in rule.name:
                violations.append({
                    "rule": rule.name,
                    "condition": rule.condition,
                    "severity": rule.severity,
                })
        return violations

    def get_rules(self) -> List[VerifyRule]:
        """Get all verification rules."""
        return list(self._rules)

    def get_rules_prompt(self) -> str:
        """Get a prompt describing all verification rules.

        For injection into skill creation/evolution context.
        """
        if not self._rules:
            return ""

        parts = ["INSTITUTIONAL RULES (learned from past failures):"]
        for rule in self._rules:
            parts.append(
                f"  - [{rule.severity}] {rule.name}: {rule.condition}"
            )
        return "\n".join(parts)

    # ── Persistence ────────────────────────────────────────────────────────

    def _append(self, rule: VerifyRule) -> None:
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(rule.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append verify rule: {e}")

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            rules = []
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        rules.append(VerifyRule.from_dict(d))
            self._rules = rules
        except Exception as e:
            logger.warning(f"Failed to load verify rules: {e}")


# ─── History Window ───────────────────────────────────────────────────────────


class HistoryWindow:
    """Bounds event history so fitness/evolution doesn't replay O(n) events.

    Keeps only events within the last `window_ticks` ticks.
    Pruned events are summarized into an archive string.
    """

    def __init__(self, window_ticks: int = 50):
        self.window_ticks = window_ticks
        self._archive_summary: str = ""

    @property
    def archive_summary(self) -> str:
        return self._archive_summary

    def apply(
        self,
        events: List[Any],
        tick: int,
    ) -> List[Any]:
        """Window events, keeping only recent ones.

        Pruned events are summarized in archive_summary.
        Returns the windowed event list.
        """
        cutoff = tick - self.window_ticks
        if cutoff <= 0:
            return events

        recent = [e for e in events if getattr(e, "tick", 0) >= cutoff]
        pruned = [e for e in events if getattr(e, "tick", 0) < cutoff]
        pruned_count = len(pruned)

        if pruned_count == 0:
            return events

        # Build archive summary
        event_types: Dict[str, int] = defaultdict(int)
        subjects: set = set()
        for e in pruned:
            event_types[getattr(e, "event_type", "unknown")] += 1
            subjects.add(getattr(e, "subject", "unknown"))

        new_summary = (
            f"Archived {pruned_count} events (ticks <{cutoff}): "
            f"types={dict(event_types)}, subjects={sorted(subjects)}"
        )
        if self._archive_summary:
            self._archive_summary = f"{self._archive_summary}\n{new_summary}"
        else:
            self._archive_summary = new_summary

        return recent


# ─── Fitness Snapshotter ──────────────────────────────────────────────────────


class FitnessSnapshotter:
    """Takes periodic snapshots of fitness rankings for trend analysis.

    Snapshots are bounded by max_snapshots (oldest dropped when full).
    """

    def __init__(
        self,
        directory: Path,
        snapshot_interval: int = 10,
        max_snapshots: int = 50,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.snapshot_interval = max(1, snapshot_interval)
        self.max_snapshots = max_snapshots

        self._snapshots: List[FitnessSnapshot] = []
        self._file = self.directory / "fitness_snapshots.jsonl"

        self._load()

    def maybe_snapshot(
        self,
        tick: int,
        fitness_records: List[Dict[str, Any]],
    ) -> Optional[FitnessSnapshot]:
        """Take a snapshot if on the snapshot interval.

        Returns the snapshot if taken, else None.
        """
        if tick == 0 or tick % self.snapshot_interval != 0:
            return None

        summary = ", ".join(
            f"{r.get('name', '?')}={r.get('fitness_score', 0):.3f}"
            for r in fitness_records[:5]
        ) if fitness_records else "no skills"

        snapshot = FitnessSnapshot(
            tick=tick,
            timestamp=time.time(),
            rankings=fitness_records[:10],
            summary=summary,
        )

        self._snapshots.append(snapshot)

        # Bound by max_snapshots
        if len(self._snapshots) > self.max_snapshots:
            self._snapshots = self._snapshots[-self.max_snapshots:]

        self._append(snapshot)
        return snapshot

    def get_trend(self, skill_name: str) -> List[Dict[str, Any]]:
        """Get fitness trend for a specific skill across snapshots."""
        trend = []
        for snap in self._snapshots:
            for r in snap.rankings:
                if r.get("name") == skill_name:
                    trend.append({
                        "tick": snap.tick,
                        "fitness": r.get("fitness_score", 0),
                    })
                    break
        return trend

    def get_recent_snapshots(
        self, last_n: int = 5,
    ) -> List[FitnessSnapshot]:
        """Get N most recent snapshots."""
        return self._snapshots[-last_n:]

    def get_stats(self) -> Dict[str, Any]:
        """Get snapshotter statistics."""
        return {
            "total_snapshots": len(self._snapshots),
            "interval": self.snapshot_interval,
            "latest_tick": self._snapshots[-1].tick if self._snapshots else 0,
        }

    # ── Persistence ────────────────────────────────────────────────────────

    def _append(self, snapshot: FitnessSnapshot) -> None:
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(snapshot.to_dict(), default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to append fitness snapshot: {e}")

    def _load(self) -> None:
        if not self._file.exists():
            return
        try:
            snaps = []
            with open(self._file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        snaps.append(FitnessSnapshot(**{
                            k: v for k, v in d.items()
                            if k in FitnessSnapshot.__dataclass_fields__
                        }))
            self._snapshots = snaps
        except Exception as e:
            logger.warning(f"Failed to load fitness snapshots: {e}")


# ─── Unified Pattern Learning Manager ─────────────────────────────────────────


class PatternLearningManager:
    """Unified manager combining pattern detection + institutional learning +
    history windowing + fitness snapshots.

    Usage:
        mgr = PatternLearningManager(directory=Path("data/patterns"))

        # Each tick (in evolution phase):
        mgr.process_tick(
            tick=5,
            events=evolution_events,
            fitness_records=[{...}],
        )

        # Get prompt for LLM:
        prompt = mgr.get_analysis_prompt(events)

        # After LLM produces pattern:
        mgr.report_pattern("failure:browser", "Browser skill fails on JS sites", ...)
    """

    def __init__(
        self,
        directory: Path,
        window_ticks: int = 50,
        snapshot_interval: int = 10,
        min_confidence: float = 0.5,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

        self.detector = PatternDetector(self.directory / "detector")
        self.learner = InstitutionalLearner(
            self.directory / "rules",
            min_confidence=min_confidence,
        )
        self.window = HistoryWindow(window_ticks)
        self.snapshotter = FitnessSnapshotter(
            self.directory / "snapshots",
            snapshot_interval=snapshot_interval,
        )

    def process_tick(
        self,
        tick: int,
        events: List[Any],
        fitness_records: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Run the full pattern learning pipeline for a tick.

        1. Window events
        2. Maybe take fitness snapshot
        3. Check for new institutional rules from patterns

        Returns summary dict.
        """
        # 1. Window events
        windowed = self.window.apply(events, tick)

        # 2. Fitness snapshot
        snapshot = None
        if fitness_records:
            snapshot = self.snapshotter.maybe_snapshot(tick, fitness_records)

        # 3. Institutional learning
        high_conf = self.detector.get_high_confidence_patterns()
        new_rules = self.learner.learn_from_patterns(high_conf, tick)

        return {
            "windowed_events": len(windowed),
            "total_events": len(events),
            "snapshot_taken": snapshot is not None,
            "new_rules": len(new_rules),
            "total_rules": len(self.learner.get_rules()),
            "total_patterns": len(self.detector.get_patterns()),
        }

    def report_pattern(
        self,
        name: str,
        description: str,
        **kwargs: Any,
    ) -> EvolutionPattern:
        """Report a pattern detected by the LLM."""
        return self.detector.report_pattern(name, description, **kwargs)

    def get_analysis_prompt(
        self, events: Sequence[Any],
    ) -> str:
        """Get the pattern analysis prompt for LLM injection."""
        return self.detector.build_analysis_prompt(events)

    def get_rules_prompt(self) -> str:
        """Get institutional rules prompt for LLM injection."""
        return self.learner.get_rules_prompt()

    def get_stats(self) -> Dict[str, Any]:
        """Get pattern learning statistics."""
        return {
            "patterns": len(self.detector.get_patterns()),
            "rules": len(self.learner.get_rules()),
            "snapshots": self.snapshotter.get_stats(),
            "archive": self.window.archive_summary[:200] if self.window.archive_summary else "",
        }
