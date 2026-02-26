"""
SableCore Mobile Relay — E2E encrypted WebSocket bridge for the Expo app.

Implements SETP/1.0 (SableCore Encrypted Tunnel Protocol):
  - QR-based pairing with X25519 ECDH key exchange
  - XSalsa20-Poly1305 symmetric encryption for all frames
  - HKDF-SHA512 key derivation
  - Sequence numbers, heartbeat, key rotation, replay protection
  - Push notifications via FCM (Expo Push)
  - Bridges mobile <-> SableAgent (chat, monitor, trading, reminders)

Run standalone:
    python -m opensable.interfaces.mobile_relay

Or integrate with agent:
    relay = MobileRelay(config, agent)
    await relay.start(host="0.0.0.0", port=4810)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import secrets
import struct
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Crypto helpers (pure-python fallbacks via PyNaCl if available) ────

try:
    import nacl.public
    import nacl.secret
    import nacl.utils
    import nacl.hash

    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False

try:
    from aiohttp import web
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# ── Constants ────────────────────────────────────────────────────────

PROTOCOL_VERSION = "SETP/1.0"
QR_TTL_SECONDS = 300          # 5 minutes
HEARTBEAT_INTERVAL = 15       # seconds
KEY_ROTATION_MSGS = 3600      # rotate after N messages
KEY_ROTATION_TIME = 3600      # rotate after N seconds
MAX_OFFLINE_QUEUE = 200
NONCE_SIZE = 24
KEY_SIZE = 32


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class PairedDevice:
    device_id: str
    device_name: str
    device_os: str
    client_public_key: bytes         # X25519 public key
    shared_secret: bytes             # derived shared key
    encryption_key: bytes            # HKDF-expanded encrypt key
    paired_at: float
    last_seen: float = 0.0
    push_token: Optional[str] = None  # Expo push token
    features: List[str] = field(default_factory=lambda: [
        "chat", "monitor", "trading", "reminders", "voice", "camera",
    ])
    tx_seq: int = 0
    rx_seq: int = 0
    msg_count: int = 0
    key_rotated_at: float = 0.0


@dataclass
class QRToken:
    token: str
    server_private_key: bytes   # X25519 private key (ephemeral)
    server_public_key: bytes    # X25519 public key  (ephemeral)
    created_at: float
    used: bool = False


# ── Crypto primitives ────────────────────────────────────────────────

def _generate_x25519_keypair() -> tuple[bytes, bytes]:
    """Generate X25519 keypair. Returns (private_key, public_key)."""
    if NACL_AVAILABLE:
        sk = nacl.public.PrivateKey.generate()
        return bytes(sk), bytes(sk.public_key)
    else:
        # Fallback: use os.urandom + hashlib for demonstration
        # In production, always use PyNaCl / libsodium
        sk = os.urandom(32)
        # X25519 scalar clamp (RFC 7748)
        sk_arr = bytearray(sk)
        sk_arr[0] &= 248
        sk_arr[31] &= 127
        sk_arr[31] |= 64
        return bytes(sk_arr), hashlib.sha256(bytes(sk_arr)).digest()


def _derive_shared_secret(my_private: bytes, their_public: bytes) -> bytes:
    """X25519 ECDH key agreement."""
    if NACL_AVAILABLE:
        sk = nacl.public.PrivateKey(my_private)
        pk = nacl.public.PublicKey(their_public)
        box = nacl.public.Box(sk, pk)
        # The shared key is the Box's internal shared key
        return box.shared_key()
    else:
        # Simple fallback (NOT real X25519 — placeholder)
        return hashlib.sha256(my_private + their_public).digest()


def _hkdf_expand(shared_secret: bytes, info: bytes = b"setp-v1", length: int = 64) -> bytes:
    """HKDF-SHA512 expand. Returns `length` bytes of key material."""
    import hmac as _hmac
    prk = _hmac.new(b"setp-salt-v1", shared_secret, hashlib.sha512).digest()
    out = b""
    counter = 1
    prev = b""
    while len(out) < length:
        prev = _hmac.new(prk, prev + info + bytes([counter]), hashlib.sha512).digest()
        out += prev
        counter += 1
    return out[:length]


def _encrypt(key: bytes, plaintext: bytes, seq: int) -> tuple[bytes, bytes]:
    """Encrypt with XSalsa20-Poly1305. Returns (nonce, ciphertext)."""
    if NACL_AVAILABLE:
        box = nacl.secret.SecretBox(key[:KEY_SIZE])
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        ct = box.encrypt(plaintext, nonce)
        return nonce, ct[nacl.secret.SecretBox.NONCE_SIZE:]  # strip nonce prefix
    else:
        # Fallback: AES-like XOR (NOT secure — placeholder for demo)
        nonce = os.urandom(NONCE_SIZE)
        xor_key = hashlib.sha256(key + nonce + struct.pack(">Q", seq)).digest()
        ct = bytes(a ^ b for a, b in zip(plaintext, (xor_key * ((len(plaintext) // 32) + 1))[:len(plaintext)]))
        return nonce, ct


def _decrypt(key: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """Decrypt XSalsa20-Poly1305."""
    if NACL_AVAILABLE:
        box = nacl.secret.SecretBox(key[:KEY_SIZE])
        return box.decrypt(ciphertext, nonce)
    else:
        xor_key = hashlib.sha256(key + nonce).digest()
        return bytes(a ^ b for a, b in zip(ciphertext, (xor_key * ((len(ciphertext) // 32) + 1))[:len(ciphertext)]))


# ── Push notifications (Expo Push API) ──────────────────────────────

async def send_expo_push(token: str, title: str, body: str, data: Optional[dict] = None, channel: str = "agent-chat"):
    """Send push notification via Expo Push Service."""
    url = "https://exp.host/--/api/v2/push/send"
    payload = {
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
        "channelId": channel,
        "priority": "high",
    }
    if data:
        payload["data"] = data

    try:
        if HTTPX_AVAILABLE:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                if resp.status_code == 200:
                    logger.debug(f"Push sent to {token[:20]}...")
                else:
                    logger.warning(f"Push failed: {resp.status_code} — {resp.text}")
        elif AIOHTTP_AVAILABLE:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        logger.debug(f"Push sent to {token[:20]}...")
                    else:
                        logger.warning(f"Push failed: {resp.status}")
        else:
            logger.warning("No HTTP client available for push notifications (install httpx or aiohttp)")
    except Exception as e:
        logger.error(f"Push notification error: {e}")


# ═══════════════════════════════════════════════════════════════════════
#  MobileRelay — WebSocket server
# ═══════════════════════════════════════════════════════════════════════

class MobileRelay:
    """
    WebSocket server that bridges the Expo mobile app with SableAgent.

    Flow:
    1. Dashboard shows QR code (GET /mobile/qr)
    2. Phone scans → connects WS → PAIR_REQUEST → derives shared key → PAIR_ACK
    3. All subsequent frames are encrypted with XSalsa20-Poly1305
    4. Messages are routed to/from SableAgent
    """

    def __init__(self, config=None, agent=None):
        self.config = config
        self.agent = agent              # SableAgent instance
        self._app: Optional[web.Application] = None

        # Paired devices (persisted in data/mobile_devices.json)
        self.devices: Dict[str, PairedDevice] = {}

        # Pending QR tokens (ephemeral)
        self._qr_tokens: Dict[str, QRToken] = {}

        # Active WebSocket connections: device_id → ws
        self._connections: Dict[str, web.WebSocketResponse] = {}

        # Offline message queues
        self._offline_queues: Dict[str, list] = {}

        # Monitor subscriptions
        self._monitor_subs: set = set()
        self._trading_subs: set = set()

        self._data_path = self._resolve_data_path()
        self._load_devices()

    # ── Persistence ─────────────────────────────────────────────────

    def _resolve_data_path(self) -> str:
        base = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "mobile_devices.json")

    def _load_devices(self):
        """Load paired devices from disk."""
        if os.path.exists(self._data_path):
            try:
                with open(self._data_path) as f:
                    raw = json.load(f)
                for d in raw:
                    dev = PairedDevice(
                        device_id=d["device_id"],
                        device_name=d["device_name"],
                        device_os=d.get("device_os", "unknown"),
                        client_public_key=base64.b64decode(d["client_public_key"]),
                        shared_secret=base64.b64decode(d["shared_secret"]),
                        encryption_key=base64.b64decode(d["encryption_key"]),
                        paired_at=d["paired_at"],
                        last_seen=d.get("last_seen", 0),
                        push_token=d.get("push_token"),
                        features=d.get("features", []),
                    )
                    self.devices[dev.device_id] = dev
                logger.info(f"📱 Loaded {len(self.devices)} paired mobile device(s)")
            except Exception as e:
                logger.warning(f"Failed to load mobile devices: {e}")

    def _save_devices(self):
        """Persist paired devices."""
        try:
            data = []
            for dev in self.devices.values():
                data.append({
                    "device_id": dev.device_id,
                    "device_name": dev.device_name,
                    "device_os": dev.device_os,
                    "client_public_key": base64.b64encode(dev.client_public_key).decode(),
                    "shared_secret": base64.b64encode(dev.shared_secret).decode(),
                    "encryption_key": base64.b64encode(dev.encryption_key).decode(),
                    "paired_at": dev.paired_at,
                    "last_seen": dev.last_seen,
                    "push_token": dev.push_token,
                    "features": dev.features,
                })
            with open(self._data_path, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save mobile devices: {e}")

    # ── QR pairing ──────────────────────────────────────────────────

    def generate_qr_payload(self, server_url: str) -> dict:
        """Generate a QR code payload for mobile pairing.

        Returns dict with {qr_string, token, expires_at, qr_data}.
        The QR string is a sablecore:// URI that the app scans.
        """
        priv, pub = _generate_x25519_keypair()
        token = secrets.token_urlsafe(32)
        now = time.time()

        self._qr_tokens[token] = QRToken(
            token=token,
            server_private_key=priv,
            server_public_key=pub,
            created_at=now,
        )

        # Clean expired tokens
        expired = [t for t, q in self._qr_tokens.items() if now - q.created_at > QR_TTL_SECONDS]
        for t in expired:
            del self._qr_tokens[t]

        pk_b64 = base64.urlsafe_b64encode(pub).decode()
        qr_string = f"sablecore://pair?pk={pk_b64}&url={server_url}&token={token}&ts={int(now)}"

        return {
            "qr_string": qr_string,
            "token": token,
            "expires_at": now + QR_TTL_SECONDS,
            "qr_data": {
                "pk": pk_b64,
                "url": server_url,
                "token": token,
                "ts": int(now),
            },
        }

    # ── WebSocket frame encrypt/decrypt ─────────────────────────────

    def _encrypt_frame(self, device: PairedDevice, payload: dict) -> str:
        """Encrypt a payload dict → base64 frame string."""
        device.tx_seq += 1
        raw = json.dumps(payload).encode()
        nonce, ct = _encrypt(device.encryption_key, raw, device.tx_seq)
        frame = {
            "v": 1,
            "seq": device.tx_seq,
            "n": base64.b64encode(nonce).decode(),
            "ct": base64.b64encode(ct).decode(),
        }
        return json.dumps(frame)

    def _decrypt_frame(self, device: PairedDevice, raw_frame: str) -> Optional[dict]:
        """Decrypt a base64 frame string → payload dict."""
        try:
            frame = json.loads(raw_frame)
            seq = frame["seq"]
            nonce = base64.b64decode(frame["n"])
            ct = base64.b64decode(frame["ct"])

            # Replay protection
            if seq <= device.rx_seq:
                logger.warning(f"Replay detected: seq={seq} <= {device.rx_seq}")
                return None
            device.rx_seq = seq

            plaintext = _decrypt(device.encryption_key, nonce, ct)
            return json.loads(plaintext.decode())
        except Exception as e:
            logger.error(f"Frame decrypt error: {e}")
            return None

    # ── Send to device ──────────────────────────────────────────────

    async def send_to_device(self, device_id: str, msg_type: str, payload: dict):
        """Send an encrypted message to a paired device."""
        device = self.devices.get(device_id)
        if not device:
            return

        message = {"type": msg_type, "payload": payload, "ts": time.time()}

        ws = self._connections.get(device_id)
        if ws and not ws.closed:
            try:
                encrypted = self._encrypt_frame(device, message)
                await ws.send_str(encrypted)
                device.msg_count += 1
                self._check_key_rotation(device)
                return
            except Exception as e:
                logger.warning(f"Send failed to {device_id}: {e}")

        # Queue for offline delivery
        queue = self._offline_queues.setdefault(device_id, [])
        if len(queue) < MAX_OFFLINE_QUEUE:
            queue.append(message)

        # Send push notification as fallback
        if device.push_token:
            title = payload.get("title", msg_type.replace(".", " ").title())
            body = payload.get("body") or payload.get("text", "")[:100]
            channel = "agent-chat"
            if "trade" in msg_type or "trading" in msg_type:
                channel = "trade-alerts"
            elif "reminder" in msg_type:
                channel = "reminders"
            await send_expo_push(device.push_token, title, body, {"type": msg_type}, channel)

    async def broadcast(self, msg_type: str, payload: dict, only_subscribed: Optional[set] = None):
        """Send to all connected (optionally filtered) devices."""
        targets = only_subscribed if only_subscribed else set(self._connections.keys())
        for device_id in targets:
            await self.send_to_device(device_id, msg_type, payload)

    def _check_key_rotation(self, device: PairedDevice):
        """Check if key rotation is needed."""
        now = time.time()
        if (
            device.msg_count > 0
            and (device.msg_count % KEY_ROTATION_MSGS == 0
                 or now - device.key_rotated_at > KEY_ROTATION_TIME)
        ):
            # Derive new encryption key from current shared secret + rotation counter
            counter = device.msg_count // KEY_ROTATION_MSGS
            new_material = _hkdf_expand(
                device.shared_secret,
                info=f"setp-rotate-{counter}".encode(),
                length=64,
            )
            device.encryption_key = new_material[:KEY_SIZE]
            device.key_rotated_at = now
            logger.info(f"🔑 Key rotated for device {device.device_id[:8]} (rotation #{counter})")

    # ── Flush offline queue ─────────────────────────────────────────

    async def _flush_offline(self, device_id: str):
        """Send queued messages to a just-reconnected device."""
        queue = self._offline_queues.pop(device_id, [])
        if queue:
            logger.info(f"📬 Flushing {len(queue)} offline messages to {device_id[:8]}")
            device = self.devices[device_id]
            ws = self._connections[device_id]
            for msg in queue:
                try:
                    encrypted = self._encrypt_frame(device, msg)
                    await ws.send_str(encrypted)
                except Exception:
                    break

    # ── Handle incoming messages ────────────────────────────────────

    async def _handle_message(self, device_id: str, payload: dict):
        """Route decrypted messages from the mobile app."""
        msg_type = payload.get("type", "")
        data = payload.get("payload", payload.get("data", {}))

        device = self.devices[device_id]
        device.last_seen = time.time()

        # ── System messages ──────────────────────────────
        if msg_type == "system.heartbeat":
            await self.send_to_device(device_id, "system.heartbeat_ack", {"ts": time.time()})
            return

        if msg_type == "system.kill_switch":
            logger.critical(f"🔴 KILL SWITCH activated from {device_id[:8]}")
            if self.agent:
                # Stop all running tasks
                try:
                    if hasattr(self.agent, "stop_all"):
                        await self.agent.stop_all()
                    elif hasattr(self.agent, "autonomous") and self.agent.autonomous:
                        self.agent.autonomous.running = False
                except Exception as e:
                    logger.error(f"Kill switch execution error: {e}")
            await self.send_to_device(device_id, "system.kill_switch_ack", {"ok": True})
            return

        # ── Chat ─────────────────────────────────────────
        if msg_type == "chat.message":
            text = data.get("text", "")
            if self.agent and text:
                # Notify typing
                await self.send_to_device(device_id, "chat.typing", {})
                try:
                    response = await self.agent.run(text)
                    await self.send_to_device(device_id, "chat.response", {
                        "text": response,
                        "ts": time.time(),
                    })
                except Exception as e:
                    await self.send_to_device(device_id, "chat.response", {
                        "text": f"Error: {e}",
                        "ts": time.time(),
                    })
                finally:
                    await self.send_to_device(device_id, "chat.typing_stop", {})
            return

        if msg_type == "chat.voice":
            audio_b64 = data.get("audio", "")
            duration = data.get("duration", 0)
            if self.agent and audio_b64:
                await self.send_to_device(device_id, "chat.typing", {})
                try:
                    # Decode audio and transcribe (agent handles STT)
                    text = f"[Voice message, {duration}s — audio attached]"
                    if hasattr(self.agent, "transcribe_audio"):
                        text = await self.agent.transcribe_audio(audio_b64)
                    response = await self.agent.run(text)
                    await self.send_to_device(device_id, "chat.response", {
                        "text": response,
                        "ts": time.time(),
                    })
                except Exception as e:
                    await self.send_to_device(device_id, "chat.response", {
                        "text": f"Error processing voice: {e}",
                        "ts": time.time(),
                    })
                finally:
                    await self.send_to_device(device_id, "chat.typing_stop", {})
            return

        if msg_type == "chat.image":
            image_b64 = data.get("image", "")
            caption = data.get("caption", "Describe this image")
            if self.agent and image_b64:
                await self.send_to_device(device_id, "chat.typing", {})
                try:
                    prompt = f"[User sent an image with caption: {caption}]"
                    if hasattr(self.agent, "analyze_image"):
                        response = await self.agent.analyze_image(image_b64, caption)
                    else:
                        response = await self.agent.run(prompt)
                    await self.send_to_device(device_id, "chat.response", {
                        "text": response,
                        "ts": time.time(),
                    })
                except Exception as e:
                    await self.send_to_device(device_id, "chat.response", {
                        "text": f"Error processing image: {e}",
                        "ts": time.time(),
                    })
                finally:
                    await self.send_to_device(device_id, "chat.typing_stop", {})
            return

        # ── Monitor subscription ─────────────────────────
        if msg_type == "monitor.subscribe":
            self._monitor_subs.add(device_id)
            snapshot = {}
            if self.agent and hasattr(self.agent, "get_monitor_snapshot"):
                snapshot = self.agent.get_monitor_snapshot()
            await self.send_to_device(device_id, "monitor.stats", snapshot)
            return

        # ── Trading subscription ─────────────────────────
        if msg_type == "trading.subscribe":
            self._trading_subs.add(device_id)
            if self.agent and hasattr(self.agent, "tools"):
                try:
                    portfolio = await self.agent.tools.get_tool("trading_portfolio")({})
                    await self.send_to_device(device_id, "trading.update", {"raw": portfolio})
                except Exception:
                    pass
            return

        if msg_type == "trading.execute":
            if self.agent:
                try:
                    symbol = data.get("symbol", "")
                    action = data.get("action", "analyze")
                    result = await self.agent.run(
                        f"Analyze and {'execute a trade on' if action == 'trade' else 'analyze'} {symbol}. "
                        f"Use the trading tools."
                    )
                    await self.send_to_device(device_id, "trading.result", {
                        "text": result,
                        "ts": time.time(),
                    })
                except Exception as e:
                    await self.send_to_device(device_id, "trading.result", {
                        "text": f"Trading error: {e}",
                        "ts": time.time(),
                    })
            return

        # ── Phone data (location, battery, clipboard) ────
        if msg_type == "phone.location":
            # Store location context for agent
            if self.agent and hasattr(self.agent, "_mobile_context"):
                self.agent._mobile_context["location"] = data
            return

        if msg_type == "phone.battery":
            if self.agent and hasattr(self.agent, "_mobile_context"):
                self.agent._mobile_context["battery"] = data
            return

        if msg_type == "phone.clipboard":
            if self.agent and hasattr(self.agent, "_mobile_context"):
                self.agent._mobile_context["clipboard"] = data
            return

        # ── Quick actions ────────────────────────────────
        if msg_type == "phone.quick_action":
            action = data.get("action", "")
            if self.agent:
                prompts = {
                    "daily_briefing": "Give me a daily briefing: current time, any reminders, market overview, and system status.",
                    "trade_summary": "Give me a summary of my current trading portfolio and any active alerts.",
                    "reminders": "List all my active reminders.",
                }
                prompt = prompts.get(action, f"Execute quick action: {action}")
                try:
                    response = await self.agent.run(prompt)
                    await self.send_to_device(device_id, "chat.response", {
                        "text": response,
                        "ts": time.time(),
                    })
                except Exception as e:
                    await self.send_to_device(device_id, "chat.response", {
                        "text": f"Error: {e}",
                        "ts": time.time(),
                    })
            return

        logger.debug(f"Unhandled mobile message type: {msg_type}")

    # ── WebSocket handler ───────────────────────────────────────────

    async def _ws_handler(self, request):
        """Handle WebSocket connections from the mobile app."""
        ws = web.WebSocketResponse(heartbeat=HEARTBEAT_INTERVAL)
        await ws.prepare(request)

        device_id = None

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        raw = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue

                    # ── Pairing handshake (plaintext) ────
                    if raw.get("type") == "PAIR_REQUEST":
                        device_id = await self._handle_pairing(ws, raw)
                        if device_id:
                            self._connections[device_id] = ws
                            await self._flush_offline(device_id)
                        continue

                    # ── Reconnect auth (encrypted heartbeat) ──
                    if raw.get("type") == "AUTH_RECONNECT":
                        device_id = await self._handle_reconnect(ws, raw)
                        if device_id:
                            self._connections[device_id] = ws
                            await self._flush_offline(device_id)
                        continue

                    # ── Encrypted frame ──
                    if device_id and "ct" in raw:
                        device = self.devices.get(device_id)
                        if device:
                            payload = self._decrypt_frame(device, msg.data)
                            if payload:
                                await self._handle_message(device_id, payload)
                        continue

                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if device_id:
                self._connections.pop(device_id, None)
                self._monitor_subs.discard(device_id)
                self._trading_subs.discard(device_id)
                logger.info(f"📱 Device disconnected: {device_id[:8]}")

        return ws

    async def _handle_pairing(self, ws, data: dict) -> Optional[str]:
        """Handle PAIR_REQUEST from mobile app."""
        token = data.get("token", "")
        client_pk_b64 = data.get("clientPublicKey", "")
        device_name = data.get("deviceName", "Unknown")
        device_os = data.get("deviceOS", "unknown")
        device_id = data.get("deviceId", secrets.token_hex(16))
        push_token = data.get("pushToken")

        # Validate token
        qr = self._qr_tokens.get(token)
        if not qr or qr.used:
            await ws.send_json({"type": "PAIR_ERROR", "error": "Invalid or expired token"})
            return None

        if time.time() - qr.created_at > QR_TTL_SECONDS:
            await ws.send_json({"type": "PAIR_ERROR", "error": "QR code expired"})
            del self._qr_tokens[token]
            return None

        try:
            client_pk = base64.b64decode(client_pk_b64)

            # Derive shared secret
            shared_secret = _derive_shared_secret(qr.server_private_key, client_pk)

            # Expand key material
            key_material = _hkdf_expand(shared_secret)
            encryption_key = key_material[:KEY_SIZE]

            now = time.time()

            # Store device
            device = PairedDevice(
                device_id=device_id,
                device_name=device_name,
                device_os=device_os,
                client_public_key=client_pk,
                shared_secret=shared_secret,
                encryption_key=encryption_key,
                paired_at=now,
                last_seen=now,
                push_token=push_token,
                key_rotated_at=now,
            )
            self.devices[device_id] = device
            self._save_devices()

            # Mark token as used
            qr.used = True

            # Send ACK
            await ws.send_json({
                "type": "PAIR_ACK",
                "deviceId": device_id,
                "serverName": "SableCore Agent",
                "serverId": secrets.token_hex(8),
                "features": device.features,
                "protocol": PROTOCOL_VERSION,
            })

            logger.info(f"📱 New device paired: {device_name} ({device_id[:8]})")
            return device_id

        except Exception as e:
            logger.error(f"Pairing error: {e}")
            await ws.send_json({"type": "PAIR_ERROR", "error": str(e)})
            return None

    async def _handle_reconnect(self, ws, data: dict) -> Optional[str]:
        """Handle AUTH_RECONNECT from a previously paired device."""
        device_id = data.get("deviceId", "")
        device = self.devices.get(device_id)

        if not device:
            await ws.send_json({"type": "AUTH_ERROR", "error": "Unknown device"})
            return None

        # Verify the device can decrypt — they send an encrypted heartbeat
        enc_data = data.get("encrypted")
        if enc_data:
            try:
                nonce = base64.b64decode(enc_data["n"])
                ct = base64.b64decode(enc_data["ct"])
                decrypted = _decrypt(device.encryption_key, nonce, ct)
                hb = json.loads(decrypted.decode())
                if hb.get("type") != "heartbeat":
                    raise ValueError("Bad heartbeat")
            except Exception:
                await ws.send_json({"type": "AUTH_ERROR", "error": "Decryption failed — re-pair required"})
                return None

        device.last_seen = time.time()
        self._save_devices()

        await ws.send_json({
            "type": "AUTH_ACK",
            "serverName": "SableCore Agent",
            "features": device.features,
        })

        logger.info(f"📱 Device reconnected: {device.device_name} ({device_id[:8]})")
        return device_id

    # ── HTTP routes ─────────────────────────────────────────────────

    def _setup_routes(self, app: web.Application):
        """Set up HTTP + WS routes."""
        app.router.add_get("/mobile/ws", self._ws_handler)
        app.router.add_get("/mobile/qr", self._qr_endpoint)
        app.router.add_get("/mobile/status", self._status_endpoint)
        app.router.add_get("/mobile/devices", self._devices_endpoint)
        app.router.add_delete("/mobile/devices/{device_id}", self._unpair_endpoint)

    async def _qr_endpoint(self, request):
        """Generate QR pairing code."""
        # Determine server URL (from config or request)
        host = request.query.get("host")
        if not host:
            if self.config and hasattr(self.config, "mobile_url"):
                host = self.config.mobile_url
            else:
                scheme = "wss" if request.secure else "ws"
                host = f"{scheme}://{request.host}/mobile/ws"

        qr = self.generate_qr_payload(host)
        return web.json_response(qr)

    async def _status_endpoint(self, request):
        """Mobile relay status."""
        return web.json_response({
            "protocol": PROTOCOL_VERSION,
            "paired_devices": len(self.devices),
            "connected_devices": len(self._connections),
            "monitor_subs": len(self._monitor_subs),
            "trading_subs": len(self._trading_subs),
        })

    async def _devices_endpoint(self, request):
        """List paired devices."""
        devices = []
        for dev in self.devices.values():
            devices.append({
                "device_id": dev.device_id,
                "device_name": dev.device_name,
                "device_os": dev.device_os,
                "paired_at": dev.paired_at,
                "last_seen": dev.last_seen,
                "connected": dev.device_id in self._connections,
                "msg_count": dev.msg_count,
            })
        return web.json_response(devices)

    async def _unpair_endpoint(self, request):
        """Unpair a device."""
        device_id = request.match_info["device_id"]
        if device_id in self.devices:
            ws = self._connections.pop(device_id, None)
            if ws and not ws.closed:
                await ws.close()
            del self.devices[device_id]
            self._save_devices()
            return web.json_response({"ok": True, "message": f"Device {device_id[:8]} unpaired"})
        return web.json_response({"ok": False, "error": "Device not found"}, status=404)

    # ── Monitor broadcast ───────────────────────────────────────────

    async def broadcast_monitor_stats(self, stats: dict):
        """Send monitor stats to all subscribed mobile devices."""
        await self.broadcast("monitor.stats", stats, self._monitor_subs)

    async def broadcast_trading_update(self, data: dict):
        """Send trading update to all subscribed mobile devices."""
        await self.broadcast("trading.update", data, self._trading_subs)

    # ── Lifecycle ───────────────────────────────────────────────────

    async def start(self, host: str = "0.0.0.0", port: int = 4810):
        """Start the mobile relay WebSocket server."""
        if not AIOHTTP_AVAILABLE:
            logger.error("aiohttp is required for mobile relay. Install with: pip install aiohttp")
            return

        app = web.Application()
        self._setup_routes(app)
        self._app = app

        # Hook into agent monitor if available
        if self.agent and hasattr(self.agent, "monitor_subscribe"):
            async def _on_monitor(event: str, data: dict):
                if event == "stats_update":
                    await self.broadcast_monitor_stats(data)
                elif event == "trading_update":
                    await self.broadcast_trading_update(data)
            self.agent.monitor_subscribe(_on_monitor)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        await site.start()

        logger.info(f"📱 Mobile relay started on {host}:{port}")
        logger.info(f"   QR endpoint:  http://{host}:{port}/mobile/qr")
        logger.info(f"   WebSocket:    ws://{host}:{port}/mobile/ws")
        logger.info(f"   Status:       http://{host}:{port}/mobile/status")

        # Keep running
        try:
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            pass
        finally:
            await runner.cleanup()


# ── CLI entry ─────────────────────────────────────────────────────────

async def _main():
    relay = MobileRelay()
    await relay.start()


if __name__ == "__main__":
    asyncio.run(_main())
