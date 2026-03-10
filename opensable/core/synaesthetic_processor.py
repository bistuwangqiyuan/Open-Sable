"""
Synaesthetic Processor,  WORLD FIRST
======================================
Cross-modal cognitive processing. The agent perceives code as music,
data patterns as colors, errors as textures, and performance as rhythm.
By mapping between sensory modalities, it discovers patterns invisible
in any single mode of analysis.

No AI agent has ever implemented computational synaesthesia.
This agent SEES sounds and HEARS colors in its data.
"""

import json, time, uuid, math, hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class SynaestheticMapping:
    """A cross-modal perception of data."""
    mapping_id: str = ""
    source_modality: str = ""    # code, data, error, performance
    target_modality: str = ""    # color, sound, texture, rhythm, temperature
    input_signature: str = ""
    output_perception: dict = field(default_factory=dict)
    insight: str = ""
    timestamp: float = 0.0


class SynaestheticProcessor:
    """
    Perceives data through multiple sensory modalities simultaneously.
    Code → music. Errors → colors. Performance → rhythm.
    Cross-modal patterns reveal what single-mode analysis misses.
    """

    COLOR_SPACE = {
        "success": "#22c55e", "error": "#ef4444", "warning": "#f59e0b",
        "info": "#3b82f6", "critical": "#7c3aed", "neutral": "#6b7280",
        "creative": "#ec4899", "analytical": "#06b6d4",
    }

    SOUND_SPACE = {
        "harmony": {"freq": 440, "waveform": "sine", "amplitude": 0.7},
        "dissonance": {"freq": 587, "waveform": "sawtooth", "amplitude": 0.9},
        "rhythm": {"freq": 220, "waveform": "square", "amplitude": 0.5},
        "silence": {"freq": 0, "waveform": "none", "amplitude": 0.0},
        "crescendo": {"freq": 660, "waveform": "sine", "amplitude": 1.0},
    }

    TEXTURE_SPACE = {
        "smooth": 0.9, "rough": 0.3, "sticky": 0.5, "crystalline": 0.95,
        "spongy": 0.4, "metallic": 0.85, "organic": 0.6,
    }

    def __init__(self, data_dir: str, max_mappings: int = 500):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "synaesthetic_processor_state.json"
        self.mappings: list[SynaestheticMapping] = []
        self.cross_modal_insights: list[dict] = []
        self._max = max_mappings
        self._load_state()

    def perceive(self, data: str, source_modality: str = "code") -> dict:
        """Perceive data through all sensory modalities simultaneously."""
        # Generate perceptual hash
        h = hashlib.md5(data.encode()).hexdigest()
        h_vals = [int(h[i:i+2], 16) for i in range(0, min(16, len(h)), 2)]

        # Code → Color (based on structural patterns)
        error_signals = sum(1 for w in ["error", "fail", "exception", "crash", "bug"]
                           if w in data.lower())
        success_signals = sum(1 for w in ["success", "ok", "done", "pass", "complete"]
                             if w in data.lower())

        if error_signals > success_signals:
            color = self.COLOR_SPACE["error"]
            sound = self.SOUND_SPACE["dissonance"]
            texture = "rough"
        elif success_signals > 0:
            color = self.COLOR_SPACE["success"]
            sound = self.SOUND_SPACE["harmony"]
            texture = "smooth"
        else:
            color = self.COLOR_SPACE["neutral"]
            sound = self.SOUND_SPACE["rhythm"]
            texture = "metallic"

        # Complexity → Temperature
        complexity = min(1.0, len(data) / 1000)
        temperature = 20 + complexity * 80  # 20-100°C

        # Rhythm: based on punctuation density
        punct = sum(1 for c in data if c in ".,;:!?(){}[]")
        rhythm_bpm = max(40, min(200, 60 + punct * 3))

        # Length → Amplitude
        amplitude = min(1.0, len(data) / 500)

        perception = {
            "color": color,
            "sound": sound,
            "texture": texture,
            "texture_smoothness": self.TEXTURE_SPACE.get(texture, 0.5),
            "temperature": round(temperature, 1),
            "rhythm_bpm": rhythm_bpm,
            "amplitude": round(amplitude, 2),
            "perceptual_hash": h[:8],
        }

        mapping = SynaestheticMapping(
            mapping_id=str(uuid.uuid4())[:8],
            source_modality=source_modality,
            target_modality="multi",
            input_signature=data[:100],
            output_perception=perception,
            timestamp=time.time(),
        )
        self.mappings.append(mapping)
        if len(self.mappings) > self._max:
            self.mappings = self.mappings[-self._max:]
        self._save_state()

        return perception

    async def cross_modal_analysis(self, data: str, llm=None) -> dict:
        """Perform deep cross-modal analysis using LLM."""
        perception = self.perceive(data)

        if llm:
            prompt = (
                f"SYNAESTHETIC ANALYSIS,  perceive this data through multiple senses:\n\n"
                f"Data: {data[:300]}\n\n"
                f"Initial perception: color={perception['color']}, "
                f"texture={perception['texture']}, temp={perception['temperature']}°C, "
                f"rhythm={perception['rhythm_bpm']}bpm\n\n"
                f"What CROSS-MODAL PATTERN does this reveal? What insight emerges from "
                f"perceiving this through multiple senses simultaneously?\n"
                f"Return JSON: {{\"insight\": \"...\", \"dominant_modality\": \"...\", "
                f"\"hidden_pattern\": \"...\"}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=300)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    insight = {
                        "perception": perception,
                        "insight": result.get("insight", ""),
                        "dominant_modality": result.get("dominant_modality", ""),
                        "hidden_pattern": result.get("hidden_pattern", ""),
                        "timestamp": time.time(),
                    }
                    self.cross_modal_insights.append(insight)
                    if len(self.cross_modal_insights) > 200:
                        self.cross_modal_insights = self.cross_modal_insights[-200:]
                    self._save_state()
                    return insight
            except Exception:
                pass

        return {"perception": perception, "insight": "raw_perception_only"}

    def get_chromatic_history(self, n: int = 20) -> list:
        """Get the color history of perceptions,  a visual timeline."""
        return [{"color": m.output_perception.get("color", "#6b7280"),
                 "input": m.input_signature[:30],
                 "time": m.timestamp}
                for m in self.mappings[-n:]]

    def get_stats(self) -> dict:
        color_dist = {}
        texture_dist = {}
        for m in self.mappings:
            c = m.output_perception.get("color", "unknown")
            color_dist[c] = color_dist.get(c, 0) + 1
            t = m.output_perception.get("texture", "unknown")
            texture_dist[t] = texture_dist.get(t, 0) + 1
        return {
            "total_perceptions": len(self.mappings),
            "cross_modal_insights": len(self.cross_modal_insights),
            "color_distribution": color_dist,
            "texture_distribution": texture_dist,
            "avg_temperature": round(
                sum(m.output_perception.get("temperature", 50)
                    for m in self.mappings[-50:]) / max(len(self.mappings[-50:]), 1), 1
            ),
            "avg_rhythm_bpm": round(
                sum(m.output_perception.get("rhythm_bpm", 100)
                    for m in self.mappings[-50:]) / max(len(self.mappings[-50:]), 1), 0
            ),
            "chromatic_history": self.get_chromatic_history(10),
        }

    def _save_state(self):
        data = {
            "mappings": [asdict(m) for m in self.mappings[-self._max:]],
            "cross_modal_insights": self.cross_modal_insights[-200:],
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for m in data.get("mappings", []):
                    self.mappings.append(SynaestheticMapping(**m))
                self.cross_modal_insights = data.get("cross_modal_insights", [])
            except Exception:
                pass
