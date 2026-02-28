"""
Tool schemas for Desktop domain.
"""

SCHEMAS = [
    # ── Desktop control tools ─────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "desktop_screenshot",
    "description": "Take a screenshot of the screen. Returns base64 PNG image and dimensions.",
    "parameters": {
    "type": "object",
    "properties": {
    "save_path": {
    "type": "string",
    "description": "Optional file path to save the PNG to instead of returning base64",
    },
    },
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "desktop_click",
    "description": "Click the mouse at screen coordinates (x, y)",
    "parameters": {
    "type": "object",
    "properties": {
    "x": {"type": "integer", "description": "X pixel coordinate"},
    "y": {"type": "integer", "description": "Y pixel coordinate"},
    "button": {
    "type": "string",
    "description": "'left' (default), 'right', or 'middle'",
    },
    "clicks": {
    "type": "integer",
    "description": "Number of clicks (2 = double-click)",
    },
    },
    "required": ["x", "y"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "desktop_type",
    "description": "Type text via the keyboard at the current cursor position",
    "parameters": {
    "type": "object",
    "properties": {
    "text": {"type": "string", "description": "The text to type"}
    },
    "required": ["text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "desktop_hotkey",
    "description": "Press a key or key combination (e.g. 'enter', 'ctrl+c', 'alt+f4', 'ctrl+shift+t')",
    "parameters": {
    "type": "object",
    "properties": {
    "key": {
    "type": "string",
    "description": "Key or combo like 'enter', 'ctrl+c', 'alt+tab'",
    }
    },
    "required": ["key"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "desktop_scroll",
    "description": "Scroll the mouse wheel. Positive = up, negative = down.",
    "parameters": {
    "type": "object",
    "properties": {
    "amount": {
    "type": "integer",
    "description": "Scroll amount (positive=up, negative=down)",
    },
    "x": {
    "type": "integer",
    "description": "Optional X coordinate to scroll at",
    },
    "y": {
    "type": "integer",
    "description": "Optional Y coordinate to scroll at",
    },
    },
    "required": ["amount"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "desktop_mouse_move",
    "description": "Move the mouse to screen coordinates (x, y)",
    "parameters": {
    "type": "object",
    "properties": {
    "x": {"type": "integer", "description": "X pixel coordinate"},
    "y": {"type": "integer", "description": "Y pixel coordinate"},
    },
    "required": ["x", "y"],
    },
    },
    },

]
