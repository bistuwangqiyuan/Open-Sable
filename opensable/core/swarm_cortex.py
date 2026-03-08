"""
Swarm Cortex — internal parallel mini-agent exploration.

WORLD FIRST: The agent can internally spawn multiple "thought-agents"
that explore different solution paths simultaneously. They compete,
cooperate, and merge findings — a swarm intelligence inside a single agent.

Persistence: ``swarm_cortex_state.json`` in *data_dir*.
"""

from __future__ import annotations

import json, logging, time, uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ThoughtAgent:
    id: str = ""
    hypothesis: str = ""
    approach: str = ""
    findings: str = ""
    confidence: float = 0.5
    status: str = "exploring"  # exploring, concluded, merged, discarded
    created: float = 0.0
    completed: float = 0.0


@dataclass
class SwarmSession:
    id: str = ""
    problem: str = ""
    agents: List[ThoughtAgent] = field(default_factory=list)
    consensus: str = ""
    winner_id: str = ""
    created: float = 0.0
    completed: float = 0.0


class SwarmCortex:
    """Internal mini-agent swarm for parallel exploration."""

    def __init__(self, data_dir: Path, max_agents_per_swarm: int = 5,
                 max_sessions: int = 100):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.max_agents_per_swarm = max_agents_per_swarm
        self.max_sessions = max_sessions

        self.sessions: List[SwarmSession] = []
        self.total_explorations: int = 0
        self.consensus_reached: int = 0

        self._load_state()

    async def swarm_explore(self, llm, problem: str,
                            num_agents: int = 3) -> Dict[str, Any]:
        """Launch a swarm of thought-agents to explore a problem."""
        num_agents = min(num_agents, self.max_agents_per_swarm)
        session = SwarmSession(
            id=uuid.uuid4().hex[:12],
            problem=problem[:300],
            created=time.time(),
        )

        # Phase 1: Diverge — each agent takes a different approach
        approaches_prompt = (
            f"Problem: {problem}\n\n"
            f"Generate {num_agents} COMPLETELY DIFFERENT approaches to solve this. "
            f"Each should be a distinct hypothesis with a unique methodology.\n"
            f"Return JSON: [{{\"hypothesis\": \"...\", \"approach\": \"...\"}}]"
        )
        try:
            resp = await llm.chat_raw(approaches_prompt, max_tokens=600)
            import re
            m = re.search(r'\[.*\]', resp, re.DOTALL)
            if m:
                approaches = json.loads(m.group())
            else:
                approaches = [{"hypothesis": f"Approach {i+1}", "approach": "General analysis"}
                              for i in range(num_agents)]
        except Exception:
            approaches = [{"hypothesis": f"Approach {i+1}", "approach": "General analysis"}
                          for i in range(num_agents)]

        # Phase 2: Explore — each agent investigates their approach
        for i, approach in enumerate(approaches[:num_agents]):
            agent = ThoughtAgent(
                id=uuid.uuid4().hex[:8],
                hypothesis=approach.get("hypothesis", "")[:200],
                approach=approach.get("approach", "")[:200],
                created=time.time(),
            )

            explore_prompt = (
                f"You are Thought-Agent #{i+1} exploring this problem:\n"
                f"Problem: {problem}\n"
                f"Your approach: {agent.approach}\n\n"
                f"Investigate deeply. What do you find? Rate your confidence 0-1.\n"
                f"Return JSON: {{\"findings\": \"...\", \"confidence\": 0.X}}"
            )
            try:
                resp = await llm.chat_raw(explore_prompt, max_tokens=300)
                m = re.search(r'\{.*\}', resp, re.DOTALL)
                if m:
                    result = json.loads(m.group())
                    agent.findings = result.get("findings", "")[:300]
                    agent.confidence = float(result.get("confidence", 0.5))
                agent.status = "concluded"
            except Exception:
                agent.findings = "Exploration inconclusive"
                agent.confidence = 0.3
                agent.status = "concluded"

            agent.completed = time.time()
            session.agents.append(agent)
            self.total_explorations += 1

        # Phase 3: Converge — merge findings and reach consensus
        findings_text = "\n".join(
            f"Agent #{i+1} (conf: {a.confidence:.1f}): {a.findings}"
            for i, a in enumerate(session.agents)
        )
        consensus_prompt = (
            f"Problem: {problem}\n\n"
            f"Multiple thought-agents explored different approaches:\n"
            f"{findings_text}\n\n"
            f"Synthesize the BEST conclusion by merging insights from all agents. "
            f"Which agent was closest to the truth? "
            f"Return JSON: {{\"consensus\": \"...\", \"winner\": N}}"
        )
        try:
            resp = await llm.chat_raw(consensus_prompt, max_tokens=400)
            m = re.search(r'\{.*\}', resp, re.DOTALL)
            if m:
                result = json.loads(m.group())
                session.consensus = result.get("consensus", "")[:400]
                winner_idx = int(result.get("winner", 1)) - 1
                if 0 <= winner_idx < len(session.agents):
                    session.winner_id = session.agents[winner_idx].id
                    session.agents[winner_idx].status = "merged"
                self.consensus_reached += 1
        except Exception:
            best = max(session.agents, key=lambda a: a.confidence)
            session.consensus = best.findings
            session.winner_id = best.id

        session.completed = time.time()
        self.sessions.append(session)
        if len(self.sessions) > self.max_sessions:
            self.sessions = self.sessions[-self.max_sessions:]

        self._save_state()

        return {
            "session_id": session.id,
            "agents_deployed": len(session.agents),
            "consensus": session.consensus,
            "individual_findings": [
                {"hypothesis": a.hypothesis, "confidence": a.confidence,
                 "findings": a.findings[:100]}
                for a in session.agents
            ],
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_sessions": len(self.sessions),
            "total_explorations": self.total_explorations,
            "consensus_reached": self.consensus_reached,
            "avg_agents_per_session": round(
                sum(len(s.agents) for s in self.sessions) / max(1, len(self.sessions)), 1),
            "recent_sessions": [
                {"problem": s.problem[:60], "agents": len(s.agents),
                 "consensus": s.consensus[:80] if s.consensus else "pending"}
                for s in self.sessions[-3:]
            ],
        }

    def _save_state(self):
        try:
            state = {
                "sessions": [
                    {**asdict(s), "agents": [asdict(a) for a in s.agents]}
                    for s in self.sessions[-50:]
                ],
                "total_explorations": self.total_explorations,
                "consensus_reached": self.consensus_reached,
            }
            (self.data_dir / "swarm_cortex_state.json").write_text(
                json.dumps(state, indent=2, default=str))
        except Exception as e:
            logger.debug(f"Swarm cortex save: {e}")

    def _load_state(self):
        try:
            fp = self.data_dir / "swarm_cortex_state.json"
            if fp.exists():
                data = json.loads(fp.read_text())
                self.total_explorations = data.get("total_explorations", 0)
                self.consensus_reached = data.get("consensus_reached", 0)
                for sd in data.get("sessions", []):
                    agents = []
                    for ad in sd.get("agents", []):
                        agents.append(ThoughtAgent(
                            **{f: ad[f] for f in ThoughtAgent.__dataclass_fields__ if f in ad}))
                    s = SwarmSession(
                        id=sd.get("id", ""),
                        problem=sd.get("problem", ""),
                        consensus=sd.get("consensus", ""),
                        winner_id=sd.get("winner_id", ""),
                        created=sd.get("created", 0),
                        completed=sd.get("completed", 0),
                        agents=agents,
                    )
                    self.sessions.append(s)
        except Exception as e:
            logger.debug(f"Swarm cortex load: {e}")
