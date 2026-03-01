#!/usr/bin/env python3
"""
Pixel-Bridge — connect OpenSable agents to the Pixel Agents VS Code extension.

This script wraps a SableAgent in an interactive terminal loop and emits
Claude-compatible JSONL transcripts that pixel-agents can watch. Each tool
call is translated to the `tool_use` / `tool_result` record pair that the
extension's transcriptParser.ts understands, giving OpenSable agents their
own animated pixel-art character in the office.

Two modes:

  Standalone (default):
    Creates its own SableAgent from the SableCore config.
    Usage: python pixel-bridge.py --session-id <uuid>

  Gateway-attached (recommended when agent is already running):
    Connects to the running SableCore gateway over WebSocket.
    All monitor events and user messages flow through the gateway.
    Usage: python pixel-bridge.py --session-id <uuid> \
                                  --gateway-url ws://127.0.0.1:8789

Launched automatically by the Pixel Agents extension, or manually:
    cd /home/nexland/SableCore_
    python scripts/pixel-bridge.py --session-id test-session-001
Set PIXEL_BRIDGE_ENABLED=true in .env to auto-start with the agent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

# ── Bootstrap SableCore path ─────────────────────────────────────────────────
_SCRIPT_DIR = Path(__file__).resolve().parent
_SABLE_ROOT = _SCRIPT_DIR.parent          # /home/nexland/SableCore_
if str(_SABLE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SABLE_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_SABLE_ROOT / ".env")
except ImportError:
    pass


# ── JSONL helpers ──────────────────────────────────────────────────────────

def _write_jsonl(path: Path, record: dict) -> None:
    """Append one JSON line to the transcript file, flush immediately."""
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        fh.flush()


def emit_user_message(path: Path, text: str) -> None:
    _write_jsonl(path, {
        "type": "user",
        "message": {"content": text},
    })


def emit_assistant_text(path: Path, text: str) -> None:
    _write_jsonl(path, {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    })


def emit_tool_start(path: Path, tool_id: str, tool_name: str, args: dict) -> None:
    _write_jsonl(path, {
        "type": "assistant",
        "message": {
            "content": [{
                "type": "tool_use",
                "id": tool_id,
                "name": _map_tool_name(tool_name),
                "input": args,
            }]
        },
    })


def emit_tool_result(path: Path, tool_id: str, result: str) -> None:
    _write_jsonl(path, {
        "type": "user",
        "message": {
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result,
            }]
        },
    })


def emit_turn_duration(path: Path, duration_ms: int) -> None:
    _write_jsonl(path, {
        "type": "system",
        "subtype": "turn_duration",
        "duration_ms": duration_ms,
    })


def emit_startup(path: Path, session_id: str) -> None:
    """Write an initial record so the JSONL file exists immediately."""
    _write_jsonl(path, {
        "type": "system",
        "subtype": "startup",
        "session_id": session_id,
    })


# ── Tool name mapping ─────────────────────────────────────────────────────────
_TOOL_NAME_MAP: dict[str, str] = {
    "read_file":        "Read",
    "write_file":       "Write",
    "edit_file":        "Edit",
    "run_bash":         "Bash",
    "bash":             "Bash",
    "shell":            "Bash",
    "grep":             "Grep",
    "glob":             "Glob",
    "search_files":     "Grep",
    "web_search":       "WebSearch",
    "search_web":       "WebSearch",
    "web_fetch":        "WebFetch",
    "fetch_url":        "WebFetch",
    "scrape":           "WebFetch",
    "task":             "Task",
    "delegate":         "Task",
    "create_agent":     "Task",
    "ask_user":         "AskUserQuestion",
    "phone_notify":     "Bash",
    "memory_store":     "Write",
    "memory_recall":    "Read",
}


def _map_tool_name(name: str) -> str:
    return _TOOL_NAME_MAP.get(name.lower(), name)


# ── Project directory ───────────────────────────────────────────────────────────

def _project_dir(cwd: str) -> Path:
    """Compute ~/.claude/projects/<hash>/ the same way pixel-agents does."""
    dir_name = re.sub(r"[^a-zA-Z0-9\-]", "-", cwd)
    return Path.home() / ".claude" / "projects" / dir_name


# ── Monitor subscriber (used in standalone mode) ────────────────────────────

class PixelBridgeMonitor:
    """Subscribes to SableAgent's monitor events and writes JSONL records."""

    def __init__(self, jsonl_path: Path) -> None:
        self._path = jsonl_path
        self._active: dict[str, deque[str]] = defaultdict(deque)

    def __call__(self, event: str, data: dict) -> None:
        if event == "tool.start":
            tool_name: str = data.get("name", "unknown")
            args: dict = data.get("args") or {}
            tool_id = f"toolu_{uuid.uuid4().hex[:24]}"
            self._active[tool_name].append(tool_id)
            emit_tool_start(self._path, tool_id, tool_name, args)

        elif event == "tool.done":
            tool_name = data.get("name", "unknown")
            queue = self._active.get(tool_name)
            if queue:
                tool_id = queue.popleft()
                result = data.get("result", "")
                if not data.get("success", True):
                    result = f"[ERROR] {result}"
                emit_tool_result(self._path, tool_id, str(result))

        elif event in ("thinking", "reasoning"):
            # Thinking events show in terminal only, not in chat
            pass


# ── Reply cleaning ────────────────────────────────────────────────────────────

# Patterns that indicate internal/debug lines to strip from chat output
_INTERNAL_PREFIXES = (
    "💭",           # thinking traces
    "ADD THIS TO",  # browser history artifacts
    "SEARCH:",      # search logging
    "MEMORY:",      # memory operations
    "DEBUG:",       # debug output
)

def _clean_reply(text: str) -> str:
    """Strip internal/debug lines from agent reply, return user-facing text."""
    lines = text.strip().splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            clean_lines.append(line)
            continue
        if any(stripped.startswith(p) for p in _INTERNAL_PREFIXES):
            continue
        clean_lines.append(line)
    # Collapse leading/trailing blank lines
    result = "\n".join(clean_lines).strip()
    return result


# ── Gateway-attached mode ─────────────────────────────────────────────────

async def run_gateway_bridge(session_id: str, gateway_url: str) -> None:
    """
    Attach to a running SableCore gateway over WebSocket.
    Subscribes to monitor events and writes JSONL for the Pixel Agents extension.
    Also forwards user input from stdin as gateway messages.
    """
    import aiohttp

    cwd = os.getcwd()
    project_dir = _project_dir(cwd)
    project_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = project_dir / f"{session_id}.jsonl"

    # Normalize gateway URL: http(s) base → ws(s) for WS connection
    ws_url = re.sub(r"^http", "ws", gateway_url.rstrip("/")) + "/"

    # Append auth token if available
    _token = os.environ.get("WEBCHAT_TOKEN", "") or os.environ.get("webchat_token", "")
    if _token:
        _sep = "&" if "?" in ws_url else "?"
        ws_url += f"{_sep}token={_token}"

    print(f"\n🟢 Pixel-Bridge (gateway mode) started")
    print(f"   Session : {session_id}")
    print(f"   JSONL   : {jsonl_path}")
    print(f"   Gateway : {ws_url}")
    print(f"\nType your message and press Enter. Type 'exit' to quit.\n")

    emit_startup(jsonl_path, session_id)

    active: dict[str, deque[str]] = defaultdict(deque)
    loop = asyncio.get_event_loop()

    async with aiohttp.ClientSession() as http:
        async with http.ws_connect(ws_url, heartbeat=30) as ws:
            # Wait for 'connected' handshake
            hello = await ws.receive_json()
            if hello.get("type") != "connected":
                print(f"Unexpected first message: {hello}")
                return

            # Subscribe to agent monitor events
            await ws.send_json({"type": "monitor.subscribe"})

            turn_start: float | None = None

            async def _reader() -> None:
                """Background task — read WS messages and write JSONL."""
                nonlocal turn_start
                async for msg in ws:
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    data = json.loads(msg.data)
                    mtype = data.get("type", "")

                    if mtype == "monitor.event":
                        event = data.get("event", "")
                        edata = data.get("data") or {}

                        if event == "tool.start":
                            tool_name = edata.get("name", "unknown")
                            args = edata.get("args") or {}
                            tool_id = f"toolu_{uuid.uuid4().hex[:24]}"
                            active[tool_name].append(tool_id)
                            emit_tool_start(jsonl_path, tool_id, tool_name, args)

                        elif event == "tool.done":
                            tool_name = edata.get("name", "unknown")
                            queue = active.get(tool_name)
                            if queue:
                                tool_id = queue.popleft()
                                result = edata.get("result", "")
                                if not edata.get("success", True):
                                    result = f"[ERROR] {result}"
                                emit_tool_result(jsonl_path, tool_id, str(result))

                        elif event in ("thinking", "reasoning"):
                            txt = edata.get("message") or edata.get("summary") or ""
                            if txt:
                                emit_assistant_text(jsonl_path, f"💭 {txt}")

                    elif mtype == "message.start":
                        turn_start = time.perf_counter()

                    elif mtype == "progress":
                        txt = data.get("text", "")
                        if txt:
                            print(f"  ↳ {txt}", flush=True)

                    elif mtype == "message.done":
                        reply = data.get("text", "")
                        if reply:
                            clean = _clean_reply(reply)
                            if clean:
                                emit_assistant_text(jsonl_path, clean)
                            print(f"\nAgent: {reply}\n")
                        if turn_start is not None:
                            duration_ms = int((time.perf_counter() - turn_start) * 1000)
                            emit_turn_duration(jsonl_path, duration_ms)
                            turn_start = None

                    elif mtype == "heartbeat":
                        pass  # ignore

            reader_task = asyncio.create_task(_reader())

            # Interactive REPL — user input → gateway message
            while True:
                try:
                    user_text: str = await loop.run_in_executor(
                        None, lambda: input("You: ").strip()
                    )
                except (EOFError, KeyboardInterrupt):
                    print("\nBye!")
                    break

                if not user_text:
                    continue
                if user_text.lower() in ("exit", "quit", "/exit", "/quit"):
                    print("Session ended.")
                    break

                emit_user_message(jsonl_path, user_text)
                await ws.send_json({
                    "type": "message",
                    "session_id": session_id,
                    "user_id": "pixel-bridge",
                    "text": user_text,
                })

            reader_task.cancel()


# ── Standalone mode ───────────────────────────────────────────────────────────────

async def run_standalone_bridge(session_id: str) -> None:
    """Create a full SableAgent and run an interactive REPL."""
    from opensable.core.config import load_config
    from opensable.core.agent import SableAgent

    cwd = os.getcwd()
    project_dir = _project_dir(cwd)
    project_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = project_dir / f"{session_id}.jsonl"

    print(f"\n🟢 Pixel-Bridge started")
    print(f"   Session : {session_id}")
    print(f"   JSONL   : {jsonl_path}")
    print(f"   Project : {cwd}")
    print(f"\nType your message and press Enter. Type 'exit' to quit.\n")

    emit_startup(jsonl_path, session_id)

    config = load_config()
    agent = SableAgent(config)
    await agent.initialize()

    monitor = PixelBridgeMonitor(jsonl_path)
    agent.monitor_subscribe(monitor)

    async def _progress(msg: str) -> None:
        print(f"  ↳ {msg}", flush=True)

    agent._progress_callback = _progress

    loop = asyncio.get_event_loop()

    while True:
        try:
            user_text: str = await loop.run_in_executor(
                None, lambda: input("You: ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        if not user_text:
            continue
        if user_text.lower() in ("exit", "quit", "/exit", "/quit"):
            print("Session ended.")
            break

        emit_user_message(jsonl_path, user_text)
        turn_start = time.perf_counter()

        try:
            reply = await agent.run(user_text)
        except Exception as exc:
            reply = f"[Agent error: {exc}]"

        duration_ms = int((time.perf_counter() - turn_start) * 1000)

        if reply:
            clean = _clean_reply(reply)
            if clean:
                emit_assistant_text(jsonl_path, clean)
            print(f"\nAgent: {reply}\n")

        emit_turn_duration(jsonl_path, duration_ms)

    agent.monitor_unsubscribe(monitor)


# ── Entry point ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pixel-Bridge: run an OpenSable agent visible in Pixel Agents"
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="UUID session identifier (passed automatically by Pixel Agents)",
    )
    parser.add_argument(
        "--gateway-url",
        default=None,
        help=(
            "Connect to a running SableCore gateway instead of spawning a new agent. "
            "Example: ws://127.0.0.1:8789  or  http://127.0.0.1:8789"
        ),
    )
    args = parser.parse_args()

    if args.gateway_url:
        asyncio.run(run_gateway_bridge(args.session_id, args.gateway_url))
    else:
        asyncio.run(run_standalone_bridge(args.session_id))


if __name__ == "__main__":
    main()

