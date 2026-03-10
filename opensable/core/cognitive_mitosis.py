"""
Cognitive Mitosis,  WORLD FIRST
================================
The agent can split into multiple independent cognitive threads
that DIVERGE, evolve separately with different strategies,
and then MERGE back with intelligent conflict resolution.

No AI agent splits its own cognition. This one does.
Like cellular mitosis but for thought.
"""

import json, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class CognitiveThread:
    """An independent cognitive thread."""
    thread_id: str = ""
    parent_id: str = ""           # the thread it split from
    strategy: str = ""
    hypothesis: str = ""
    findings: list = field(default_factory=list)
    confidence: float = 0.5
    status: str = "active"        # active, completed, merged, discarded
    created_at: float = 0.0
    completed_at: float = 0.0


@dataclass
class MergeEvent:
    """Record of merging threads back together."""
    merge_id: str = ""
    thread_ids: list = field(default_factory=list)
    conflicts: list = field(default_factory=list)
    resolution: str = ""
    final_conclusion: str = ""
    timestamp: float = 0.0


class CognitiveMitosis:
    """
    Splits cognition into parallel threads that diverge and merge.
    Each thread explores a different hypothesis or strategy independently.
    Merger includes intelligent conflict resolution.
    """

    def __init__(self, data_dir: str, max_threads: int = 20, max_sessions: int = 200):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self._dir / "cognitive_mitosis_state.json"
        self.threads: dict[str, CognitiveThread] = {}
        self.merges: list[MergeEvent] = []
        self.active_splits: int = 0
        self._max_threads = max_threads
        self._max_sessions = max_sessions
        self._load_state()

    def split(self, problem: str, strategies: list[str]) -> list[str]:
        """
        Split cognition into N parallel threads, each with a different strategy.
        Returns list of thread IDs.
        """
        parent_id = str(uuid.uuid4())[:8]
        thread_ids = []

        for strategy in strategies[:self._max_threads]:
            tid = str(uuid.uuid4())[:8]
            thread = CognitiveThread(
                thread_id=tid,
                parent_id=parent_id,
                strategy=strategy,
                hypothesis=f"Approach '{problem[:50]}' via {strategy}",
                status="active",
                created_at=time.time(),
            )
            self.threads[tid] = thread
            thread_ids.append(tid)

        self.active_splits += 1
        self._save_state()
        return thread_ids

    async def evolve_thread(self, thread_id: str, llm=None, context: str = "") -> dict:
        """Evolve a specific thread independently."""
        if thread_id not in self.threads:
            return {"error": "thread_not_found"}

        thread = self.threads[thread_id]
        if thread.status != "active":
            return {"error": "thread_not_active"}

        if llm:
            prompt = (
                f"You are cognitive thread '{thread.thread_id}' exploring strategy: "
                f"'{thread.strategy}'\n\n"
                f"Hypothesis: {thread.hypothesis}\n"
                f"Previous findings: {json.dumps(thread.findings[-3:])}\n"
                f"Additional context: {context[:300]}\n\n"
                f"Explore this strategy further. What do you discover?\n"
                f"Return JSON: {{\"finding\": \"...\", \"confidence\": 0.0-1.0, "
                f"\"should_continue\": true/false}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=300)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    thread.findings.append({
                        "finding": result.get("finding", ""),
                        "confidence": result.get("confidence", 0.5),
                        "step": len(thread.findings) + 1,
                    })
                    thread.confidence = result.get("confidence", thread.confidence)
                    if not result.get("should_continue", True):
                        thread.status = "completed"
                        thread.completed_at = time.time()
                    if len(thread.findings) > 20:
                        thread.findings = thread.findings[-20:]
                    self._save_state()
                    return result
            except Exception:
                pass

        # Heuristic evolution
        thread.findings.append({
            "finding": f"Explored {thread.strategy},  step {len(thread.findings)+1}",
            "confidence": thread.confidence,
            "step": len(thread.findings) + 1,
        })
        self._save_state()
        return {"finding": thread.findings[-1]["finding"], "confidence": thread.confidence}

    async def merge(self, thread_ids: list[str], llm=None) -> dict:
        """Merge multiple threads back together with conflict resolution."""
        threads_to_merge = []
        for tid in thread_ids:
            if tid in self.threads:
                threads_to_merge.append(self.threads[tid])

        if len(threads_to_merge) < 2:
            return {"error": "need_at_least_2_threads"}

        if llm:
            thread_summaries = []
            for t in threads_to_merge:
                thread_summaries.append({
                    "strategy": t.strategy,
                    "confidence": t.confidence,
                    "findings": [f.get("finding", "") for f in t.findings[-3:]],
                })
            prompt = (
                f"COGNITIVE MERGE,  combine {len(threads_to_merge)} divergent "
                f"thought threads:\n\n"
                f"Threads: {json.dumps(thread_summaries)}\n\n"
                f"1. Identify CONFLICTS between threads\n"
                f"2. Resolve each conflict\n"
                f"3. Synthesize a FINAL CONCLUSION\n\n"
                f"Return JSON: {{\"conflicts\": [\"...\"], "
                f"\"resolution\": \"...\", \"conclusion\": \"...\", "
                f"\"winning_strategy\": \"...\"}}"
            )
            try:
                raw = await llm.chat_raw(prompt, max_tokens=500)
                import re
                m = re.search(r'\{.*\}', raw, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    merge_event = MergeEvent(
                        merge_id=str(uuid.uuid4())[:8],
                        thread_ids=thread_ids,
                        conflicts=result.get("conflicts", []),
                        resolution=result.get("resolution", ""),
                        final_conclusion=result.get("conclusion", ""),
                        timestamp=time.time(),
                    )
                    self.merges.append(merge_event)
                    for t in threads_to_merge:
                        t.status = "merged"
                    self._save_state()
                    return {
                        "merge_id": merge_event.merge_id,
                        "conflicts": merge_event.conflicts,
                        "resolution": merge_event.resolution,
                        "conclusion": merge_event.final_conclusion,
                    }
            except Exception:
                pass

        # Heuristic merge: highest confidence wins
        winner = max(threads_to_merge, key=lambda t: t.confidence)
        merge_event = MergeEvent(
            merge_id=str(uuid.uuid4())[:8],
            thread_ids=thread_ids,
            conflicts=["confidence_based_resolution"],
            resolution=f"Thread '{winner.strategy}' had highest confidence",
            final_conclusion=winner.findings[-1]["finding"] if winner.findings else "",
            timestamp=time.time(),
        )
        self.merges.append(merge_event)
        for t in threads_to_merge:
            t.status = "merged"
        if len(self.merges) > self._max_sessions:
            self.merges = self.merges[-self._max_sessions:]
        self._save_state()
        return {
            "merge_id": merge_event.merge_id,
            "resolution": merge_event.resolution,
            "conclusion": merge_event.final_conclusion,
        }

    def get_active_threads(self) -> list:
        return [
            {"id": t.thread_id, "strategy": t.strategy,
             "confidence": round(t.confidence, 2), "steps": len(t.findings)}
            for t in self.threads.values() if t.status == "active"
        ]

    def get_stats(self) -> dict:
        status_counts = {}
        for t in self.threads.values():
            status_counts[t.status] = status_counts.get(t.status, 0) + 1
        return {
            "total_threads": len(self.threads),
            "active_threads": status_counts.get("active", 0),
            "merged_threads": status_counts.get("merged", 0),
            "total_merges": len(self.merges),
            "active_splits": self.active_splits,
            "active_thread_list": self.get_active_threads()[:5],
            "recent_merges": [
                {"conflicts": len(m.conflicts), "conclusion": m.final_conclusion[:80]}
                for m in self.merges[-3:]
            ],
        }

    def _save_state(self):
        # Only keep last N threads
        if len(self.threads) > self._max_threads * 10:
            active = {k: v for k, v in self.threads.items() if v.status == "active"}
            recent = dict(sorted(self.threads.items(),
                                key=lambda x: x[1].created_at,
                                reverse=True)[:self._max_threads * 5])
            self.threads = {**recent, **active}
        data = {
            "threads": {k: asdict(v) for k, v in self.threads.items()},
            "merges": [asdict(m) for m in self.merges[-self._max_sessions:]],
            "active_splits": self.active_splits,
        }
        self._state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self):
        if self._state_file.exists():
            try:
                data = json.loads(self._state_file.read_text())
                for k, v in data.get("threads", {}).items():
                    self.threads[k] = CognitiveThread(**v)
                for m in data.get("merges", []):
                    self.merges.append(MergeEvent(**m))
                self.active_splits = data.get("active_splits", 0)
            except Exception:
                pass
