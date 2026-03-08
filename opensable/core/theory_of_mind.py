"""
Theory of Mind — user preference and intention modeling.

Builds and maintains models of each user the agent interacts with,
tracking their preferences, communication style, satisfaction signals,
and implicit intentions to enable more personalized responses.

Key ideas:
  - **Preference tracking**: learns what users like/dislike over time
  - **Satisfaction scoring**: estimates user satisfaction from interaction patterns
  - **Communication style**: adapts verbosity, formality, language
  - **Intent prediction**: anticipates what the user likely wants next
  - **Relationship history**: tracks rapport over time

Persistence: ``theory_of_mind_state.json`` in *data_dir*.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserModel:
    """Mental model of a specific user."""

    user_id: str
    display_name: str = ""

    # Communication preferences
    preferred_language: str = "auto"
    verbosity: str = "normal"  # brief, normal, detailed
    formality: str = "casual"  # formal, casual, technical
    emoji_preference: str = "none"  # none, minimal, frequent

    # Behavioral patterns
    typical_request_types: List[str] = field(default_factory=list)
    topics_of_interest: List[str] = field(default_factory=list)
    disliked_topics: List[str] = field(default_factory=list)

    # Satisfaction tracking
    satisfaction_score: float = 0.7  # 0-1
    total_interactions: int = 0
    positive_signals: int = 0
    negative_signals: int = 0

    # Temporal patterns
    active_hours: List[int] = field(default_factory=list)
    avg_response_words: float = 50.0

    # Relationship
    rapport_score: float = 0.5  # 0-1
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now


@dataclass
class InteractionSignal:
    """A signal from a user interaction."""

    user_id: str
    signal_type: str  # positive, negative, neutral, preference
    content: str
    tick: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class TheoryOfMind:
    """Models user preferences, intentions, and satisfaction."""

    def __init__(
        self,
        data_dir: Path,
        max_users: int = 100,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "theory_of_mind_state.json"

        self._max_users = max_users
        self._users: Dict[str, UserModel] = {}
        self._signals: List[InteractionSignal] = []
        self._total_interactions: int = 0

        self._load_state()

    # ── User model management ─────────────────────────────────────────────────

    def get_or_create_user(self, user_id: str, display_name: str = "") -> UserModel:
        """Get or create a user model."""
        if user_id not in self._users:
            self._users[user_id] = UserModel(
                user_id=user_id,
                display_name=display_name or user_id,
            )

            # Prune old users if too many
            if len(self._users) > self._max_users:
                sorted_users = sorted(
                    self._users.items(),
                    key=lambda x: x[1].total_interactions,
                )
                to_remove = len(self._users) - self._max_users
                for uid, _ in sorted_users[:to_remove]:
                    del self._users[uid]

        return self._users[user_id]

    # ── Signal recording ──────────────────────────────────────────────────────

    def record_interaction(
        self,
        user_id: str,
        message: str,
        response: str,
        tick: int,
        display_name: str = "",
    ):
        """Record a user interaction and update their model."""
        user = self.get_or_create_user(user_id, display_name)
        user.total_interactions += 1
        user.last_seen = datetime.now().isoformat()
        self._total_interactions += 1

        # Track active hours
        hour = datetime.now().hour
        if hour not in user.active_hours:
            user.active_hours.append(hour)
            user.active_hours = user.active_hours[-24:]

        # Track message length preference
        words = len(message.split())
        alpha = 0.1
        user.avg_response_words = alpha * words + (1 - alpha) * user.avg_response_words

        # Detect communication style signals
        self._detect_style_signals(user, message)

        # Detect satisfaction signals
        self._detect_satisfaction_signals(user, message, tick)

        self._save_state()

    def record_signal(self, user_id: str, signal_type: str, content: str, tick: int):
        """Record an explicit signal about user satisfaction."""
        user = self.get_or_create_user(user_id)

        signal = InteractionSignal(
            user_id=user_id,
            signal_type=signal_type,
            content=content[:200],
            tick=tick,
        )
        self._signals.append(signal)

        if signal_type == "positive":
            user.positive_signals += 1
            user.satisfaction_score = min(1.0, user.satisfaction_score + 0.05)
            user.rapport_score = min(1.0, user.rapport_score + 0.03)
        elif signal_type == "negative":
            user.negative_signals += 1
            user.satisfaction_score = max(0.0, user.satisfaction_score - 0.1)
            user.rapport_score = max(0.0, user.rapport_score - 0.05)

        # Keep bounded
        if len(self._signals) > 500:
            self._signals = self._signals[-500:]

        self._save_state()

    def _detect_style_signals(self, user: UserModel, message: str):
        """Detect communication style from message content."""
        lower = message.lower()

        # Language detection (simple heuristic)
        spanish_words = {"que", "de", "la", "el", "en", "es", "un", "por", "una", "con", "para", "como", "pero", "todo", "pues", "ahora"}
        words = set(lower.split())
        spanish_overlap = len(words & spanish_words)
        if spanish_overlap >= 3:
            user.preferred_language = "es"
        elif spanish_overlap == 0 and user.preferred_language == "auto":
            user.preferred_language = "en"

        # Verbosity detection
        word_count = len(message.split())
        if word_count < 10:
            user.verbosity = "brief"
        elif word_count > 100:
            user.verbosity = "detailed"

        # Formality
        formal_markers = {"please", "kindly", "would you", "could you", "thank you"}
        if any(m in lower for m in formal_markers):
            user.formality = "formal"

        informal_markers = {"lol", "xd", "jaja", "haha", "omg", "bro", "dude"}
        if any(m in lower for m in informal_markers):
            user.formality = "casual"

    def _detect_satisfaction_signals(self, user: UserModel, message: str, tick: int):
        """Detect satisfaction signals from message content."""
        lower = message.lower()

        positive_markers = {
            "thank", "thanks", "gracias", "perfect", "perfecto", "great",
            "genial", "awesome", "love it", "exactly", "nice", "good job",
            "bien hecho", "excelente", "increible",
        }
        negative_markers = {
            "wrong", "error", "fix", "broken", "malo", "terrible",
            "hate", "stupid", "useless", "fail", "mierda", "joder",
            "no funciona", "bug",
        }

        for marker in positive_markers:
            if marker in lower:
                self.record_signal(user.user_id, "positive", message[:100], tick)
                return

        for marker in negative_markers:
            if marker in lower:
                self.record_signal(user.user_id, "negative", message[:100], tick)
                return

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Get context about a user for response generation."""
        user = self._users.get(user_id)
        if not user:
            return {"known": False}

        return {
            "known": True,
            "display_name": user.display_name,
            "language": user.preferred_language,
            "verbosity": user.verbosity,
            "formality": user.formality,
            "satisfaction": round(user.satisfaction_score, 2),
            "rapport": round(user.rapport_score, 2),
            "interactions": user.total_interactions,
            "topics": user.topics_of_interest[:5],
            "active_hours": user.active_hours[-8:],
        }

    def get_adaptation_hints(self, user_id: str) -> Dict[str, str]:
        """Get response adaptation hints for a user."""
        user = self._users.get(user_id)
        if not user:
            return {}

        hints = {}

        if user.preferred_language == "es":
            hints["language"] = "Respond in Spanish"
        if user.verbosity == "brief":
            hints["length"] = "Keep response very concise"
        elif user.verbosity == "detailed":
            hints["length"] = "Provide detailed explanation"
        if user.formality == "casual":
            hints["tone"] = "Use casual/friendly tone"
        if user.satisfaction_score < 0.3:
            hints["recovery"] = "User seems dissatisfied — be extra careful and helpful"
        if user.rapport_score > 0.8:
            hints["rapport"] = "Strong rapport — user trusts the agent"

        return hints

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        users_summary = []
        for u in sorted(self._users.values(), key=lambda x: -x.total_interactions)[:10]:
            users_summary.append({
                "user_id": u.user_id[:20],
                "name": u.display_name[:30],
                "interactions": u.total_interactions,
                "satisfaction": round(u.satisfaction_score, 2),
                "rapport": round(u.rapport_score, 2),
                "language": u.preferred_language,
                "style": u.formality,
            })

        avg_satisfaction = 0.0
        if self._users:
            avg_satisfaction = sum(u.satisfaction_score for u in self._users.values()) / len(self._users)

        return {
            "total_users": len(self._users),
            "total_interactions": self._total_interactions,
            "total_signals": len(self._signals),
            "avg_satisfaction": round(avg_satisfaction, 3),
            "users": users_summary,
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "users": {k: asdict(v) for k, v in self._users.items()},
                "signals": [asdict(s) for s in self._signals[-500:]],
                "total_interactions": self._total_interactions,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Theory of mind save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._total_interactions = data.get("total_interactions", 0)

                for uid, udata in data.get("users", {}).items():
                    self._users[uid] = UserModel(**udata)

                for sdata in data.get("signals", []):
                    self._signals.append(InteractionSignal(**sdata))
        except Exception as e:
            logger.debug(f"Theory of mind load failed: {e}")
