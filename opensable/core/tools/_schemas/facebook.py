"""
Tool schemas for Facebook domain.
"""

SCHEMAS = [
    # ── Facebook tools ────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "fb_post",
    "description": "Publish a text post to Facebook (your timeline or page)",
    "parameters": {
    "type": "object",
    "properties": {
    "message": {"type": "string", "description": "Post text content"},
    "link": {"type": "string", "description": "URL to attach (optional)"},
    },
    "required": ["message"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_upload_photo",
    "description": "Upload a photo to Facebook with caption",
    "parameters": {
    "type": "object",
    "properties": {
    "photo_path": {"type": "string", "description": "Path to the photo file"},
    "caption": {"type": "string", "description": "Photo caption text (optional)"},
    },
    "required": ["photo_path"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_get_feed",
    "description": "Get recent posts from your Facebook feed or a page's feed",
    "parameters": {
    "type": "object",
    "properties": {
    "count": {"type": "integer", "description": "Number of posts (default: 10)"},
    },
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_like_post",
    "description": "Like a Facebook post by its ID",
    "parameters": {
    "type": "object",
    "properties": {
    "post_id": {"type": "string", "description": "Facebook post ID"},
    },
    "required": ["post_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_comment",
    "description": "Comment on a Facebook post",
    "parameters": {
    "type": "object",
    "properties": {
    "post_id": {"type": "string", "description": "Facebook post ID"},
    "message": {"type": "string", "description": "Comment text"},
    },
    "required": ["post_id", "message"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_get_profile",
    "description": "Get Facebook profile information for a user or page",
    "parameters": {
    "type": "object",
    "properties": {
    "user_id": {"type": "string", "description": "User/page ID or 'me' (default: me)"},
    },
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "fb_search",
    "description": "Search Facebook for pages, people, groups, etc.",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Search query"},
    "search_type": {"type": "string", "description": "Type: page, user, group, event (default: page)"},
    "count": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["query"],
    },
    },
    },

]
