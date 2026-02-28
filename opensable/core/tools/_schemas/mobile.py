"""
Tool schemas for Mobile domain.
"""

SCHEMAS = [
    # ── Mobile phone tools ──────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "phone_notify",
    "description": "Send a push notification to the user's phone. Use this to alert the user about important events, trade signals, task completions, or any information they should see immediately.",
    "parameters": {
    "type": "object",
    "properties": {
    "title": {
    "type": "string",
    "description": "Notification title (short)",
    },
    "body": {
    "type": "string",
    "description": "Notification body/message",
    },
    "channel": {
    "type": "string",
    "description": "Notification channel: 'agent-chat', 'trade-alerts', 'reminders', 'system'",
    "default": "agent-chat",
    },
    "urgency": {
    "type": "string",
    "description": "Urgency level: 'low', 'normal', 'high', 'critical'",
    "default": "normal",
    },
    },
    "required": ["title", "body"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "phone_reminder",
    "description": "Create a smart reminder on the user's phone. Can be time-based (triggers at a specific time) or geo-fenced (triggers when the user enters a location area). Use 'geo' type for location-based reminders like 'remind me to buy medicine when I'm near a pharmacy'.",
    "parameters": {
    "type": "object",
    "properties": {
    "title": {
    "type": "string",
    "description": "Reminder title",
    },
    "body": {
    "type": "string",
    "description": "Reminder details/description",
    },
    "type": {
    "type": "string",
    "description": "Reminder type: 'time' (triggers at a time), 'geo' (triggers at a location), 'manual' (user dismisses)",
    "default": "manual",
    },
    "trigger_at": {
    "type": "string",
    "description": "For time-based: ISO 8601 timestamp when to trigger (e.g. '2025-01-15T09:00:00')",
    },
    "latitude": {
    "type": "number",
    "description": "For geo-based: latitude of the target location",
    },
    "longitude": {
    "type": "number",
    "description": "For geo-based: longitude of the target location",
    },
    "radius": {
    "type": "integer",
    "description": "For geo-based: radius in meters (default 200)",
    "default": 200,
    },
    "location_name": {
    "type": "string",
    "description": "Human-readable name of the location (e.g. 'Walgreens on 5th Ave')",
    },
    },
    "required": ["title"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "phone_geofence",
    "description": "Set a geofence that triggers when the user enters a specific area. Use this for location-based alerts, check-ins, or context-aware actions. The phone will monitor the area in the background.",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {
    "type": "string",
    "description": "Geofence name (e.g. 'Office', 'Pharmacy', 'Gym')",
    },
    "latitude": {
    "type": "number",
    "description": "Latitude of the geofence center",
    },
    "longitude": {
    "type": "number",
    "description": "Longitude of the geofence center",
    },
    "radius": {
    "type": "integer",
    "description": "Radius in meters (default 200)",
    "default": 200,
    },
    "action_title": {
    "type": "string",
    "description": "Notification title when geofence is entered",
    },
    "action_body": {
    "type": "string",
    "description": "Notification body when geofence is entered",
    },
    "max_triggers": {
    "type": "integer",
    "description": "Max times to trigger (default 1, set higher for recurring geofences)",
    "default": 1,
    },
    },
    "required": ["name", "latitude", "longitude"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "phone_location",
    "description": "Get the user's current phone location (GPS coordinates and address). Use this to provide location-aware responses or set up geo-fences near the user.",
    "parameters": {
    "type": "object",
    "properties": {},
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "phone_device",
    "description": "Get the user's phone device status including battery level, charging state, and network connectivity. Use this to adapt behavior (e.g. reduce notifications when battery is low).",
    "parameters": {
    "type": "object",
    "properties": {},
    },
    },
    },

]
