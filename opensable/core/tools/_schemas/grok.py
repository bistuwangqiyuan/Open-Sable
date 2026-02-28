"""
Tool schemas for Grok domain.
"""

SCHEMAS = [
    # ── Grok AI tools ─────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "grok_chat",
    "description": "Chat with Grok AI (free via your X account). Ask questions, get analysis, brainstorm ideas.",
    "parameters": {
    "type": "object",
    "properties": {
    "message": {"type": "string", "description": "Message/prompt to send to Grok"},
    "conversation_id": {"type": "string", "description": "Continue existing conversation (optional)"},
    },
    "required": ["message"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "grok_analyze_image",
    "description": "Send images to Grok AI for analysis/description (vision capability)",
    "parameters": {
    "type": "object",
    "properties": {
    "image_paths": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of image file paths to analyze",
    },
    "prompt": {"type": "string", "description": "Question about the images (default: describe them)"},
    },
    "required": ["image_paths"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "grok_generate_image",
    "description": "Generate images using Grok AI",
    "parameters": {
    "type": "object",
    "properties": {
    "prompt": {"type": "string", "description": "Image generation prompt"},
    "save_path": {"type": "string", "description": "Path to save generated image (optional)"},
    },
    "required": ["prompt"],
    },
    },
    },

]
