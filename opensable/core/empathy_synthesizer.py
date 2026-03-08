"""
Empathy Synthesizer — simulates being the user to predict reactions.

WORLD FIRST: Goes beyond Theory of Mind. The agent actually constructs
a virtual model of the user and "becomes" them temporarily to predict
emotional reactions, preferences, and frustrations BEFORE acting.
Like method acting for AI — it doesn't just understand the user,
it BECOMES the user to feel what they'd feel.

Persistence: ``empathy_synthesizer_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class UserModel:
    personality_traits: Dict[str, float] = field(default_factory=lambda: {
        "patience": 0.5, "technical_level": 0.5, "detail_preference": 0.5,
        "formality": 0.5, "humor_appreciation": 0.3,
    })
    preferences: Dict[str, str] = field(default_factory=dict)
    pet_peeves: List[str] = field(default_factory=list)
    positive_reactions: List[str] = field(default_factory=list)
    communication_style: str = "balanced"
    interaction_history_summary: str = ""
    observations: int = 0


@dataclass
class Simulation:
    proposed_action: str = ""
    simulated_reaction: str = ""
    predicted_satisfaction: float = 0.5
    adjustments: List[str] = field(default_factory=list)
    timestamp: float = 0.0


class EmpathySynthesizer:
    """Simulates being the user to predict their reactions."""

    def __init__(self, data_dir: Path, simulation_depth: int = 3):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.simulation_depth = simulation_depth

        self.user_model = UserModel()
        self.simulations: List[Simulation] = []
        self.accuracy_log: List[float] = []
        self.total_simulations: int = 0

        self._load_state()

    def observe(self, user_message: str, context: str = ""):
        """Learn about the user from their messages."""
        msg = user_message.lower()
        self.user_model.observations += 1

        # Detect patience level
        if any(w in msg for w in ["please", "when you can", "no rush"]):
            self.user_model.personality_traits["patience"] = min(1.0,
                self.user_model.personality_traits["patience"] + 0.02)
        if any(w in msg for w in ["now", "urgent", "asap", "hurry"]):
            self.user_model.personality_traits["patience"] = max(0,
                self.user_model.personality_traits["patience"] - 0.03)

        # Detect technical level
        tech_words = ["api", "docker", "kubernetes", "async", "webhook",
                      "endpoint", "deploy", "ci/cd", "pipeline"]
        if any(w in msg for w in tech_words):
            self.user_model.personality_traits["technical_level"] = min(1.0,
                self.user_model.personality_traits["technical_level"] + 0.02)

        # Detect detail preference
        if len(user_message) > 200:
            self.user_model.personality_traits["detail_preference"] = min(1.0,
                self.user_model.personality_traits["detail_preference"] + 0.01)
        elif len(user_message) < 20:
            self.user_model.personality_traits["detail_preference"] = max(0,
                self.user_model.personality_traits["detail_preference"] - 0.01)

        # Detect language preferences
        if any(w in msg for w in ["español", "Spanish", "gracias", "por favor"]):
            self.user_model.preferences["language"] = "es"
        if "english" in msg:
            self.user_model.preferences["language"] = "en"

        # Detect pet peeves
        if any(w in msg for w in ["don't", "stop", "never", "hate when"]):
            for phrase in msg.split("."):
                if any(w in phrase for w in ["don't", "stop", "never"]):
                    self.user_model.pet_peeves.append(phrase.strip()[:100])
                    if len(self.user_model.pet_peeves) > 20:
                        self.user_model.pet_peeves = self.user_model.pet_peeves[-20:]

    async def simulate_reaction(self, llm, proposed_action: str) -> Dict[str, Any]:
        """Become the user and predict how they'd react to proposed action."""
        persona = (
            f"Patience: {self.user_model.personality_traits['patience']:.1f}/1.0\n"
            f"Technical level: {self.user_model.personality_traits['technical_level']:.1f}/1.0\n"
            f"Detail preference: {self.user_model.personality_traits['detail_preference']:.1f}/1.0\n"
            f"Pet peeves: {', '.join(self.user_model.pet_peeves[-5:]) or 'none known'}\n"
            f"Preferences: {json.dumps(self.user_model.preferences)}\n"
            f"Style: {self.user_model.communication_style}"
        )

        prompt = (
            f"You ARE the user with this personality profile:\n{persona}\n\n"
            f"The AI agent is about to: {proposed_action}\n\n"
            f"As this user, how would you FEEL and REACT? "
            f"Rate satisfaction 0-1 and suggest adjustments.\n"
            f"Return JSON: {{\"reaction\": \"...\", \"satisfaction\": 0.X, "
            f"\"adjustments\": [\"...\"], \"emotional_response\": \"...\"}}"
        )

        try:
            resp = await llm.chat_raw(prompt, max_tokens=400)
            import re
            m = re.search(r'\{.*\}', resp, re.DOTALL)
            if m:
                data = json.loads(m.group())
                sim = Simulation(
                    proposed_action=proposed_action[:200],
                    simulated_reaction=data.get("reaction", "")[:300],
                    predicted_satisfaction=float(data.get("satisfaction", 0.5)),
                    adjustments=data.get("adjustments", [])[:5],
                    timestamp=time.time(),
                )
                self.simulations.append(sim)
                self.total_simulations += 1
                if len(self.simulations) > 100:
                    self.simulations = self.simulations[-100:]

                return {
                    "predicted_reaction": sim.simulated_reaction,
                    "satisfaction": sim.predicted_satisfaction,
                    "adjustments": sim.adjustments,
                    "emotional_response": data.get("emotional_response", ""),
                    "should_proceed": sim.predicted_satisfaction >= 0.4,
                }
        except Exception as e:
            logger.debug(f"Empathy simulation failed: {e}")

        return {
            "predicted_reaction": "Unable to simulate",
            "satisfaction": 0.5,
            "adjustments": [],
            "should_proceed": True,
        }

    def quick_check(self, proposed_action: str) -> Dict[str, Any]:
        """Fast heuristic check without LLM (for frequent use)."""
        action_lower = proposed_action.lower()
        warnings = []
        satisfaction = 0.7

        # Check pet peeves
        for peeve in self.user_model.pet_peeves:
            peeve_words = set(peeve.lower().split())
            action_words = set(action_lower.split())
            if len(peeve_words & action_words) >= 2:
                warnings.append(f"Might trigger pet peeve: {peeve[:60]}")
                satisfaction -= 0.2

        # Check patience
        if "long" in action_lower or "wait" in action_lower:
            if self.user_model.personality_traits["patience"] < 0.4:
                warnings.append("User has low patience — keep it quick")
                satisfaction -= 0.1

        # Check detail level
        traits = self.user_model.personality_traits
        if traits["detail_preference"] < 0.3 and "detailed" in action_lower:
            warnings.append("User prefers concise responses")
            satisfaction -= 0.1

        return {
            "satisfaction_estimate": round(max(0, satisfaction), 2),
            "warnings": warnings,
            "proceed": satisfaction >= 0.4,
        }

    def feedback(self, was_satisfied: bool, details: str = ""):
        """Record whether the user was actually satisfied."""
        score = 1.0 if was_satisfied else 0.0
        self.accuracy_log.append(score)
        if len(self.accuracy_log) > 100:
            self.accuracy_log = self.accuracy_log[-100:]

        if was_satisfied:
            self.user_model.positive_reactions.append(details[:100])
            if len(self.user_model.positive_reactions) > 20:
                self.user_model.positive_reactions = self.user_model.positive_reactions[-20:]
        else:
            self.user_model.pet_peeves.append(details[:100])
            if len(self.user_model.pet_peeves) > 20:
                self.user_model.pet_peeves = self.user_model.pet_peeves[-20:]

    def get_stats(self) -> Dict[str, Any]:
        return {
            "user_model": {
                "traits": {k: round(v, 2) for k, v in self.user_model.personality_traits.items()},
                "preferences": self.user_model.preferences,
                "pet_peeves": len(self.user_model.pet_peeves),
                "observations": self.user_model.observations,
                "style": self.user_model.communication_style,
            },
            "simulations_run": self.total_simulations,
            "accuracy": round(
                sum(self.accuracy_log) / max(1, len(self.accuracy_log)), 2),
            "recent_simulations": [
                {"action": s.proposed_action[:60],
                 "satisfaction": round(s.predicted_satisfaction, 2)}
                for s in self.simulations[-3:]
            ],
        }

    def _save_state(self):
        try:
            state = {
                "user_model": asdict(self.user_model),
                "simulations": [asdict(s) for s in self.simulations[-30:]],
                "accuracy_log": self.accuracy_log[-50:],
                "total_simulations": self.total_simulations,
            }
            (self.data_dir / "empathy_synthesizer_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Empathy synthesizer save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "empathy_synthesizer_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_simulations = data.get("total_simulations", 0)
                self.accuracy_log = data.get("accuracy_log", [])
                um = data.get("user_model", {})
                self.user_model = UserModel(
                    **{f: um[f] for f in UserModel.__dataclass_fields__ if f in um})
                for sd in data.get("simulations", []):
                    self.simulations.append(Simulation(
                        **{f: sd[f] for f in Simulation.__dataclass_fields__ if f in sd}))
        except Exception as e:
            logger.debug(f"Empathy synthesizer load: {e}")
