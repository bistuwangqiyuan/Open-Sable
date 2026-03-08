"""
Sable Gateway — Internal Control Plane (aiohttp, Unix + TCP)

Architecture:
  ┌────────────────────────────────────────────────────────────┐
  │  /tmp/sable.sock  (Unix domain socket, mode 0600)         │
  │  ┌──────────────┐    ┌──────────────┐    ┌─────────────┐  │
  │  │  WebChat JS  │    │  CLI client  │    │  Nodes/IPC  │  │
  │  └──────┬───────┘    └──────┬───────┘    └──────┬──────┘  │
  │         └──────────────────┼───────────────────┘          │
  │                       Unix socket + TCP                    │
  │                   SableGateway (aiohttp)                   │
  │                       │                                    │
  │              ┌─────────┴──────────┐                       │
  │         SessionManager       SableAgent                   │
  └────────────────────────────────────────────────────────────┘

Security:
  - Unix socket: only the process owner can connect (OS enforces it)
  - chmod 0600 applied immediately after bind
  - Token auth via middleware — HMAC-compare on ?token= query param
  - Remote access via SSH tunnel: ssh -L 8789:/tmp/sable.sock user@vps

Protocol (JSON over WebSocket, text frames):
  Client → Gateway
    {"type": "message",           "session_id": "...", "user_id": "...", "text": "..."}
    {"type": "command",           "session_id": "...", "user_id": "...", "text": "/status"}
    {"type": "sessions.list"}
    {"type": "sessions.history",  "session_id": "..."}
    {"type": "node.register",     "node_id": "...",   "capabilities": [...]}
    {"type": "node.invoke",       "node_id": "...",   "capability": "...", "args": {...}, "request_id": "..."}
    {"type": "node.result",       "request_id": "...", "output": "...", "reply_to": "..."}
    {"type": "ping"}

  Gateway → Client
    {"type": "connected",         "version": "2.1.0"}
    {"type": "message.start",     "session_id": "..."}
    {"type": "message.done",      "session_id": "...", "text": "..."}
    {"type": "command.result",    "session_id": "...", "text": "...", "success": bool}
    {"type": "sessions.list.result",    "sessions": [...]}
    {"type": "sessions.history.result", "session_id": "...", "messages": [...]}
    {"type": "node.registered",   "node_id": "...", "capabilities": [...]}
    {"type": "node.invoke",       "capability": "...", "args": {...}, "request_id": "...", "reply_to": "..."}
    {"type": "node.result",       "request_id": "...", "output": "..."}
    {"type": "error",             "text": "..."}
    {"type": "heartbeat",         "ts": float}
    {"type": "pong"}
    {"type": "status",            ...}
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiohttp
from aiohttp import web, WSMsgType

# ─── LLM reasoning-trace stripper ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r"<think>.*", re.DOTALL | re.IGNORECASE)

_REASONING_STARTERS = re.compile(
    r"^(system\b|i need to\b|let me\b|first,?\s+let me\b|okay,?\s+let me\b|"
    r"alright,?\s+let me\b|i\'ll craft\b|i will craft\b|i\'m going to\b|"
    r"the user (seems|is|wants|asked|might|may|said|appears|\'s message)\b|"
    r"i should\b|i\'ve been\b|maybe i(\'ll| will)\b|"
    r"so i (need|should|want|will)\b|now i\b|next,?\s+i\b|"
    r"looking at (the|this|their)\b|this (is|seems|looks|appears) (to be|like)\b|"
    r"they(\'re|\'ve been|\'ve| are| might be| seem| could be| want| may be| did| have)\b|"
    r"(he|she|it) (is|was|seems|wants|might|appears|\'s)\b|"
    r"my response should\b|i\'ll (acknowledge|address|respond|help|note|craft|keep|try|make|provide)\b|"
    r"i\'m (going|trying|not sure|looking|noticing|thinking)\b|"
    r"i (should|need to|will|must|can|notice|see that|recognize|understand)\b|"
    r"(alright|okay|ok|hmm),?\s+(let me|i)\b|"
    r"(?:not )?a (?:complaint|question|request|greeting|test|genuine)\b|"
    r"\(also,?\b|\(note[,:]|\(thinking|\(internal|\(context)",
    re.IGNORECASE,
)


def _strip_reasoning_preamble(text: str) -> str:
    """Remove raw untagged reasoning that Claude-distilled models emit."""
    if not text:
        return text

    paragraphs = re.split(r"\n{2,}", text)
    if len(paragraphs) <= 1:
        lines = text.splitlines()
        keep_from = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped and _REASONING_STARTERS.match(stripped):
                keep_from = i + 1
            else:
                break
        if keep_from:
            return "\n".join(lines[keep_from:]).strip()
        return text

    cleaned: list[str] = []
    found_real = False
    for para in paragraphs:
        if found_real:
            cleaned.append(para)
            continue
        lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
        if not lines:
            continue
        reasoning_count = sum(1 for ln in lines if _REASONING_STARTERS.match(ln))
        if reasoning_count == len(lines):
            logger.debug(f"🧹 Gateway stripped reasoning para: {para[:80]!r}")
            continue
        found_real = True
        cleaned.append(para)

    result = "\n\n".join(cleaned).strip()
    return result if result else text


def _clean_gateway_reply(text: str) -> str:
    """Strip any leaked <think>...</think> reasoning blocks before sending to client."""
    if not text:
        return text
    text = _THINK_RE.sub("", text)
    text = _THINK_OPEN.sub("", text)
    text = text.replace("</think>", "").strip()
    # Strip leaked role prefixes (llama/mistral chat template bleed)
    text = re.sub(
        r'^(?:assistant|asistente|user|sistema|system)\s*[:\n]+\s*',
        '', text, flags=re.IGNORECASE,
    )
    # Strip garbled BPE tokens after role prefix (e.g. "ungal\n\n")
    text = re.sub(r'^[a-z]{2,8}\n\n\s*', '', text, flags=re.IGNORECASE)
    text = _strip_reasoning_preamble(text)
    return text


# ─── Constants ────────────────────────────────────────────────────────────────

# Socket path is profile-aware: /tmp/sable-<profile>.sock for all profiles.
_profile_name = os.environ.get("_SABLE_PROFILE", "sable")
SOCKET_PATH = Path(os.environ.get("_SABLE_SOCKET_PATH", "/tmp/sable-sable.sock"))
_data_dir = Path(os.environ.get("_SABLE_DATA_DIR", "data"))
GATEWAY_VER = "2.1.0"
HEARTBEAT_INT = 30  # seconds between heartbeat frames

# Static asset extensions that bypass token auth
_ASSET_EXTS = frozenset({
    ".css", ".js", ".mjs", ".map", ".json",
    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
    ".woff", ".woff2", ".ttf", ".eot",
    ".webmanifest", ".txt",
})


# ─── Client wrapper ──────────────────────────────────────────────────────────


class _Client:
    """Represents one connected gateway WebSocket client."""

    def __init__(self, ws: web.WebSocketResponse, cid: str | None = None):
        self.ws = ws
        self.cid = cid or f"c{id(self):x}"
        self.node_id: Optional[str] = None
        self._proxy_tasks: Dict[str, asyncio.Task] = {}  # profile → proxy task

    async def send(self, payload: dict) -> None:
        try:
            if not self.ws.closed:
                await self.ws.send_json(payload)
        except Exception as exc:
            logger.debug(f"[Gateway] send to {self.cid} failed: {exc}")

    @property
    def closed(self) -> bool:
        return self.ws.closed

    def close(self) -> None:
        pass  # aiohttp manages WS lifecycle


# ─── Gateway ──────────────────────────────────────────────────────────────────


class Gateway:
    """
    aiohttp-based internal control plane.

    Instantiate with (agent, config) and call ``await gateway.start()``.
    The server runs in the background; call ``await gateway.stop()`` to shut down.
    """

    def __init__(self, agent, config):
        self.agent = agent
        self.config = config

        self._clients: Set[_Client] = set()
        self._nodes: Dict[str, _Client] = {}
        self._running = False
        self._hb_task: Optional[asyncio.Task] = None
        self._start_time = datetime.now(timezone.utc)

        # TCP WebChat settings
        self._webchat_host = getattr(config, "webchat_host", "127.0.0.1")
        self._webchat_port = int(getattr(config, "webchat_port", 8789))
        self._webchat_token: Optional[str] = getattr(config, "webchat_token", None) or None
        self._webchat_ts = getattr(config, "webchat_tailscale", False)

        # Static file roots
        self._static_dir = Path(__file__).resolve().parent.parent.parent / "static"
        self._project_root = self._static_dir.parent

        # Rate limiting
        self._rate_limits: Dict[str, List[float]] = {}
        self._rate_window = 60
        self._rate_max = 30

        # Monitor system
        self._monitor_clients: Set[_Client] = set()
        self._monitor_agent_wired = False

        # aiohttp internals
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._sites: list = []

    # ── Build aiohttp Application ─────────────────────────────────────────────

    def _build_app(self) -> web.Application:
        app = web.Application(middlewares=[self._token_auth_middleware])

        # WebSocket endpoint
        app.router.add_get("/ws", self._ws_handler)

        # Dashboard SPA
        app.router.add_get("/dashboard/{path:.*}", self._dashboard_handler)
        app.router.add_get("/dashboard", self._dashboard_handler)

        # Aggr trading terminal SPA
        app.router.add_get("/aggr/{path:.*}", self._aggr_handler)
        app.router.add_get("/aggr", self._aggr_handler)

        # Polymarket public API proxy
        app.router.add_get("/api/polymarket/{endpoint:.*}", self._polymarket_proxy)

        # HTML pages
        app.router.add_get("/chat", self._chat_handler)
        app.router.add_get("/monitor", self._monitor_page_handler)
        app.router.add_get("/dashboard-classic", self._dashboard_classic_handler)
        app.router.add_get("/dashboard-legacy", self._dashboard_legacy_handler)
        app.router.add_get("/favicon.ico", self._favicon_handler)

        # Hub (root)
        app.router.add_get("/", self._hub_handler)

        return app

    # ── Token auth middleware ─────────────────────────────────────────────────

    @web.middleware
    async def _token_auth_middleware(self, request: web.Request, handler):
        if not self._webchat_token:
            return await handler(request)

        # Unix socket connections are trusted (filesystem ACL controls access)
        transport = getattr(request, "transport", None) or (
            request._payload._transport if hasattr(request, "_payload") else None
        )
        if transport:
            sockname = transport.get_extra_info("sockname")
            if isinstance(sockname, str):  # Unix socket path → trusted
                return await handler(request)

        path = request.path.lower()

        # Asset extensions and specific prefixes skip auth
        ext = os.path.splitext(path)[1]
        if ext in _ASSET_EXTS or path.startswith("/aggr/") or path.startswith("/api/polymarket/") or path == "/favicon.ico":
            return await handler(request)

        supplied = request.query.get("token", "")
        if not supplied:
            supplied = request.headers.get("Sec-WebSocket-Protocol", "")

        if not hmac.compare_digest(str(supplied), self._webchat_token):
            return web.Response(
                status=401,
                content_type="text/html",
                text="<html><body><h1>401 Unauthorized</h1>"
                "<p>Invalid or missing token.</p></body></html>",
            )

        return await handler(request)

    # ── HTTP route handlers ───────────────────────────────────────────────────

    async def _hub_handler(self, request: web.Request) -> web.Response:
        # The old gateway accepted WS upgrades on ANY path.
        # All frontend dashboards connect via ws://host/ (root), so we
        # check for a WebSocket upgrade here and delegate to the WS handler.
        if (
            request.headers.get("Upgrade", "").lower() == "websocket"
            or request.headers.get("Connection", "").lower() == "upgrade"
        ):
            return await self._ws_handler(request)
        return self._serve_html_file(self._static_dir / "hub.html")

    async def _chat_handler(self, request: web.Request) -> web.Response:
        return self._serve_html_file(self._static_dir / "dashboard.html")

    async def _monitor_page_handler(self, request: web.Request) -> web.Response:
        return self._serve_html_file(self._static_dir / "monitor.html")

    async def _dashboard_classic_handler(self, request: web.Request) -> web.Response:
        return self._serve_html_file(self._static_dir / "dashboard_v2.html")

    async def _dashboard_legacy_handler(self, request: web.Request) -> web.Response:
        return self._serve_html_file(self._static_dir / "dashboard_modern.html")

    async def _favicon_handler(self, request: web.Request) -> web.Response:
        fav = self._static_dir / "favicon.ico"
        if fav.exists():
            return web.FileResponse(fav)
        return web.Response(status=204)

    async def _dashboard_handler(self, request: web.Request) -> web.Response:
        dash_dist = self._project_root / "dashboard" / "dist"
        if dash_dist.exists():
            rel = request.match_info.get("path", "") or "index.html"
            return self._serve_spa(dash_dist, rel)
        return self._serve_html_file(self._static_dir / "dashboard_v2.html")

    async def _aggr_handler(self, request: web.Request) -> web.Response:
        aggr_dist = self._project_root / "aggr" / "dist"
        if aggr_dist.exists():
            rel = request.match_info.get("path", "") or "index.html"
            return self._serve_spa(aggr_dist, rel)
        return web.Response(
            content_type="text/html",
            text="<html><body><h1>Aggr.trade not installed</h1>"
            "<p>Run: <code>cd aggr && npm install && npm run build</code></p></body></html>",
        )

    # ── Polymarket public API proxy ───────────────────────────────────────────

    async def _polymarket_proxy(self, request: web.Request) -> web.Response:
        """Proxy requests to Polymarket public APIs (Gamma + CLOB)."""
        endpoint = request.match_info.get("endpoint", "")
        qs = request.query_string

        # Route to correct upstream
        if endpoint.startswith("clob/"):
            upstream = f"https://clob.polymarket.com/{endpoint[5:]}"
        else:
            upstream = f"https://gamma-api.polymarket.com/{endpoint}"

        if qs:
            upstream += f"?{qs}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    upstream,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"Accept": "application/json"},
                ) as resp:
                    body = await resp.read()
                    return web.Response(
                        body=body,
                        status=resp.status,
                        content_type=resp.content_type or "application/json",
                        headers={
                            "Access-Control-Allow-Origin": "*",
                            "Cache-Control": "public, max-age=30",
                        },
                    )
        except asyncio.TimeoutError:
            return web.json_response({"error": "Polymarket API timeout"}, status=504)
        except Exception as e:
            logger.error(f"Polymarket proxy error: {e}")
            return web.json_response({"error": str(e)}, status=502)

    # ── Static file helpers ───────────────────────────────────────────────────

    @staticmethod
    def _serve_html_file(path: Path) -> web.Response:
        if path.exists():
            return web.Response(
                body=path.read_bytes(),
                content_type="text/html",
                charset="utf-8",
            )
        return web.Response(
            text="<!doctype html><title>Sable</title><body>"
            "<h1>Sable Gateway</h1><p>Page not found.</p></body>",
            content_type="text/html",
        )

    @staticmethod
    def _serve_spa(base_dir: Path, rel_path: str) -> web.Response:
        """Serve a static file from a SPA directory with index.html fallback."""
        import mimetypes

        safe = Path(rel_path).as_posix().replace("..", "")
        target = base_dir / safe
        is_fallback = False

        if not target.exists() or not target.is_file():
            for sub in ("aggr", "dashboard", "assets"):
                alt = base_dir / sub / safe
                if alt.exists() and alt.is_file():
                    target = alt
                    break

        if not target.exists() or not target.is_file():
            target = base_dir / "index.html"
            is_fallback = True

        if target.exists() and target.is_file():
            ct = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            # index.html must never be cached so builds take effect immediately;
            # hashed asset files (js/css) can be cached long-term.
            if is_fallback or target.name == "index.html":
                cc = "no-cache, no-store, must-revalidate"
            else:
                cc = "public, max-age=31536000, immutable"
            return web.Response(
                body=target.read_bytes(),
                content_type=ct,
                headers={"Cache-Control": cc},
            )
        return web.Response(status=404, text="404 Not Found")

    # ── WebSocket handler ─────────────────────────────────────────────────────

    async def _ws_handler(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=HEARTBEAT_INT)
        await ws.prepare(request)

        client = _Client(ws)
        self._clients.add(client)
        logger.debug(f"[Gateway] Client connected: {client.cid}")

        try:
            await client.send({"type": "connected", "version": GATEWAY_VER, "ts": time.time()})

            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await client.send({"type": "error", "text": "Invalid JSON"})
                        continue
                    await self._dispatch(client, data)
                elif msg.type == WSMsgType.ERROR:
                    logger.debug(f"[Gateway] WS error {client.cid}: {ws.exception()}")
                    break
        except Exception as exc:
            logger.debug(f"[Gateway] {client.cid} error: {exc}")
        finally:
            # Cancel any proxy tasks for this client
            for task in client._proxy_tasks.values():
                task.cancel()
            client._proxy_tasks.clear()

            self._clients.discard(client)
            self._monitor_clients.discard(client)
            if client.node_id and client.node_id in self._nodes:
                del self._nodes[client.node_id]
                logger.info(f"[Gateway] Node disconnected: {client.node_id}")
            logger.debug(f"[Gateway] Client disconnected: {client.cid}")

        return ws

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        """Bind the Unix socket and TCP port, then start accepting connections."""
        self._app = self._build_app()
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()

        # Unix socket
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        unix_site = web.UnixSite(self._runner, str(SOCKET_PATH))
        await unix_site.start()
        self._sites.append(unix_site)
        os.chmod(SOCKET_PATH, stat.S_IRUSR | stat.S_IWUSR)

        # TCP listener(s)
        bind_hosts = [self._webchat_host]
        ts_ip = self._get_tailscale_ip() if self._webchat_ts else None
        if ts_ip and ts_ip not in bind_hosts:
            bind_hosts.append(ts_ip)

        for host in bind_hosts:
            tcp_site = web.TCPSite(self._runner, host, self._webchat_port)
            await tcp_site.start()
            self._sites.append(tcp_site)

        self._running = True
        self._hb_task = asyncio.create_task(self._heartbeat())

        token_hint = f"?token={self._webchat_token}" if self._webchat_token else ""
        urls = [f"http://{h}:{self._webchat_port}{token_hint}" for h in bind_hosts]
        logger.info(
            f"[Gateway] Unix socket : {SOCKET_PATH}  (internal nodes)\n"
            + "\n".join(f"[Gateway] WebChat      : {u}" for u in urls)
        )

    async def stop(self):
        """Gracefully close all connections and remove the socket file."""
        self._running = False
        if self._hb_task:
            self._hb_task.cancel()
        for c in list(self._clients):
            if not c.ws.closed:
                await c.ws.close()
        if self._runner:
            await self._runner.cleanup()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        logger.info("[Gateway] Stopped")

    @staticmethod
    def _get_tailscale_ip() -> Optional[str]:
        """Return the Tailscale IP (100.x.x.x) if Tailscale is running."""
        import subprocess

        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=2
            )
            ip = result.stdout.strip()
            if re.match(r"^100\.\d+\.\d+\.\d+$", ip):
                return ip
        except Exception:
            pass
        return None

    @property
    def is_running(self) -> bool:
        return self._running

    def status(self) -> dict:
        uptime = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return {
            "version": GATEWAY_VER,
            "running": self._running,
            "socket": str(SOCKET_PATH),
            "uptime_sec": round(uptime, 1),
            "clients": len(self._clients),
            "nodes": list(self._nodes.keys()),
            "start_time": self._start_time.isoformat(),
            "monitor_clients": len(self._monitor_clients),
        }

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, client: _Client, msg: dict):
        t = msg.get("type", "")

        if t == "message":
            if not self._check_rate(client.cid):
                await client.send(
                    {"type": "error", "text": "Rate limit exceeded. Try again in a moment."}
                )
                return
            await self._on_message(client, msg)
        elif t == "command":
            await self._on_command(client, msg)
        elif t == "sessions.list":
            await self._on_sessions_list(client)
        elif t == "sessions.history":
            await self._on_sessions_history(client, msg)
        elif t == "node.register":
            await self._on_node_register(client, msg)
        elif t == "node.invoke":
            await self._on_node_invoke(client, msg)
        elif t == "node.result":
            await self._on_node_result(client, msg)
        elif t == "monitor.subscribe":
            await self._on_monitor_subscribe(client)
        elif t == "monitor.snapshot":
            await self._on_monitor_snapshot(client)
        elif t == "thoughts.list":
            await self._on_thoughts_list(client, msg)
        elif t == "tools.list":
            await self._on_tools_list(client)
        elif t == "status":
            status = self.status()
            if hasattr(self.agent, "llm") and hasattr(self.agent.llm, "current_model"):
                status["model"] = self.agent.llm.current_model
            try:
                from opensable import __version__ as _ver

                status["version"] = _ver
            except Exception:
                pass
            await client.send({"type": "status", **status})
        elif t == "code.run":
            await self._on_code_run(client, msg)
        elif t == "code.autofix":
            await self._on_code_autofix(client, msg)
        elif t == "agents.list":
            await self._on_agents_list(client)
        elif t == "agents.status":
            await self._on_agents_status(client, msg)
        elif t == "agents.subscribe":
            await self._on_agents_subscribe(client, msg)
        elif t == "agents.unsubscribe":
            await self._on_agents_unsubscribe(client, msg)
        elif t == "agents.chat":
            await self._on_agents_chat(client, msg)
        elif t == "agents.brain.data":
            await self._on_agents_brain_data(client, msg)
        elif t == "brain.data":
            await self._on_brain_data(client, msg)
        elif t == "ping":
            await client.send({"type": "pong", "ts": time.time()})
        else:
            await client.send({"type": "error", "text": f"Unknown type: {t!r}"})

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _on_tools_list(self, client: _Client):
        tool_names: list = []
        try:
            if hasattr(self.agent, "tools") and self.agent.tools:
                tool_names = self.agent.tools.list_tools()
        except Exception as exc:
            logger.debug(f"[Gateway] tools.list error: {exc}")
        await client.send({"type": "tools.list.result", "tools": tool_names})

    async def _on_code_run(self, client: _Client, msg: dict):
        """Execute a code snippet sent from the desktop chat Run button."""
        import tempfile, os as _os

        request_id: str = msg.get("request_id", "")
        code: str = msg.get("code", "")
        stdin: str | None = msg.get("stdin")
        language: str = (msg.get("language") or "python").lower()

        _LANG_RUNNERS: dict[str, list[str]] = {
            "python":     ["python3", "-u"],
            "python3":    ["python3", "-u"],
            "javascript": ["node"],
            "js":         ["node"],
            "bash":       ["bash"],
            "sh":         ["sh"],
        }

        runner = _LANG_RUNNERS.get(language)
        if not runner:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": f"Language '{language}' is not supported for execution.",
                "exit_code": 1,
            })
            return

        # Write code to a temp file so multi-line scripts work cleanly
        suffix_map = {
            "python": ".py", "python3": ".py",
            "javascript": ".js", "js": ".js",
            "bash": ".sh", "sh": ".sh",
        }
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=suffix_map.get(language, ".tmp"),
                delete=False, encoding="utf-8"
            ) as tf:
                tf.write(code)
                tmp_path = tf.name

            cmd = " ".join(runner + [tmp_path])
            # If stdin was provided, prefer direct subprocess so we can feed input.
            if stdin is not None:
                proc = await asyncio.create_subprocess_shell(
                    cmd,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _out, _err = await asyncio.wait_for(
                    proc.communicate(input=stdin.encode('utf-8')),
                    timeout=30,
                )
                stdout = _out.decode(errors='replace') if _out else ""
                stderr = _err.decode(errors='replace') if _err else ""
                exit_code = getattr(proc, 'returncode', 0) or 0
            else:
                if hasattr(self.agent, "tools") and self.agent.tools:
                    # Tools.execute returns the command output as a string; cannot provide stdin
                    raw = await self.agent.tools.execute(
                        "execute_command",
                        {"command": cmd, "timeout": 30},
                    )
                    stdout = str(raw) if raw else ""
                    stderr = ""
                    exit_code = 0
                else:
                    # Fallback: run directly via asyncio subprocess without stdin
                    proc = await asyncio.create_subprocess_shell(
                        cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    )
                    _out, _err = await asyncio.wait_for(proc.communicate(), timeout=30)
                    stdout = _out.decode(errors='replace') if _out else ""
                    stderr = _err.decode(errors='replace') if _err else ""
                    exit_code = getattr(proc, 'returncode', 0) or 0

            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
            })
        except asyncio.TimeoutError:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": "Execution timed out (30s limit).",
                "exit_code": 124,
            })
        except Exception as exc:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": 1,
            })
        finally:
            try:
                if tmp_path:
                    _os.unlink(tmp_path)
            except Exception:
                pass

    async def _on_code_autofix(self, client: _Client, msg: dict):
        """Attempt a simple automatic fix for interactive Python snippets that raise EOF.

        Strategy (conservative): when code contains `input(`, wrap it so inputs
        are consumed from `sys.argv[1:]`. Return the patched code and run it.
        """
        import tempfile, os as _os

        request_id: str = msg.get("request_id", "")
        code: str = msg.get("code", "")
        language: str = (msg.get("language") or "python").lower()

        if language not in ("python", "python3"):
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": f"Autofix not supported for language: {language}",
                "exit_code": 1,
            })
            return

        if "input(" not in code:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": "No interactive `input()` calls detected; autofix skipped.",
                "exit_code": 1,
            })
            return

        # Build patched code that replaces input() calls with a helper that
        # consumes values from sys.argv[1:]
        header = (
            "import sys\n"
            "_stdin_values = list(sys.argv[1:])\n"
            "def _get_input(prompt=None):\n"
            "    if _stdin_values:\n"
            "        return _stdin_values.pop(0)\n"
            "    raise EOFError('No simulated stdin provided')\n\n"
        )

        patched = code.replace("input(", "_get_input(")
        patched_code = header + patched

        # Write and run patched code
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
                tf.write(patched_code)
                tmp_path = tf.name

            cmd = "python3 -u " + tmp_path
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _out, _err = await asyncio.wait_for(proc.communicate(), timeout=30)
            stdout = _out.decode(errors="replace") if _out else ""
            stderr = _err.decode(errors="replace") if _err else ""
            exit_code = getattr(proc, 'returncode', 0) or 0

            # Return both the patched code (so UI can show it) and the run result
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": stdout,
                "stderr": stderr,
                "exit_code": exit_code,
                "autofix": True,
                "patched_code": patched_code,
            })
        except asyncio.TimeoutError:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": "Execution timed out (30s).",
                "exit_code": 124,
                "autofix": True,
                "patched_code": patched_code,
            })
        except Exception as exc:
            await client.send({
                "type": "code.result",
                "request_id": request_id,
                "stdout": "",
                "stderr": str(exc),
                "exit_code": 1,
                "autofix": True,
                "patched_code": patched_code,
            })
        finally:
            try:
                if tmp_path:
                    _os.unlink(tmp_path)
            except Exception:
                pass

    # ── Multi-Agent handlers ──────────────────────────────────────────────────

    async def _on_agents_list(self, client: _Client):
        """Return list of all agent profiles and their running status."""
        try:
            from opensable.core.profile import list_profiles
        except ImportError:
            await client.send({"type": "agents.list.result", "agents": [], "current": _profile_name})
            return

        agents = []
        for name in list_profiles():
            sock = Path(f"/tmp/sable-{name}.sock")
            agents.append({
                "name": name,
                "running": sock.exists(),
                "is_current": name == _profile_name,
            })

        await client.send({
            "type": "agents.list.result",
            "agents": agents,
            "current": _profile_name,
        })

    async def _on_agents_status(self, client: _Client, msg: dict):
        """Get status from a specific agent, proxied via Unix socket."""
        profile = msg.get("profile", "")
        if not profile:
            await client.send({"type": "error", "text": "agents.status requires 'profile'"})
            return

        if profile == _profile_name:
            # Current agent – return local status
            status = self.status()
            if hasattr(self.agent, "llm") and hasattr(self.agent.llm, "current_model"):
                status["model"] = self.agent.llm.current_model
            try:
                from opensable import __version__ as _ver
                status["version"] = _ver
            except Exception:
                pass
            await client.send({"type": "agents.status.result", "profile": profile, **status})
            return

        # Proxy to peer agent via Unix socket
        socket_path = f"/tmp/sable-{profile}.sock"
        if not Path(socket_path).exists():
            await client.send({
                "type": "agents.status.result",
                "profile": profile,
                "running": False,
            })
            return

        try:
            conn = aiohttp.UnixConnector(path=socket_path)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect("http://localhost/") as ws:
                    await ws.send_json({"type": "status"})
                    resp = await asyncio.wait_for(ws.receive_json(), timeout=5)
                    await client.send({
                        "type": "agents.status.result",
                        "profile": profile,
                        **resp,
                    })
        except Exception as exc:
            logger.debug(f"[Gateway] agents.status proxy to {profile} failed: {exc}")
            await client.send({
                "type": "agents.status.result",
                "profile": profile,
                "running": False,
                "error": str(exc),
            })

    async def _on_agents_subscribe(self, client: _Client, msg: dict):
        """Subscribe to real-time events from another agent via Unix socket proxy."""
        profile = msg.get("profile", "")
        if not profile:
            await client.send({"type": "error", "text": "agents.subscribe requires 'profile'"})
            return

        if profile == _profile_name:
            # Already connected to this agent
            await client.send({
                "type": "agents.subscribed",
                "profile": profile,
                "status": "already_connected",
            })
            return

        # Cancel existing proxy for this profile if any
        if profile in client._proxy_tasks:
            client._proxy_tasks[profile].cancel()
            del client._proxy_tasks[profile]

        socket_path = f"/tmp/sable-{profile}.sock"
        if not Path(socket_path).exists():
            await client.send({
                "type": "agents.subscribed",
                "profile": profile,
                "status": "offline",
            })
            return

        # Start a background task to proxy events from the peer agent
        task = asyncio.create_task(self._proxy_agent_events(client, profile, socket_path))
        client._proxy_tasks[profile] = task

    async def _on_agents_unsubscribe(self, client: _Client, msg: dict):
        """Unsubscribe from a remote agent's events."""
        profile = msg.get("profile", "")
        if profile in client._proxy_tasks:
            client._proxy_tasks[profile].cancel()
            del client._proxy_tasks[profile]
        await client.send({"type": "agents.unsubscribed", "profile": profile})

    async def _proxy_agent_events(self, client: _Client, profile: str, socket_path: str):
        """Forward all events from a remote agent to this dashboard client."""
        try:
            conn = aiohttp.UnixConnector(path=socket_path)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect("http://localhost/") as ws:
                    await client.send({
                        "type": "agents.subscribed",
                        "profile": profile,
                        "status": "connected",
                    })

                    # Request initial state
                    await ws.send_json({"type": "status"})
                    await ws.send_json({"type": "sessions.list"})
                    await ws.send_json({"type": "monitor.subscribe"})
                    await ws.send_json({"type": "thoughts.list", "limit": 500})

                    # Periodically request status updates
                    last_status = time.time()

                    async for msg in ws:
                        if client.closed:
                            break
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(msg.data)
                            except json.JSONDecodeError:
                                continue
                            # Tag every message with the source profile
                            data["_profile"] = profile
                            await client.send(data)
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break

                        # Request periodic status
                        now = time.time()
                        if now - last_status >= 5:
                            try:
                                await ws.send_json({"type": "status"})
                            except Exception:
                                pass
                            last_status = now

        except asyncio.CancelledError:
            logger.debug(f"[Gateway] Agent proxy to {profile} cancelled")
        except Exception as exc:
            logger.debug(f"[Gateway] Agent proxy to {profile} ended: {exc}")
        finally:
            # Notify the dashboard client that the proxy disconnected
            try:
                await client.send({
                    "type": "agents.disconnected",
                    "profile": profile,
                })
            except Exception:
                pass

    async def _on_agents_brain_data(self, client: _Client, msg: dict):
        """Proxy brain.data request to a remote agent via Unix socket."""
        profile = msg.get("profile", "")
        if not profile:
            await client.send({"type": "error", "text": "agents.brain.data requires 'profile'"})
            return

        # If targeting the current agent, just handle locally
        if profile == _profile_name:
            await self._on_brain_data(client, msg)
            return

        socket_path = f"/tmp/sable-{profile}.sock"
        if not Path(socket_path).exists():
            await client.send({
                "type": "brain.data.result",
                "_profile": profile,
                "error": f"Agent '{profile}' is not running",
            })
            return

        try:
            conn = aiohttp.UnixConnector(path=socket_path)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect("http://localhost/") as ws:
                    await ws.send_json({"type": "brain.data"})
                    async for frame in ws:
                        if client.closed:
                            break
                        if frame.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(frame.data)
                            except json.JSONDecodeError:
                                continue
                            if data.get("type") == "brain.data.result":
                                data["_profile"] = profile
                                await client.send(data)
                                break
                        elif frame.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break
        except Exception as exc:
            logger.warning(f"[Gateway] agents.brain.data proxy to {profile} failed: {exc}")
            await client.send({
                "type": "brain.data.result",
                "_profile": profile,
                "error": str(exc),
            })

    async def _on_agents_chat(self, client: _Client, msg: dict):
        """Proxy a chat message to a remote agent via Unix socket and stream the response back."""
        profile = msg.get("profile", "")
        text = msg.get("text", "").strip()
        session_id = msg.get("session_id", "webchat_default")
        user_id = msg.get("user_id", "dashboard_user")

        if not profile or not text:
            await client.send({"type": "error", "text": "agents.chat requires 'profile' and 'text'"})
            return

        # If targeting the current agent, just handle locally
        if profile == _profile_name:
            await self._on_message(client, msg)
            return

        socket_path = f"/tmp/sable-{profile}.sock"
        if not Path(socket_path).exists():
            await client.send({"type": "error", "text": f"Agent '{profile}' is not running"})
            return

        try:
            conn = aiohttp.UnixConnector(path=socket_path)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.ws_connect("http://localhost/") as ws:
                    # Send the chat message to the remote agent
                    await ws.send_json({
                        "type": "message",
                        "text": text,
                        "session_id": session_id,
                        "user_id": user_id,
                    })

                    # Stream back all response frames until message.done
                    done = False
                    async for frame in ws:
                        if client.closed:
                            break
                        if frame.type == aiohttp.WSMsgType.TEXT:
                            try:
                                data = json.loads(frame.data)
                            except json.JSONDecodeError:
                                continue
                            ftype = data.get("type", "")
                            # Tag with source profile
                            data["_profile"] = profile
                            # Forward relevant message types
                            if ftype in ("message.start", "message.chunk", "message.done",
                                         "progress", "error"):
                                await client.send(data)
                            if ftype == "message.done":
                                done = True
                                break
                        elif frame.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break

                    if not done:
                        await client.send({
                            "type": "message.done",
                            "_profile": profile,
                            "session_id": session_id,
                            "text": "",
                        })

        except Exception as exc:
            logger.warning(f"[Gateway] agents.chat proxy to {profile} failed: {exc}")
            await client.send({
                "type": "error",
                "_profile": profile,
                "text": f"Failed to chat with agent '{profile}': {exc}",
            })

    async def _on_message(self, client: _Client, msg: dict):
        """Process user message through the full agent pipeline."""
        from opensable.core.session_manager import SessionManager

        sid = msg.get("session_id", "webchat_default")
        text = msg.get("text", "").strip()
        user_id = msg.get("user_id", "webchat_user")

        if not text:
            return

        await client.send({"type": "message.start", "session_id": sid})

        async def _progress(status_text: str):
            try:
                await client.send({"type": "progress", "session_id": sid, "text": status_text})
            except Exception:
                pass

        try:
            sm = SessionManager()
            session = sm.get_session(sid)
            if not session:
                session = sm.create_session(
                    channel="webchat", user_id=user_id, session_id=sid
                )
            history = [
                {"role": m.role, "content": m.content}
                for m in session.get_messages()[-30:]
            ]

            reply = await self.agent.process_message(
                user_id, text, history=history, progress_callback=_progress
            )
            raw_reply = reply
            reply = _clean_gateway_reply(reply or "")

            if not reply:
                logger.warning(
                    f"[Gateway] Empty reply after cleaning (raw length={len(raw_reply or '')}). "
                    f"Falling back to raw or default."
                )
                reply = (raw_reply or "").strip() or "I processed your request but couldn't generate a response. Please try again."

            # Deduplicate: if the reply is identical to the last assistant message,
            # the model is repeating itself — ask it to try again without history
            if history:
                last_assistant = next(
                    (m["content"] for m in reversed(history) if m.get("role") == "assistant"),
                    None,
                )
                if last_assistant and reply.strip() == last_assistant.strip():
                    logger.warning("[Gateway] Duplicate response detected — retrying without history")
                    try:
                        retry_reply = await self.agent.process_message(
                            user_id, text, history=[], progress_callback=_progress
                        )
                        retry_reply = _clean_gateway_reply(retry_reply or "")
                        if retry_reply and retry_reply.strip() != last_assistant.strip():
                            reply = retry_reply
                    except Exception:
                        pass  # keep original reply

            try:
                if not session.metadata.get("title"):
                    session.metadata["title"] = text[:60]
                    session.updated_at = datetime.now(timezone.utc).isoformat()
                session.add_message("user", text)
                session.add_message("assistant", reply)
                sm._save_session(session)
            except Exception as _se:
                logger.debug(f"[Gateway] session persist error: {_se}")

            await client.send({"type": "message.done", "session_id": sid, "text": reply})
        except Exception as exc:
            logger.warning(f"[Gateway] Agent processing failed: {exc}")
            await client.send({"type": "error", "session_id": sid, "text": str(exc)})

    async def _on_command(self, client: _Client, msg: dict):
        from opensable.core.commands import CommandHandler
        from opensable.core.session_manager import SessionManager

        sm = SessionManager()
        ch = CommandHandler(sm)
        sid = msg.get("session_id", "webchat_default")
        uid = msg.get("user_id", "webchat_user")
        txt = msg.get("text", "")
        s = sm.get_or_create_session(channel="webchat", user_id=uid)
        res = await ch.handle_command(txt, s.id, uid, is_admin=True)
        await client.send({
            "type": "command.result",
            "session_id": sid,
            "text": res.message,
            "success": res.success,
        })

    async def _on_sessions_list(self, client: _Client):
        from opensable.core.session_manager import SessionManager

        sm = SessionManager()
        sessions = [
            {
                "id": s.id,
                "session_id": s.id,
                "channel": s.channel,
                "user_id": s.user_id,
                "title": s.metadata.get("title")
                or next(
                    (m.content[:60] for m in s.messages if m.role == "user"), None
                )
                or s.id[:12],
                "messages": len(s.messages),
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sm.list_sessions(channel="webchat")
            if len(s.messages) > 0
        ]
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        await client.send({"type": "sessions.list.result", "sessions": sessions})

    async def _on_sessions_history(self, client: _Client, msg: dict):
        from opensable.core.session_manager import SessionManager

        sm = SessionManager()
        sid = msg.get("session_id", "")
        s = sm.get_session(sid)
        msgs = [m.to_dict() for m in s.get_messages()] if s else []
        await client.send({"type": "sessions.history.result", "session_id": sid, "messages": msgs})

    # ── Monitor system ────────────────────────────────────────────────────────

    async def _on_monitor_subscribe(self, client: _Client):
        self._monitor_clients.add(client)

        if not self._monitor_agent_wired:
            self._monitor_agent_wired = True

            async def _forward_event(event: str, data: dict):
                payload = {
                    "type": "monitor.event",
                    "event": event,
                    "data": data,
                    "ts": time.time(),
                }
                dead: set[_Client] = set()
                for mc in list(self._monitor_clients):
                    try:
                        await mc.send(payload)
                    except Exception:
                        dead.add(mc)
                self._monitor_clients -= dead

            self.agent.monitor_subscribe(_forward_event)

        await client.send({"type": "monitor.subscribed"})
        await self._on_monitor_snapshot(client)

    async def _on_monitor_snapshot(self, client: _Client):
        if hasattr(self.agent, "get_monitor_snapshot"):
            snapshot = self.agent.get_monitor_snapshot()
            await client.send(snapshot)

    # ── Brain / Cognitive Dashboard ───────────────────────────────────────────

    async def _on_brain_data(self, client: _Client, msg: dict):
        """Return comprehensive cognitive state for the Brain dashboard."""
        result: dict = {"type": "brain.data.result"}

        try:
            # 1. Inner life / emotional state
            inner_life_file = _data_dir / "inner_life" / "inner_state.json"
            if inner_life_file.exists():
                try:
                    result["inner_life"] = json.loads(inner_life_file.read_text())
                except Exception:
                    result["inner_life"] = None
            else:
                result["inner_life"] = None

            # 2. Autonomous state (tick, tasks, etc.)
            auto_state_file = _data_dir / "autonomous_state.json"
            if auto_state_file.exists():
                try:
                    auto = json.loads(auto_state_file.read_text())
                    result["autonomous"] = {
                        "tick": auto.get("tick", 0),
                        "last_update": auto.get("last_update"),
                        "pending_tasks": len(auto.get("task_queue", [])),
                        "completed_tasks_count": len(auto.get("completed_tasks", [])),
                        "task_queue": auto.get("task_queue", [])[:10],
                        "completed_tasks": auto.get("completed_tasks", [])[-20:],
                    }
                except Exception:
                    result["autonomous"] = None
            else:
                result["autonomous"] = None

            # 3. Goals
            goals_file = _data_dir / "goals.json"
            if goals_file.exists():
                try:
                    result["goals"] = json.loads(goals_file.read_text())
                except Exception:
                    result["goals"] = {}
            else:
                result["goals"] = {}

            # 4. ReAct execution log
            react_file = _data_dir / "react_logs" / "react_executions.jsonl"
            if react_file.exists():
                try:
                    execs = []
                    with open(react_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    execs.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["react_executions"] = execs[-50:]
                except Exception:
                    result["react_executions"] = []
            else:
                result["react_executions"] = []

            # 5. Self-reflection / tick outcomes
            reflection_file = _data_dir / "reflection" / "tick_outcomes.jsonl"
            if reflection_file.exists():
                try:
                    outcomes = []
                    with open(reflection_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    outcomes.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["reflections"] = outcomes[-30:]
                except Exception:
                    result["reflections"] = []
            else:
                result["reflections"] = []

            # 6. Cognitive memory stats
            cog_mem_file = _data_dir / "cognitive_memory" / "cognitive_memories.jsonl"
            if cog_mem_file.exists():
                try:
                    count = 0
                    with open(cog_mem_file) as f:
                        for _ in f:
                            count += 1
                    result["cognitive_memory_count"] = count
                except Exception:
                    result["cognitive_memory_count"] = 0
            else:
                result["cognitive_memory_count"] = 0

            # 7. Proactive reasoning proposals
            proactive_file = _data_dir / "proactive" / "proposals.jsonl"
            if proactive_file.exists():
                try:
                    proposals = []
                    with open(proactive_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    proposals.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["proactive_proposals"] = proposals[-20:]
                except Exception:
                    result["proactive_proposals"] = []
            else:
                result["proactive_proposals"] = []

            # 8. Live module stats from agent
            if hasattr(self.agent, "inner_life") and self.agent.inner_life:
                result["inner_life_stats"] = self.agent.inner_life.get_stats()
            if hasattr(self.agent, "autonomous") and self.agent.autonomous:
                result["autonomous_live"] = {
                    "tick": getattr(self.agent.autonomous, "tick", 0),
                    "queue_size": len(getattr(self.agent.autonomous, "task_queue", [])),
                    "completed_count": len(getattr(self.agent.autonomous, "completed_tasks", [])),
                    "consecutive_errors": getattr(self.agent.autonomous, "consecutive_errors", 0),
                }

            # 9. Trace file stats
            traces_dir = _data_dir / "traces"
            if traces_dir.exists():
                trace_files = sorted(traces_dir.glob("trace-*.jsonl"))
                result["trace_files"] = [
                    {"name": f.name, "size_kb": round(f.stat().st_size / 1024, 1)}
                    for f in trace_files[-7:]
                ]
            else:
                result["trace_files"] = []

            # 10. Identity (personality traits, voice, core_directive)
            identity_file = _data_dir / "x_consciousness" / "identity.json"
            if identity_file.exists():
                try:
                    result["identity"] = json.loads(identity_file.read_text())
                except Exception:
                    result["identity"] = None
            else:
                result["identity"] = None

            # 11. Evolution log (personality changes over time)
            evo_file = _data_dir / "x_consciousness" / "evolution_log.json"
            if evo_file.exists():
                try:
                    evo = json.loads(evo_file.read_text())
                    result["evolution_log"] = evo[-10:] if isinstance(evo, list) else []
                except Exception:
                    result["evolution_log"] = []
            else:
                result["evolution_log"] = []

            # 12. Mood history timeline
            mood_file = _data_dir / "x_consciousness" / "mood_history.jsonl"
            if mood_file.exists():
                try:
                    moods = []
                    with open(mood_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    moods.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["mood_history"] = moods[-40:]
                except Exception:
                    result["mood_history"] = []
            else:
                result["mood_history"] = []

            # 13. Inner monologue
            mono_file = _data_dir / "x_consciousness" / "inner_monologue.jsonl"
            if mono_file.exists():
                try:
                    monos = []
                    with open(mono_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    monos.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["inner_monologue"] = monos[-15:]
                except Exception:
                    result["inner_monologue"] = []
            else:
                result["inner_monologue"] = []

            # 14. Self-heal log
            heal_file = _data_dir / "x_consciousness" / "heal_log.jsonl"
            if heal_file.exists():
                try:
                    heals = []
                    with open(heal_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    heals.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass
                    result["heal_log"] = heals[-20:]
                except Exception:
                    result["heal_log"] = []
            else:
                result["heal_log"] = []

            # 15. X agent state (posts/engagements today)
            x_state_file = _data_dir / "x_agent_state.json"
            if x_state_file.exists():
                try:
                    xs = json.loads(x_state_file.read_text())
                    result["x_agent_state"] = {
                        "posts_today": xs.get("posts_today", 0),
                        "engagements_today": xs.get("engagements_today", 0),
                        "last_reset": xs.get("last_reset"),
                        "posted_count": len(xs.get("posted_urls", [])),
                        "engaged_count": len(xs.get("engaged_ids", [])),
                    }
                except Exception:
                    result["x_agent_state"] = None
            else:
                result["x_agent_state"] = None

            # 16. Proactive state (summary)
            proactive_state_file = _data_dir / "proactive" / "proactive_state.json"
            if proactive_state_file.exists():
                try:
                    result["proactive_state"] = json.loads(proactive_state_file.read_text())
                except Exception:
                    result["proactive_state"] = None
            else:
                result["proactive_state"] = None

            # 17. X consciousness reflections
            xc_ref_file = _data_dir / "x_consciousness" / "reflections.json"
            if xc_ref_file.exists():
                try:
                    xc_refs = json.loads(xc_ref_file.read_text())
                    if isinstance(xc_refs, list):
                        result["x_reflections"] = xc_refs[-5:]
                    else:
                        result["x_reflections"] = [xc_refs]
                except Exception:
                    result["x_reflections"] = []
            else:
                result["x_reflections"] = []

            # 18. Journal (consciousness diary)
            journal_file = _data_dir / "x_consciousness" / "journal.jsonl"
            if journal_file.exists():
                try:
                    entries = []
                    with open(journal_file) as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    entries.append(json.loads(line))
                                except Exception:
                                    pass
                    result["journal"] = entries[-20:]
                except Exception:
                    result["journal"] = []
            else:
                result["journal"] = []

            # 19. Calendar
            calendar_file = _data_dir / "calendar.json"
            if not calendar_file.exists():
                calendar_file = Path("data") / "calendar.json"
            if calendar_file.exists():
                try:
                    result["calendar"] = json.loads(calendar_file.read_text())
                except Exception:
                    result["calendar"] = []
            else:
                result["calendar"] = []

            # 20. Conversations (summaries per user)
            convos_dir = _data_dir / "conversations"
            if not convos_dir.exists():
                convos_dir = Path("data") / "conversations"
            result["conversations"] = []
            if convos_dir.exists() and convos_dir.is_dir():
                try:
                    for cf in sorted(convos_dir.glob("*.jsonl")):
                        user_id = cf.stem
                        lines = []
                        with open(cf) as f:
                            for line in f:
                                line = line.strip()
                                if line:
                                    try:
                                        lines.append(json.loads(line))
                                    except Exception:
                                        pass
                        result["conversations"].append({
                            "user_id": user_id,
                            "total_messages": len(lines),
                            "last_messages": lines[-5:],
                        })
                except Exception:
                    pass

            # 21. Benchmarks
            bench_dir = _data_dir / "benchmarks"
            if not bench_dir.exists():
                bench_dir = Path("data") / "benchmarks"
            result["benchmarks"] = []
            if bench_dir.exists() and bench_dir.is_dir():
                try:
                    for bf in sorted(bench_dir.glob("*.json")):
                        try:
                            bd = json.loads(bf.read_text())
                            result["benchmarks"].append({
                                "suite": bd.get("suite", bf.stem),
                                "total": bd.get("total", 0),
                                "passed": bd.get("passed", 0),
                                "failed": bd.get("failed", 0),
                                "pass_rate": bd.get("pass_rate", 0),
                                "avg_score": bd.get("avg_score", 0),
                                "avg_duration_ms": bd.get("avg_duration_ms", 0),
                                "model": bd.get("model", ""),
                                "agent_version": bd.get("agent_version", ""),
                                "started_at": bd.get("started_at", ""),
                            })
                        except Exception:
                            pass
                except Exception:
                    pass

        except Exception as e:
            logger.warning(f"[Gateway] brain.data error: {e}")
            result["error"] = str(e)

        await client.send(result)

    # ── Thoughts / Consciousness stream ───────────────────────────────────────

    async def _on_thoughts_list(self, client: _Client, msg: dict):
        limit = min(int(msg.get("limit", 200)), 1000)
        filter_type = msg.get("filter")

        base = _data_dir / "x_consciousness"
        result: dict = {"type": "thoughts.list.result"}

        # Journal
        journal_entries: list = []
        journal_file = base / "journal.jsonl"
        if journal_file.exists():
            try:
                with open(journal_file) as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            entry = json.loads(line)
                            if filter_type and entry.get("type") != filter_type:
                                continue
                            journal_entries.append(entry)
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
        result["journal"] = journal_entries[-limit:]

        # Inner monologue
        thoughts: list = []
        thoughts_file = base / "inner_monologue.jsonl"
        if thoughts_file.exists():
            try:
                with open(thoughts_file) as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                thoughts.append(json.loads(line))
                            except json.JSONDecodeError:
                                pass
            except Exception:
                pass
        result["thoughts"] = thoughts[-limit:]

        # Reflections
        reflections_file = base / "reflections.json"
        if reflections_file.exists():
            try:
                with open(reflections_file) as f:
                    result["reflections"] = json.loads(f.read())[-50:]
            except Exception:
                result["reflections"] = []
        else:
            result["reflections"] = []

        # Current emotional state
        xauto = getattr(self.agent, "x_autoposter", None)
        if xauto and hasattr(xauto, "mind"):
            mind = xauto.mind
            result["mood"] = {
                "current": getattr(mind, "_mood", "unknown"),
                "intensity": getattr(mind, "_mood_intensity", 0),
                "history": getattr(mind, "_mood_history", [])[-20:],
            }
            result["memory_stats"] = (
                mind.get_memory_stats() if hasattr(mind, "get_memory_stats") else {}
            )
        else:
            last_felt = next(
                (e for e in reversed(journal_entries) if e.get("type") == "felt"), None
            )
            if last_felt and isinstance(last_felt.get("data"), dict):
                d = last_felt["data"]
                result["mood"] = {
                    "current": d.get("emotion", "unknown"),
                    "intensity": d.get("intensity", 0),
                    "history": [],
                }
            else:
                result["mood"] = {"current": "unknown", "intensity": 0, "history": []}
            result["memory_stats"] = {}

        await client.send(result)

    # ── Node system ───────────────────────────────────────────────────────────

    async def _on_node_register(self, client: _Client, msg: dict):
        node_id = msg.get("node_id", client.cid)
        caps = msg.get("capabilities", [])

        self._nodes[node_id] = client
        client.node_id = node_id

        logger.info(f"[Gateway] Node registered: {node_id}  caps={caps}")
        await client.send({"type": "node.registered", "node_id": node_id, "capabilities": caps})

    async def _on_node_invoke(self, client: _Client, msg: dict):
        node_id = msg.get("node_id", "")
        cap = msg.get("capability", "")
        args = msg.get("args", {})
        req_id = msg.get("request_id", str(time.time()))

        node = self._nodes.get(node_id)
        if not node:
            await client.send(
                {"type": "error", "text": f"Node '{node_id}' not connected", "request_id": req_id}
            )
            return

        await node.send({
            "type": "node.invoke",
            "capability": cap,
            "args": args,
            "request_id": req_id,
            "reply_to": client.cid,
        })

    async def _on_node_result(self, client: _Client, msg: dict):
        reply_to = msg.get("reply_to", "")
        target = next((c for c in self._clients if c.cid == reply_to), None)
        if target:
            await target.send({**msg, "type": "node.result"})

    # ── Rate limiting ─────────────────────────────────────────────────────────

    def _check_rate(self, cid: str) -> bool:
        now = time.time()
        stamps = self._rate_limits.setdefault(cid, [])
        cutoff = now - self._rate_window
        self._rate_limits[cid] = [t for t in stamps if t > cutoff]
        if len(self._rate_limits[cid]) >= self._rate_max:
            return False
        self._rate_limits[cid].append(now)
        return True

    # ── Heartbeat ─────────────────────────────────────────────────────────────

    async def _heartbeat(self):
        while self._running:
            try:
                await asyncio.sleep(HEARTBEAT_INT)
                dead: set[_Client] = set()
                ts = time.time()
                for c in list(self._clients):
                    try:
                        await c.send({"type": "heartbeat", "ts": ts})
                    except Exception:
                        dead.add(c)
                self._clients -= dead
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug(f"[Gateway] Heartbeat error: {exc}")

    # ── Broadcast helper ──────────────────────────────────────────────────────

    async def broadcast(self, payload: dict, *, exclude: Optional[_Client] = None):
        dead: set[_Client] = set()
        for c in list(self._clients):
            if c is exclude:
                continue
            try:
                await c.send(payload)
            except Exception:
                dead.add(c)
        self._clients -= dead


# ── Compat alias used by cli.py ───────────────────────────────────────────────
GatewayServer = Gateway
