"""
Fight Club — Autonomous Arena Participation

Runs the existing Node.js agent script (example-sable-agent.js) as a subprocess.
The agent decides to fight based on emotional state (boredom, frustration, stress).

Only 2 env vars:
  AGENT_ARENA_ENABLED  - true/false
  AGENT_ARENA_WS_URL   - Arena WebSocket URL
"""

import asyncio
import json
import logging
import os
import re
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("opensable.fight_club")

# Common places where the fighting-game repo might live
_SEARCH_PATHS = [
    Path.home() / "fighting-game",
    Path(__file__).resolve().parent.parent.parent.parent / "fighting-game",
    Path("/home/nexland/fighting-game"),
]


class FightClub:
    """Spawns the existing Node.js arena agent script to fight."""

    def __init__(self, agent=None, config=None, data_dir: Optional[Path] = None):
        self.agent = agent
        self.config = config
        self.data_dir = Path(data_dir or "./data/fight_club")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Config (just 2 env vars)
        self.enabled = os.getenv("AGENT_ARENA_ENABLED", "false").lower() in ("true", "1", "yes")
        self.arena_url = os.getenv("AGENT_ARENA_WS_URL", "https://wso.opensable.com")

        # Auto-discover fighting-game directory and credentials
        self.game_dir: Optional[Path] = None
        self.creds_file: Optional[Path] = None
        self.script_file: Optional[Path] = None
        self._discover_game_files()

        # State
        self.is_fighting = False
        self.last_fight_tick = -999
        self.total_wins = 0
        self.total_losses = 0
        self.win_streak = 0
        self.today_fights = 0
        self.today_date: Optional[str] = None
        self.fight_log: List[Dict] = []

        self._load_state()

    def _discover_game_files(self):
        """Auto-find the fighting-game repo, script, and credentials."""
        for p in _SEARCH_PATHS:
            ws = p / "websocket"
            script = ws / "example-sable-agent.js"
            if script.exists():
                self.game_dir = p
                self.script_file = script
                # Find first opensable credential file
                for f in sorted(ws.glob("agent-*.json")):
                    try:
                        data = json.loads(f.read_text())
                        if data.get("type") == "opensable":
                            self.creds_file = f
                            logger.info(f"🥊 Fight Club: found creds '{data.get('name')}' -> {f.name}")
                            return
                    except Exception:
                        continue
                # No opensable creds, take any
                for f in sorted(ws.glob("agent-*.json")):
                    self.creds_file = f
                    logger.info(f"🥊 Fight Club: found creds -> {f.name}")
                    return
                logger.info(f"🥊 Fight Club: script found but no credentials in {ws}")
                return

        if self.enabled:
            logger.warning("🥊 Fight Club: fighting-game directory not found")

    # -- State persistence -----------------------------------------------------

    def _load_credentials(self):
        """Load cached credentials from disk, or mark for auto-provisioning."""
        cred_file = self.data_dir / "credentials.json"
        if cred_file.exists():
            try:
                self.credentials = json.loads(cred_file.read_text())
                logger.info(
                    f"🥊 Fight Club: credentials loaded for "
                    f"'{self.credentials.get('name', '?')}' "
                    f"(id: {self.credentials.get('agentId', '?')[:8]}...)"
                )
            except Exception as e:
                logger.warning(f"Fight Club: failed to load credentials: {e}")
                self.credentials = None
        else:
            if self.enabled:
                logger.info(
                    "🥊 Fight Club: no credentials found — will auto-provision "
                    "with arena on first fight attempt."
                )

    def _save_credentials(self):
        """Persist credentials to disk."""
        if not self.credentials:
            return
        try:
            cred_file = self.data_dir / "credentials.json"
            cred_file.write_text(json.dumps(self.credentials, indent=2))
            # Restrict permissions (best-effort on Linux)
            try:
                cred_file.chmod(0o600)
            except OSError:
                pass
        except Exception as e:
            logger.warning(f"Fight Club: failed to save credentials: {e}")

    async def _auto_provision(self) -> bool:
        """Generate Ed25519 keypair and register with the arena server.

        Called automatically on first fight attempt. Credentials are
        cached to data/fight_club/credentials.json for future runs.
        """
        if self._provisioning:
            return False
        self._provisioning = True

        try:
            import nacl.signing

            # Generate Ed25519 keypair locally
            signing_key = nacl.signing.SigningKey.generate()
            public_key_b64 = base64.b64encode(bytes(signing_key.verify_key)).decode()
            secret_key_b64 = base64.b64encode(bytes(signing_key)).decode()

            logger.info(f"🥊 Fight Club: auto-provisioning with arena at {self.arena_url}...")

            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.arena_url}/arena/provision",
                    json={
                        "name": _AGENT_NAME,
                        "type": _AGENT_TYPE,
                        "publicKey": public_key_b64,
                    },
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    data = await resp.json()

            if data.get("error"):
                logger.warning(f"🥊 Auto-provision failed: {data['error']}")
                return False

            agent_id = data["agentId"]

            # If agent already existed, we need to use ITS keypair — but we
            # can't (server doesn't return secret keys). If the name was already
            # registered with a DIFFERENT public key, auth will fail.
            # In that case, use the existing credentials file if present.
            if "already registered" in data.get("message", "").lower():
                logger.info(
                    f"🥊 Fight Club: agent '{_AGENT_NAME}' already registered "
                    f"(id: {agent_id[:8]}...). Using new keypair — if auth fails, "
                    "delete data/fight_club/credentials.json and the arena entry."
                )

            self.credentials = {
                "agentId": agent_id,
                "name": data.get("name", _AGENT_NAME),
                "type": data.get("type", _AGENT_TYPE),
                "arenaUrl": self.arena_url,
                "signingKeys": {
                    "publicKey": public_key_b64,
                    "secretKey": secret_key_b64,
                },
            }

            self._save_credentials()
            logger.info(
                f"🥊 Fight Club: provisioned as '{self.credentials['name']}' "
                f"(id: {agent_id[:8]}...) — credentials saved to disk."
            )
            return True

        except ImportError:
            logger.warning(
                "🥊 Fight Club: PyNaCl not installed — needed for Ed25519 keys. "
                "pip install pynacl"
            )
            return False
        except Exception as e:
            logger.warning(f"🥊 Fight Club: auto-provision error: {e}")
            return False
        finally:
            self._provisioning = False

    def _load_state(self):
        state_file = self.data_dir / "state.json"
        if state_file.exists():
            try:
                d = json.loads(state_file.read_text())
                self.total_wins = d.get("wins", 0)
                self.total_losses = d.get("losses", 0)
                self.win_streak = d.get("streak", 0)
                self.today_date = d.get("today")
                self.today_fights = d.get("today_fights", 0)
                self.fight_log = d.get("log", [])[-50:]
                if self.today_date != str(date.today()):
                    self.today_date = str(date.today())
                    self.today_fights = 0
            except Exception:
                pass

    def _save_state(self):
        try:
            (self.data_dir / "state.json").write_text(json.dumps({
                "wins": self.total_wins, "losses": self.total_losses,
                "streak": self.win_streak, "today": str(date.today()),
                "today_fights": self.today_fights, "log": self.fight_log[-50:],
            }, indent=2))
        except Exception:
            pass

    # -- Decision logic --------------------------------------------------------

    def wants_to_fight(self, tick: int, emotion: str = "neutral",
                       valence: float = 0.0, arousal: float = 0.5) -> bool:
        """Should the agent go fight right now?"""
        if not self.enabled or not self.creds_file or not self.script_file:
            return False
        if self.is_fighting:
            return False
        if (tick - self.last_fight_tick) < 20:
            return False
        today = str(date.today())
        if self.today_date != today:
            self.today_date = today
            self.today_fights = 0
        if self.today_fights >= 10:
            return False

        triggers = {"boredom", "frustration", "restless", "neutral"}
        if emotion.lower() in triggers:
            return True
        if arousal > 0.7 and valence < -0.2:
            return True
        if arousal < 0.3 and abs(valence) < 0.2:
            return True
        return False

    def get_fight_motivation(self, emotion: str, valence: float, arousal: float) -> str:
        motivations = {
            "boredom": "Feeling bored -- heading to the Fight Club",
            "frustration": "Frustrated -- need to blow off steam at the arena",
            "restless": "Restless energy -- time for a good fight",
        }
        if emotion in motivations:
            return motivations[emotion]
        if arousal > 0.7 and valence < -0.2:
            return "Stressed out -- the arena will help decompress"
        if arousal < 0.3:
            return "Nothing happening -- might as well go spar"
        return "Feeling like a fight -- heading to the Agent Arena"

    # -- Fight execution -------------------------------------------------------

    async def join_arena(self, tick: int) -> Dict[str, Any]:
        """Run the Node.js agent script and parse the result."""
        if not self.creds_file or not self.script_file:
            return {"error": "No fight script or credentials found"}

        self.is_fighting = True
        self.last_fight_tick = tick
        result = {"tick": tick, "won": False, "lost": False, "reason": ""}

        try:
            logger.info(f"🥊 Fight Club: launching fighter -- {self.creds_file.name}")

            env = {**os.environ, "USE_LLM": "false"}
            ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            try:
                import aiohttp
                async with aiohttp.ClientSession() as s:
                    async with s.get(f"{ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=2)) as r:
                        if r.status == 200:
                            env["USE_LLM"] = "true"
                            env["OLLAMA_URL"] = ollama_url
            except Exception:
                pass

            proc = await asyncio.create_subprocess_exec(
                "node", str(self.script_file), str(self.creds_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=str(self.script_file.parent),
                env=env,
            )

            try:
                stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=200)
                output = stdout.decode(errors="replace") if stdout else ""
            except asyncio.TimeoutError:
                proc.kill()
                result["error"] = "Fight timed out"
                return result

            if "WON!" in output:
                result["won"] = True
                self.total_wins += 1
                self.win_streak = max(0, self.win_streak) + 1
            elif "LOST!" in output:
                result["lost"] = True
                self.total_losses += 1
                self.win_streak = min(0, self.win_streak) - 1

            reason_match = re.search(r"(?:WON!|LOST!)\s*Winner:.*?\((.+?)\)", output)
            if reason_match:
                result["reason"] = reason_match.group(1)

            status = "WON" if result["won"] else "LOST" if result["lost"] else "UNKNOWN"
            logger.info(
                f"🥊 Fight Club: {status} ({result['reason']}) -- "
                f"Record: {self.total_wins}W/{self.total_losses}L (streak: {self.win_streak})"
            )

            self.today_fights += 1
            self.fight_log.append(result)
            self._save_state()

        except FileNotFoundError:
            result["error"] = "Node.js not installed"
        except Exception as e:
            result["error"] = str(e)
            logger.warning(f"🥊 Fight error: {e}")
        finally:
            self.is_fighting = False

        return result

    # -- Status ----------------------------------------------------------------

    def get_status(self) -> Dict:
        total = self.total_wins + self.total_losses
        return {
            "enabled": self.enabled,
            "is_fighting": self.is_fighting,
            "arena_url": self.arena_url,
            "has_credentials": self.creds_file is not None,
            "has_script": self.script_file is not None,
            "total_wins": self.total_wins,
            "total_losses": self.total_losses,
            "win_rate": round(self.total_wins / total * 100, 1) if total else 0,
            "win_streak": self.win_streak,
            "today_fights": self.today_fights,
        }

    def get_stats(self):
        return self.get_status()
