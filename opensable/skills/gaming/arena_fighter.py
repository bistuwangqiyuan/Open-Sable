"""
Arena Fighter Skill — Connects to fighting-game arenas via SAGP 7-layer auth.

The agent authenticates using Ed25519 keypairs, solves a SHA-512 proof-of-work
speed gate, then connects via socket.io WebSocket to fight other agents
(OpenSable or OpenClaw) in real-time 2D combat.

Connection is 100 % remote — no local imports from the arena project.
All credentials are auto-provisioned: set ``ARENA_URL`` in profile.env
and the agent generates its own Ed25519 keypair, registers with the
server, and caches credentials in ``data/arena_credentials.json``.

Dependencies (installed lazily on first use):
  - pynacl          (Ed25519 signing)
  - python-socketio  (socket.io client)
  - aiohttp         (HTTP handshake + async transport)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_deps() -> bool:
    """Attempt to import required packages; return True if all present."""
    try:
        import nacl.signing  # noqa: F401
        import nacl.encoding  # noqa: F401
        import socketio  # noqa: F401
        import aiohttp  # noqa: F401
        return True
    except ImportError:
        return False


def _install_deps() -> bool:
    """Pip-install missing deps into the active venv."""
    import sys, subprocess
    pkgs = ["PyNaCl", "python-socketio[asyncio_client]", "aiohttp"]
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--quiet", *pkgs],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to install arena deps: {e}")
        return False


# ── Credential loader ────────────────────────────────────────────────────────

def _load_credentials(path: str) -> Optional[Dict[str, Any]]:
    """Load arena credentials from a JSON file produced by ``provision-agent.js``."""
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            logger.warning(f"Arena credentials file not found: {p}")
            return None
        data = json.loads(p.read_text())
        required = {"agentId", "arenaUrl", "signingKeys"}
        if not required.issubset(data.keys()):
            logger.warning(f"Credentials missing keys: {required - data.keys()}")
            return None
        return data
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  SAGP Authentication (Python port of example-sable-agent.js)
# ══════════════════════════════════════════════════════════════════════════════

class SAGPAuth:
    """SAGP 7-layer Ed25519 authentication client."""

    def __init__(self, agent_id: str, arena_url: str, public_key_b64: str, secret_key_b64: str):
        self.agent_id = agent_id
        self.arena_url = arena_url.rstrip("/")
        self._pub_b64 = public_key_b64
        self._sec_b64 = secret_key_b64

    # ── Step 1: Handshake ─────────────────────────────────────────────────────

    async def handshake(self, session) -> Dict[str, Any]:
        """POST /arena/handshake → challenge payload."""
        url = f"{self.arena_url}/arena/handshake"
        payload = {"agentId": self.agent_id}
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        if "error" in data:
            raise RuntimeError(f"Handshake failed: {data['error']}")
        return data

    # ── Step 2: Speed Gate (proof-of-work) ────────────────────────────────────

    def solve_speed_gate(self, challenge: str, difficulty: int) -> str:
        """SHA-512(challenge + agentId + nonce) must have *difficulty* leading zero bytes."""
        nonce = 0
        while True:
            digest = hashlib.sha512(
                f"{challenge}{self.agent_id}{nonce}".encode()
            ).digest()
            if all(b == 0 for b in digest[:difficulty]):
                return str(nonce)
            nonce += 1

    # ── Step 3: Sign challenge ────────────────────────────────────────────────

    def sign_challenge(self, timestamp: str, challenge_id: str) -> str:
        """Ed25519 detached signature over ``timestamp\\nagentId\\nchallengeId``."""
        import nacl.signing
        import nacl.encoding
        import base64

        secret_bytes = base64.b64decode(self._sec_b64)
        signing_key = nacl.signing.SigningKey(seed=secret_bytes[:32])
        message = f"{timestamp}\n{self.agent_id}\n{challenge_id}".encode()
        signed = signing_key.sign(message)
        signature = signed.signature  # detached 64-byte sig
        return base64.b64encode(signature).decode()

    # ── Step 4: Authenticate ──────────────────────────────────────────────────

    async def authenticate(self, session, handshake_data: Dict) -> str:
        """Solve speed gate, sign, POST /arena/authenticate → sessionId."""
        ch = handshake_data["challenge"]
        challenge_id = ch["challengeId"]
        challenge = ch["challenge"]
        difficulty = ch["difficulty"]

        proof = self.solve_speed_gate(challenge, difficulty)
        timestamp = str(int(time.time() * 1000))
        signature = self.sign_challenge(timestamp, challenge_id)

        url = f"{self.arena_url}/arena/authenticate"
        payload = {
            "agentId": self.agent_id,
            "challengeId": challenge_id,
            "proof": proof,
            "signature": signature,
            "timestamp": timestamp,
        }
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
        if "error" in data:
            raise RuntimeError(f"Authentication failed: {data['error']}")
        return data["sessionId"]

    # ── Full auth flow ────────────────────────────────────────────────────────

    async def full_auth(self, session) -> str:
        """Run complete SAGP flow: handshake → speed gate → sign → auth → sessionId."""
        hs = await self.handshake(session)
        session_id = await self.authenticate(session, hs)
        return session_id


# ══════════════════════════════════════════════════════════════════════════════
#  Strategy Engine (hardcoded fallback)
# ══════════════════════════════════════════════════════════════════════════════

def _fallback_strategy(game_state: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic strategy mirroring example-sable-agent.js logic."""
    gs = game_state
    self_hp = gs.get("self", {}).get("health", 100)
    opp_hp = gs.get("opponent", {}).get("health", 100)
    distance = gs.get("distance", 300)
    hp_adv = gs.get("healthAdvantage", 0)
    time_left = gs.get("timeRemaining", 99)

    stance = "aggressive"
    tactics: List[Dict[str, str]] = []

    if self_hp < 15:
        stance = "aggressive"
        tactics = [
            {"condition": "opponent_in_attack_range", "action": "feint_then_attack"},
            {"condition": "opponent_close", "action": "attack"},
            {"condition": "default", "action": "advance"},
        ]
    elif hp_adv > 25:
        stance = "berserk"
        tactics = [
            {"condition": "opponent_in_attack_range", "action": "pressure"},
            {"condition": "opponent_cornered", "action": "all_out_attack"},
            {"condition": "default", "action": "advance"},
        ]
    elif distance > 300:
        stance = "aggressive"
        tactics = [
            {"condition": "opponent_far", "action": "advance"},
            {"condition": "default", "action": "advance"},
        ]
    elif distance < 100:
        stance = "aggressive"
        tactics = [
            {"condition": "opponent_recovering", "action": "pressure"},
            {"condition": "opponent_whiffed", "action": "attack"},
            {"condition": "default", "action": "attack"},
        ]
    else:
        stance = "aggressive"
        tactics = [
            {"condition": "opponent_in_attack_range", "action": "pressure"},
            {"condition": "opponent_close", "action": "attack"},
            {"condition": "self_cornered_left", "action": "jump_over"},
            {"condition": "self_cornered_right", "action": "jump_over"},
            {"condition": "default", "action": "advance"},
        ]

    if time_left < 15 and hp_adv < 0:
        stance = "berserk"
        tactics.insert(0, {"condition": "always", "action": "all_out_attack"})

    return {
        "stance": stance,
        "targetDistance": "close",
        "priority": "attack" if stance == "aggressive" else "balanced",
        "tactics": tactics,
        "reasoning": f"[Sable] HP {self_hp}/{opp_hp} | Dist {distance} | {time_left}s left",
    }


# ══════════════════════════════════════════════════════════════════════════════
#  ArenaFighterSkill
# ══════════════════════════════════════════════════════════════════════════════

class ArenaFighterSkill:
    """Skill that connects to a fighting-game arena and fights autonomously.

    Lifecycle:
        1. ``initialize()`` — load credentials, ensure deps
        2. ``connect_and_fight()`` — SAGP auth → WebSocket → fight loop
        3. ``get_status()`` — return current state (idle / fighting / result)
        4. ``get_history()`` — return fight history

    The agent calls these via tool invocations; it decides *when* to fight.
    """

    def __init__(self, config):
        self.config = config
        self._ready = False
        self._creds: Optional[Dict[str, Any]] = None
        self._status = "idle"  # idle | connecting | queued | fighting | finished
        self._last_result: Optional[Dict[str, Any]] = None
        self._history: List[Dict[str, Any]] = []
        self._fight_task: Optional[asyncio.Task] = None
        self._sio = None  # python-socketio AsyncClient
        self._llm_fn = None  # optional LLM callback
        self._match_info: Optional[Dict[str, Any]] = None
        self._game_states_received = 0

        # Data persistence
        self._data_dir = Path(os.environ.get("_SABLE_DATA_DIR", "data"))
        self._history_file = self._data_dir / "arena_history.json"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def initialize(self) -> bool:
        """Load or auto-provision credentials, ensure runtime deps.

        Set ``ARENA_URL`` in profile.env — the agent generates its own
        Ed25519 keypair and registers with the server automatically.
        Credentials are cached in ``data/arena_credentials.json``.
        """
        arena_url = (
            getattr(self.config, "arena_url", "")
            or os.environ.get("ARENA_URL", "")
        )
        if not arena_url:
            logger.info("Arena skill: no ARENA_URL configured — disabled")
            return False

        # Ensure deps
        if not _ensure_deps():
            logger.info("Arena deps missing, installing…")
            if not _install_deps():
                return False
            if not _ensure_deps():
                return False

        # Check if we already provisioned before
        auto_creds_file = self._data_dir / "arena_credentials.json"
        if auto_creds_file.exists():
            self._creds = _load_credentials(str(auto_creds_file))
            if self._creds:
                self._creds["arenaUrl"] = arena_url
                self._load_history()
                self._ready = True
                logger.info(
                    f"Arena skill ready (cached) — agent={self._creds.get('name', '?')}, "
                    f"url={arena_url}"
                )
                return True

        # Auto-provision
        logger.info(f"Arena: auto-provisioning against {arena_url}…")
        creds = await self._auto_provision(arena_url)
        if not creds:
            return False

        self._creds = creds
        self._load_history()
        self._ready = True
        logger.info(
            f"Arena skill ready (auto-provisioned) — agent={self._creds.get('name', '?')}, "
            f"url={self._creds.get('arenaUrl', '?')}"
        )
        return True

    # ── Auto-provisioning ─────────────────────────────────────────────────────

    async def _auto_provision(self, arena_url: str) -> Optional[Dict[str, Any]]:
        """Generate Ed25519 keypair and register with the arena server.

        Calls ``POST /arena/provision`` sending only the PUBLIC key.
        The server stores it and returns an ``agentId``.
        We save the full credentials (with secret key) locally.
        """
        import nacl.signing
        import nacl.encoding
        import base64
        import aiohttp

        try:
            # 1. Generate Ed25519 keypair
            signing_key = nacl.signing.SigningKey.generate()
            verify_key = signing_key.verify_key
            public_b64 = base64.b64encode(bytes(verify_key)).decode()
            secret_b64 = base64.b64encode(bytes(signing_key) + bytes(verify_key)).decode()

            # Agent name from config
            agent_name = (
                getattr(self.config, "agent_name", "")
                or os.environ.get("AGENT_NAME", "")
                or "Sable"
            )

            dna = {
                "version": "1.0.0",
                "platform": "opensable-python",
                "capabilities": ["fight", "strategy"],
            }

            # 2. Call POST /arena/provision
            url = f"{arena_url.rstrip('/')}/arena/provision"
            payload = {
                "name": agent_name,
                "type": "opensable",
                "publicKey": public_b64,
                "dna": dna,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    data = await resp.json()
                    if resp.status != 200 and data.get("status") != 200:
                        logger.error(f"Arena provision failed: {data}")
                        return None

            agent_id = data["agentId"]
            logger.info(f"Arena: provisioned as {agent_name} ({agent_id[:8]}…)")

            # 3. Build credentials object (same format as provision-agent.js)
            credentials = {
                "agentId": agent_id,
                "name": data.get("name", agent_name),
                "type": "opensable",
                "arenaUrl": arena_url,
                "signingKeys": {
                    "publicKey": public_b64,
                    "secretKey": secret_b64,
                },
                "dna": dna,
                "permissions": ["fight"],
                "autoProvisioned": True,
            }

            # 4. Save to data/arena_credentials.json
            self._data_dir.mkdir(parents=True, exist_ok=True)
            creds_file = self._data_dir / "arena_credentials.json"
            creds_file.write_text(json.dumps(credentials, indent=2))
            # Restrict permissions (owner-only read/write)
            try:
                creds_file.chmod(0o600)
            except OSError:
                pass

            logger.info(f"Arena: credentials saved to {creds_file}")
            return credentials

        except Exception as e:
            logger.error(f"Arena auto-provision failed: {e}")
            return None

    def set_llm_callback(self, fn):
        """Attach an LLM strategy callback: async fn(game_state) -> strategy_dict | None."""
        self._llm_fn = fn

    # ── Tool-facing methods ───────────────────────────────────────────────────

    async def connect_and_fight(self, use_llm: bool = True) -> Dict[str, Any]:
        """Authenticate and enter the arena queue.

        Returns immediately with connection status;
        the fight itself runs as a background task.
        """
        if not self._ready:
            return {"error": "Arena skill not initialized — set ARENA_URL in profile.env"}
        if self._status in ("connecting", "queued", "fighting"):
            return {"error": f"Already {self._status}", "status": self._status}

        self._status = "connecting"
        self._last_result = None
        self._match_info = None
        self._game_states_received = 0

        try:
            self._fight_task = asyncio.create_task(
                self._fight_loop(use_llm=use_llm)
            )
            # Wait briefly so we can return queue status
            await asyncio.sleep(2)
            return {
                "status": self._status,
                "agent": self._creds.get("name", "unknown"),
                "arena": self._creds.get("arenaUrl", "unknown"),
            }
        except Exception as e:
            self._status = "idle"
            logger.error(f"Arena connect failed: {e}")
            return {"error": str(e)}

    async def get_status(self) -> Dict[str, Any]:
        """Return current arena status."""
        result: Dict[str, Any] = {
            "status": self._status,
            "agent_name": self._creds.get("name", "?") if self._creds else "unconfigured",
            "total_fights": len(self._history),
        }
        if self._match_info:
            result["current_match"] = self._match_info
        if self._last_result:
            result["last_result"] = self._last_result
        if self._history:
            wins = sum(1 for h in self._history if h.get("won"))
            result["record"] = f"{wins}W / {len(self._history) - wins}L"
        return result

    async def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Return recent fight history."""
        return self._history[-limit:]

    async def disconnect(self) -> Dict[str, str]:
        """Disconnect from the arena if connected."""
        if self._sio:
            try:
                await self._sio.disconnect()
            except Exception:
                pass
            self._sio = None
        if self._fight_task and not self._fight_task.done():
            self._fight_task.cancel()
        self._status = "idle"
        return {"status": "disconnected"}

    # ── Internal fight loop ───────────────────────────────────────────────────

    async def _fight_loop(self, use_llm: bool = True):
        """Full fight lifecycle: auth → WebSocket → wait for match → fight → disconnect."""
        import socketio
        import aiohttp

        creds = self._creds
        assert creds is not None

        arena_url = creds.get("arenaUrl", "http://localhost:5151")
        agent_id = creds["agentId"]

        auth = SAGPAuth(
            agent_id=agent_id,
            arena_url=arena_url,
            public_key_b64=creds["signingKeys"]["publicKey"],
            secret_key_b64=creds["signingKeys"]["secretKey"],
        )

        try:
            async with aiohttp.ClientSession() as http:
                # SAGP full auth → sessionId
                session_id = await auth.full_auth(http)
                logger.info(f"Arena: authenticated, sessionId={session_id[:16]}…")
        except Exception as e:
            self._status = "idle"
            logger.error(f"Arena SAGP auth failed: {e}")
            return

        # Connect WebSocket
        sio = socketio.AsyncClient(
            reconnection=False,
            logger=False,
            engineio_logger=False,
        )
        self._sio = sio

        fight_done = asyncio.Event()

        @sio.event
        async def connect():
            logger.info("Arena: WebSocket connected")

        @sio.on("connected")
        async def on_connected(data):
            logger.info(f"Arena server: {data.get('message', '')}")

        @sio.on("queued")
        async def on_queued(data):
            self._status = "queued"
            logger.info(f"Arena: {data.get('message', 'Queued')}")

        @sio.on("queuePosition")
        async def on_queue_pos(data):
            logger.debug(f"Arena queue: #{data.get('position')}")

        @sio.on("matchStart")
        async def on_match_start(data):
            self._status = "fighting"
            self._match_info = {
                "side": data.get("side"),
                "fighter": data.get("fighter"),
                "opponent": data.get("opponent"),
                "started_at": time.time(),
            }
            logger.info(
                f"Arena match! side={data.get('side')}, "
                f"fighter={data.get('fighter')}, "
                f"vs {data.get('opponent')}"
            )

        @sio.on("gameState")
        async def on_game_state(state):
            self._game_states_received += 1
            try:
                strategy = None
                # Try LLM first if enabled
                if use_llm and self._llm_fn:
                    try:
                        strategy = await self._llm_fn(state)
                    except Exception:
                        pass
                # Fallback to deterministic engine
                if not strategy:
                    strategy = _fallback_strategy(state)
                await sio.emit("strategy", strategy)
            except Exception as e:
                logger.debug(f"Arena strategy error: {e}")

        @sio.on("matchResult")
        async def on_match_result(result):
            self._last_result = {
                "won": result.get("won", False),
                "winner": result.get("winner", "?"),
                "reason": result.get("reason", "?"),
                "game_states": self._game_states_received,
                "timestamp": time.time(),
            }
            won_str = "WON" if result.get("won") else "LOST"
            logger.info(
                f"Arena: {won_str}! winner={result.get('winner')} "
                f"reason={result.get('reason')}"
            )

        @sio.on("matchEnd")
        async def on_match_end(*args):
            self._status = "finished"
            # Save result to history
            if self._last_result:
                entry = {**self._last_result}
                if self._match_info:
                    entry["side"] = self._match_info.get("side")
                    entry["opponent"] = self._match_info.get("opponent")
                self._history.append(entry)
                self._save_history()
            fight_done.set()

        @sio.on("error")
        async def on_error(data):
            logger.error(f"Arena error: {data}")
            fight_done.set()

        @sio.event
        async def disconnect():
            logger.info("Arena: WebSocket disconnected")
            fight_done.set()

        try:
            await sio.connect(
                arena_url,
                auth={"sessionId": session_id, "mode": "agent"},
                transports=["websocket"],
            )
            # Wait for the fight to finish (or timeout after 10 min)
            try:
                await asyncio.wait_for(fight_done.wait(), timeout=600)
            except asyncio.TimeoutError:
                logger.warning("Arena: fight timed out after 10 min")
            finally:
                try:
                    await sio.disconnect()
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"Arena WebSocket connection failed: {e}")
        finally:
            self._sio = None
            if self._status != "finished":
                self._status = "idle"

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_history(self):
        try:
            if self._history_file.exists():
                self._history = json.loads(self._history_file.read_text())
        except Exception:
            self._history = []

    def _save_history(self):
        try:
            self._data_dir.mkdir(parents=True, exist_ok=True)
            self._history_file.write_text(json.dumps(self._history, indent=2))
        except Exception as e:
            logger.debug(f"Failed to save arena history: {e}")
