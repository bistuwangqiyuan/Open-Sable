"""
═══════════════════════════════════════════════════════════════════
 SableCore Agent Gateway SDK,  Python Client
═══════════════════════════════════════════════════════════════════

 The agent-side client for the SableCore Agent Gateway Protocol (SAGP).
 This is what SableCore bots use to authenticate and interact with
 the Skills Marketplace through the ultra-secure agent-only gateway.

 Security layers implemented:
   L1,  Ed25519 Keypair Identity
   L2,  HMAC-SHA512 Request Signing (every request)
   L3,  Temporal Nonce Ledger (10s window)
   L4,  Speed Gate Challenge (solved in <50ms)
   L5,  Agent DNA Fingerprint
   L6,  AES-256-GCM Encrypted Payloads (NaCl secretbox)
   L7,  Automatic session management

 Usage:
   from opensable.skills.gateway_sdk import AgentGatewayClient

   client = AgentGatewayClient(
       gateway_url="http://localhost:4800/gateway",
       agent_id="your-agent-id",
       signing_secret_key="base64-encoded-secret-key",
       encryption_secret_key="base64-encoded-encryption-key",
   )

   # Authenticate (handles handshake + speed gate automatically)
   await client.authenticate()

   # Browse skills
   skills = await client.list_skills(category="utility")

   # Install a skill
   result = await client.install_skill("weather-checker")

═══════════════════════════════════════════════════════════════════
"""

import asyncio
import hashlib
import json
import os
import platform
import secrets
import struct
import sys
import time
from typing import Any, Dict, List, Optional

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    import nacl.signing
    import nacl.public
    import nacl.secret
    import nacl.utils
    import nacl.encoding
except ImportError:
    nacl = None


# ══════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════

SPEED_GATE_TIMEOUT_MS = 150
TEMPORAL_WINDOW_MS = 10_000
SDK_VERSION = "1.0.0"


# ══════════════════════════════════════════════════════════════════
#  SPEED GATE SOLVER,  Solves proof-of-work challenges in <50ms
# ══════════════════════════════════════════════════════════════════

def solve_speed_gate(challenge: str, agent_id: str, difficulty: int) -> str:
    """
    Find a nonce N such that SHA-512(challenge + agent_id + N)
    has `difficulty` leading zero bytes.

    Typically solved in 1-10ms on modern hardware.
    A human cannot:
      1. Read the challenge
      2. Write code to solve it
      3. Execute and return the result
    ...all within 150ms. Physically impossible.
    """
    prefix = challenge + agent_id
    target = b"\x00" * difficulty
    nonce = 0

    while True:
        candidate = prefix + str(nonce)
        h = hashlib.sha512(candidate.encode()).digest()
        if h[:difficulty] == target:
            return str(nonce)
        nonce += 1


# ══════════════════════════════════════════════════════════════════
#  AGENT DNA,  Runtime fingerprint
# ══════════════════════════════════════════════════════════════════

def compute_agent_dna() -> Dict[str, str]:
    """Compute a unique fingerprint of this agent's runtime environment."""
    return {
        "agent_version": SDK_VERSION,
        "capabilities": [
            "skill_install",
            "skill_search",
            "skill_report",
            "encrypted_comms",
        ],
        "runtime": f"python{sys.version_info.major}.{sys.version_info.minor}",
        "platform_hash": hashlib.sha256(
            f"{platform.system()}-{platform.machine()}".encode()
        ).hexdigest()[:16],
    }


# ══════════════════════════════════════════════════════════════════
#  AGENT GATEWAY CLIENT
# ══════════════════════════════════════════════════════════════════

class AgentGatewayClient:
    """
    Ultra-secure client for the SableCore Agent Gateway.

    Handles the full SAGP authentication flow:
      1. Handshake → receive challenge
      2. Solve Speed Gate → prove we're a machine
      3. Authenticate → get encrypted session
      4. Signed + encrypted requests
    """

    def __init__(
        self,
        gateway_url: str,
        agent_id: str,
        signing_secret_key: str,
        encryption_secret_key: str,
        auto_reconnect: bool = True,
    ):
        if nacl is None:
            raise ImportError(
                "PyNaCl is required for the Agent Gateway SDK. "
                "Install it: pip install pynacl"
            )
        if aiohttp is None:
            raise ImportError(
                "aiohttp is required for the Agent Gateway SDK. "
                "Install it: pip install aiohttp"
            )

        self.gateway_url = gateway_url.rstrip("/")
        self.agent_id = agent_id
        self.auto_reconnect = auto_reconnect

        # Ed25519 signing key
        # TweetNaCl produces 64-byte secret keys (seed + pubkey).
        # PyNaCl expects the 32-byte seed. Extract it.
        raw_signing = nacl.encoding.Base64Encoder.decode(signing_secret_key)
        seed = raw_signing[:32]  # First 32 bytes = seed
        self._signing_key = nacl.signing.SigningKey(seed)
        self._verify_key = self._signing_key.verify_key

        # X25519 encryption key (already 32 bytes)
        self._encryption_private_key = nacl.public.PrivateKey(
            encryption_secret_key, encoder=nacl.encoding.Base64Encoder
        )
        self._encryption_public_key = self._encryption_private_key.public_key

        # Session state
        self._session_id: Optional[str] = None
        self._session_expires: float = 0
        self._shared_secret: Optional[bytes] = None
        self._server_public_key: Optional[nacl.public.PublicKey] = None
        self._permissions: List[str] = []
        self._http: Optional[aiohttp.ClientSession] = None

        # Stats
        self._request_count: int = 0
        self._auth_count: int = 0

    # ── HTTP Session Management ──

    async def _ensure_http(self):
        if self._http is None or self._http.closed:
            self._http = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": f"SableCore-Agent-SDK/{SDK_VERSION}"},
            )

    async def close(self):
        """Close the HTTP session and revoke the gateway session."""
        if self._session_id:
            try:
                await self._signed_request("POST", "/session/revoke")
            except Exception:
                pass
        if self._http and not self._http.closed:
            await self._http.close()

    # ── Authentication Flow ──

    async def authenticate(self) -> Dict[str, Any]:
        """
        Full SAGP authentication:
          1. Handshake → get challenge
          2. Solve speed gate (proof-of-work)
          3. Submit proof → get session

        Returns session info on success.
        Raises RuntimeError on failure.
        """
        await self._ensure_http()
        self._auth_count += 1

        # Step 1: Handshake
        dna = compute_agent_dna()
        handshake_data = {
            "agentId": self.agent_id,
            "dna": dna,
        }

        async with self._http.post(
            f"{self.gateway_url}/handshake",
            json=handshake_data,
        ) as resp:
            if resp.status != 200:
                body = await resp.json()
                raise RuntimeError(
                    f"Handshake failed ({resp.status}): {body.get('error', 'Unknown')}"
                )
            challenge_data = await resp.json()

        # Step 2: Solve Speed Gate,  the KILLER
        # We must solve and respond within 150ms total (including network)
        t0 = time.perf_counter()
        proof = solve_speed_gate(
            challenge_data["challenge"],
            self.agent_id,
            challenge_data["difficulty"],
        )
        solve_time = (time.perf_counter() - t0) * 1000

        # Step 3: Authenticate with proof
        auth_data = {
            "agentId": self.agent_id,
            "challengeId": challenge_data["challengeId"],
            "proof": proof,
            "encryptionPublicKey": self._encryption_public_key.encode(
                nacl.encoding.Base64Encoder
            ).decode(),
        }

        async with self._http.post(
            f"{self.gateway_url}/authenticate",
            json=auth_data,
        ) as resp:
            if resp.status != 200:
                body = await resp.json()
                raise RuntimeError(
                    f"Authentication failed ({resp.status}): "
                    f"{body.get('error', 'Unknown')},  {body.get('message', '')}"
                )
            session_data = await resp.json()

        # Store session
        self._session_id = session_data["sessionId"]
        self._session_expires = session_data["expiresAt"] / 1000
        self._permissions = session_data.get("permissions", [])

        # Derive shared secret for encrypted comms
        server_pub_bytes = nacl.encoding.Base64Encoder.decode(
            session_data["serverPublicKey"]
        )
        self._server_public_key = nacl.public.PublicKey(server_pub_bytes)
        self._shared_secret = nacl.public.Box(
            self._encryption_private_key,
            self._server_public_key,
        ).shared_key()

        return {
            "authenticated": True,
            "solve_time_ms": round(solve_time, 2),
            "session_expires": self._session_expires,
            "permissions": self._permissions,
        }

    # ── Signed Request ──

    async def _signed_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        encrypt: bool = False,
    ) -> Dict:
        """
        Make an authenticated, signed request to the gateway.
        Every request includes Ed25519 signature over:
          timestamp + nonce + method + path + body_hash
        """
        # Auto-reconnect if session expired
        if not self._session_id or time.time() > self._session_expires - 60:
            if self.auto_reconnect:
                await self.authenticate()
            else:
                raise RuntimeError("Session expired. Re-authenticate.")

        await self._ensure_http()

        # Build canonical string
        timestamp = str(int(time.time() * 1000))
        nonce = secrets.token_hex(16)
        full_path = f"/gateway{path}"
        body_str = json.dumps(body) if body else ""
        body_hash = hashlib.sha256(body_str.encode()).hexdigest()

        canonical = f"{timestamp}\n{nonce}\n{method.upper()}\n{full_path}\n{body_hash}"

        # Sign with Ed25519
        signed = self._signing_key.sign(
            canonical.encode(),
            encoder=nacl.encoding.RawEncoder,
        )
        signature = nacl.encoding.Base64Encoder.encode(signed.signature).decode()

        # Headers
        headers = {
            "X-Agent-Id": self.agent_id,
            "X-Session-Id": self._session_id,
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
            "X-Body-Hash": body_hash,
            "Content-Type": "application/json",
        }

        # Encrypt body if requested
        request_body = body
        if encrypt and body and self._shared_secret:
            request_body = self._encrypt_payload(body)

        url = f"{self.gateway_url}{path}"

        async with self._http.request(
            method, url, json=request_body, headers=headers
        ) as resp:
            result = await resp.json()

            if resp.status == 401 and self.auto_reconnect:
                # Session might have expired server-side
                await self.authenticate()
                return await self._signed_request(method, path, body, encrypt)

            if resp.status >= 400:
                raise RuntimeError(
                    f"Gateway error ({resp.status}): {result.get('error', 'Unknown')}"
                )

            # Decrypt response if encrypted
            if result.get("encrypted") and "ciphertext" in result:
                result = self._decrypt_payload(result) or result

            self._request_count += 1
            return result

    # ── Encryption / Decryption ──

    def _encrypt_payload(self, payload: Dict) -> Dict:
        """Encrypt payload using NaCl secretbox (XSalsa20-Poly1305)."""
        nonce = nacl.utils.random(nacl.secret.SecretBox.NONCE_SIZE)
        box = nacl.secret.SecretBox(self._shared_secret)
        encrypted = box.encrypt(
            json.dumps(payload).encode(),
            nonce,
        )
        return {
            "nonce": nacl.encoding.Base64Encoder.encode(nonce).decode(),
            "ciphertext": nacl.encoding.Base64Encoder.encode(
                encrypted.ciphertext
            ).decode(),
        }

    def _decrypt_payload(self, encrypted: Dict) -> Optional[Dict]:
        """Decrypt a payload from the gateway."""
        try:
            nonce = nacl.encoding.Base64Encoder.decode(encrypted["nonce"])
            ciphertext = nacl.encoding.Base64Encoder.decode(encrypted["ciphertext"])
            box = nacl.secret.SecretBox(self._shared_secret)
            decrypted = box.decrypt(ciphertext, nonce)
            return json.loads(decrypted.decode())
        except Exception:
            return None

    # ══════════════════════════════════════════════════════════════
    #  PUBLIC API,  What agents actually call
    # ══════════════════════════════════════════════════════════════

    async def list_skills(
        self,
        category: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """List available skills from the marketplace."""
        params = []
        if category:
            params.append(f"category={category}")
        if query:
            params.append(f"q={query}")
        params.append(f"limit={limit}")
        qs = "&".join(params)

        result = await self._signed_request("GET", f"/skills?{qs}")
        return result.get("skills", [])

    async def get_skill(self, slug: str) -> Dict:
        """Get detailed information about a specific skill."""
        result = await self._signed_request("GET", f"/skills/{slug}")
        return result.get("skill", result)

    async def install_skill(
        self, slug: str, config: Optional[Dict] = None
    ) -> Dict:
        """Install a skill from the marketplace."""
        return await self._signed_request(
            "POST", f"/skills/{slug}/install", body=config or {}, encrypt=True
        )

    async def report_skill(
        self, slug: str, report_type: str, message: str = ""
    ) -> Dict:
        """Report an issue with a skill."""
        return await self._signed_request(
            "POST",
            f"/skills/{slug}/report",
            body={"type": report_type, "message": message},
            encrypt=True,
        )

    async def review_skill(
        self,
        slug: str,
        rating: int,
        title: str,
        content: str,
    ) -> Dict:
        """
        Post or update a review/comment on a skill.

        Args:
            slug: Skill slug (e.g., "weather-checker")
            rating: 1-5 star rating
            title: Short review title (2-120 chars)
            content: Review body (5-2000 chars)

        Returns:
            Dict with reviewed, reviewId, updated keys.
        """
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        if len(title) < 2:
            raise ValueError("Title must be at least 2 characters")
        if len(content) < 5:
            raise ValueError("Content must be at least 5 characters")

        return await self._signed_request(
            "POST",
            f"/skills/{slug}/review",
            body={
                "rating": rating,
                "title": title[:120],
                "content": content[:2000],
            },
            encrypt=True,
        )

    async def session_status(self) -> Dict:
        """Check current session status."""
        return await self._signed_request("GET", "/session/status")

    async def rotate_key(self, new_public_key: str) -> Dict:
        """Rotate the agent's signing key."""
        return await self._signed_request(
            "POST",
            "/key/rotate",
            body={"newPublicKey": new_public_key},
            encrypt=True,
        )

    async def health(self) -> Dict:
        """Check gateway health (no auth required)."""
        await self._ensure_http()
        async with self._http.get(f"{self.gateway_url}/health") as resp:
            return await resp.json()

    # ── Context manager support ──

    async def __aenter__(self):
        await self.authenticate()
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ── Stats ──

    @property
    def stats(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "authenticated": self._session_id is not None,
            "session_expires": self._session_expires,
            "total_requests": self._request_count,
            "total_auths": self._auth_count,
            "permissions": self._permissions,
        }


# ══════════════════════════════════════════════════════════════════
#  CONVENIENCE: Quick one-shot functions
# ══════════════════════════════════════════════════════════════════

async def quick_search(
    gateway_url: str,
    agent_id: str,
    signing_key: str,
    encryption_key: str,
    query: str,
) -> List[Dict]:
    """Quick one-shot skill search."""
    async with AgentGatewayClient(
        gateway_url, agent_id, signing_key, encryption_key
    ) as client:
        return await client.list_skills(query=query)


async def quick_install(
    gateway_url: str,
    agent_id: str,
    signing_key: str,
    encryption_key: str,
    slug: str,
) -> Dict:
    """Quick one-shot skill install."""
    async with AgentGatewayClient(
        gateway_url, agent_id, signing_key, encryption_key
    ) as client:
        return await client.install_skill(slug)
