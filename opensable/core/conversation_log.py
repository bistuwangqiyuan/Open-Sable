"""
Conversation Persistence,  Cross-session conversation memory.

Saves raw conversation history (including tool calls) per session and
injects the last N sessions' conversation back into the context.

This gives the agent continuity across sessions,  it can remember what it
did 5, 10, or 25 conversations ago, including which tools it called and
what results it got.

Usage::

    from opensable.core.conversation_log import ConversationLogger

    logger = ConversationLogger("data/conversations")
    logger.save_conversation(run_id, user_id, messages, tick=5)
    history = logger.load_recent(user_id, last_n=10)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """One conversation turn,  user message + agent response + tools used."""

    ts: float
    run_id: str
    user_id: str
    tick: int = 0

    user_message: str = ""
    agent_response: str = ""
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)

    plan_summary: str = ""
    duration_ms: float = 0.0
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "tick": self.tick,
            "user_message": self.user_message,
            "agent_response": self.agent_response,
            "tool_calls": self.tool_calls,
            "tool_results": self.tool_results,
            "plan_summary": self.plan_summary,
            "duration_ms": self.duration_ms,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ConversationTurn":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_context_string(self, max_chars: int = 2000) -> str:
        """Format this turn as a context string for injection into prompts."""
        parts = []
        ts_str = datetime.fromtimestamp(self.ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
        parts.append(f"[{ts_str}]")

        if self.user_message:
            msg = self.user_message[:max_chars // 3]
            parts.append(f"User: {msg}")

        if self.tool_calls:
            tools = ", ".join(
                tc.get("name", "?") for tc in self.tool_calls[:5]
            )
            parts.append(f"Tools: {tools}")

        if self.agent_response:
            resp = self.agent_response[:max_chars // 3]
            parts.append(f"Agent: {resp}")

        return "\n".join(parts)


class ConversationLogger:
    """Persistent conversation logger with JSONL append-only storage.

    Stores one JSONL line per conversation turn.  Supports per-user
    history retrieval and context injection.
    """

    def __init__(
        self,
        directory: str | Path = "data/conversations",
        *,
        max_history: int = 25,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.max_history = max_history

    def _user_file(self, user_id: str) -> Path:
        """Get the conversation file for a user."""
        safe = user_id.replace("/", "_").replace("..", "_").replace(" ", "_")
        return self.directory / f"{safe}.jsonl"

    # ── Save ────────────────────────────────────────────────────────────

    def save_conversation(
        self,
        run_id: str,
        user_id: str,
        messages: List[Dict[str, Any]],
        *,
        tick: int = 0,
        model: str = "",
        duration_ms: float = 0.0,
        plan_summary: str = "",
    ) -> ConversationTurn:
        """Save a conversation from the agent's message history.

        Extracts user message, agent response, tool calls, and tool results
        from the raw message list (Ollama format).
        """
        user_message = ""
        agent_response = ""
        tool_calls: List[Dict[str, Any]] = []
        tool_results: List[Dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "user" and not user_message:
                user_message = content[:4000] if isinstance(content, str) else str(content)[:4000]
            elif role == "assistant":
                # Keep last assistant message as the response
                if isinstance(content, str):
                    agent_response = content[:4000]
            elif role == "tool":
                tool_results.append({
                    "tool": msg.get("name", ""),
                    "result": str(content)[:2000],
                })

            # Extract tool calls from assistant messages
            if role == "assistant" and isinstance(content, str):
                pass  # Tool calls come from tool_calls field
            tc = msg.get("tool_calls", [])
            if tc:
                for call in tc:
                    if isinstance(call, dict):
                        tool_calls.append({
                            "name": call.get("name", call.get("function", {}).get("name", "")),
                            "args": call.get("arguments", call.get("function", {}).get("arguments", {})),
                        })

        # Also check for final_response role (Open-Sable convention)
        for msg in reversed(messages):
            if msg.get("role") == "final_response":
                agent_response = str(msg.get("content", ""))[:4000]
                break

        turn = ConversationTurn(
            ts=time.time(),
            run_id=run_id,
            user_id=user_id,
            tick=tick,
            user_message=user_message,
            agent_response=agent_response,
            tool_calls=tool_calls,
            tool_results=tool_results,
            plan_summary=plan_summary,
            duration_ms=duration_ms,
            model=model,
        )

        # Append to user's file
        path = self._user_file(user_id)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(turn.to_dict(), ensure_ascii=False, default=str) + "\n")

        logger.debug(f"Saved conversation: {run_id} for user {user_id}")
        return turn

    # ── Load ────────────────────────────────────────────────────────────

    def load_recent(
        self,
        user_id: str,
        last_n: Optional[int] = None,
    ) -> List[ConversationTurn]:
        """Load the last N conversation turns for a user."""
        if last_n is None:
            last_n = self.max_history

        path = self._user_file(user_id)
        if not path.exists():
            return []

        turns: List[ConversationTurn] = []
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
            for line in lines[-last_n:]:
                if line.strip():
                    try:
                        turns.append(ConversationTurn.from_dict(json.loads(line)))
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load conversations for {user_id}: {e}")

        return turns

    def build_context_prompt(
        self,
        user_id: str,
        last_n: Optional[int] = None,
        max_chars: int = 8000,
    ) -> str:
        """Build a context string from recent conversations for prompt injection.

        Returns empty string if no history exists.
        """
        turns = self.load_recent(user_id, last_n)
        if not turns:
            return ""

        parts = [
            f"CONVERSATION HISTORY (last {len(turns)} interactions,  "
            "raw messages including tool calls):"
        ]
        total_chars = len(parts[0])

        for turn in turns:
            ctx = turn.to_context_string(max_chars=max_chars // len(turns))
            if total_chars + len(ctx) > max_chars:
                break
            parts.append(f"---\n{ctx}")
            total_chars += len(ctx) + 5

        return "\n".join(parts)

    # ── Cleanup ─────────────────────────────────────────────────────────

    def trim_history(
        self,
        user_id: str,
        keep_last: int = 100,
    ) -> int:
        """Trim a user's conversation file to the last N turns.

        Returns the number of turns removed.
        """
        path = self._user_file(user_id)
        if not path.exists():
            return 0

        lines = path.read_text(encoding="utf-8").splitlines()
        if len(lines) <= keep_last:
            return 0

        removed = len(lines) - keep_last
        kept = lines[-keep_last:]
        path.write_text("\n".join(kept) + "\n", encoding="utf-8")
        logger.info(f"Trimmed {removed} old conversations for {user_id}")
        return removed

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        """Get conversation stats for a user."""
        turns = self.load_recent(user_id, last_n=10000)
        if not turns:
            return {"user_id": user_id, "total_turns": 0}

        tool_usage: Dict[str, int] = {}
        for turn in turns:
            for tc in turn.tool_calls:
                name = tc.get("name", "unknown")
                tool_usage[name] = tool_usage.get(name, 0) + 1

        return {
            "user_id": user_id,
            "total_turns": len(turns),
            "first_interaction": turns[0].ts,
            "last_interaction": turns[-1].ts,
            "top_tools": sorted(tool_usage.items(), key=lambda x: x[1], reverse=True)[:10],
            "avg_tools_per_turn": round(
                sum(len(t.tool_calls) for t in turns) / len(turns), 1
            ) if turns else 0,
        }
