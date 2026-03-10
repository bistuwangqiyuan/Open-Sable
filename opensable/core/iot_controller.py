"""
IoT / Smart Home Controller

Home Assistant REST API integration for controlling smart home devices.
Supports lights, switches, locks, thermostats, cameras, sensors, scenes,
and automation management through Home Assistant's REST API.

Features:
  1. Device discovery,  Auto-discover all HA entities
  2. Light control,  On/off/brightness/color/temperature
  3. Climate control,  Temperature/HVAC mode/fan speed
  4. Lock/switch control,  Lock/unlock, turn on/off
  5. Scene activation,  Trigger HA scenes
  6. Sensor reading,  Temperature, humidity, motion, door/window state
  7. Automation management,  Enable/disable/trigger HA automations
  8. NL commands,  "Turn off the living room lights"
  9. Routines,  Combine multiple commands into one action
  10. State monitoring,  Watch for device state changes
"""
import json
import logging
import asyncio
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


# ── Data Models ───────────────────────────────────────────────────────

@dataclass
class IoTDevice:
    """Represents a discovered Home Assistant entity."""
    entity_id: str
    friendly_name: str
    domain: str          # light, switch, lock, climate, sensor, etc.
    state: str = "unknown"
    attributes: Dict[str, Any] = field(default_factory=dict)
    last_updated: str = ""

@dataclass
class IoTRoutine:
    """A named sequence of device actions."""
    name: str
    description: str = ""
    actions: List[Dict[str, Any]] = field(default_factory=list)
    created: str = ""
    last_run: str = ""
    run_count: int = 0


# ── Core Controller ──────────────────────────────────────────────────

class IoTController:
    """
    Home Assistant integration for smart-home control.
    Uses the HA REST API to discover and control devices.
    """

    SUPPORTED_DOMAINS = [
        "light", "switch", "lock", "climate", "sensor",
        "binary_sensor", "cover", "fan", "media_player",
        "scene", "automation", "camera", "vacuum",
    ]

    def __init__(self, data_dir: Path, ha_url: str = "", ha_token: str = ""):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.data_dir / "iot_controller_state.json"

        self.ha_url = ha_url.rstrip("/") if ha_url else ""
        self.ha_token = ha_token
        self._llm = None

        # Device registry
        self.devices: Dict[str, IoTDevice] = {}
        self.routines: Dict[str, IoTRoutine] = {}

        # Stats
        self.total_commands = 0
        self.total_discoveries = 0
        self.total_routines_run = 0
        self.total_queries = 0
        self.errors = 0

        self._load_state()

    def set_llm(self, llm):
        self._llm = llm

    def configure(self, ha_url: str, ha_token: str):
        """Configure Home Assistant connection."""
        self.ha_url = ha_url.rstrip("/")
        self.ha_token = ha_token
        self._save_state()

    @property
    def is_configured(self) -> bool:
        return bool(self.ha_url and self.ha_token)

    # ── HA REST API ──────────────────────────────────────────────────

    async def _ha_request(
        self, method: str, path: str, data: Optional[Dict] = None
    ) -> Optional[Any]:
        """Make authenticated request to Home Assistant API."""
        if not self.is_configured:
            return {"error": "Home Assistant not configured. Set HA_URL and HA_TOKEN."}
        if not AIOHTTP_AVAILABLE:
            return {"error": "aiohttp not installed"}

        url = f"{self.ha_url}/api/{path}"
        headers = {
            "Authorization": f"Bearer {self.ha_token}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, headers=headers, json=data, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        self.errors += 1
                        text = await resp.text()
                        return {"error": f"HA returned {resp.status}: {text[:200]}"}
        except Exception as e:
            self.errors += 1
            return {"error": f"HA request failed: {str(e)}"}

    # ── Device Discovery ─────────────────────────────────────────────

    async def discover_devices(self) -> Dict[str, Any]:
        """Discover all entities from Home Assistant."""
        self.total_discoveries += 1
        states = await self._ha_request("GET", "states")

        if isinstance(states, dict) and "error" in states:
            return states

        if not isinstance(states, list):
            return {"error": "Unexpected response from HA", "raw": str(states)[:200]}

        count = 0
        for entity in states:
            eid = entity.get("entity_id", "")
            domain = eid.split(".")[0] if "." in eid else ""

            if domain not in self.SUPPORTED_DOMAINS:
                continue

            attrs = entity.get("attributes", {})
            self.devices[eid] = IoTDevice(
                entity_id=eid,
                friendly_name=attrs.get("friendly_name", eid),
                domain=domain,
                state=entity.get("state", "unknown"),
                attributes=attrs,
                last_updated=entity.get("last_updated", ""),
            )
            count += 1

        self._save_state()
        return {
            "devices_discovered": count,
            "by_domain": self._count_by_domain(),
        }

    def _count_by_domain(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for dev in self.devices.values():
            counts[dev.domain] = counts.get(dev.domain, 0) + 1
        return counts

    def list_devices(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """List discovered devices, optionally filtered by domain."""
        devices = list(self.devices.values())
        if domain:
            devices = [d for d in devices if d.domain == domain]
        return [
            {
                "entity_id": d.entity_id,
                "name": d.friendly_name,
                "domain": d.domain,
                "state": d.state,
            }
            for d in devices
        ]

    # ── Device Control ───────────────────────────────────────────────

    async def call_service(
        self, domain: str, service: str, entity_id: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Call a Home Assistant service on a device."""
        self.total_commands += 1
        payload = {"entity_id": entity_id}
        if data:
            payload.update(data)

        result = await self._ha_request("POST", f"services/{domain}/{service}", payload)
        if result is not None and not (isinstance(result, dict) and "error" in result):
            # Update local state
            if entity_id in self.devices:
                if service in ("turn_on",):
                    self.devices[entity_id].state = "on"
                elif service in ("turn_off",):
                    self.devices[entity_id].state = "off"
                elif service in ("lock",):
                    self.devices[entity_id].state = "locked"
                elif service in ("unlock",):
                    self.devices[entity_id].state = "unlocked"
            self._save_state()
            return {"ok": True, "entity_id": entity_id, "service": f"{domain}.{service}"}

        return result or {"error": "No response from HA"}

    async def light_control(
        self,
        entity_id: str,
        action: str = "on",
        brightness: Optional[int] = None,
        color_rgb: Optional[List[int]] = None,
        color_temp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Control a light entity."""
        data = {}
        if brightness is not None:
            data["brightness"] = min(255, max(0, brightness))
        if color_rgb:
            data["rgb_color"] = color_rgb[:3]
        if color_temp:
            data["color_temp"] = color_temp

        service = "turn_on" if action.lower() in ("on", "turn_on") else "turn_off"
        return await self.call_service("light", service, entity_id, data if data else None)

    async def climate_control(
        self,
        entity_id: str,
        temperature: Optional[float] = None,
        hvac_mode: Optional[str] = None,
        fan_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Control a climate/thermostat entity."""
        results = []

        if temperature is not None:
            r = await self.call_service("climate", "set_temperature", entity_id, {"temperature": temperature})
            results.append(r)

        if hvac_mode:
            r = await self.call_service("climate", "set_hvac_mode", entity_id, {"hvac_mode": hvac_mode})
            results.append(r)

        if fan_mode:
            r = await self.call_service("climate", "set_fan_mode", entity_id, {"fan_mode": fan_mode})
            results.append(r)

        return {"results": results} if results else {"error": "No action specified"}

    async def lock_control(self, entity_id: str, action: str = "lock") -> Dict[str, Any]:
        """Lock or unlock a lock entity."""
        service = "lock" if action.lower() in ("lock",) else "unlock"
        return await self.call_service("lock", service, entity_id)

    async def switch_control(self, entity_id: str, action: str = "on") -> Dict[str, Any]:
        """Turn a switch on or off."""
        service = "turn_on" if action.lower() in ("on", "turn_on") else "turn_off"
        return await self.call_service("switch", service, entity_id)

    async def activate_scene(self, entity_id: str) -> Dict[str, Any]:
        """Activate a Home Assistant scene."""
        return await self.call_service("scene", "turn_on", entity_id)

    async def trigger_automation(self, entity_id: str) -> Dict[str, Any]:
        """Trigger a Home Assistant automation."""
        return await self.call_service("automation", "trigger", entity_id)

    # ── Sensor Reading ───────────────────────────────────────────────

    async def read_sensor(self, entity_id: str) -> Dict[str, Any]:
        """Read current sensor state from HA."""
        self.total_queries += 1
        result = await self._ha_request("GET", f"states/{entity_id}")

        if isinstance(result, dict) and "error" not in result:
            state = result.get("state", "unknown")
            attrs = result.get("attributes", {})

            # Update local
            if entity_id in self.devices:
                self.devices[entity_id].state = state
                self.devices[entity_id].attributes = attrs

            return {
                "entity_id": entity_id,
                "state": state,
                "unit": attrs.get("unit_of_measurement", ""),
                "friendly_name": attrs.get("friendly_name", entity_id),
                "device_class": attrs.get("device_class", ""),
                "last_updated": result.get("last_updated", ""),
            }
        return result or {"error": "Failed to read sensor"}

    async def get_all_sensor_readings(self) -> List[Dict[str, Any]]:
        """Read all sensors."""
        sensors = [d for d in self.devices.values() if d.domain in ("sensor", "binary_sensor")]
        readings = []
        for s in sensors[:50]:  # Limit to 50 for performance
            r = await self.read_sensor(s.entity_id)
            if "error" not in r:
                readings.append(r)
        return readings

    # ── Natural Language Commands ─────────────────────────────────────

    async def execute_nl_command(self, command: str) -> Dict[str, Any]:
        """Parse and execute a natural language smart home command."""
        self.total_commands += 1
        command_lower = command.lower()

        # Try LLM parsing first
        if self._llm and self.devices:
            return await self._llm_parse_command(command)

        # Heuristic parsing
        return await self._heuristic_command(command_lower)

    async def _llm_parse_command(self, command: str) -> Dict[str, Any]:
        """Use LLM to parse smart home command."""
        device_list = "\n".join(
            f"- {d.entity_id} ({d.friendly_name}, {d.domain}, state={d.state})"
            for d in list(self.devices.values())[:50]
        )

        prompt = (
            "Parse this smart home command and return JSON with the action to take.\n"
            f"Available devices:\n{device_list}\n\n"
            f"Command: {command}\n\n"
            'Return JSON: {{"entity_id": "...", "domain": "...", "service": "...", "data": {{}}}}\n'
            "JSON:"
        )

        try:
            resp = await self._llm.invoke_with_tools(
                [{"role": "user", "content": prompt}], []
            )
            raw = resp.get("text", "")

            import re
            match = re.search(r'\{[\s\S]*?\}', raw)
            if match:
                action = json.loads(match.group())
                entity_id = action.get("entity_id", "")
                domain = action.get("domain", entity_id.split(".")[0] if "." in entity_id else "")
                service = action.get("service", "turn_on")
                data = action.get("data", {})

                result = await self.call_service(domain, service, entity_id, data if data else None)
                return {"parsed": action, "result": result}
        except Exception as e:
            logger.debug(f"[IoT] LLM parse failed: {e}")

        return await self._heuristic_command(command.lower())

    async def _heuristic_command(self, cmd: str) -> Dict[str, Any]:
        """Parse command with simple heuristics."""
        # Find matching device
        target_device = None
        for dev in self.devices.values():
            if dev.friendly_name.lower() in cmd or dev.entity_id.lower() in cmd:
                target_device = dev
                break

        if not target_device:
            return {"error": f"Could not find matching device for: {cmd}"}

        # Determine action
        if any(w in cmd for w in ("turn off", "off", "apaga", "apagar")):
            service = "turn_off"
        elif any(w in cmd for w in ("turn on", "on", "enciende", "encender", "prende")):
            service = "turn_on"
        elif any(w in cmd for w in ("lock", "cierra")):
            service = "lock"
        elif any(w in cmd for w in ("unlock", "abre")):
            service = "unlock"
        else:
            service = "turn_on"

        return await self.call_service(
            target_device.domain, service, target_device.entity_id
        )

    # ── Routines ─────────────────────────────────────────────────────

    def create_routine(
        self, name: str, description: str, actions: List[Dict[str, Any]]
    ) -> IoTRoutine:
        """Create a named routine (sequence of actions)."""
        routine = IoTRoutine(
            name=name,
            description=description,
            actions=actions,
            created=datetime.now(timezone.utc).isoformat(),
        )
        self.routines[name] = routine
        self._save_state()
        return routine

    async def run_routine(self, name: str) -> Dict[str, Any]:
        """Execute a named routine."""
        if name not in self.routines:
            return {"error": f"Routine '{name}' not found"}

        routine = self.routines[name]
        routine.run_count += 1
        routine.last_run = datetime.now(timezone.utc).isoformat()
        self.total_routines_run += 1

        results = []
        for action in routine.actions:
            result = await self.call_service(
                domain=action.get("domain", ""),
                service=action.get("service", "turn_on"),
                entity_id=action.get("entity_id", ""),
                data=action.get("data"),
            )
            results.append(result)
            await asyncio.sleep(0.2)  # Small delay between actions

        self._save_state()
        return {"routine": name, "actions_executed": len(results), "results": results}

    # ── Persistence ──────────────────────────────────────────────────

    def _save_state(self):
        try:
            state = {
                "ha_url": self.ha_url,
                "devices": {eid: asdict(d) for eid, d in self.devices.items()},
                "routines": {name: asdict(r) for name, r in self.routines.items()},
                "total_commands": self.total_commands,
                "total_discoveries": self.total_discoveries,
                "total_routines_run": self.total_routines_run,
                "total_queries": self.total_queries,
                "errors": self.errors,
            }
            self.state_file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
        except Exception as e:
            logger.error(f"[IoT] Save failed: {e}")

    def _load_state(self):
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.ha_url = state.get("ha_url", self.ha_url)

                for eid, dd in state.get("devices", {}).items():
                    self.devices[eid] = IoTDevice(**{
                        k: v for k, v in dd.items() if k in IoTDevice.__dataclass_fields__
                    })

                for name, rd in state.get("routines", {}).items():
                    self.routines[name] = IoTRoutine(**{
                        k: v for k, v in rd.items() if k in IoTRoutine.__dataclass_fields__
                    })

                self.total_commands = state.get("total_commands", 0)
                self.total_discoveries = state.get("total_discoveries", 0)
                self.total_routines_run = state.get("total_routines_run", 0)
                self.total_queries = state.get("total_queries", 0)
                self.errors = state.get("errors", 0)

                logger.info(f"[IoT] Loaded {len(self.devices)} devices, {len(self.routines)} routines")
            except Exception as e:
                logger.error(f"[IoT] Load failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "configured": self.is_configured,
            "ha_url": self.ha_url or "(not set)",
            "total_devices": len(self.devices),
            "by_domain": self._count_by_domain(),
            "total_routines": len(self.routines),
            "total_commands": self.total_commands,
            "total_discoveries": self.total_discoveries,
            "total_routines_run": self.total_routines_run,
            "total_queries": self.total_queries,
            "errors": self.errors,
        }
