"""
Tool schemas for Arena Fighter skill.
"""

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "arena_fight",
            "description": (
                "Connect to the fighting-game arena, authenticate via SAGP 7-layer "
                "Ed25519 protocol, and queue for a fight against another agent (OpenSable "
                "or OpenClaw). The fight runs asynchronously — use arena_status to check progress. "
                "Requires ARENA_URL to be configured."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "use_llm": {
                        "type": "boolean",
                        "description": "Use LLM for strategy decisions (default: true). If false, uses deterministic strategy engine.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arena_status",
            "description": (
                "Check the current status of the arena fighter. "
                "Returns: status (idle/connecting/queued/fighting/finished), "
                "current match info, win/loss record, and last result."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arena_history",
            "description": (
                "Get the history of arena fights. Returns recent matches "
                "with win/loss, opponent, side, reason, and timestamps."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of recent fights to return (default: 10).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "arena_disconnect",
            "description": (
                "Disconnect from the arena if currently connected or fighting. "
                "Useful to abort a queued or active fight."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]
