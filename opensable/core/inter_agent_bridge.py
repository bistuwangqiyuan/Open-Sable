"""
Inter-Agent Learning Bridge,  Knowledge sharing between Sable & Nexus Erebus.

Each agent runs its own profile with isolated data. This bridge:
  • Exports "learnings" (patterns, strategies, insights) to a shared vault
  • Imports relevant learnings from sibling agents
  • De-duplicates and scores by relevance before import
  • Tracks provenance,  every learning carries its origin agent + timestamp
  • Runs asynchronously on a configurable schedule (default: every 10 ticks)
  • Persists a shared vault on disk readable by any agent instance
"""

import json
import logging
import os
import time
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class Learning:
    """A single transferable piece of knowledge."""
    learning_id: str
    source_agent: str               # e.g. "sable", "nexus_erebus"
    category: str                    # strategy | pattern | insight | skill | error_recovery
    title: str
    content: str                     # The actual knowledge
    confidence: float = 0.7          # 0.0 – 1.0
    usefulness_score: float = 0.5    # Updated by consuming agent
    created_at: str = ""
    imported_by: List[str] = field(default_factory=list)  # agents that imported this
    tags: List[str] = field(default_factory=list)
    context: str = ""                # When/why this was learned


@dataclass
class ImportRecord:
    """Record of an imported learning."""
    learning_id: str
    source_agent: str
    imported_at: str
    applied: bool = False
    benefit_score: float = 0.0


# ── LLM Prompts ──────────────────────────────────────────────────────────────

_EXTRACT_LEARNINGS_PROMPT = """\
You are an autonomous AI agent's learning extraction engine.
Review the agent's recent activity and extract transferable learnings that
another sibling agent could benefit from.

Categories:
- strategy: Successful approaches to solving problems
- pattern: Recurring patterns in task execution or failures
- insight: Non-obvious observations about the environment or task space
- skill: New capabilities or tool usage patterns discovered
- error_recovery: How errors were detected and resolved

For each learning, output:
  {"category": "...", "title": "short title", "content": "detailed description",
   "confidence": 0.0-1.0, "tags": ["tag1", "tag2"]}

Output ONLY a valid JSON array. If nothing valuable, return [].
"""

_RELEVANCE_PROMPT = """\
You are evaluating whether learnings from a sibling AI agent are relevant
to the current agent's context. Rate each learning 0.0-1.0 for relevance.
Consider: Does this help with current goals? Is it already known? Is it actionable?

Input: a list of learnings and the current agent's context.
Output ONLY a JSON array of objects: [{"learning_id": "...", "relevance": 0.0-1.0}]
"""


class InterAgentBridge:
    """
    Shared learning vault between multiple agent profiles.

    The vault lives in a shared directory (default: <project_root>/data/shared_learnings/).
    Each agent reads/writes from the same vault but only imports what's relevant.
    """

    def __init__(
        self,
        profile: str,
        shared_dir: Optional[Path] = None,
        local_dir: Optional[Path] = None,
        sync_every_n_ticks: int = 10,
    ):
        self._profile = profile
        self._shared_dir = Path(shared_dir or Path("data") / "shared_learnings")
        self._local_dir = Path(local_dir or Path("data") / "inter_agent")
        self._shared_dir.mkdir(parents=True, exist_ok=True)
        self._local_dir.mkdir(parents=True, exist_ok=True)
        self._sync_every = sync_every_n_ticks

        # State
        self._exported: Dict[str, Learning] = {}
        self._imported: Dict[str, ImportRecord] = {}
        self._total_exported = 0
        self._total_imported = 0
        self._total_syncs = 0
        self._last_sync_tick = -1

        self._load_state()

    # ── Public API ────────────────────────────────────────────────────────────

    async def export_learnings(self, llm, recent_activity: str, tick: int = 0):
        """Extract learnings from recent activity and export to shared vault."""
        if not llm:
            return

        messages = [
            {"role": "system", "content": _EXTRACT_LEARNINGS_PROMPT},
            {"role": "user", "content": (
                f"Agent: {self._profile}\n"
                f"Tick: {tick}\n\n"
                f"Recent activity:\n{recent_activity[:3000]}"
            )},
        ]

        try:
            response = await llm.invoke_with_tools(messages, [])
            text = response.get("text", "") or ""
            learnings_data = self._parse_json_array(text)
            if not learnings_data:
                return

            exported = 0
            for ld in learnings_data:
                if not isinstance(ld, dict) or not ld.get("content"):
                    continue

                lid = self._make_learning_id(ld.get("content", ""))

                # Skip if already exported
                if lid in self._exported:
                    continue

                learning = Learning(
                    learning_id=lid,
                    source_agent=self._profile,
                    category=ld.get("category", "insight"),
                    title=ld.get("title", "Untitled")[:100],
                    content=ld.get("content", "")[:1000],
                    confidence=float(ld.get("confidence", 0.7)),
                    created_at=datetime.now().isoformat(),
                    tags=ld.get("tags", []),
                    context=f"tick={tick}",
                )

                self._exported[lid] = learning
                self._write_to_shared_vault(learning)
                exported += 1

            if exported:
                self._total_exported += exported
                self._save_state()
                logger.info(
                    f"🔗 InterAgentBridge [{self._profile}]: Exported {exported} learnings to vault"
                )

        except Exception as e:
            logger.warning(f"InterAgentBridge: Export failed: {e}")

    async def import_learnings(self, llm, current_context: str = "") -> List[Learning]:
        """Import relevant learnings from sibling agents."""
        vault = self._read_shared_vault()

        # Filter: only learnings from OTHER agents that we haven't imported yet
        candidates = [
            l for l in vault
            if l.source_agent != self._profile
            and l.learning_id not in self._imported
        ]

        if not candidates:
            return []

        # If we have LLM, score relevance; otherwise import all
        if llm and current_context and len(candidates) > 3:
            candidates = await self._filter_by_relevance(
                llm, candidates, current_context
            )

        imported = []
        for learning in candidates[:10]:  # Max 10 per sync
            record = ImportRecord(
                learning_id=learning.learning_id,
                source_agent=learning.source_agent,
                imported_at=datetime.now().isoformat(),
            )
            self._imported[learning.learning_id] = record

            # Mark in vault that we imported it
            learning.imported_by.append(self._profile)
            imported.append(learning)

        if imported:
            self._total_imported += len(imported)
            self._save_state()
            logger.info(
                f"🔗 InterAgentBridge [{self._profile}]: Imported {len(imported)} learnings "
                f"from {set(l.source_agent for l in imported)}"
            )

        return imported

    async def sync(self, llm, tick: int, recent_activity: str = "", current_context: str = ""):
        """Full sync cycle: export local learnings, import sibling learnings."""
        if tick - self._last_sync_tick < self._sync_every:
            return  # Not time yet

        self._last_sync_tick = tick
        self._total_syncs += 1

        # Export
        if recent_activity:
            await self.export_learnings(llm, recent_activity, tick)

        # Import
        imported = await self.import_learnings(llm, current_context)

        return imported

    def mark_applied(self, learning_id: str, benefit: float = 0.5):
        """Mark an imported learning as applied, with a benefit score."""
        record = self._imported.get(learning_id)
        if record:
            record.applied = True
            record.benefit_score = benefit
            self._save_state()

    def get_imported_learnings(self) -> List[Dict]:
        """Return all imported learnings for the current agent."""
        vault = {l.learning_id: l for l in self._read_shared_vault()}
        results = []
        for lid, record in self._imported.items():
            l = vault.get(lid)
            if l:
                results.append({
                    "learning_id": lid,
                    "source_agent": l.source_agent,
                    "category": l.category,
                    "title": l.title,
                    "content": l.content[:200],
                    "confidence": l.confidence,
                    "applied": record.applied,
                    "benefit_score": record.benefit_score,
                    "imported_at": record.imported_at,
                })
        return results

    def get_stats(self) -> Dict[str, Any]:
        vault = self._read_shared_vault()
        agents_in_vault = set(l.source_agent for l in vault)
        return {
            "profile": self._profile,
            "total_exported": self._total_exported,
            "total_imported": self._total_imported,
            "total_syncs": self._total_syncs,
            "vault_size": len(vault),
            "agents_in_vault": list(agents_in_vault),
            "pending_imports": len([
                l for l in vault
                if l.source_agent != self._profile
                and l.learning_id not in self._imported
            ]),
            "applied_count": sum(1 for r in self._imported.values() if r.applied),
            "avg_benefit": (
                sum(r.benefit_score for r in self._imported.values() if r.applied)
                / max(1, sum(1 for r in self._imported.values() if r.applied))
            ),
            "recent_exports": [
                {"id": l.learning_id, "title": l.title, "category": l.category}
                for l in list(self._exported.values())[-5:]
            ],
            "recent_imports": [
                {
                    "id": r.learning_id,
                    "source": r.source_agent,
                    "applied": r.applied,
                    "benefit": r.benefit_score,
                }
                for r in list(self._imported.values())[-5:]
            ],
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_learning_id(self, content: str) -> str:
        return hashlib.sha256(
            f"{self._profile}:{content[:200]}".encode()
        ).hexdigest()[:16]

    def _write_to_shared_vault(self, learning: Learning):
        """Append a learning to the shared JSONL vault."""
        vault_file = self._shared_dir / "vault.jsonl"
        try:
            with open(vault_file, "a") as f:
                f.write(json.dumps(asdict(learning), default=str) + "\n")
        except Exception as e:
            logger.debug(f"InterAgentBridge: Write to vault failed: {e}")

    def _read_shared_vault(self) -> List[Learning]:
        """Read all learnings from the shared vault."""
        vault_file = self._shared_dir / "vault.jsonl"
        if not vault_file.exists():
            return []
        learnings = []
        try:
            with open(vault_file) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                        learnings.append(Learning(
                            learning_id=d["learning_id"],
                            source_agent=d["source_agent"],
                            category=d.get("category", "insight"),
                            title=d.get("title", ""),
                            content=d.get("content", ""),
                            confidence=d.get("confidence", 0.5),
                            usefulness_score=d.get("usefulness_score", 0.5),
                            created_at=d.get("created_at", ""),
                            imported_by=d.get("imported_by", []),
                            tags=d.get("tags", []),
                            context=d.get("context", ""),
                        ))
                    except (json.JSONDecodeError, KeyError):
                        pass
        except Exception as e:
            logger.debug(f"InterAgentBridge: Read vault failed: {e}")
        return learnings

    async def _filter_by_relevance(
        self, llm, candidates: List[Learning], context: str
    ) -> List[Learning]:
        """Use LLM to score relevance of candidate learnings."""
        candidates_desc = "\n".join(
            f"- ID: {l.learning_id} | {l.category} | {l.title}: {l.content[:150]}"
            for l in candidates[:15]
        )

        messages = [
            {"role": "system", "content": _RELEVANCE_PROMPT},
            {"role": "user", "content": (
                f"Current agent context:\n{context[:1500]}\n\n"
                f"Candidate learnings:\n{candidates_desc}"
            )},
        ]

        try:
            response = await llm.invoke_with_tools(messages, [])
            text = response.get("text", "") or ""
            scores = self._parse_json_array(text)
            if not scores:
                return candidates[:5]

            # Build score map
            score_map = {}
            for s in scores:
                if isinstance(s, dict):
                    score_map[s.get("learning_id", "")] = float(s.get("relevance", 0.5))

            # Filter by relevance threshold (> 0.4)
            scored = []
            for l in candidates:
                rel = score_map.get(l.learning_id, 0.5)
                if rel > 0.4:
                    scored.append((rel, l))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [l for _, l in scored[:10]]

        except Exception as e:
            logger.debug(f"InterAgentBridge: Relevance scoring failed: {e}")
            return candidates[:5]

    def _parse_json_array(self, text: str) -> Optional[List[dict]]:
        import re
        match = re.search(r'\[[\s\S]*?\]', text)
        if match:
            try:
                data = json.loads(match.group())
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass
        return None

    # ── Persistence ───────────────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "profile": self._profile,
                "total_exported": self._total_exported,
                "total_imported": self._total_imported,
                "total_syncs": self._total_syncs,
                "last_sync_tick": self._last_sync_tick,
                "exported": {
                    k: asdict(v) for k, v in self._exported.items()
                },
                "imported": {
                    k: asdict(v) for k, v in self._imported.items()
                },
            }
            (self._local_dir / "bridge_state.json").write_text(
                json.dumps(state, indent=2, default=str)
            )
        except Exception as e:
            logger.debug(f"InterAgentBridge: Save state failed: {e}")

    def _load_state(self):
        sf = self._local_dir / "bridge_state.json"
        if not sf.exists():
            return
        try:
            state = json.loads(sf.read_text())
            self._total_exported = state.get("total_exported", 0)
            self._total_imported = state.get("total_imported", 0)
            self._total_syncs = state.get("total_syncs", 0)
            self._last_sync_tick = state.get("last_sync_tick", -1)

            for k, v in state.get("exported", {}).items():
                self._exported[k] = Learning(**{
                    f: v.get(f, d) for f, d in [
                        ("learning_id", k), ("source_agent", ""), ("category", ""),
                        ("title", ""), ("content", ""), ("confidence", 0.5),
                        ("usefulness_score", 0.5), ("created_at", ""),
                        ("imported_by", []), ("tags", []), ("context", ""),
                    ]
                })

            for k, v in state.get("imported", {}).items():
                self._imported[k] = ImportRecord(
                    learning_id=v.get("learning_id", k),
                    source_agent=v.get("source_agent", ""),
                    imported_at=v.get("imported_at", ""),
                    applied=v.get("applied", False),
                    benefit_score=v.get("benefit_score", 0.0),
                )

            logger.info(
                f"🔗 InterAgentBridge [{self._profile}]: Loaded state,  "
                f"{self._total_exported} exported, {self._total_imported} imported"
            )
        except Exception as e:
            logger.warning(f"InterAgentBridge: Load state failed: {e}")
