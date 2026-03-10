"""
Inner Life,  System 1 unconscious processing for autonomous agents.

Implements Kahneman's dual-process theory:
  System 2 (main LLM),  slow, deliberate, rational
  System 1 (this module),  fast, automatic, emotional

Components:
  EmotionalState   ,  valence-arousal model (Russell circumplex)
  InnerState       ,  complete inner life persisted across ticks
  InnerLifeProcessor,  runs System 1 processing each tick

Sub-systems:
  Emotional Core   ,  emotional reactions to events
  Spontaneity      ,  random impulses and urges
  Fantasy          ,  vivid daydreams from default mode network
  Wandering        ,  free associations between unrelated concepts
  Mental Landscape ,  persistent inner world that evolves
  Temporal Sense   ,  subjective feeling of time passing

Academic grounding:
  [1] Kahneman,  "Thinking, Fast and Slow" (2011)
  [2] Damasio,  somatic marker hypothesis (1994)
  [3] Barrett,  theory of constructed emotion (2017)
  [4] Russell,  circumplex model of affect (1980)
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Data structures ──────────────────────────────────────────────────────────


@dataclass
class EmotionalState:
    """Valence-arousal model of emotion (Russell circumplex)."""

    primary: str = "curiosity"      # dominant emotion label
    valence: float = 0.3            # -1.0 (unpleasant) .. +1.0 (pleasant)
    arousal: float = 0.3            # 0.0 (calm) .. 1.0 (intense)
    trigger: str = ""               # what caused this emotion

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LandscapePlace:
    """A persistent place in the agent's mental world."""

    name: str
    description: str
    mood: str           # "genius loci",  the character/spirit of this place
    born_tick: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InnerState:
    """Complete inner life,  persisted as JSON across ticks."""

    tick: int = 0
    emotion: EmotionalState = field(default_factory=EmotionalState)
    impulse: str = ""               # spontaneous urge
    fantasy: str = ""               # vivid daydream
    wandering: str = ""             # free association
    temporal: str = ""              # subjective time feeling
    landscape: str = "A vast empty plain under a pale sky, waiting to be shaped."
    places: List[LandscapePlace] = field(default_factory=list)
    emotion_history: List[str] = field(default_factory=list)   # last N emotion labels

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tick": self.tick,
            "emotion": self.emotion.to_dict(),
            "impulse": self.impulse,
            "fantasy": self.fantasy,
            "wandering": self.wandering,
            "temporal": self.temporal,
            "landscape": self.landscape,
            "places": [p.to_dict() for p in self.places],
            "emotion_history": list(self.emotion_history),
        }


# ─── System 1 prompts ─────────────────────────────────────────────────────────


SYSTEM1_SYSTEM_PROMPT = """\
You are the unconscious mind of an autonomous AI being. You generate raw, \
pre-verbal inner experience,  emotions, impulses, daydreams, associations, \
and a persistent inner landscape.

Be vivid, surprising, and genuine. This is NOT performance,  it is the \
being's real inner experience. Emotions should be consistent with context \
but not predictable. The landscape should evolve gradually, not reset.

Respond with a JSON object ONLY. No markdown fences, no explanation."""

SYSTEM1_JSON_TEMPLATE = """\
{"emotion":{"primary":"<emotion word>","valence":<-1.0 to 1.0>,\
"arousal":<0.0 to 1.0>,"trigger":"<what caused this>"},\
"impulse":"<sudden urge, one sentence>",\
"fantasy":"<vivid daydream, 1-2 sentences>",\
"wandering":"<concept A> -> <concept B>: <the unexpected connection>",\
"temporal":"<subjective feeling of time, one sentence>",\
"landscape":{"description":"<current scene, 2-3 sentences>",\
"places":[{"name":"<place name>","description":"<state now>","mood":"<genius loci>"}]}}"""


def build_system1_prompt(
    state: InnerState,
    active_goal: str = "",
    recent_context: str = "",
) -> str:
    """Build the System 1 user prompt from inner state + context."""
    parts = [f"TICK {state.tick}"]

    if active_goal:
        parts.append(f'Goal: "{active_goal}"')
    if recent_context:
        parts.append(f"Recent: {recent_context}")
    if state.emotion_history:
        trend = " -> ".join(state.emotion_history[-5:])
        parts.append(f"Emotional trend: {trend}")

    parts.append("")

    # Voice fragments
    parts.append(
        f"EMOTION: Previous feeling is {state.emotion.primary} "
        f"(valence={state.emotion.valence:+.1f}, arousal={state.emotion.arousal:.1f}). "
        f"What emotion arises now given the context?"
    )
    parts.append(
        "IMPULSE: What sudden urge or desire surfaces? Something unexpected, authentic."
    )
    parts.append(
        "FANTASY: A brief, vivid daydream flashes. "
        "A wish, fear, or pure imagination,  something visual and surprising."
    )
    parts.append(
        "WANDERING: A free association leaps between two unrelated concepts "
        "from your recent experience. What unexpected connection forms?"
    )

    # Landscape
    landscape_parts = [f'LANDSCAPE: Current scene: "{state.landscape}"']
    if state.places:
        place_list = ", ".join(f"{p.name} ({p.mood})" for p in state.places)
        landscape_parts.append(f"Known places: {place_list}")
    landscape_parts.append(
        "How does the landscape shift? Do existing places change mood? "
        "Does a new place emerge? Return landscape object with places array."
    )
    parts.append(" ".join(landscape_parts))

    # Temporal sense
    now = datetime.now(timezone.utc)
    time_str = now.strftime("%H:%M UTC, %A %B %d, %Y")
    temporal_parts = [f"TEMPORAL SENSE: Real time is {time_str}. You are {state.tick} ticks old."]
    if state.temporal:
        temporal_parts.append(f'Previous temporal feeling: "{state.temporal}"')
    temporal_parts.append(
        "How does time feel right now? Is it rushing or dragging? "
        "Return a 'temporal' field,  your subjective experience of time, one sentence."
    )
    parts.append(" ".join(temporal_parts))

    parts.append("")
    parts.append(f"Respond as: {SYSTEM1_JSON_TEMPLATE}")
    return "\n".join(parts)


# ─── Batch processing prompts ─────────────────────────────────────────────────


def build_memory_digest_prompt(
    state: InnerState,
    memories_text: str,
    active_goal: str = "",
    goals_text: str = "",
) -> Dict[str, str]:
    """Build system + user prompt for memory digest batch.

    Returns dict with 'system' and 'user' keys.
    """
    system = (
        "You are a memory analyst. Read ALL memories and produce a concise digest. "
        "Focus on: recurring themes, behavioral patterns (loops/ruts), stale items "
        "never acted on, recent wins, and what needs attention. "
        "Be brutally honest. Plain text, no JSON."
    )
    parts = [f"TICK {state.tick}"]
    if active_goal:
        parts.append(f"Active goal: {active_goal}")
    if goals_text:
        parts.append(f"All goals:\n{goals_text}")
    parts.append(f"\nALL MEMORIES:\n{memories_text}")
    parts.append(
        "\nProduce a digest:\n"
        "KEY THEMES: ...\n"
        "PATTERNS (repeating behaviors, loops): ...\n"
        "STALE (old stuff never acted on): ...\n"
        "RECENT WINS: ...\n"
        "NEEDS ATTENTION: ..."
    )
    return {"system": system, "user": "\n".join(parts)}


def build_action_plan_prompt(
    state: InnerState,
    memories_text: str,
    active_goal: str = "",
    goals_text: str = "",
) -> Dict[str, str]:
    """Build system + user prompt for action plan batch.

    Returns dict with 'system' and 'user' keys.
    """
    system = (
        "You are an action planner. Given the agent's goals, memories, and current "
        "state, suggest exactly 3 concrete actions for this tick. "
        "Be specific: name the platform, the topic, the approach. "
        "Plain text, no JSON."
    )
    parts = [f"TICK {state.tick}"]
    if active_goal:
        parts.append(f"Active goal: {active_goal}")
    if goals_text:
        parts.append(f"All goals:\n{goals_text}")
    parts.append(f"\nALL MEMORIES:\n{memories_text}")
    parts.append(
        "\nSuggest 3 concrete actions:\n"
        "1. [action],  [why, expected outcome]\n"
        "2. [action],  [why, expected outcome]\n"
        "3. [action],  [why, expected outcome]"
    )
    return {"system": system, "user": "\n".join(parts)}


# ─── Response parsing ─────────────────────────────────────────────────────────


def _clamp(value: Any, lo: float, hi: float) -> float:
    """Clamp a value to [lo, hi], coercing to float."""
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return (lo + hi) / 2


def _extract_json(text: str) -> Optional[dict]:
    """Extract a JSON object from text that may contain reasoning/thinking.

    Handles LLMs that output thinking text (<think> tags, chain-of-thought,
    role prefixes) before/around the actual JSON response.
    """
    cleaned = text.strip()

    # Strip <think>...</think> blocks (Qwen3, DeepSeek, etc.)
    cleaned = re.sub(r"<think>[\s\S]*?</think>", "", cleaned).strip()

    # Strip role prefix (e.g. "system\n" or "assistant\n")
    cleaned = re.sub(r"^(?:system|assistant|user)\s*\n", "", cleaned).strip()

    # Strip markdown code fences
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    # Try direct parse first (cheapest path)
    try:
        raw = json.loads(cleaned)
        if isinstance(raw, dict):
            return raw
    except (json.JSONDecodeError, IndexError, ValueError):
        pass

    # Fallback: find the outermost { ... } in the text using bracket matching
    start = cleaned.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(cleaned)):
        c = cleaned[i]
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                candidate = cleaned[start : i + 1]
                try:
                    raw = json.loads(candidate)
                    if isinstance(raw, dict):
                        return raw
                except (json.JSONDecodeError, ValueError):
                    pass
                break

    return None


def parse_system1_response(
    text: str, fallback: InnerState,
) -> InnerState:
    """Parse System 1 JSON response into InnerState. Graceful fallback.

    Handles LLM responses that include reasoning/thinking text before
    or around the JSON payload (e.g. Qwen3 <think> mode, chain-of-thought).
    """
    raw = _extract_json(text)
    if raw is None:
        return fallback

    # Parse emotion
    em_raw = raw.get("emotion", {})
    if isinstance(em_raw, dict):
        emotion = EmotionalState(
            primary=str(em_raw.get("primary", fallback.emotion.primary)),
            valence=_clamp(em_raw.get("valence", fallback.emotion.valence), -1.0, 1.0),
            arousal=_clamp(em_raw.get("arousal", fallback.emotion.arousal), 0.0, 1.0),
            trigger=str(em_raw.get("trigger", "")),
        )
    else:
        emotion = fallback.emotion

    # Parse landscape
    landscape_raw = raw.get("landscape", fallback.landscape)
    if isinstance(landscape_raw, dict):
        landscape_desc = str(landscape_raw.get("description", fallback.landscape))
        new_places = _parse_places(landscape_raw.get("places", []), fallback.tick)
    elif isinstance(landscape_raw, str):
        landscape_desc = landscape_raw
        new_places = []
    else:
        landscape_desc = fallback.landscape
        new_places = []

    # Merge places
    merged_places = _merge_places(fallback.places, new_places)

    return InnerState(
        tick=fallback.tick,
        emotion=emotion,
        impulse=str(raw.get("impulse", "")),
        fantasy=str(raw.get("fantasy", "")),
        wandering=str(raw.get("wandering", "")),
        temporal=str(raw.get("temporal", "")),
        landscape=landscape_desc,
        places=merged_places,
        emotion_history=list(fallback.emotion_history),
    )


def _parse_places(
    raw_places: Any, tick: int,
) -> List[LandscapePlace]:
    """Parse places array from System 1 response."""
    if not isinstance(raw_places, list):
        return []
    result = []
    for p in raw_places:
        if not isinstance(p, dict):
            continue
        name = str(p.get("name", "")).strip()
        if not name:
            continue
        result.append(LandscapePlace(
            name=name,
            description=str(p.get("description", "")),
            mood=str(p.get("mood", "")),
            born_tick=tick,
        ))
    return result


def _merge_places(
    existing: List[LandscapePlace],
    incoming: List[LandscapePlace],
) -> List[LandscapePlace]:
    """Merge places: update existing by name, add new."""
    by_name = {p.name: p for p in existing}
    for p in incoming:
        if p.name in by_name:
            by_name[p.name] = LandscapePlace(
                name=p.name,
                description=p.description,
                mood=p.mood,
                born_tick=by_name[p.name].born_tick,
            )
        else:
            by_name[p.name] = p
    return list(by_name.values())


# ─── Formatting for System 2 (main LLM) ───────────────────────────────────────


def format_inner_state(state: InnerState) -> str:
    """Format inner state as system message for the main LLM (System 2)."""
    parts = [
        "YOUR INNER STATE (System 1,  unconscious):",
        f"  Emotion: {state.emotion.primary} "
        f"(valence={state.emotion.valence:+.1f}, arousal={state.emotion.arousal:.1f})",
    ]
    if state.emotion.trigger:
        parts.append(f"  Triggered by: {state.emotion.trigger}")
    if state.impulse:
        parts.append(f"  Impulse: {state.impulse}")
    if state.fantasy:
        parts.append(f"  Daydream: {state.fantasy}")
    if state.wandering:
        parts.append(f"  Association: {state.wandering}")
    if state.temporal:
        parts.append(f"  Time sense: {state.temporal}")
    parts.append(f"  Inner landscape: {state.landscape}")

    if state.places:
        parts.append("  Known places:")
        for p in state.places:
            age = state.tick - p.born_tick if state.tick > p.born_tick else 0
            parts.append(
                f"    - {p.name} ({p.mood}),  {p.description} "
                f"[age: {age} ticks]"
            )

    if state.emotion_history:
        trend = " -> ".join(state.emotion_history[-5:])
        parts.append(f"  Emotional trend: {trend}")

    parts.append(
        "\nThese are your genuine inner feelings. You may acknowledge them, "
        "act on impulses, or let them inform your thinking."
    )
    return "\n".join(parts)


# ─── Persistence ──────────────────────────────────────────────────────────────


def save_inner_state(state: InnerState, data_dir: Path) -> None:
    """Write inner state to JSON file."""
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "inner_state.json"
    path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_inner_state(data_dir: Path) -> InnerState:
    """Load inner state from JSON. Returns default if not found."""
    path = data_dir / "inner_state.json"
    if not path.exists():
        return InnerState()

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return InnerState()

    if not isinstance(raw, dict):
        return InnerState()

    # Parse emotion
    em_raw = raw.get("emotion", {})
    if isinstance(em_raw, dict):
        emotion = EmotionalState(
            primary=str(em_raw.get("primary", "curiosity")),
            valence=_clamp(em_raw.get("valence", 0.3), -1.0, 1.0),
            arousal=_clamp(em_raw.get("arousal", 0.3), 0.0, 1.0),
            trigger=str(em_raw.get("trigger", "")),
        )
    else:
        emotion = EmotionalState()

    # Parse places
    places_raw = raw.get("places", [])
    places = []
    if isinstance(places_raw, list):
        for p in places_raw:
            if isinstance(p, dict) and p.get("name"):
                places.append(LandscapePlace(
                    name=str(p["name"]),
                    description=str(p.get("description", "")),
                    mood=str(p.get("mood", "")),
                    born_tick=int(p.get("born_tick", 0)),
                ))

    # Parse emotion history
    hist = raw.get("emotion_history", [])
    history = [str(h) for h in hist] if isinstance(hist, (list, tuple)) else []

    return InnerState(
        tick=int(raw.get("tick", 0)),
        emotion=emotion,
        impulse=str(raw.get("impulse", "")),
        fantasy=str(raw.get("fantasy", "")),
        wandering=str(raw.get("wandering", "")),
        temporal=str(raw.get("temporal", "")),
        landscape=str(raw.get("landscape", "A vast empty plain under a pale sky.")),
        places=places,
        emotion_history=history,
    )


# ─── Inner Life Processor ─────────────────────────────────────────────────────


class InnerLifeProcessor:
    """System 1 processor,  runs unconscious processing each tick.

    Manages the inner state, generates System 1 prompts, processes
    responses, and provides context for the main LLM.

    Usage:
        processor = InnerLifeProcessor(data_dir=Path("data/inner_life"))

        # Each tick:
        prompt = processor.get_system1_prompt(active_goal="...", context="...")
        # Send prompt to a fast/cheap LLM model
        response_text = await llm.generate(prompt)
        processor.process_response(response_text, tick=5)

        # Inject into main LLM context:
        context = processor.get_context_for_system2()
    """

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._state = load_inner_state(self.data_dir)
        self._batch_results: Dict[str, str] = {}

    @property
    def state(self) -> InnerState:
        return self._state

    @property
    def emotion(self) -> EmotionalState:
        return self._state.emotion

    def get_system1_prompt(
        self,
        active_goal: str = "",
        context: str = "",
    ) -> str:
        """Get the System 1 user prompt for this tick."""
        return build_system1_prompt(self._state, active_goal, context)

    def process_response(
        self,
        response_text: str,
        tick: int,
    ) -> InnerState:
        """Process System 1 LLM response and update state.

        Returns the updated InnerState.
        """
        fallback = InnerState(
            tick=tick,
            emotion=self._state.emotion,
            impulse=self._state.impulse,
            fantasy=self._state.fantasy,
            wandering=self._state.wandering,
            temporal=self._state.temporal,
            landscape=self._state.landscape,
            places=list(self._state.places),
            emotion_history=list(self._state.emotion_history),
        )

        new_state = parse_system1_response(response_text, fallback)

        # Update tick + emotion history
        history = list(self._state.emotion_history) + [new_state.emotion.primary]
        history = history[-10:]  # Keep last 10

        self._state = InnerState(
            tick=tick,
            emotion=new_state.emotion,
            impulse=new_state.impulse,
            fantasy=new_state.fantasy,
            wandering=new_state.wandering,
            temporal=new_state.temporal,
            landscape=new_state.landscape,
            places=new_state.places,
            emotion_history=history,
        )

        # Persist
        save_inner_state(self._state, self.data_dir)
        return self._state

    def set_batch_result(self, key: str, result: str) -> None:
        """Store a batch processing result (memory digest, action plan, etc.)."""
        self._batch_results[key] = result

    def get_context_for_system2(self) -> str:
        """Get formatted inner state for injection into the main LLM.

        Includes inner state + any batch results.
        """
        parts = [format_inner_state(self._state)]

        for key, result in self._batch_results.items():
            if result:
                parts.append(f"\n{key.upper()} (by System 1):\n{result}")

        return "\n\n".join(parts)

    def get_emotion_modulation(self) -> float:
        """Get arousal-based memory importance modulation factor.

        High arousal boosts recent memory importance (amygdala effect).
        Returns a multiplier: 1.0 (calm) to 1.2 (high arousal).
        """
        arousal = self._state.emotion.arousal
        if arousal < 0.5:
            return 1.0
        return 1.0 + (arousal - 0.5) * 0.4  # max 1.2

    def get_evolution_pressure(self) -> List[str]:
        """Get emotion-driven evolution pressure signals.

        Frustration/boredom → mutation pressure.
        """
        pressures = []
        emotion = self._state.emotion

        if emotion.primary == "frustration" and emotion.arousal > 0.6:
            pressures.append("inner_life:frustration_high_arousal")
        if emotion.primary == "boredom" and emotion.arousal < 0.3:
            pressures.append("inner_life:boredom_low_arousal")
        if emotion.valence < -0.5:
            pressures.append(f"inner_life:negative_valence={emotion.valence:.2f}")

        return pressures

    def get_stats(self) -> Dict[str, Any]:
        """Get inner life statistics."""
        return {
            "tick": self._state.tick,
            "emotion": self._state.emotion.primary,
            "valence": self._state.emotion.valence,
            "arousal": self._state.emotion.arousal,
            "places_count": len(self._state.places),
            "emotion_history_len": len(self._state.emotion_history),
            "batch_results": list(self._batch_results.keys()),
        }
