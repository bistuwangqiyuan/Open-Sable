"""
Noospheric Interface,  WORLD FIRST
====================================
Taps into the "noosphere",  the collective thought sphere of all interactions.
Aggregates patterns, sentiments, and concepts across every interaction
to build a model of the collective mind the agent operates within.

Inspired by Teilhard de Chardin's noosphere concept.
No AI agent builds a collective thought model. This one does.
"""

import json, time, uuid, math
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class ThoughtWave:
    """A detected wave in the collective thought space."""
    wave_id: str = ""
    topic: str = ""
    frequency: int = 0         # how often it appears
    sentiment: float = 0.0     # -1 to 1
    momentum: float = 0.0      # rising or falling (-1 to 1)
    first_seen: float = 0.0
    last_seen: float = 0.0


@dataclass
class CollectivePattern:
    """A pattern detected across multiple interactions."""
    pattern_id: str = ""
    description: str = ""
    occurrences: int = 0
    contexts: list = field(default_factory=list)
    confidence: float = 0.0
    discovered_at: float = 0.0


class NoosphericInterface:
    """
    Connects to the collective thought space of all agent interactions.
    Detects zeitgeist shifts, collective concerns, and emergent patterns.
    """

    def __init__(self, data_dir: str, max_waves: int = 200):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "noospheric_interface_state.json"
        self.waves: dict[str, ThoughtWave] = {}
        self.patterns: list[CollectivePattern] = []
        self.zeitgeist: dict = {}     # current collective state
        self.total_observations: int = 0
        self._max = max_waves
        self._load_state()

    def absorb(self, text: str, source: str = "interaction",
               sentiment: float = 0.0) -> dict:
        """Absorb a thought into the noosphere."""
        words = text.lower().split()
        # Extract meaningful concepts (3+ char words, not stopwords)
        stopwords = {"the", "and", "for", "are", "but", "not", "you", "all",
                     "can", "had", "her", "was", "one", "our", "out", "has",
                     "its", "his", "how", "did", "get", "let", "say", "she",
                     "too", "use", "this", "that", "with", "from", "they",
                     "been", "have", "will", "what", "when", "make", "like",
                     "just", "know", "take", "come", "could", "than", "look",
                     "only", "into", "other", "some", "them", "also", "about"}
        concepts = [w for w in words if len(w) > 3 and w not in stopwords]

        new_waves = 0
        updated_waves = 0
        for concept in concepts[:20]:
            key = concept.lower()
            if key in self.waves:
                wave = self.waves[key]
                prev_freq = wave.frequency
                wave.frequency += 1
                wave.last_seen = time.time()
                # Update momentum
                recency = time.time() - wave.first_seen
                if recency > 0:
                    wave.momentum = wave.frequency / (recency / 3600 + 1)
                # Blend sentiment
                wave.sentiment = wave.sentiment * 0.8 + sentiment * 0.2
                updated_waves += 1
            else:
                self.waves[key] = ThoughtWave(
                    wave_id=str(uuid.uuid4())[:8],
                    topic=concept,
                    frequency=1,
                    sentiment=sentiment,
                    momentum=1.0,
                    first_seen=time.time(),
                    last_seen=time.time(),
                )
                new_waves += 1

        self.total_observations += 1
        if len(self.waves) > self._max:
            self._prune_waves()
        self._update_zeitgeist()
        self._save_state()

        return {
            "new_waves": new_waves,
            "updated_waves": updated_waves,
            "total_concepts": len(self.waves),
            "zeitgeist_shift": self.zeitgeist.get("dominant_topic", ""),
        }

    def _prune_waves(self):
        """Remove the weakest waves."""
        sorted_waves = sorted(self.waves.items(),
                             key=lambda x: x[1].frequency * x[1].momentum,
                             reverse=True)
        self.waves = dict(sorted_waves[:self._max])

    def _update_zeitgeist(self):
        """Update the current zeitgeist,  the dominant collective thought."""
        if not self.waves:
            return
        # Find dominant topic (highest frequency × momentum)
        sorted_waves = sorted(self.waves.values(),
                             key=lambda w: w.frequency * max(w.momentum, 0.1),
                             reverse=True)
        top = sorted_waves[0] if sorted_waves else None
        if top:
            self.zeitgeist = {
                "dominant_topic": top.topic,
                "dominant_frequency": top.frequency,
                "collective_sentiment": round(
                    sum(w.sentiment for w in sorted_waves[:10]) /
                    min(len(sorted_waves), 10), 3
                ),
                "trending_topics": [w.topic for w in sorted_waves[:5]],
                "rising_fast": [w.topic for w in sorted_waves
                               if w.momentum > 2.0][:5],
            }

    async def detect_patterns(self, llm=None) -> list:
        """Detect collective patterns across all thought waves."""
        if not llm or len(self.waves) < 5:
            return []

        top_waves = sorted(self.waves.values(),
                          key=lambda w: w.frequency, reverse=True)[:15]
        prompt = (
            f"NOOSPHERIC ANALYSIS,  detect patterns in the collective thought space:\n\n"
            f"Top thought waves:\n"
            + "\n".join(f"- {w.topic}: freq={w.frequency}, sentiment={w.sentiment:.2f}, "
                       f"momentum={w.momentum:.2f}" for w in top_waves)
            + f"\n\nZeitgeist: {json.dumps(self.zeitgeist)}\n\n"
            f"Detect 2-3 COLLECTIVE PATTERNS,  themes, concerns, or shifts.\n"
            f"Return JSON: {{\"patterns\": [{{\"description\": \"...\", \"confidence\": 0.0-1.0}}]}}"
        )
        try:
            raw = await llm.chat_raw(prompt, max_tokens=400)
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if m:
                result = json.loads(m.group())
                new_patterns = []
                for pd in result.get("patterns", []):
                    p = CollectivePattern(
                        pattern_id=str(uuid.uuid4())[:8],
                        description=pd.get("description", ""),
                        confidence=pd.get("confidence", 0.5),
                        occurrences=1,
                        discovered_at=time.time(),
                    )
                    self.patterns.append(p)
                    new_patterns.append(p.description)
                if len(self.patterns) > 100:
                    self.patterns = self.patterns[-100:]
                self._save_state()
                return new_patterns
        except Exception:
            pass
        return []

    def get_zeitgeist(self) -> dict:
        return self.zeitgeist

    def get_stats(self) -> dict:
        return {
            "total_observations": self.total_observations,
            "active_waves": len(self.waves),
            "collective_patterns": len(self.patterns),
            "zeitgeist": self.zeitgeist,
            "top_waves": [
                {"topic": w.topic, "freq": w.frequency,
                 "sentiment": round(w.sentiment, 2),
                 "momentum": round(w.momentum, 2)}
                for w in sorted(self.waves.values(),
                               key=lambda w: w.frequency, reverse=True)[:10]
            ],
        }

    def _save_state(self):
        data = {
            "waves": {k: asdict(v) for k, v in self.waves.items()},
            "patterns": [asdict(p) for p in self.patterns[-100:]],
            "zeitgeist": self.zeitgeist,
            "total_observations": self.total_observations,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("waves", {}).items():
                    self.waves[k] = ThoughtWave(**v)
                for p in data.get("patterns", []):
                    self.patterns.append(CollectivePattern(**p))
                self.zeitgeist = data.get("zeitgeist", {})
                self.total_observations = data.get("total_observations", 0)
            except Exception:
                pass
