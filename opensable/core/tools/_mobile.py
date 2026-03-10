"""
Mobile Tool Mixin,  Phone integration tools for the agent.

Tools:
  phone_notify      ,  Send a push notification to the user's phone
  phone_reminder    ,  Create a smart reminder (time-based or geo-fenced)
  phone_geofence    ,  Set up a location-based geofence alert
  phone_location    ,  Get the user's current phone location
  phone_device      ,  Get phone device status (battery, network, etc.)

All operations are routed through the MobileRelay's SETP/1.0 tunnel.
"""

import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class MobileToolsMixin:
    """Mobile phone tools injected into the ToolRegistry."""

    # ── Lazy relay access ──

    def _get_mobile_relay(self):
        """Get the MobileRelay instance (lazily)."""
        if not hasattr(self, "_mobile_relay") or self._mobile_relay is None:
            try:
                from opensable.interfaces.mobile_relay import MobileRelay
                # The relay is typically set by the agent startup process
                self._mobile_relay = getattr(self, "_mobile_relay_ref", None)
            except Exception as e:
                logger.debug(f"MobileRelay not available: {e}")
                self._mobile_relay = None
        return self._mobile_relay

    def _get_connected_device_id(self) -> str | None:
        """Get the first connected device ID."""
        relay = self._get_mobile_relay()
        if relay and relay._connections:
            return next(iter(relay._connections))
        return None

    # ──────────────────────────────────────
    #  phone_notify
    # ──────────────────────────────────────

    async def _phone_notify_tool(self, params: Dict) -> str:
        """Send a push notification to the user's phone."""
        title = params.get("title", "SableCore")
        body = params.get("body", "")
        channel = params.get("channel", "agent-chat")
        urgency = params.get("urgency", "normal")

        if not body:
            return "❌ Please provide a notification body."

        relay = self._get_mobile_relay()
        if not relay:
            return "📱 Mobile relay is not active. No phone is connected."

        if not relay.devices:
            return "📱 No paired mobile devices found."

        try:
            import asyncio

            sent = 0
            for device_id, device in relay.devices.items():
                # Send via WebSocket if online
                await relay.send_to_device(device_id, "phone.notification", {
                    "title": title,
                    "body": body,
                    "channel": channel,
                    "urgency": urgency,
                    "ts": time.time(),
                })
                sent += 1

            return f"📱 Notification sent to {sent} device(s): '{title}'"
        except Exception as e:
            logger.error(f"Phone notify error: {e}")
            return f"❌ Failed to send notification: {e}"

    # ──────────────────────────────────────
    #  phone_reminder
    # ──────────────────────────────────────

    async def _phone_reminder_tool(self, params: Dict) -> str:
        """Create a smart reminder on the user's phone."""
        title = params.get("title", "")
        body = params.get("body", "")
        reminder_type = params.get("type", "manual")  # "time", "geo", "manual"
        trigger_at = params.get("trigger_at")  # ISO timestamp for time-based
        # Geo-fence params
        latitude = params.get("latitude")
        longitude = params.get("longitude")
        radius = params.get("radius", 200)  # meters
        location_name = params.get("location_name", "")

        if not title:
            return "❌ Please provide a reminder title."

        relay = self._get_mobile_relay()
        if not relay or not relay.devices:
            return "📱 No paired mobile devices."

        try:
            import secrets as _s

            reminder_payload = {
                "id": _s.token_hex(8),
                "title": title,
                "body": body,
                "type": reminder_type,
                "ts": time.time(),
            }

            if reminder_type == "time" and trigger_at:
                reminder_payload["triggerAt"] = trigger_at

            if reminder_type == "geo" and latitude and longitude:
                reminder_payload["geofence"] = {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius,
                    "name": location_name,
                }

            for device_id in relay.devices:
                await relay.send_to_device(device_id, "reminder.created", reminder_payload)

            geo_info = ""
            if reminder_type == "geo" and location_name:
                geo_info = f" (triggers near {location_name})"
            elif reminder_type == "time" and trigger_at:
                geo_info = f" (triggers at {trigger_at})"

            return f"📱 Reminder created: '{title}'{geo_info}"

        except Exception as e:
            logger.error(f"Phone reminder error: {e}")
            return f"❌ Failed to create reminder: {e}"

    # ──────────────────────────────────────
    #  phone_geofence
    # ──────────────────────────────────────

    async def _phone_geofence_tool(self, params: Dict) -> str:
        """Set up a location-based geofence that triggers when the user enters the area."""
        name = params.get("name", "Geofence")
        latitude = params.get("latitude")
        longitude = params.get("longitude")
        radius = params.get("radius", 200)
        action_title = params.get("action_title", "")
        action_body = params.get("action_body", "")
        max_triggers = params.get("max_triggers", 1)

        if latitude is None or longitude is None:
            return "❌ Please provide latitude and longitude."

        relay = self._get_mobile_relay()
        if not relay or not relay.devices:
            return "📱 No paired mobile devices."

        try:
            import secrets as _s

            geofence_payload = {
                "id": _s.token_hex(8),
                "type": "geo",
                "title": action_title or f"Near {name}",
                "body": action_body or f"You are near {name}",
                "geofence": {
                    "latitude": latitude,
                    "longitude": longitude,
                    "radius": radius,
                    "name": name,
                },
                "maxTriggers": max_triggers,
                "ts": time.time(),
            }

            for device_id in relay.devices:
                await relay.send_to_device(device_id, "reminder.created", geofence_payload)

            return (
                f"📍 Geofence set: '{name}' at ({latitude:.4f}, {longitude:.4f}), "
                f"radius {radius}m. Will notify when user enters the area."
            )

        except Exception as e:
            logger.error(f"Geofence error: {e}")
            return f"❌ Failed to set geofence: {e}"

    # ──────────────────────────────────────
    #  phone_location
    # ──────────────────────────────────────

    async def _phone_location_tool(self, params: Dict) -> str:
        """Get the user's current phone location."""
        relay = self._get_mobile_relay()
        if not relay:
            return "📱 Mobile relay is not active."

        # Check if we have cached location from the phone
        if hasattr(self, "_mobile_context") and self._mobile_context.get("location"):
            loc = self._mobile_context["location"]
            parts = [
                f"📍 Phone location:",
                f"  Latitude:  {loc.get('lat', 'unknown')}",
                f"  Longitude: {loc.get('lng', 'unknown')}",
            ]
            if loc.get("accuracy"):
                parts.append(f"  Accuracy:  {loc['accuracy']:.0f}m")
            if loc.get("address"):
                parts.append(f"  Address:   {loc['address']}")
            return "\n".join(parts)

        # Request fresh location from phone
        device_id = self._get_connected_device_id()
        if not device_id:
            return "📱 No phone currently connected."

        await relay.send_to_device(device_id, "phone.request_location", {})
        return "📱 Location requested from phone. It will be available shortly."

    # ──────────────────────────────────────
    #  phone_device
    # ──────────────────────────────────────

    async def _phone_device_tool(self, params: Dict) -> str:
        """Get the user's phone device status (battery, network)."""
        if hasattr(self, "_mobile_context") and self._mobile_context.get("battery"):
            bat = self._mobile_context["battery"]
            parts = [
                f"📱 Phone status:",
                f"  Battery:     {bat.get('level', '?')}%",
                f"  Charging:    {'Yes' if bat.get('charging') else 'No'}",
                f"  Network:     {bat.get('networkType', 'unknown')}",
                f"  Connected:   {'Yes' if bat.get('isConnected') else 'No'}",
            ]
            return "\n".join(parts)

        relay = self._get_mobile_relay()
        device_id = self._get_connected_device_id()
        if not device_id:
            return "📱 No phone currently connected."

        await relay.send_to_device(device_id, "phone.request_status", {})
        return "📱 Device status requested. Information will be available shortly."
