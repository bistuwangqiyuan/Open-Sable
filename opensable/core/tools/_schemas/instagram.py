"""
Tool schemas for Instagram domain.
"""

SCHEMAS = [
    # ── Instagram tools ───────────────────────────
    {
    "type": "function",
    "function": {
    "name": "ig_upload_photo",
    "description": "Upload a photo to Instagram with caption",
    "parameters": {
    "type": "object",
    "properties": {
    "photo_path": {"type": "string", "description": "Path to the photo file"},
    "caption": {"type": "string", "description": "Photo caption text"},
    },
    "required": ["photo_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_upload_reel",
    "description": "Upload a reel (short video) to Instagram with caption",
    "parameters": {
    "type": "object",
    "properties": {
    "video_path": {"type": "string", "description": "Path to the video file"},
    "caption": {"type": "string", "description": "Reel caption text"},
    },
    "required": ["video_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_upload_story",
    "description": "Upload a story (photo or video) to Instagram",
    "parameters": {
    "type": "object",
    "properties": {
    "file_path": {"type": "string", "description": "Path to photo or video file"},
    "caption": {"type": "string", "description": "Story caption/sticker text (optional)"},
    },
    "required": ["file_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_search_users",
    "description": "Search for Instagram users by query string",
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
    "name": "ig_search_hashtags",
    "description": "Search Instagram hashtags",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Hashtag search query"},
    "count": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_get_user_info",
    "description": "Get detailed info about an Instagram user by username",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "Instagram username"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_get_timeline",
    "description": "Get the authenticated user's Instagram timeline/feed",
    "parameters": {
    "type": "object",
    "properties": {
    "count": {"type": "integer", "description": "Number of posts to fetch (default: 20)"},
    },
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_like_media",
    "description": "Like an Instagram post by its media ID or URL",
    "parameters": {
    "type": "object",
    "properties": {
    "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
    },
    "required": ["media_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_comment",
    "description": "Comment on an Instagram post",
    "parameters": {
    "type": "object",
    "properties": {
    "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
    "text": {"type": "string", "description": "Comment text"},
    },
    "required": ["media_id", "text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_follow_user",
    "description": "Follow an Instagram user by username",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "Instagram username to follow"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_send_dm",
    "description": "Send a direct message to an Instagram user",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "Instagram username to DM"},
    "text": {"type": "string", "description": "Message text"},
    },
    "required": ["username", "text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "ig_get_media_comments",
    "description": "Get comments on an Instagram post",
    "parameters": {
    "type": "object",
    "properties": {
    "media_id": {"type": "string", "description": "Media ID or Instagram post URL"},
    "count": {"type": "integer", "description": "Max comments to fetch (default: 20)"},
    },
    "required": ["media_id"],
    },
    },
    },

]
