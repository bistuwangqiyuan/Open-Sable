"""
Tool schemas for Youtube domain.
"""

SCHEMAS = [
    # ── YouTube tools ─────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "yt_search_videos",
    "description": "Search YouTube videos by keyword",
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
    "name": "yt_search_channels",
    "description": "Search YouTube channels by keyword",
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
    "name": "yt_get_channel",
    "description": "Get detailed info about a YouTube channel (subscribers, videos, description)",
    "parameters": {
    "type": "object",
    "properties": {
    "channel_id": {"type": "string", "description": "YouTube channel ID"},
    },
    "required": ["channel_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_get_channel_videos",
    "description": "Get recent videos from a YouTube channel",
    "parameters": {
    "type": "object",
    "properties": {
    "channel_id": {"type": "string", "description": "YouTube channel ID"},
    "count": {"type": "integer", "description": "Max videos (default: 10)"},
    },
    "required": ["channel_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_get_video",
    "description": "Get detailed info about a YouTube video (views, likes, duration, description)",
    "parameters": {
    "type": "object",
    "properties": {
    "video_id": {"type": "string", "description": "YouTube video ID"},
    },
    "required": ["video_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_get_comments",
    "description": "Get top comments on a YouTube video",
    "parameters": {
    "type": "object",
    "properties": {
    "video_id": {"type": "string", "description": "YouTube video ID"},
    "count": {"type": "integer", "description": "Max comments (default: 20)"},
    },
    "required": ["video_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_comment",
    "description": "Post a comment on a YouTube video (requires OAuth access token)",
    "parameters": {
    "type": "object",
    "properties": {
    "video_id": {"type": "string", "description": "YouTube video ID"},
    "text": {"type": "string", "description": "Comment text"},
    },
    "required": ["video_id", "text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_get_playlist",
    "description": "Get videos in a YouTube playlist",
    "parameters": {
    "type": "object",
    "properties": {
    "playlist_id": {"type": "string", "description": "YouTube playlist ID"},
    "count": {"type": "integer", "description": "Max items (default: 20)"},
    },
    "required": ["playlist_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_rate_video",
    "description": "Like or dislike a YouTube video (requires OAuth access token)",
    "parameters": {
    "type": "object",
    "properties": {
    "video_id": {"type": "string", "description": "YouTube video ID"},
    "rating": {"type": "string", "description": "'like', 'dislike', or 'none'"},
    },
    "required": ["video_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_subscribe",
    "description": "Subscribe to a YouTube channel (requires OAuth access token)",
    "parameters": {
    "type": "object",
    "properties": {
    "channel_id": {"type": "string", "description": "YouTube channel ID"},
    },
    "required": ["channel_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_trending",
    "description": "Get trending YouTube videos by region",
    "parameters": {
    "type": "object",
    "properties": {
    "region_code": {"type": "string", "description": "ISO country code (default: US)"},
    "count": {"type": "integer", "description": "Max videos (default: 10)"},
    },
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "yt_upload_video",
    "description": "Upload a video to YouTube (requires OAuth access token). Defaults to private.",
    "parameters": {
    "type": "object",
    "properties": {
    "file_path": {"type": "string", "description": "Path to video file"},
    "title": {"type": "string", "description": "Video title"},
    "description": {"type": "string", "description": "Video description"},
    "tags": {"type": "array", "items": {"type": "string"}, "description": "Video tags"},
    "privacy": {"type": "string", "description": "'private', 'public', or 'unlisted'"},
    },
    "required": ["file_path", "title"],
    },
    },
    },

]
