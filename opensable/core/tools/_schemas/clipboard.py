"""
Tool schemas for Clipboard domain.
"""

SCHEMAS = [
    # ── Clipboard tools ───────────────────────────
    {
    "type": "function",
    "function": {
    "name": "clipboard_copy",
    "description": "Copy text to the system clipboard",
    "parameters": {
    "type": "object",
    "properties": {
    "text": {"type": "string", "description": "Text to copy to clipboard"},
    },
    "required": ["text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "clipboard_paste",
    "description": "Read current text from the system clipboard",
    "parameters": {
    "type": "object",
    "properties": {},
    "required": [],
    },
    },
    },

]
