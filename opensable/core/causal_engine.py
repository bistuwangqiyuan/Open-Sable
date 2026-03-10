"""
Causal Reasoning Engine,  understanding *why*, not just *what*.

Builds a causal graph from observed task outcomes, enabling:
  - Root cause analysis for failures
  - Counterfactual reasoning ("what if I had done X?")
  - Causal attribution (which actions causally led to success/failure?)

The engine doesn't try full Bayesian inference,  it uses LLM-assisted
causal extraction and a simple weighted directed graph to track
cause → effect relationships.

Persistence: ``causal_engine_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CAUSAL_SYSTEM = """You are a causal reasoning engine for an autonomous AI agent.
Given a set of recent task outcomes, extract cause-effect relationships.

Output ONLY valid JSON,  an array of objects:
[
  {
    "cause": "short description of the cause",
    "effect": "short description of the effect",
    "strength": 0.1 to 1.0,
    "type": "success_factor|failure_factor|neutral"
  }
]

Rules:
- Each cause/effect should be 5-15 words
- Strength 1.0 = certain causal link, 0.1 = weak correlation
- type: "success_factor" if the cause leads to good outcomes, "failure_factor" if bad, "neutral" otherwise
- Extract 3-8 relationships per batch
- Focus on actionable causes (things the agent can control)
- If no clear causal links, return []"""

_COUNTERFACTUAL_SYSTEM = """You are a counterfactual reasoning engine for an autonomous AI agent.
Given:
1. What actually happened (the factual outcome)
2. A counterfactual question ("what if X had been different?")
3. Known causal relationships

Reason about what would have likely happened differently.
Output a JSON object:
{
  "counterfactual_outcome": "description of likely alternative outcome",
  "confidence": 0.0 to 1.0,
  "reasoning": "brief chain of reasoning",
  "actionable_insight": "what the agent should do differently next time"
}"""


@dataclass
class CausalLink:
    """A directed cause → effect relationship."""

    cause: str
    effect: str
    strength: float  # 0-1
    link_type: str  # success_factor, failure_factor, neutral
    observations: int = 1
    first_seen: str = ""
    last_seen: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat()
        if not self.first_seen:
            self.first_seen = now
        if not self.last_seen:
            self.last_seen = now


@dataclass
class RootCauseAnalysis:
    """Result of root cause analysis on a failure."""

    failure_description: str
    root_causes: List[Dict[str, Any]]
    confidence: float
    tick: int
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class CausalEngine:
    """Builds and queries a causal graph from observed outcomes."""

    def __init__(
        self,
        data_dir: Path,
        extract_interval: int = 20,
        max_links: int = 500,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "causal_engine_state.json"

        self._extract_interval = extract_interval
        self._max_links = max_links

        self._links: Dict[str, CausalLink] = {}  # key = f"{cause}→{effect}"
        self._root_cause_analyses: List[RootCauseAnalysis] = []
        self._last_extract_tick: int = 0
        self._total_extractions: int = 0
        self._total_counterfactuals: int = 0

        self._load_state()

    @staticmethod
    def _link_key(cause: str, effect: str) -> str:
        return f"{cause.strip().lower()}→{effect.strip().lower()}"

    # ── Core methods ──────────────────────────────────────────────────────────

    async def extract_causes(
        self,
        llm: Any,
        outcomes: List[str],
        tick: int,
    ) -> int:
        """Extract causal relationships from recent outcomes using LLM.

        Returns number of new/updated links.
        """
        if tick - self._last_extract_tick < self._extract_interval:
            return 0
        if len(outcomes) < 3:
            return 0

        self._last_extract_tick = tick

        try:
            batch = "\n".join(f"- {o}" for o in outcomes[-30:])
            messages = [
                {"role": "system", "content": _CAUSAL_SYSTEM},
                {"role": "user", "content": f"Recent task outcomes:\n{batch}"},
            ]
            result = await llm.invoke_with_tools(messages, [])
            text = result.get("text", "") if isinstance(result, dict) else str(result)

            # Parse JSON from response
            import re
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if m:
                    text = m.group(1).strip()

            start = text.find("[")
            end = text.rfind("]")
            if start < 0 or end < 0:
                return 0
            items = json.loads(text[start:end + 1])

            count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                cause = str(item.get("cause", "")).strip()
                effect = str(item.get("effect", "")).strip()
                if not cause or not effect:
                    continue

                strength = float(item.get("strength", 0.5))
                link_type = str(item.get("type", "neutral"))

                key = self._link_key(cause, effect)
                if key in self._links:
                    link = self._links[key]
                    link.observations += 1
                    link.strength = 0.7 * link.strength + 0.3 * strength
                    link.last_seen = datetime.now().isoformat()
                else:
                    self._links[key] = CausalLink(
                        cause=cause,
                        effect=effect,
                        strength=strength,
                        link_type=link_type,
                    )
                count += 1

            self._total_extractions += 1

            # Prune if too many links
            if len(self._links) > self._max_links:
                sorted_links = sorted(
                    self._links.items(),
                    key=lambda x: x[1].strength * x[1].observations,
                )
                to_remove = len(self._links) - self._max_links
                for key, _ in sorted_links[:to_remove]:
                    del self._links[key]

            self._save_state()
            return count

        except Exception as e:
            logger.debug(f"Causal extraction failed: {e}")
            return 0

    async def root_cause_analysis(
        self,
        failure: str,
        tick: int,
    ) -> Optional[RootCauseAnalysis]:
        """Trace back through causal graph to find root causes of a failure."""
        # Find links where the failure matches an effect
        failure_lower = failure.lower()
        contributing = []

        for link in self._links.values():
            if link.link_type == "failure_factor":
                # Check if effect relates to the failure
                if any(
                    word in link.effect.lower()
                    for word in failure_lower.split()
                    if len(word) > 3
                ):
                    contributing.append({
                        "cause": link.cause,
                        "strength": round(link.strength, 2),
                        "observations": link.observations,
                    })

        if not contributing:
            return None

        # Sort by strength * observations
        contributing.sort(key=lambda x: -x["strength"] * x["observations"])
        contributing = contributing[:5]

        confidence = min(1.0, contributing[0]["strength"] * 0.8 + 0.1 * len(contributing))

        analysis = RootCauseAnalysis(
            failure_description=failure[:200],
            root_causes=contributing,
            confidence=round(confidence, 2),
            tick=tick,
        )
        self._root_cause_analyses.append(analysis)

        # Keep only last 50
        if len(self._root_cause_analyses) > 50:
            self._root_cause_analyses = self._root_cause_analyses[-50:]

        self._save_state()
        return analysis

    async def counterfactual(
        self,
        llm: Any,
        factual: str,
        what_if: str,
    ) -> Optional[Dict[str, Any]]:
        """Ask 'what if X had been different?' using causal graph + LLM."""
        try:
            # Build causal context
            relevant = []
            for link in self._links.values():
                if link.strength > 0.3 and link.observations > 1:
                    relevant.append(f"- {link.cause} → {link.effect} "
                                    f"(strength={link.strength:.1f}, seen {link.observations}x)")

            context = "\n".join(relevant[-20:]) if relevant else "No established causal links yet."

            messages = [
                {"role": "system", "content": _COUNTERFACTUAL_SYSTEM},
                {"role": "user", "content": (
                    f"Known causal relationships:\n{context}\n\n"
                    f"What actually happened:\n{factual}\n\n"
                    f"Counterfactual question:\n{what_if}"
                )},
            ]
            result = await llm.invoke_with_tools(messages, [])
            text = result.get("text", "") if isinstance(result, dict) else str(result)

            import re
            text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
            if "```" in text:
                m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
                if m:
                    text = m.group(1).strip()

            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end + 1])
                self._total_counterfactuals += 1
                self._save_state()
                return parsed

        except Exception as e:
            logger.debug(f"Counterfactual reasoning failed: {e}")

        return None

    def get_strongest_causes(self, top_k: int = 10, link_type: Optional[str] = None) -> List[Dict]:
        """Return the strongest causal links."""
        links = list(self._links.values())
        if link_type:
            links = [l for l in links if l.link_type == link_type]
        links.sort(key=lambda l: -l.strength * l.observations)
        return [
            {
                "cause": l.cause,
                "effect": l.effect,
                "strength": round(l.strength, 2),
                "type": l.link_type,
                "observations": l.observations,
            }
            for l in links[:top_k]
        ]

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        success = [l for l in self._links.values() if l.link_type == "success_factor"]
        failure = [l for l in self._links.values() if l.link_type == "failure_factor"]

        return {
            "total_links": len(self._links),
            "success_factors": len(success),
            "failure_factors": len(failure),
            "total_extractions": self._total_extractions,
            "total_counterfactuals": self._total_counterfactuals,
            "total_root_cause_analyses": len(self._root_cause_analyses),
            "strongest_links": self.get_strongest_causes(top_k=8),
            "recent_root_causes": [
                {
                    "failure": rca.failure_description[:100],
                    "root_causes": rca.root_causes[:3],
                    "confidence": rca.confidence,
                }
                for rca in self._root_cause_analyses[-5:]
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "links": {k: asdict(v) for k, v in self._links.items()},
                "root_cause_analyses": [asdict(r) for r in self._root_cause_analyses[-50:]],
                "last_extract_tick": self._last_extract_tick,
                "total_extractions": self._total_extractions,
                "total_counterfactuals": self._total_counterfactuals,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Causal engine save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._last_extract_tick = data.get("last_extract_tick", 0)
                self._total_extractions = data.get("total_extractions", 0)
                self._total_counterfactuals = data.get("total_counterfactuals", 0)

                for key, ldata in data.get("links", {}).items():
                    self._links[key] = CausalLink(**ldata)

                for rdata in data.get("root_cause_analyses", []):
                    self._root_cause_analyses.append(RootCauseAnalysis(**rdata))
        except Exception as e:
            logger.debug(f"Causal engine load failed: {e}")
