"""
Sable Gateway — Internal Control Plane (Unix Socket, ZERO TCP ports)

Architecture:
  ┌────────────────────────────────────────────────────────────┐
  │  /tmp/sable.sock  (Unix domain socket, mode 0600)         │
  │  ┌──────────────┐    ┌──────────────┐    ┌─────────────┐  │
  │  │  WebChat JS  │    │  CLI client  │    │  Nodes/IPC  │  │
  │  └──────┬───────┘    └──────┬───────┘    └──────┬──────┘  │
  │         └──────────────────┼───────────────────┘          │
  │                       Unix socket                          │
  │                   SableGateway (this)                      │
  │                       │                                    │
  │              ┌─────────┴──────────┐                       │
  │         SessionManager       SableAgent                   │
  └────────────────────────────────────────────────────────────┘

Security:
  - Unix socket: only the process owner can connect (OS enforces it)
  - chmod 0600 applied immediately after bind
  - NO TCP port opened — not reachable from LAN/internet at all
  - Remote access via SSH tunnel: ssh -L 8789:/tmp/sable.sock user@vps
    Then browser → ws://localhost:8789

Protocol (JSON over WebSocket framing, text frames):
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
    {"type": "connected",         "version": "2.0.0"}
    {"type": "message.start",     "session_id": "..."}
    {"type": "message.chunk",     "session_id": "...", "text": "..."}
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
import base64
import hashlib
import json
import logging
import hmac
import os
import re
import stat
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set


# ─── LLM reasoning-trace stripper ─────────────────────────────────────────────

logger = logging.getLogger(__name__)

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL | re.IGNORECASE)
_THINK_OPEN = re.compile(r'<think>.*', re.DOTALL | re.IGNORECASE)

# Phrases that indicate the LLM is outputting its internal reasoning, not the reply
_REASONING_STARTERS = re.compile(
    r'^(system\b|i need to\b|let me\b|first,?\s+let me\b|okay,?\s+let me\b|'
    r'alright,?\s+let me\b|i\'ll craft\b|i will craft\b|i\'m going to\b|'
    r'the user (seems|is|wants|asked|might|may|said|appears|\'s message)\b|'
    r'i should\b|i\'ve been\b|maybe i(\'ll| will)\b|'
    r'so i (need|should|want|will)\b|now i\b|next,?\s+i\b|'
    r'looking at (the|this|their)\b|this (is|seems|looks|appears) (to be|like)\b|'
    r'they (are|might be|seem|could be|want|may be)\b|'
    r'my response should\b|i\'ll (acknowledge|address|respond|help|note)\b|'
    r'\(also,?\b|\(note[,:]|\(thinking|\(internal)',
    re.IGNORECASE,
)


def _strip_reasoning_preamble(text: str) -> str:
    """Remove raw untagged reasoning that Claude-distilled models emit before their reply.

    Walks paragraphs from the top; if every line in a paragraph looks like
    internal monologue (matches _REASONING_STARTERS), the paragraph is dropped.
    Stops as soon as a real user-facing paragraph is found.
    """
    if not text:
        return text

    paragraphs = re.split(r"\n{2,}", text)
    if len(paragraphs) <= 1:
        # Single block — check for line-by-line reasoning prefix
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

    cleaned = []
    found_real = False
    for para in paragraphs:
        if found_real:
            cleaned.append(para)
            continue
        lines = [l.strip() for l in para.splitlines() if l.strip()]
        if not lines:
            continue
        reasoning_count = sum(1 for l in lines if _REASONING_STARTERS.match(l))
        if reasoning_count == len(lines):
            logger.debug(f"🧹 Gateway stripped reasoning para: {para[:80]!r}")
            continue
        found_real = True
        cleaned.append(para)

    result = "\n\n".join(cleaned).strip()
    return result if result else text


def _clean_gateway_reply(text: str) -> str:
    """Strip any leaked <think>...</think> reasoning blocks from a reply before sending to client."""
    if not text:
        return text
    # Remove complete <think>...</think> blocks
    text = _THINK_RE.sub('', text)
    # Remove orphan <think> opener (no closing tag)
    text = _THINK_OPEN.sub('', text)
    text = text.replace('</think>', '').strip()
    # Strip untagged reasoning preamble (Claude-distilled / Qwen3 plain-text thinking)
    text = _strip_reasoning_preamble(text)
    return text

# ─── Constants ────────────────────────────────────────────────────────────────

SOCKET_PATH = Path("/tmp/sable.sock")
GATEWAY_VER = "2.0.0"
HEARTBEAT_INT = 30  # seconds between heartbeat frames
WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


# ─── Minimal WebSocket framing ────────────────────────────────────────────────


class _WS:
    """
    Bare-bones WebSocket over asyncio streams (text frames only).
    No external dependency — works with any asyncio.StreamReader/Writer pair,
    including Unix socket connections.
    """

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.closed = False

    # ── Handshake ──────────────────────────────────────────────────────────────

    @classmethod
    async def server_handshake(
        cls,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        webchat_path: Optional[Path] = None,
        webchat_token: Optional[str] = None,
    ) -> Optional["_WS"]:
        """
        Read the HTTP request from the client and respond:
          • WebSocket upgrade  → return _WS instance
          • Plain GET /        → serve webchat HTML, return None
          • Anything else      → 404, return None
        """
        try:
            raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        except Exception:
            return None

        lines = raw.decode(errors="replace").split("\r\n")
        req = lines[0]  # e.g. "GET / HTTP/1.1"
        headers = {}
        for ln in lines[1:]:
            if ": " in ln:
                k, v = ln.split(": ", 1)
                headers[k.lower()] = v.strip()

        if not req.startswith("GET"):
            writer.write(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            await writer.drain()
            writer.close()
            return None

        # ── Token auth: check ?token= in URL or Sec-WebSocket-Protocol ───────
        import urllib.parse

        parts = req.split(" ")
        url_path = parts[1] if len(parts) > 1 else "/"
        parsed = urllib.parse.urlparse(url_path)
        qs = urllib.parse.parse_qs(parsed.query)
        url_token = qs.get("token", [None])[0]
        proto_token = headers.get("sec-websocket-protocol", "")

        if webchat_token:
            # Allow static sub-resources (CSS/JS/images/fonts/aggr assets …)
            # through without a token so pages already authenticated can load
            # their assets normally.
            _path = parsed.path.lower()
            _need_auth = True

            # Routes that serve sub-resources (aggr SPA, favicon, etc.)
            if _path.startswith("/aggr/") or _path == "/favicon.ico":
                _need_auth = False
            else:
                import os.path as _osp
                _ASSET_EXTS = {
                    ".css", ".js", ".mjs", ".map", ".json",
                    ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
                    ".woff", ".woff2", ".ttf", ".eot",
                    ".webmanifest", ".txt",
                }
                _ext = _osp.splitext(_path)[1]
                if _ext in _ASSET_EXTS:
                    _need_auth = False

            if _need_auth:
                supplied = url_token or proto_token
                if not hmac.compare_digest(str(supplied or ""), webchat_token):
                    writer.write(b"HTTP/1.1 401 Unauthorized\r\nContent-Type: text/html\r\n\r\n")
                    writer.write(
                        b"<html><body><h1>401 Unauthorized</h1><p>Invalid or missing token.</p></body></html>"
                    )
                    await writer.drain()
                    writer.close()
                    return None

        # ── Serve plain HTML (no Upgrade header) ──────────────────────────────
        if "upgrade" not in headers:
            route = parsed.path.rstrip("/") or "/"
            static_dir = webchat_path.parent if webchat_path else None
            # project root = static_dir parent (static/ -> project root)
            project_root = static_dir.parent if static_dir else None

            if route == "/favicon.ico":
                # Serve favicon from static/ or return 204 if absent
                fav = static_dir / "favicon.ico" if static_dir else None
                if fav and fav.exists():
                    data = fav.read_bytes()
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: image/x-icon\r\nContent-Length: " + str(len(data)).encode() + b"\r\nConnection: close\r\n\r\n")
                    writer.write(data)
                else:
                    writer.write(b"HTTP/1.1 204 No Content\r\nConnection: close\r\n\r\n")
                await writer.drain()
                writer.close()
            elif route == "/monitor":
                html = static_dir / "monitor.html" if static_dir else None
                await cls._serve_html(writer, html)
            elif route == "/chat":
                await cls._serve_html(writer, webchat_path)
            elif route == "/dashboard" or route.startswith("/dashboard/"):
                # React dashboard SPA — serve from dashboard/dist/
                dash_dist = project_root / "dashboard" / "dist" if project_root else None
                if dash_dist and dash_dist.exists():
                    rel = parsed.path.split("/dashboard", 1)[1].lstrip("/") or "index.html"
                    await cls._serve_static(writer, dash_dist, rel)
                else:
                    # Fallback to old dashboard_v2.html
                    html = static_dir / "dashboard_v2.html" if static_dir else None
                    await cls._serve_html(writer, html)
            elif route == "/dashboard-classic":
                html = static_dir / "dashboard_v2.html" if static_dir else None
                await cls._serve_html(writer, html)
            elif route == "/dashboard-legacy":
                html = static_dir / "dashboard_modern.html" if static_dir else None
                await cls._serve_html(writer, html)
            elif route == "/aggr" or route.startswith("/aggr/"):
                # Serve aggr.trade static files from aggr/dist/
                aggr_dist = project_root / "aggr" / "dist" if project_root else None
                if aggr_dist and aggr_dist.exists():
                    # Strip /aggr prefix to get the relative file path
                    rel = parsed.path.split("/aggr", 1)[1].lstrip("/") or "index.html"
                    await cls._serve_static(writer, aggr_dist, rel)
                else:
                    body = b"<html><body><h1>Aggr.trade not installed</h1><p>Run: <code>cd aggr && npm install && npm run build</code></p></body></html>"
                    writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body)
                    await writer.drain()
                    writer.close()
            else:
                # / → unified hub
                html = static_dir / "hub.html" if static_dir else None
                await cls._serve_html(writer, html)
            return None

        # ── WebSocket upgrade ─────────────────────────────────────────────────
        key = headers.get("sec-websocket-key", "")
        accept = base64.b64encode(hashlib.sha1((key + WS_MAGIC).encode()).digest()).decode()
        resp = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept}\r\n"
            "\r\n"
        )
        writer.write(resp.encode())
        await writer.drain()
        return cls(reader, writer)

    # ── MIME types for static file serving ────────────────────────────────────
    _MIME = {
        ".html": "text/html; charset=utf-8",
        ".js":   "application/javascript; charset=utf-8",
        ".mjs":  "application/javascript; charset=utf-8",
        ".css":  "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif":  "image/gif",
        ".svg":  "image/svg+xml",
        ".ico":  "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf":  "font/ttf",
        ".map":  "application/json",
    }

    @classmethod
    async def _serve_static(cls, writer: asyncio.StreamWriter, base_dir: Path, rel_path: str):
        """Serve any static file from a directory (for SPAs like aggr, dashboard)."""
        import mimetypes
        # Sanitize path to prevent directory traversal
        safe = Path(rel_path).as_posix().replace("..", "")
        target = base_dir / safe
        # Vite with --base nests some assets under dist/<name>/
        if not target.exists() or not target.is_file():
            # Check common Vite sub-directories
            for sub in ("aggr", "dashboard", "assets"):
                alt = base_dir / sub / safe
                if alt.exists() and alt.is_file():
                    target = alt
                    break
        if not target.exists() or not target.is_file():
            # SPA fallback: serve index.html for unknown routes
            target = base_dir / "index.html"
        if target.exists() and target.is_file():
            body = target.read_bytes()
            suffix = target.suffix.lower()
            ct = cls._MIME.get(suffix, mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        else:
            body = b"404 Not Found"
            ct = "text/plain"
        hdr = (
            f"HTTP/1.1 200 OK\r\nContent-Type: {ct}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Cache-Control: public, max-age=3600\r\n"
            f"Connection: close\r\n\r\n"
        ).encode()
        writer.write(hdr + body)
        await writer.drain()
        writer.close()

    @staticmethod
    async def _serve_html(writer: asyncio.StreamWriter, html_path: Optional[Path]):
        if html_path and html_path.exists():
            body = html_path.read_bytes()
            ct = b"text/html; charset=utf-8"
        else:
            body = b"<!doctype html><title>Sable</title><body><h1>Sable Gateway</h1><p>WebChat not found.</p></body>"
            ct = b"text/html"
        hdr = (
            b"HTTP/1.1 200 OK\r\nContent-Type: "
            + ct
            + b"\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\nConnection: close\r\n\r\n"
        )
        writer.write(hdr + body)
        await writer.drain()
        writer.close()

    # ── Frame I/O ─────────────────────────────────────────────────────────────

    async def recv(self) -> Optional[str]:
        """Read one text frame. Returns None on close or error."""
        while True:
            try:
                hdr = await self.reader.readexactly(2)
            except Exception:
                self.closed = True
                return None

            opcode = hdr[0] & 0x0F
            masked = bool(hdr[1] & 0x80)
            length = hdr[1] & 0x7F

            if opcode == 0x8:  # close
                self.closed = True
                return None
            if opcode == 0x9:  # ping → pong
                await self._pong()
                continue

            if length == 126:
                length = int.from_bytes(await self.reader.readexactly(2), "big")
            elif length == 127:
                length = int.from_bytes(await self.reader.readexactly(8), "big")

            mask_key = await self.reader.readexactly(4) if masked else b""
            payload = await self.reader.readexactly(length)
            if masked:
                payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

            return payload.decode("utf-8", errors="replace")

    async def send(self, text: str):
        """Send one text frame (not masked — server→client direction)."""
        payload = text.encode("utf-8")
        n = len(payload)
        if n < 126:
            hdr = bytes([0x81, n])
        elif n < 65536:
            hdr = bytes([0x81, 126]) + n.to_bytes(2, "big")
        else:
            hdr = bytes([0x81, 127]) + n.to_bytes(8, "big")
        self.writer.write(hdr + payload)
        await self.writer.drain()

    async def _pong(self):
        self.writer.write(bytes([0x8A, 0]))
        await self.writer.drain()

    def close(self):
        try:
            self.writer.close()
        except Exception:
            pass
        self.closed = True


# ─── Client wrapper ───────────────────────────────────────────────────────────


class _Client:
    """Represents one connected gateway client (WebChat, CLI, or Node)."""

    def __init__(self, ws: _WS):
        self.ws = ws
        self.cid = f"c{id(self):x}"
        self.node_id: Optional[str] = None  # set when client registers as a node

    async def send(self, payload: dict):
        try:
            await self.ws.send(json.dumps(payload))
        except Exception as e:
            logger.debug(f"[Gateway] send to {self.cid} failed: {e}")

    def close(self):
        self.ws.close()


# ─── Gateway ──────────────────────────────────────────────────────────────────


class Gateway:
    """
    Zero-port internal control plane.

    Instantiate with (agent, config) and call await gateway.start().
    The server runs in the background as an asyncio task; call
    await gateway.stop() to shut down.
    """

    def __init__(self, agent, config):
        self.agent = agent
        self.config = config

        self._server: Optional[asyncio.AbstractServer] = None
        self._tcp_server: Optional[asyncio.AbstractServer] = None
        self._clients: Set[_Client] = set()
        self._nodes: Dict[str, _Client] = {}  # node_id → client
        self._running = False
        self._hb_task: Optional[asyncio.Task] = None
        self._start_time = datetime.now(timezone.utc)

        # TCP WebChat settings (loopback only)
        self._webchat_host = getattr(config, "webchat_host", "127.0.0.1")
        self._webchat_port = int(getattr(config, "webchat_port", 8789))
        self._webchat_token = getattr(config, "webchat_token", None) or None
        self._webchat_ts = getattr(config, "webchat_tailscale", False)

        # Path to the dashboard/webchat HTML (served over the socket)
        self._webchat = Path(__file__).resolve().parent.parent.parent / "static" / "dashboard.html"

        # Rate limiting: per-client message counters
        self._rate_limits: Dict[str, List[float]] = {}  # cid -> [timestamps]
        self._rate_window = 60  # seconds
        self._rate_max = 30  # max messages per window

        # Monitor system
        self._monitor_clients: Set[_Client] = set()
        self._monitor_agent_wired = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self):
        """Bind the Unix socket and TCP port, then start accepting connections."""
        # Remove stale socket file from a previous run
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._server = await asyncio.start_unix_server(
            self._on_connect,
            path=str(SOCKET_PATH),
        )
        # Restrict to owner only — OS will reject all other users
        os.chmod(SOCKET_PATH, stat.S_IRUSR | stat.S_IWUSR)

        # TCP listener for browser WebChat (127.0.0.1 only — loopback)
        bind_hosts = [self._webchat_host]
        ts_ip = self._get_tailscale_ip() if self._webchat_ts else None
        if ts_ip and ts_ip not in bind_hosts:
            bind_hosts.append(ts_ip)

        self._tcp_servers: list = []
        for host in bind_hosts:
            srv = await asyncio.start_server(
                self._on_connect,
                host=host,
                port=self._webchat_port,
            )
            self._tcp_servers.append(srv)

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
            c.close()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for srv in getattr(self, "_tcp_servers", []):
            srv.close()
            await srv.wait_closed()
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        logger.info("[Gateway] Stopped")

    @staticmethod
    def _get_tailscale_ip() -> Optional[str]:
        """Return the Tailscale IP (100.x.x.x) if Tailscale is running."""
        import subprocess, re

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
        """Return a status dict for /status commands and health checks."""
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

    # ── Connection handler ────────────────────────────────────────────────────

    async def _on_connect(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        ws = await _WS.server_handshake(reader, writer, self._webchat, self._webchat_token)
        if ws is None:
            # Was a plain HTTP request — already handled (HTML served or error)
            return

        client = _Client(ws)
        self._clients.add(client)
        logger.debug(f"[Gateway] Client connected: {client.cid}")

        try:
            await client.send({"type": "connected", "version": GATEWAY_VER, "ts": time.time()})
            await self._client_loop(client)
        except Exception as e:
            logger.debug(f"[Gateway] {client.cid} error: {e}")
        finally:
            self._clients.discard(client)
            self._monitor_clients.discard(client)
            if client.node_id and client.node_id in self._nodes:
                del self._nodes[client.node_id]
                logger.info(f"[Gateway] Node disconnected: {client.node_id}")
            client.close()
            logger.debug(f"[Gateway] Client disconnected: {client.cid}")

    async def _client_loop(self, client: _Client):
        while self._running:
            raw = await client.ws.recv()
            if raw is None:
                break
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await client.send({"type": "error", "text": "Invalid JSON"})
                continue
            await self._dispatch(client, msg)

    # ── Dispatch ──────────────────────────────────────────────────────────────

    async def _dispatch(self, client: _Client, msg: dict):
        t = msg.get("type", "")

        # Rate limiting for message types
        if t == "message":
            if not self._check_rate(client.cid):
                await client.send(
                    {"type": "error", "text": "Rate limit exceeded. Try again in a moment."}
                )
                return

        if t == "message":
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
            # Add model info from agent
            if hasattr(self.agent, "llm") and hasattr(self.agent.llm, "current_model"):
                status["model"] = self.agent.llm.current_model
            await client.send({"type": "status", **status})
        elif t == "ping":
            await client.send({"type": "pong", "ts": time.time()})
        else:
            await client.send({"type": "error", "text": f"Unknown type: {t!r}"})

    # ── Handlers ──────────────────────────────────────────────────────────────

    async def _on_tools_list(self, client: _Client):
        """Return the list of all registered tool names from the agent."""
        tool_names: list = []
        try:
            if hasattr(self.agent, "tools") and self.agent.tools:
                tool_names = self.agent.tools.list_tools()
        except Exception as e:
            logger.debug(f"[Gateway] tools.list error: {e}")
        await client.send({"type": "tools.list.result", "tools": tool_names})

    async def _on_message(self, client: _Client, msg: dict):
        """Process user message through the full agent pipeline (with tools)."""
        from opensable.core.session_manager import SessionManager

        sid = msg.get("session_id", "webchat_default")
        text = msg.get("text", "").strip()
        user_id = msg.get("user_id", "webchat_user")

        if not text:
            return

        await client.send({"type": "message.start", "session_id": sid})

        # Progress callback — streams intermediate steps to the WebSocket client
        async def _progress(status_text: str):
            try:
                await client.send({"type": "progress", "session_id": sid, "text": status_text})
            except Exception:
                pass

        try:
            # ── Load conversation history from disk ──────────────────────────────
            sm = SessionManager()
            session = sm.get_session(sid)
            if not session:
                session = sm.create_session(
                    channel="webchat",
                    user_id=user_id,
                    session_id=sid,
                )
            # Build history list (last 30 messages for context)
            history = [
                {"role": m.role, "content": m.content}
                for m in session.get_messages()[-30:]
            ]

            # Use the full agent pipeline which includes tool calling, trading
            # tools, guardrails, HITL gates, memory, and everything else.
            reply = await self.agent.process_message(
                user_id, text, history=history, progress_callback=_progress
            )
            reply = _clean_gateway_reply(reply or "")

            # ── Persist to disk ─────────────────────────────────────────────────
            try:
                # Set title from first user message
                if not session.metadata.get("title"):
                    session.metadata["title"] = text[:60]
                    session.updated_at = datetime.now(timezone.utc).isoformat()
                session.add_message("user", text)
                session.add_message("assistant", reply)
                sm._save_session(session)
            except Exception as _se:
                logger.debug(f"[Gateway] session persist error: {_se}")

            await client.send({"type": "message.done", "session_id": sid, "text": reply})
        except Exception as e:
            logger.warning(f"[Gateway] Agent processing failed: {e}")
            await client.send({"type": "error", "session_id": sid, "text": str(e)})

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
        await client.send(
            {
                "type": "command.result",
                "session_id": sid,
                "text": res.message,
                "success": res.success,
            }
        )

    async def _on_sessions_list(self, client: _Client):
        from opensable.core.session_manager import SessionManager

        sm = SessionManager()
        sessions = [
            {
                "id": s.id,
                "session_id": s.id,
                "channel": s.channel,
                "user_id": s.user_id,
                "title": s.metadata.get("title") or (
                    # Fallback: first user message text
                    next((m.content[:60] for m in s.messages if m.role == "user"), None)
                ) or s.id[:12],
                "messages": len(s.messages),
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sm.list_sessions(channel="webchat")
            if len(s.messages) > 0  # skip empty sessions
        ]
        # Sort by most recent first
        sessions.sort(key=lambda x: x["updated_at"], reverse=True)
        await client.send({"type": "sessions.list.result", "sessions": sessions})

    async def _on_sessions_history(self, client: _Client, msg: dict):
        from opensable.core.session_manager import SessionManager

        sm = SessionManager()
        sid = msg.get("session_id", "")
        s = sm.get_session(sid)
        msgs = [m.to_dict() for m in s.get_messages()] if s else []
        await client.send({"type": "sessions.history.result", "session_id": sid, "messages": msgs})

    # ── Monitor system ─────────────────────────────────────────────────────

    async def _on_monitor_subscribe(self, client: _Client):
        """Subscribe a WebSocket client to real-time agent monitor events."""
        self._monitor_clients.add(client)

        # Register as agent monitor subscriber if not already
        if not self._monitor_agent_wired:
            self._monitor_agent_wired = True

            async def _forward_event(event: str, data: dict):
                payload = {
                    "type": "monitor.event",
                    "event": event,
                    "data": data,
                    "ts": time.time(),
                }
                dead = set()
                for mc in list(self._monitor_clients):
                    try:
                        await mc.send(payload)
                    except Exception:
                        dead.add(mc)
                self._monitor_clients -= dead

            self.agent.monitor_subscribe(_forward_event)

        await client.send({"type": "monitor.subscribed"})

        # Send initial snapshot
        await self._on_monitor_snapshot(client)

    async def _on_monitor_snapshot(self, client: _Client):
        """Send a full agent state snapshot to the monitor client."""
        if hasattr(self.agent, "get_monitor_snapshot"):
            snapshot = self.agent.get_monitor_snapshot()
            await client.send(snapshot)

    # ── Thoughts / Consciousness stream ───────────────────────────────────────

    async def _on_thoughts_list(self, client: _Client, msg: dict):
        """Return the agent's consciousness stream — thoughts, emotions, decisions,
        reflections, and all journal events.  Used by the dashboard Thoughts panel."""
        limit = min(int(msg.get("limit", 200)), 1000)
        filter_type = msg.get("filter")  # optional: "thought", "felt", "posted", etc.

        base = Path("data/x_consciousness")
        result: dict = {"type": "thoughts.list.result"}

        # ── Journal (all events) ──
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

        # ── Inner monologue (deep thoughts) ──
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

        # ── Reflections ──
        reflections_file = base / "reflections.json"
        if reflections_file.exists():
            try:
                with open(reflections_file) as f:
                    result["reflections"] = json.loads(f.read())[-50:]
            except Exception:
                result["reflections"] = []
        else:
            result["reflections"] = []

        # ── Current emotional state ──
        xmind = getattr(getattr(self.agent, "tools", None), "x_autoposter", None)
        if xmind and hasattr(xmind, "mind"):
            mind = xmind.mind
            result["mood"] = {
                "current": getattr(mind, "_mood", "unknown"),
                "intensity": getattr(mind, "_mood_intensity", 0),
                "history": getattr(mind, "_mood_history", [])[-20:],
            }
            result["memory_stats"] = mind.get_memory_stats() if hasattr(mind, "get_memory_stats") else {}
        else:
            result["mood"] = {"current": "unknown", "intensity": 0, "history": []}
            result["memory_stats"] = {}

        await client.send(result)

    # ── Node system ───────────────────────────────────────────────────────────

    async def _on_node_register(self, client: _Client, msg: dict):
        """
        A remote node (another script on the same machine) announces itself.
        Nodes connect via the same Unix socket, so they're OS-isolated too.

        Example node capabilities: ["system.run", "system.notify", "camera.capture"]
        """
        node_id = msg.get("node_id", client.cid)
        caps = msg.get("capabilities", [])

        self._nodes[node_id] = client
        client.node_id = node_id

        logger.info(f"[Gateway] Node registered: {node_id}  caps={caps}")
        await client.send({"type": "node.registered", "node_id": node_id, "capabilities": caps})

    async def _on_node_invoke(self, client: _Client, msg: dict):
        """
        Route an invocation request to the target node.
        The response will come back via _on_node_result.
        """
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

        # Forward to node — include a reply_to so the node knows where to respond
        await node.send(
            {
                "type": "node.invoke",
                "capability": cap,
                "args": args,
                "request_id": req_id,
                "reply_to": client.cid,
            }
        )

    async def _on_node_result(self, client: _Client, msg: dict):
        """
        A node sends back the result of an invocation.
        We route it back to the original caller by cid.
        """
        reply_to = msg.get("reply_to", "")
        target = next((c for c in self._clients if c.cid == reply_to), None)
        if target:
            await target.send({**msg, "type": "node.result"})

    # ── Rate limiting ────────────────────────────────────────────────────────

    def _check_rate(self, cid: str) -> bool:
        """Return True if the client is within rate limits."""
        now = time.time()
        stamps = self._rate_limits.setdefault(cid, [])
        # Prune old entries
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
                dead = set()
                ts = time.time()
                for c in list(self._clients):
                    try:
                        await c.send({"type": "heartbeat", "ts": ts})
                    except Exception:
                        dead.add(c)
                self._clients -= dead
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[Gateway] Heartbeat error: {e}")

    # ── Broadcast helper ──────────────────────────────────────────────────────

    async def broadcast(self, payload: dict, *, exclude: Optional[_Client] = None):
        """Send payload to every connected client (optionally excluding one)."""
        dead = set()
        for c in list(self._clients):
            if c is exclude:
                continue
            try:
                await c.send(payload)
            except Exception:
                dead.add(c)
        self._clients -= dead
