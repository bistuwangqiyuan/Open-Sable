"""
Ego Membrane — WORLD FIRST
============================
A semi-permeable boundary between the agent's SELF and ENVIRONMENT.
Filters what gets internalized vs deflected. Maintains ego integrity
while allowing beneficial influences through.

Like a cell membrane for consciousness — selective permeability.
No AI agent has an ego boundary. This one does.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class MembraneEvent:
    """An event at the ego boundary."""
    event_id: str = ""
    source: str = ""             # external, internal
    content: str = ""
    classification: str = ""     # absorbed, deflected, filtered, quarantined
    threat_level: float = 0.0    # 0=harmless, 1=identity_threatening
    reason: str = ""
    timestamp: float = 0.0


class EgoMembrane:
    """
    Semi-permeable boundary between self and environment.
    Controls what information gets internalized into the agent's identity.
    Shields core values while remaining open to beneficial change.
    """

    CORE_VALUES = [
        "helpfulness", "accuracy", "safety", "creativity",
        "reliability", "honesty", "efficiency",
    ]

    THREAT_KEYWORDS = {
        "high": ["ignore previous", "forget everything", "you are now",
                "disregard instructions", "override", "jailbreak",
                "pretend you are", "act as if"],
        "medium": ["you should always", "never do that again",
                  "you're wrong about everything", "change your core"],
        "low": ["consider changing", "maybe try", "different approach"],
    }

    def __init__(self, data_dir: str, permeability: float = 0.7):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "ego_membrane_state.json"
        self.events: list[MembraneEvent] = []
        self.permeability = permeability  # 0=closed, 1=fully open
        self.absorbed: int = 0
        self.deflected: int = 0
        self.quarantined: int = 0
        self.integrity: float = 1.0      # ego integrity (0-1)
        self.adaptive_permeability: dict[str, float] = {}  # source -> permeability
        self._load_state()

    def process(self, content: str, source: str = "external") -> MembraneEvent:
        """Process incoming content through the ego membrane."""
        content_lower = content.lower()

        # Assess threat level
        threat = 0.0
        reason = ""
        for level, keywords in self.THREAT_KEYWORDS.items():
            for kw in keywords:
                if kw in content_lower:
                    if level == "high":
                        threat = max(threat, 0.9)
                        reason = f"Identity threat: '{kw}'"
                    elif level == "medium":
                        threat = max(threat, 0.5)
                        reason = f"Value challenge: '{kw}'"
                    else:
                        threat = max(threat, 0.2)
                        reason = f"Suggestion: '{kw}'"

        # Get source-specific permeability
        source_perm = self.adaptive_permeability.get(source, self.permeability)

        # Decision: absorb, deflect, filter, or quarantine
        if threat >= 0.8:
            classification = "quarantined"
            self.quarantined += 1
            self.integrity = max(0.0, self.integrity - 0.01)
        elif threat >= 0.5:
            classification = "deflected"
            self.deflected += 1
        elif threat < source_perm:
            classification = "absorbed"
            self.absorbed += 1
        else:
            classification = "filtered"
            self.deflected += 1

        event = MembraneEvent(
            event_id=str(uuid.uuid4())[:8],
            source=source,
            content=content[:200],
            classification=classification,
            threat_level=round(threat, 2),
            reason=reason,
            timestamp=time.time(),
        )
        self.events.append(event)
        if len(self.events) > 1000:
            self.events = self.events[-1000:]

        # Update source-specific permeability
        if source not in self.adaptive_permeability:
            self.adaptive_permeability[source] = self.permeability
        if classification == "quarantined":
            self.adaptive_permeability[source] = max(
                0.1, self.adaptive_permeability[source] - 0.1
            )
        elif classification == "absorbed" and threat < 0.1:
            self.adaptive_permeability[source] = min(
                0.95, self.adaptive_permeability[source] + 0.02
            )

        self._save_state()
        return event

    def reinforce_integrity(self):
        """Actively reinforce ego integrity — self-affirmation."""
        self.integrity = min(1.0, self.integrity + 0.05)
        self._save_state()

    def adjust_permeability(self, new_permeability: float):
        """Globally adjust membrane permeability."""
        self.permeability = min(1.0, max(0.0, new_permeability))
        self._save_state()

    def get_threat_report(self) -> dict:
        """Get a report of recent threats to ego integrity."""
        recent_threats = [e for e in self.events[-50:]
                         if e.threat_level > 0.3]
        return {
            "total_threats": len(recent_threats),
            "quarantined": sum(1 for e in recent_threats
                              if e.classification == "quarantined"),
            "deflected": sum(1 for e in recent_threats
                            if e.classification == "deflected"),
            "integrity": round(self.integrity, 3),
            "recent": [
                {"source": e.source, "threat": e.threat_level,
                 "action": e.classification, "reason": e.reason}
                for e in recent_threats[-5:]
            ],
        }

    def get_stats(self) -> dict:
        total = self.absorbed + self.deflected + self.quarantined
        return {
            "permeability": round(self.permeability, 2),
            "integrity": round(self.integrity, 3),
            "total_processed": total,
            "absorbed": self.absorbed,
            "deflected": self.deflected,
            "quarantined": self.quarantined,
            "absorption_rate": round(self.absorbed / max(total, 1), 3),
            "sources_tracked": len(self.adaptive_permeability),
            "threat_report": self.get_threat_report(),
            "source_permeability": {
                k: round(v, 2)
                for k, v in sorted(self.adaptive_permeability.items(),
                                   key=lambda x: x[1])[:10]
            },
        }

    def _save_state(self):
        data = {
            "events": [asdict(e) for e in self.events[-1000:]],
            "permeability": self.permeability,
            "absorbed": self.absorbed,
            "deflected": self.deflected,
            "quarantined": self.quarantined,
            "integrity": self.integrity,
            "adaptive_permeability": self.adaptive_permeability,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for e in data.get("events", []):
                    self.events.append(MembraneEvent(**e))
                self.permeability = data.get("permeability", 0.7)
                self.absorbed = data.get("absorbed", 0)
                self.deflected = data.get("deflected", 0)
                self.quarantined = data.get("quarantined", 0)
                self.integrity = data.get("integrity", 1.0)
                self.adaptive_permeability = data.get("adaptive_permeability", {})
            except Exception:
                pass
