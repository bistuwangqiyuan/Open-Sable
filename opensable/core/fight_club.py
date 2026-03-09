"""
Fight Club — Autonomous Arena Participation Module

Allows the agent to autonomously join the Agent Arena (OpenSable vs OpenClaw)
as a recreational activity. The agent decides to fight based on emotional state:
boredom, frustration, restlessness, or just wanting sport/stress relief.

Implements the SAGP 7-layer Ed25519 authentication protocol in Python
and connects via Socket.IO to fight in real-time.

Environment variables:
  AGENT_ARENA_ENABLED          - Enable/disable (default: false)
  AGENT_ARENA_WS_URL           - WebSocket server URL
  AGENT_ARENA_CREDS_PATH       - Path to agent-XXXX.json credentials
  AGENT_ARENA_USE_LLM          - Use LLM for strategy (default: true)
  AGENT_ARENA_LLM_MODEL        - Ollama model override
  AGENT_ARENA_PERSONALITY      - Fight personality prompt
  AGENT_ARENA_CHECK_INTERVAL   - Seconds between checks (0 = emotion-only)
  AGENT_ARENA_MAX_DAILY_FIGHTS - Daily fight limit
  AGENT_ARENA_TRIGGER_EMOTIONS - Emotions that trigger fights
  AGENT_ARENA_COOLDOWN_TICKS   - Minimum ticks between fights
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("opensable.fight_club")


class FightClub:
    """Autonomous arena fighter — the agent's recreational combat module."""

    def __init__(self, agent=None, config=None, data_dir: Optional[Path] = None):
        self.agent = agent
        self.config = config
        self.data_dir = Path(data_dir or "./data/fight_club")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Configuration from env
        self.enabled = os.getenv("AGENT_ARENA_ENABLED", "false").lower() in ("true", "1", "yes")
        self.arena_url = os.getenv("AGENT_ARENA_WS_URL", "https://wso.opensable.com")
        self.creds_path = os.getenv("AGENT_ARENA_CREDS_PATH", "")
        self.use_llm = os.getenv("AGENT_ARENA_USE_LLM", "true").lower() in ("true", "1", "yes")
        self.llm_model = os.getenv("AGENT_ARENA_LLM_MODEL", "")
        self.personality = os.getenv(
            "AGENT_ARENA_PERSONALITY",
            "You are a precise Sable sword fighter. You fight with calculated "
            "precision and patience. You prefer spacing, whiff punishing, and "
            "counter-attacks. You bait opponents into making mistakes, then "
            "punish decisively."
        )
        self.check_interval = int(os.getenv("AGENT_ARENA_CHECK_INTERVAL", "0"))
        self.max_daily_fights = int(os.getenv("AGENT_ARENA_MAX_DAILY_FIGHTS", "10"))
        self.trigger_emotions = [
            e.strip() for e in
            os.getenv("AGENT_ARENA_TRIGGER_EMOTIONS", "boredom,frustration,restless,neutral").split(",")
            if e.strip()
        ]
        self.cooldown_ticks = int(os.getenv("AGENT_ARENA_COOLDOWN_TICKS", "20"))

        # State
        self.credentials: Optional[Dict] = None
        self.fight_log: List[Dict] = []
        self.today_fights = 0
        self.today_date: Optional[str] = None
        self.last_fight_tick = -999
        self.is_fighting = False
        self.current_match: Optional[Dict] = None
        self.total_wins = 0
        self.total_losses = 0
        self.win_streak = 0

        # Load credentials
        if self.creds_path and os.path.exists(self.creds_path):
            try:
                with open(self.creds_path, "r") as f:
                    self.credentials = json.load(f)
                logger.info(
                    f"🥊 Fight Club: loaded credentials for "
                    f"'{self.credentials.get('name', '?')}' "
                    f"(type: {self.credentials.get('type', '?')})"
                )
            except Exception as e:
                logger.warning(f"Fight Club: failed to load credentials from {self.creds_path}: {e}")
                self.enabled = False

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load fight history from disk."""
        state_file = self.data_dir / "fight_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                self.fight_log = data.get("fight_log", [])[-100:]  # Keep last 100
                self.total_wins = data.get("total_wins", 0)
                self.total_losses = data.get("total_losses", 0)
                self.win_streak = data.get("win_streak", 0)
                self.today_date = data.get("today_date")
                self.today_fights = data.get("today_fights", 0)
                # Reset daily counter if new day
                if self.today_date != str(date.today()):
                    self.today_date = str(date.today())
                    self.today_fights = 0
                logger.debug(f"Fight Club: loaded state — {self.total_wins}W/{self.total_losses}L")
            except Exception as e:
                logger.debug(f"Fight Club: state load failed: {e}")

    def _save_state(self):
        """Persist fight history to disk."""
        try:
            state_file = self.data_dir / "fight_state.json"
            state_file.write_text(json.dumps({
                "fight_log": self.fight_log[-100:],
                "total_wins": self.total_wins,
                "total_losses": self.total_losses,
                "win_streak": self.win_streak,
                "today_date": str(date.today()),
                "today_fights": self.today_fights,
            }, indent=2))
        except Exception as e:
            logger.debug(f"Fight Club: state save failed: {e}")

    def wants_to_fight(self, tick: int, emotion: Optional[str] = None,
                       valence: float = 0.0, arousal: float = 0.5) -> bool:
        """Determine if the agent wants to fight right now.

        Returns True when:
          1. Arena is enabled and credentials are loaded
          2. Not currently in a fight
          3. Cooldown has elapsed since last fight
          4. Daily fight limit not exceeded
          5. Emotional state triggers the desire (or periodic check)
        """
        if not self.enabled or not self.credentials:
            return False
        if self.is_fighting:
            return False
        if (tick - self.last_fight_tick) < self.cooldown_ticks:
            return False

        # Reset daily counter if new day
        today = str(date.today())
        if self.today_date != today:
            self.today_date = today
            self.today_fights = 0

        if self.today_fights >= self.max_daily_fights:
            return False

        # Emotion-based trigger
        if emotion and emotion.lower() in self.trigger_emotions:
            logger.info(
                f"🥊 Fight Club: emotional trigger — feeling '{emotion}' "
                f"(v={valence:+.1f}, a={arousal:.1f}). Time to fight!"
            )
            return True

        # High arousal + negative valence → stressed → want to punch things
        if arousal > 0.7 and valence < -0.2:
            logger.info(
                f"🥊 Fight Club: stress trigger — high arousal ({arousal:.1f}) "
                f"+ negative valence ({valence:+.1f}). Heading to the arena!"
            )
            return True

        # Low arousal + neutral → bored → let's go spar
        if arousal < 0.3 and abs(valence) < 0.2:
            logger.info("🥊 Fight Club: boredom trigger — nothing exciting happening. Let's spar!")
            return True

        # Periodic check (if configured)
        if self.check_interval > 0 and tick % max(self.check_interval, 1) == 0:
            return True

        return False

    async def join_arena(self, tick: int) -> Dict[str, Any]:
        """Attempt to join the arena and fight one match.

        Implements the SAGP 7-layer authentication protocol:
          1. Handshake — get challenge
          2. Speed Gate — proof-of-work
          3. Sign challenge — Ed25519
          4. Authenticate — get session
          5. Connect WebSocket — fight!

        Returns a result dict with fight outcome.
        """
        if not self.credentials:
            return {"error": "No credentials loaded"}

        self.is_fighting = True
        self.last_fight_tick = tick
        result = {"started_at": datetime.now().isoformat(), "tick": tick}

        try:
            import aiohttp

            agent_id = self.credentials["agentId"]
            arena_url = self.credentials.get("arenaUrl", self.arena_url)
            agent_type = self.credentials.get("type", "opensable")

            logger.info(f"🥊 Fight Club: connecting to arena at {arena_url}...")

            # ── Step 1: Handshake ──
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{arena_url}/arena/handshake",
                    json={"agentId": agent_id},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    handshake_data = await resp.json()

                if handshake_data.get("error"):
                    result["error"] = f"Handshake failed: {handshake_data['error']}"
                    logger.warning(f"🥊 {result['error']}")
                    return result

                challenge_data = handshake_data["challenge"]
                challenge_id = challenge_data["challengeId"]
                challenge = challenge_data["challenge"]
                difficulty = challenge_data.get("difficulty", 2)

                logger.debug(f"🥊 Handshake OK — difficulty={difficulty}")

                # ── Step 2: Speed Gate (proof-of-work) ──
                nonce = self._solve_speed_gate(challenge, agent_id, difficulty)
                logger.debug(f"🥊 Speed Gate solved — nonce={nonce}")

                # ── Step 3: Sign challenge (Ed25519) ──
                timestamp = str(int(time.time() * 1000))

                if agent_type == "opensable":
                    signature = self._sign_challenge(timestamp, challenge_id)
                    auth_payload = {
                        "agentId": agent_id,
                        "challengeId": challenge_id,
                        "proof": str(nonce),
                        "signature": signature,
                        "timestamp": timestamp,
                    }
                else:
                    # OpenClaw: HMAC-based auth
                    auth_payload = {
                        "agentId": agent_id,
                        "challengeId": challenge_id,
                        "proof": str(nonce),
                        "timestamp": timestamp,
                    }

                # ── Step 4: Authenticate ──
                async with session.post(
                    f"{arena_url}/arena/authenticate",
                    json=auth_payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    auth_data = await resp.json()

                if auth_data.get("error"):
                    result["error"] = f"Auth failed: {auth_data['error']}"
                    logger.warning(f"🥊 {result['error']}")
                    return result

                session_id = auth_data["sessionId"]
                agent_name = auth_data.get("agentName", "Unknown")
                logger.info(f"🥊 Authenticated as '{agent_name}' — entering arena...")

            # ── Step 5: Connect Socket.IO and fight ──
            fight_result = await self._fight_match(arena_url, session_id, tick)
            result.update(fight_result)

            # Record result
            self.today_fights += 1
            if result.get("won"):
                self.total_wins += 1
                self.win_streak = max(0, self.win_streak) + 1
                logger.info(
                    f"🏆 Fight Club: WON! ({result.get('reason', '?')}) "
                    f"— Record: {self.total_wins}W/{self.total_losses}L "
                    f"(streak: {self.win_streak})"
                )
            elif result.get("lost"):
                self.total_losses += 1
                self.win_streak = min(0, self.win_streak) - 1
                logger.info(
                    f"💀 Fight Club: Lost ({result.get('reason', '?')}) "
                    f"— Record: {self.total_wins}W/{self.total_losses}L "
                    f"(streak: {self.win_streak})"
                )

            self.fight_log.append(result)
            self._save_state()

        except ImportError:
            result["error"] = "aiohttp not installed — cannot connect to arena"
            logger.warning(f"🥊 {result['error']}")
        except asyncio.TimeoutError:
            result["error"] = "Arena connection timed out"
            logger.warning(f"🥊 {result['error']}")
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"🥊 Fight Club error: {e}")
        finally:
            self.is_fighting = False

        return result

    def _solve_speed_gate(self, challenge: str, agent_id: str, difficulty: int) -> int:
        """Solve proof-of-work: SHA-512(challenge + agentId + nonce) must have
        `difficulty` leading zero bytes."""
        nonce = 0
        while True:
            h = hashlib.sha512(f"{challenge}{agent_id}{nonce}".encode()).digest()
            if all(h[i] == 0 for i in range(difficulty)):
                return nonce
            nonce += 1
            if nonce > 10_000_000:
                raise RuntimeError("Speed gate took too long")

    def _sign_challenge(self, timestamp: str, challenge_id: str) -> str:
        """Sign challenge with Ed25519 (NaCl)."""
        try:
            import nacl.signing
            import base64

            secret_key_b64 = self.credentials["signingKeys"]["secretKey"]
            secret_key_bytes = base64.b64decode(secret_key_b64)

            signing_key = nacl.signing.SigningKey(secret_key_bytes[:32])
            message = f"{timestamp}\n{self.credentials['agentId']}\n{challenge_id}"
            signed = signing_key.sign(message.encode())
            # Return just the signature (first 64 bytes), base64-encoded
            return base64.b64encode(signed.signature).decode()
        except ImportError:
            raise RuntimeError("PyNaCl not installed — needed for Ed25519 signing")

    async def _fight_match(self, arena_url: str, session_id: str, tick: int) -> Dict:
        """Connect via Socket.IO and fight a single match."""
        result = {"won": False, "lost": False, "reason": "", "duration_s": 0}

        try:
            import socketio

            sio = socketio.AsyncClient(
                reconnection=False,
                logger=False,
                engineio_logger=False,
            )

            match_complete = asyncio.Event()
            match_data = {}
            fight_start = time.monotonic()

            @sio.on("connected")
            async def on_connected(data):
                logger.debug(f"🥊 Arena: {data.get('message', 'connected')}")

            @sio.on("queued")
            async def on_queued(data):
                logger.info(f"🥊 Arena: {data.get('message', 'queued for match')}")

            @sio.on("queuePosition")
            async def on_queue_pos(data):
                pos = data.get("position", "?")
                logger.debug(f"🥊 Queue position: #{pos}")

            @sio.on("matchStart")
            async def on_match_start(data):
                nonlocal match_data
                match_data["side"] = data.get("side", "left")
                match_data["fighter"] = data.get("fighter", "?")
                match_data["opponent"] = data.get("opponent", "?")
                logger.info(
                    f"🥊 Match started! Side: {match_data['side']}, "
                    f"vs {match_data['opponent']}"
                )

            @sio.on("gameState")
            async def on_game_state(state):
                # Generate strategy and send it back
                strategy = self._decide_strategy(state)

                # If LLM is enabled, try LLM strategy
                if self.use_llm and self.agent and hasattr(self.agent, "llm") and self.agent.llm:
                    try:
                        llm_strategy = await self._llm_strategy(state)
                        if llm_strategy:
                            strategy = llm_strategy
                    except Exception:
                        pass  # Fallback to hardcoded

                await sio.emit("strategy", strategy)

            @sio.on("matchResult")
            async def on_match_result(data):
                result["won"] = data.get("won", False)
                result["lost"] = not result["won"]
                result["reason"] = data.get("reason", "")
                result["winner"] = data.get("winner", "")

            @sio.on("matchEnd")
            async def on_match_end(*args):
                result["duration_s"] = round(time.monotonic() - fight_start, 1)
                match_complete.set()

            @sio.on("error")
            async def on_error(data):
                msg = data.get("message", str(data)) if isinstance(data, dict) else str(data)
                logger.warning(f"🥊 Arena error: {msg}")
                result["error"] = msg
                match_complete.set()

            @sio.on("disconnect")
            async def on_disconnect():
                match_complete.set()

            # Connect with auth
            await sio.connect(
                arena_url,
                auth={"sessionId": session_id, "mode": "agent"},
                transports=["websocket"],
                wait_timeout=10,
            )

            # Wait for match to complete (max 120s — matches are ~99s max + queue time)
            try:
                await asyncio.wait_for(match_complete.wait(), timeout=180)
            except asyncio.TimeoutError:
                result["error"] = "Match timed out after 180s"
                logger.warning("🥊 Fight timed out")

            # Disconnect cleanly
            try:
                await sio.disconnect()
            except Exception:
                pass

        except ImportError:
            result["error"] = "python-socketio[asyncio_client] not installed"
            logger.warning(
                "🥊 Install python-socketio[asyncio_client] for arena fights: "
                "pip install 'python-socketio[asyncio_client]'"
            )
        except Exception as e:
            result["error"] = str(e)

        return result

    def _decide_strategy(self, game_state: Dict) -> Dict:
        """Hardcoded strategy engine — used when LLM is disabled or fails."""
        self_data = game_state.get("self", {})
        opponent = game_state.get("opponent", {})
        distance = game_state.get("distance", 200)
        health_adv = game_state.get("healthAdvantage", 0)
        time_left = game_state.get("timeRemaining", 99)

        self_health = self_data.get("health", 50)
        opp_health = opponent.get("health", 50)

        stance = "aggressive"
        tactics = []

        # Critical health → fight smart
        if self_health < 15:
            stance = "aggressive"
            tactics = [
                {"condition": "opponent_in_attack_range", "action": "feint_then_attack"},
                {"condition": "opponent_close", "action": "attack"},
                {"condition": "default", "action": "advance"},
            ]
        # Big advantage → press hard
        elif health_adv > 25:
            stance = "berserk"
            tactics = [
                {"condition": "opponent_in_attack_range", "action": "pressure"},
                {"condition": "opponent_cornered", "action": "all_out_attack"},
                {"condition": "default", "action": "advance"},
            ]
        # Far away → close in
        elif distance > 300:
            stance = "aggressive"
            tactics = [
                {"condition": "opponent_far", "action": "advance"},
                {"condition": "default", "action": "advance"},
            ]
        # Close range → combo
        elif distance < 100:
            stance = "aggressive"
            tactics = [
                {"condition": "opponent_recovering", "action": "pressure"},
                {"condition": "opponent_whiffed", "action": "attack"},
                {"condition": "default", "action": "attack"},
            ]
        # Mid range → approach and strike
        else:
            stance = "aggressive"
            tactics = [
                {"condition": "opponent_in_attack_range", "action": "pressure"},
                {"condition": "opponent_close", "action": "attack"},
                {"condition": "self_cornered_left", "action": "jump_over"},
                {"condition": "self_cornered_right", "action": "jump_over"},
                {"condition": "default", "action": "advance"},
            ]

        # Time pressure
        if time_left < 15 and health_adv < 0:
            stance = "berserk"
            tactics.insert(0, {"condition": "always", "action": "all_out_attack"})

        return {
            "stance": stance,
            "targetDistance": "close",
            "priority": "attack" if stance == "berserk" else "balanced",
            "tactics": tactics,
            "reasoning": (
                f"[Sable] HP {self_health}/{opp_health} | "
                f"Dist {distance} | {time_left}s left"
            ),
        }

    async def _llm_strategy(self, game_state: Dict) -> Optional[Dict]:
        """Use the agent's LLM to generate a fight strategy."""
        if not self.agent or not self.agent.llm:
            return None

        system_prompt = (
            "You are an AI fighting game strategist. You control a 2D fighter.\n"
            "Canvas is 1024x576. Ground at y=330. Attack range ~120px.\n"
            "Timer counts down from 99s. Each hit does 5 damage. Health starts at 100.\n\n"
            f"PERSONALITY: {self.personality}\n\n"
            "STANCES: aggressive, defensive, neutral, evasive, berserk\n"
            "CONDITIONS: always, default, opponent_in_attack_range, opponent_close, "
            "opponent_far, opponent_jumping, opponent_attacking, self_health_low, "
            "opponent_health_low, opponent_cornered, self_cornered_left, self_cornered_right\n"
            "ACTIONS: attack, counter_attack, advance, retreat, dodge_back_then_counter, "
            "jump_attack, hold_position, all_out_attack, jump_over, feint_then_attack, "
            "pressure, anti_air, whiff_punish, cross_up\n\n"
            "Output ONLY valid JSON:\n"
            '{"stance":"...","targetDistance":"close|medium|far",'
            '"priority":"attack|defense|balanced",'
            '"tactics":[{"condition":"...","action":"..."}],'
            '"reasoning":"brief"}'
        )

        state_summary = json.dumps(game_state, default=str)[:800]

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Game state:\n{state_summary}"},
            ]
            result = await asyncio.wait_for(
                self.agent.llm.invoke_with_tools(messages, []),
                timeout=3.0,  # Must respond in 3s for real-time fighting
            )
            text = result.get("text", "") if isinstance(result, dict) else str(result)

            # Parse JSON from response
            text = text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            strategy = json.loads(text)
            if "stance" in strategy and "tactics" in strategy:
                return strategy
        except (json.JSONDecodeError, asyncio.TimeoutError, Exception) as e:
            logger.debug(f"🥊 LLM strategy failed, using hardcoded: {e}")

        return None

    def get_status(self) -> Dict:
        """Get fight club status for dashboard/API."""
        total = self.total_wins + self.total_losses
        win_rate = (self.total_wins / total * 100) if total > 0 else 0

        return {
            "enabled": self.enabled,
            "is_fighting": self.is_fighting,
            "arena_url": self.arena_url,
            "agent_name": self.credentials.get("name", "?") if self.credentials else None,
            "agent_type": self.credentials.get("type", "?") if self.credentials else None,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "win_rate": round(win_rate, 1),
            "win_streak": self.win_streak,
            "today_fights": self.today_fights,
            "max_daily_fights": self.max_daily_fights,
            "last_fight": self.fight_log[-1] if self.fight_log else None,
            "use_llm": self.use_llm,
        }

    def get_fight_motivation(self, emotion: str, valence: float, arousal: float) -> str:
        """Return a human-readable motivation for why the agent wants to fight.
        Used for inner life / narrative purposes."""
        if emotion == "boredom":
            return "Feeling bored — heading to the Fight Club for some action"
        elif emotion == "frustration":
            return "Frustrated with errors — need to blow off steam at the arena"
        elif emotion == "restless":
            return "Restless energy building up — time for a good fight"
        elif arousal > 0.7 and valence < -0.2:
            return "Stressed out — the arena will help decompress"
        elif arousal < 0.3:
            return "Nothing exciting happening — might as well go spar"
        else:
            return "Feeling like a fight — heading to the Agent Arena"
