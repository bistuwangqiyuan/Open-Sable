"""
Tool schemas for Tiktok domain.
"""

SCHEMAS = [
    # ── TikTok tools (read-only) ──────────────────
    {
    "type": "function",
    "function": {
    "name": "tiktok_trending",
    "description": "Get trending TikTok videos. Note: TikTok API is read-only, cannot post content.",
    "parameters": {
    "type": "object",
    "properties": {
    "count": {"type": "integer", "description": "Number of videos (default: 10)"},
    },
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "tiktok_search_videos",
    "description": "Search TikTok videos by keyword",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Search query"},
    "count": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "tiktok_search_users",
    "description": "Search TikTok users by keyword",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Search query"},
    "count": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "tiktok_get_user_info",
    "description": "Get information about a TikTok user",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "TikTok username"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "tiktok_get_user_videos",
    "description": "Get videos posted by a TikTok user",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "TikTok username"},
    "count": {"type": "integer", "description": "Max videos (default: 10)"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "tiktok_get_hashtag_videos",
    "description": "Get videos under a TikTok hashtag",
    "parameters": {
    "type": "object",
    "properties": {
    "hashtag": {"type": "string", "description": "Hashtag name (without #)"},
    "count": {"type": "integer", "description": "Max videos (default: 10)"},
    },
    "required": ["hashtag"],
    },
    },
    },

]
