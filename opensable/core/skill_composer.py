"""
Skill Composer — automatic compound skill creation.

Discovers which atomic skills are frequently chained together and
creates reusable compound skill recipes. For example, if the agent
often does "web_search → summarize → email", the composer creates
a compound skill "research_and_report" that chains them.

Key ideas:
  - **Sequence mining**: tracks skill execution sequences from completed tasks
  - **Frequency detection**: identifies frequently co-occurring skill chains
  - **Recipe creation**: LLM generates a named compound skill recipe
  - **Auto-execution**: compound skills can be invoked as single actions

Persistence: ``skill_composer_state.json`` in *data_dir*.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_COMPOSE_SYSTEM = """You are a skill composition engine for an autonomous AI agent.
Given frequently co-occurring tool/skill chains, create a reusable compound skill.

Output ONLY valid JSON:
{
  "name": "short_snake_case_name",
  "display_name": "Human readable name",
  "description": "What this compound skill does (1-2 sentences)",
  "steps": [
    {"skill": "skill_name", "description": "what this step does", "pass_output": true}
  ],
  "use_case": "When to use this compound skill"
}

Rules:
- name should be concise snake_case (e.g., research_and_report)
- steps should describe the data flow between skills
- pass_output: if true, output of this step is input to the next
- Max 6 steps per compound skill"""


@dataclass
class CompoundSkill:
    """A reusable compound skill composed from atomic skills."""

    skill_id: str
    name: str
    display_name: str
    description: str
    steps: List[Dict[str, Any]]
    use_case: str
    source_chain: List[str]
    frequency: int  # How often the chain was observed
    uses: int = 0
    successes: int = 0
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class SkillChainObservation:
    """An observed sequence of skills used together."""

    chain: Tuple[str, ...]
    count: int = 1
    last_seen_tick: int = 0


class SkillComposer:
    """Discovers and creates compound skills from skill execution patterns."""

    def __init__(
        self,
        data_dir: Path,
        min_frequency: int = 3,
        analyze_interval: int = 30,
        max_chain_length: int = 5,
    ):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._data_dir / "skill_composer_state.json"

        self._min_frequency = min_frequency
        self._analyze_interval = analyze_interval
        self._max_chain_length = max_chain_length

        self._chains: Dict[str, SkillChainObservation] = {}
        self._compounds: Dict[str, CompoundSkill] = {}
        self._execution_buffer: List[str] = []
        self._last_analyze_tick: int = 0
        self._total_compositions: int = 0

        self._load_state()

    # ── Record skill executions ───────────────────────────────────────────────

    def record_execution(self, skill_name: str, tick: int):
        """Record a skill execution to the buffer for sequence mining."""
        self._execution_buffer.append(skill_name)
        # Keep buffer bounded
        if len(self._execution_buffer) > 1000:
            self._execution_buffer = self._execution_buffer[-500:]

    def record_chain(self, skills: List[str], tick: int):
        """Record a known chain of skills used for a single task."""
        if len(skills) < 2:
            return
        chain = tuple(skills[:self._max_chain_length])
        key = "→".join(chain)
        if key in self._chains:
            self._chains[key].count += 1
            self._chains[key].last_seen_tick = tick
        else:
            self._chains[key] = SkillChainObservation(
                chain=chain, count=1, last_seen_tick=tick
            )

    # ── Analyze and compose ───────────────────────────────────────────────────

    async def analyze_and_compose(
        self,
        llm: Any,
        tick: int,
    ) -> List[CompoundSkill]:
        """Mine execution buffer for patterns and compose new compound skills."""
        if tick - self._last_analyze_tick < self._analyze_interval:
            return []

        self._last_analyze_tick = tick

        # Mine n-grams from execution buffer
        self._mine_ngrams()

        # Find frequent chains not yet composed
        frequent = []
        for key, obs in self._chains.items():
            if obs.count >= self._min_frequency:
                # Check if already composed
                chain_hash = hashlib.md5(key.encode()).hexdigest()[:8]
                if f"comp_{chain_hash}" not in self._compounds:
                    frequent.append(obs)

        if not frequent:
            return []

        # Sort by frequency and take top 3
        frequent.sort(key=lambda o: -o.count)
        new_compounds = []

        for obs in frequent[:3]:
            try:
                compound = await self._compose_skill(llm, obs)
                if compound:
                    self._compounds[compound.skill_id] = compound
                    new_compounds.append(compound)
                    self._total_compositions += 1
            except Exception as e:
                logger.debug(f"Skill composition failed for {obs.chain}: {e}")

        if new_compounds:
            self._save_state()

        return new_compounds

    def _mine_ngrams(self):
        """Extract n-grams from the execution buffer."""
        buf = self._execution_buffer
        for n in range(2, min(self._max_chain_length + 1, len(buf) + 1)):
            for i in range(len(buf) - n + 1):
                chain = tuple(buf[i:i + n])
                # Skip boring chains (same skill repeated)
                if len(set(chain)) < 2:
                    continue
                key = "→".join(chain)
                if key in self._chains:
                    self._chains[key].count += 1
                else:
                    self._chains[key] = SkillChainObservation(chain=chain)

    async def _compose_skill(
        self, llm: Any, obs: SkillChainObservation
    ) -> Optional[CompoundSkill]:
        """Use LLM to create a compound skill from a frequent chain."""
        chain_str = " → ".join(obs.chain)

        messages = [
            {"role": "system", "content": _COMPOSE_SYSTEM},
            {"role": "user", "content": (
                f"The following skill chain appears {obs.count} times:\n"
                f"Chain: {chain_str}\n\n"
                f"Create a reusable compound skill from this chain."
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
        if start < 0 or end < 0:
            return None

        data = json.loads(text[start:end + 1])

        chain_hash = hashlib.md5("→".join(obs.chain).encode()).hexdigest()[:8]
        skill_id = f"comp_{chain_hash}"

        return CompoundSkill(
            skill_id=skill_id,
            name=str(data.get("name", skill_id)),
            display_name=str(data.get("display_name", "Compound skill")),
            description=str(data.get("description", "")),
            steps=data.get("steps", []),
            use_case=str(data.get("use_case", "")),
            source_chain=list(obs.chain),
            frequency=obs.count,
        )

    # ── Execute compound skill ────────────────────────────────────────────────

    def get_compound(self, name: str) -> Optional[CompoundSkill]:
        """Lookup a compound skill by name or ID."""
        for c in self._compounds.values():
            if c.name == name or c.skill_id == name:
                return c
        return None

    def record_compound_result(self, skill_id: str, success: bool):
        """Record the result of executing a compound skill."""
        if skill_id in self._compounds:
            self._compounds[skill_id].uses += 1
            if success:
                self._compounds[skill_id].successes += 1
            self._save_state()

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        compounds = sorted(
            self._compounds.values(),
            key=lambda c: -c.uses,
        )

        frequent_chains = sorted(
            self._chains.values(),
            key=lambda o: -o.count,
        )[:8]

        return {
            "total_compositions": self._total_compositions,
            "total_compounds": len(self._compounds),
            "total_tracked_chains": len(self._chains),
            "buffer_size": len(self._execution_buffer),
            "compounds": [
                {
                    "id": c.skill_id,
                    "name": c.display_name,
                    "chain": c.source_chain,
                    "frequency": c.frequency,
                    "uses": c.uses,
                    "success_rate": round(c.successes / max(c.uses, 1), 2),
                }
                for c in compounds[:10]
            ],
            "frequent_chains": [
                {
                    "chain": list(o.chain),
                    "count": o.count,
                }
                for o in frequent_chains
            ],
        }

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "compounds": {k: asdict(v) for k, v in self._compounds.items()},
                "chains": {
                    k: {"chain": list(v.chain), "count": v.count, "last_seen_tick": v.last_seen_tick}
                    for k, v in sorted(
                        self._chains.items(), key=lambda x: -x[1].count
                    )[:200]
                },
                "execution_buffer": self._execution_buffer[-500:],
                "last_analyze_tick": self._last_analyze_tick,
                "total_compositions": self._total_compositions,
            }
            self._state_file.write_text(json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Skill composer save failed: {e}")

    def _load_state(self):
        try:
            if self._state_file.exists():
                data = json.loads(self._state_file.read_text())
                self._last_analyze_tick = data.get("last_analyze_tick", 0)
                self._total_compositions = data.get("total_compositions", 0)
                self._execution_buffer = data.get("execution_buffer", [])

                for kid, kdata in data.get("compounds", {}).items():
                    self._compounds[kid] = CompoundSkill(**kdata)

                for key, cdata in data.get("chains", {}).items():
                    self._chains[key] = SkillChainObservation(
                        chain=tuple(cdata["chain"]),
                        count=cdata["count"],
                        last_seen_tick=cdata.get("last_seen_tick", 0),
                    )
        except Exception as e:
            logger.debug(f"Skill composer load failed: {e}")
