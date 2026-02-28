"""
Tool schemas for Calendar Google domain.
"""

SCHEMAS = [
    # ── Calendar tools (local + Google Calendar) ──
    {
    "type": "function",
    "function": {
    "name": "calendar_list_events",
    "description": "List upcoming calendar events (local store or Google Calendar if configured)",
    "parameters": {
    "type": "object",
    "properties": {
    "days_ahead": {"type": "integer", "description": "Number of days to look ahead (default: 7)"},
    "source": {"type": "string", "description": "'local' or 'google' (default: auto-detect)"},
    },
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "calendar_add_event",
    "description": "Add a new calendar event (to local store or Google Calendar)",
    "parameters": {
    "type": "object",
    "properties": {
    "title": {"type": "string", "description": "Event title"},
    "date": {"type": "string", "description": "Date/time in YYYY-MM-DD HH:MM format"},
    "duration_minutes": {"type": "integer", "description": "Duration in minutes (default: 60)"},
    "description": {"type": "string", "description": "Event description (optional)"},
    "location": {"type": "string", "description": "Event location (optional)"},
    "source": {"type": "string", "description": "'local' or 'google'"},
    },
    "required": ["title", "date"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "calendar_delete_event",
    "description": "Delete a calendar event by ID",
    "parameters": {
    "type": "object",
    "properties": {
    "event_id": {"type": "string", "description": "Event ID to delete"},
    "source": {"type": "string", "description": "'local' or 'google'"},
    },
    "required": ["event_id"],
    },
    },
    },

]
