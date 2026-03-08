"""
Phantom Limb — missing capability auto-detection.

WORLD FIRST: The agent detects capabilities it SHOULD have but doesn't.
When tasks repeatedly fail for the same structural reason, the agent
identifies the "phantom limb" — a tool, skill, or integration it lacks —
and generates capability acquisition requests.

Persistence: ``phantom_limb_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MissingCapability:
    id: str = ""
    description: str = ""
    evidence: List[str] = field(default_factory=list)
    failure_count: int = 0
    severity: float = 0.0  # 0-1
    first_detected: float = 0.0
    last_triggered: float = 0.0
    resolved: bool = False
    resolution: str = ""


class PhantomLimb:
    """Detects capabilities the agent needs but doesn't have."""

    def __init__(self, data_dir: Path, detect_threshold: int = 3,
                 max_phantoms: int = 100):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.detect_threshold = detect_threshold
        self.max_phantoms = max_phantoms

        self.failure_patterns: Dict[str, List[str]] = {}
        self.phantoms: Dict[str, MissingCapability] = {}
        self.resolved: List[MissingCapability] = []

        self._load_state()

    def record_failure(self, task: str, error: str, context: str = ""):
        """Record a task failure with its error signature."""
        sig = self._error_signature(error)
        if sig not in self.failure_patterns:
            self.failure_patterns[sig] = []
        self.failure_patterns[sig].append(task[:200])
        if len(self.failure_patterns[sig]) > 20:
            self.failure_patterns[sig] = self.failure_patterns[sig][-20:]

        # Check if pattern crosses threshold
        if len(self.failure_patterns[sig]) >= self.detect_threshold:
            if sig not in self.phantoms:
                self.phantoms[sig] = MissingCapability(
                    id=sig,
                    description=f"Repeated failures: {error[:200]}",
                    evidence=self.failure_patterns[sig][-5:],
                    failure_count=len(self.failure_patterns[sig]),
                    severity=min(1.0, len(self.failure_patterns[sig]) / 10),
                    first_detected=time.time(),
                    last_triggered=time.time(),
                )
                if len(self.phantoms) > self.max_phantoms:
                    weakest = min(self.phantoms.values(), key=lambda p: p.severity)
                    del self.phantoms[weakest.id]
            else:
                p = self.phantoms[sig]
                p.failure_count = len(self.failure_patterns[sig])
                p.severity = min(1.0, p.failure_count / 10)
                p.last_triggered = time.time()
                p.evidence = self.failure_patterns[sig][-5:]

    async def diagnose(self, llm) -> List[Dict[str, Any]]:
        """Use LLM to analyze phantoms and suggest capability acquisitions."""
        active = [p for p in self.phantoms.values() if not p.resolved]
        if not active:
            return []
        phantoms_text = "\n".join(
            f"- [{p.severity:.1f}] {p.description} ({p.failure_count} failures)"
            for p in sorted(active, key=lambda x: x.severity, reverse=True)[:5]
        )
        prompt = (
            f"The AI agent keeps failing at these tasks:\n{phantoms_text}\n\n"
            f"For each, identify the MISSING CAPABILITY (tool, skill, integration, "
            f"or knowledge) the agent needs. Return JSON:\n"
            f"[{{\"phantom\": \"...\", \"capability_needed\": \"...\", \"acquisition_plan\": \"...\"}}]"
        )
        try:
            resp = await llm.chat_raw(prompt, max_tokens=600)
            import re
            m = re.search(r'\[.*\]', resp, re.DOTALL)
            if m:
                return json.loads(m.group())
        except Exception as e:
            logger.debug(f"Phantom diagnosis failed: {e}")
        return []

    def resolve(self, phantom_id: str, resolution: str = ""):
        """Mark a phantom as resolved."""
        if phantom_id in self.phantoms:
            p = self.phantoms[phantom_id]
            p.resolved = True
            p.resolution = resolution
            self.resolved.append(p)
            del self.phantoms[phantom_id]
            if len(self.resolved) > 50:
                self.resolved = self.resolved[-50:]

    def get_critical_phantoms(self, top_n: int = 5) -> List[Dict[str, Any]]:
        """Get the most severe unresolved phantoms."""
        active = [p for p in self.phantoms.values() if not p.resolved]
        return [
            {"id": p.id, "description": p.description[:100],
             "severity": round(p.severity, 2), "failures": p.failure_count}
            for p in sorted(active, key=lambda x: x.severity, reverse=True)[:top_n]
        ]

    def get_stats(self) -> Dict[str, Any]:
        active = [p for p in self.phantoms.values() if not p.resolved]
        return {
            "active_phantoms": len(active),
            "resolved": len(self.resolved),
            "failure_patterns_tracked": len(self.failure_patterns),
            "critical": self.get_critical_phantoms(3),
            "most_severe": round(max((p.severity for p in active), default=0), 2),
            "total_failures": sum(p.failure_count for p in active),
        }

    def _error_signature(self, error: str) -> str:
        # Normalize error to create a signature
        normalized = error.lower().strip()
        # Remove variable parts (numbers, paths, etc.)
        import re
        normalized = re.sub(r'\d+', 'N', normalized)
        normalized = re.sub(r'/\S+', '/PATH', normalized)
        normalized = re.sub(r'0x[0-9a-f]+', '0xADDR', normalized)
        return hashlib.md5(normalized.encode()).hexdigest()[:12]

    def _save_state(self):
        try:
            state = {
                "failure_patterns": {k: v[-10:] for k, v in self.failure_patterns.items()},
                "phantoms": {k: asdict(v) for k, v in self.phantoms.items()},
                "resolved": [asdict(r) for r in self.resolved[-20:]],
            }
            (self.data_dir / "phantom_limb_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Phantom limb save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "phantom_limb_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.failure_patterns = data.get("failure_patterns", {})
                for k, v in data.get("phantoms", {}).items():
                    self.phantoms[k] = MissingCapability(
                        **{f: v[f] for f in MissingCapability.__dataclass_fields__ if f in v})
                for r in data.get("resolved", []):
                    self.resolved.append(MissingCapability(
                        **{f: r[f] for f in MissingCapability.__dataclass_fields__ if f in r}))
        except Exception as e:
            logger.debug(f"Phantom limb load: {e}")
