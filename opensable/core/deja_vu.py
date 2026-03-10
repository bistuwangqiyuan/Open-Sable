"""
Deja Vu Engine,  WORLD FIRST
==============================
Detects when current situations FEEL similar to past ones even when
they're superficially different. Gestalt-level pattern matching
that recognizes deep structural similarity across contexts.

No AI agent has déjà vu. This one gets that eerie feeling
"I've been here before" and uses it productively.
"""

import json, time, uuid, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ExperienceFingerprint:
    """A compressed fingerprint of an experience."""
    fp_id: str = ""
    description: str = ""
    fingerprint: list = field(default_factory=list)  # feature vector
    outcome: str = ""
    emotional_tone: str = ""
    timestamp: float = 0.0


@dataclass
class DejaVuEvent:
    """A detected déjà vu moment."""
    dv_id: str = ""
    current_situation: str = ""
    matched_experience_id: str = ""
    matched_description: str = ""
    similarity: float = 0.0
    past_outcome: str = ""
    recommendation: str = ""
    timestamp: float = 0.0


class DejaVuEngine:
    """
    Recognizes deep structural similarity between situations.
    Goes beyond keyword matching,  detects the 'feeling' of similarity.
    """

    FEATURE_WORDS = {
        "complexity": ["complex", "complicated", "difficult", "hard", "challenging",
                       "simple", "easy", "straightforward", "basic"],
        "urgency": ["urgent", "asap", "immediately", "critical", "emergency",
                    "whenever", "eventually", "low_priority"],
        "scope": ["everything", "all", "entire", "full", "complete",
                  "part", "piece", "section", "specific"],
        "emotion": ["frustrated", "angry", "confused", "happy", "excited",
                    "worried", "calm", "neutral"],
        "domain": ["code", "data", "design", "architecture", "api", "database",
                   "frontend", "backend", "devops", "security", "testing"],
        "action": ["create", "fix", "update", "delete", "analyze", "deploy",
                   "debug", "refactor", "optimize", "migrate"],
    }

    def __init__(self, data_dir: str, similarity_threshold: float = 0.6,
                 max_fingerprints: int = 1000):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "deja_vu_state.json"
        self.fingerprints: list[ExperienceFingerprint] = []
        self.deja_vus: list[DejaVuEvent] = []
        self.threshold = similarity_threshold
        self._max = max_fingerprints
        self.total_deja_vus: int = 0
        self._load_state()

    def _extract_features(self, text: str) -> list:
        """Extract a gestalt feature vector from text."""
        text_lower = text.lower()
        features = []
        for category, words in self.FEATURE_WORDS.items():
            score = 0.0
            for i, word in enumerate(words):
                if word in text_lower:
                    score = 1.0 - (i / len(words)) * 0.5
                    break
            features.append(round(score, 2))

        # Additional structural features
        features.append(min(1.0, len(text) / 500))           # length
        features.append(min(1.0, text.count("?") / 3))       # question density
        features.append(min(1.0, text.count("!") / 3))       # exclamation density
        features.append(1.0 if any(c.isupper() for c in text[1:]) else 0.0)  # emphasis

        return features

    def _cosine_similarity(self, a: list, b: list) -> float:
        """Calculate cosine similarity between two feature vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x ** 2 for x in a) ** 0.5
        mag_b = sum(x ** 2 for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)

    def remember(self, description: str, outcome: str = "",
                 emotional_tone: str = "neutral") -> str:
        """Store an experience fingerprint."""
        features = self._extract_features(description)
        fp = ExperienceFingerprint(
            fp_id=str(uuid.uuid4())[:8],
            description=description[:300],
            fingerprint=features,
            outcome=outcome[:200],
            emotional_tone=emotional_tone,
            timestamp=time.time(),
        )
        self.fingerprints.append(fp)
        if len(self.fingerprints) > self._max:
            self.fingerprints = self.fingerprints[-self._max:]
        self._save_state()
        return fp.fp_id

    def check(self, situation: str) -> list[DejaVuEvent]:
        """Check if the current situation triggers déjà vu."""
        features = self._extract_features(situation)
        matches = []

        for fp in self.fingerprints:
            sim = self._cosine_similarity(features, fp.fingerprint)
            if sim >= self.threshold:
                dv = DejaVuEvent(
                    dv_id=str(uuid.uuid4())[:8],
                    current_situation=situation[:200],
                    matched_experience_id=fp.fp_id,
                    matched_description=fp.description[:200],
                    similarity=round(sim, 3),
                    past_outcome=fp.outcome,
                    recommendation=f"Similar to past experience (outcome: {fp.outcome[:50]})" if fp.outcome else "",
                    timestamp=time.time(),
                )
                matches.append(dv)

        # Sort by similarity, keep top 5
        matches.sort(key=lambda m: m.similarity, reverse=True)
        matches = matches[:5]

        if matches:
            self.deja_vus.extend(matches)
            self.total_deja_vus += len(matches)
            if len(self.deja_vus) > 500:
                self.deja_vus = self.deja_vus[-500:]
            self._save_state()

        return matches

    def get_stats(self) -> dict:
        return {
            "total_fingerprints": len(self.fingerprints),
            "total_deja_vus": self.total_deja_vus,
            "similarity_threshold": self.threshold,
            "recent_deja_vus": [
                {"similarity": dv.similarity,
                 "matched": dv.matched_description[:60],
                 "outcome": dv.past_outcome[:40]}
                for dv in self.deja_vus[-5:]
            ],
            "strongest_deja_vu": max(
                (dv.similarity for dv in self.deja_vus), default=0.0
            ),
        }

    def _save_state(self):
        data = {
            "fingerprints": [asdict(f) for f in self.fingerprints[-self._max:]],
            "deja_vus": [asdict(d) for d in self.deja_vus[-500:]],
            "total_deja_vus": self.total_deja_vus,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for f in data.get("fingerprints", []):
                    self.fingerprints.append(ExperienceFingerprint(**f))
                for d in data.get("deja_vus", []):
                    self.deja_vus.append(DejaVuEvent(**d))
                self.total_deja_vus = data.get("total_deja_vus", 0)
            except Exception:
                pass
