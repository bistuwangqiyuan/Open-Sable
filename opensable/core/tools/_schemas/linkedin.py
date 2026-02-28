"""
Tool schemas for Linkedin domain.
"""

SCHEMAS = [
    # ── LinkedIn tools ────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "linkedin_get_profile",
    "description": "Get a LinkedIn user's profile by their public ID or URL",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "LinkedIn public profile ID or vanity URL"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_search_people",
    "description": "Search for people on LinkedIn by keywords, location, company, etc.",
    "parameters": {
    "type": "object",
    "properties": {
    "keywords": {"type": "string", "description": "Search keywords"},
    "limit": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["keywords"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_search_companies",
    "description": "Search for companies on LinkedIn",
    "parameters": {
    "type": "object",
    "properties": {
    "keywords": {"type": "string", "description": "Search keywords"},
    "limit": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["keywords"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_search_jobs",
    "description": "Search for jobs on LinkedIn",
    "parameters": {
    "type": "object",
    "properties": {
    "keywords": {"type": "string", "description": "Job search keywords"},
    "location": {"type": "string", "description": "Job location (optional)"},
    "limit": {"type": "integer", "description": "Max results (default: 10)"},
    },
    "required": ["keywords"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_post_update",
    "description": "Publish a post/update on LinkedIn",
    "parameters": {
    "type": "object",
    "properties": {
    "text": {"type": "string", "description": "Post text content"},
    },
    "required": ["text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_send_message",
    "description": "Send a message to a LinkedIn connection",
    "parameters": {
    "type": "object",
    "properties": {
    "profile_id": {"type": "string", "description": "LinkedIn profile public ID of recipient"},
    "message": {"type": "string", "description": "Message text"},
    },
    "required": ["profile_id", "message"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_send_connection",
    "description": "Send a connection request on LinkedIn",
    "parameters": {
    "type": "object",
    "properties": {
    "profile_id": {"type": "string", "description": "LinkedIn public profile ID"},
    "message": {"type": "string", "description": "Connection request message (optional)"},
    },
    "required": ["profile_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "linkedin_get_feed",
    "description": "Get recent posts from your LinkedIn feed",
    "parameters": {
    "type": "object",
    "properties": {
    "count": {"type": "integer", "description": "Number of posts (default: 10)"},
    },
    },
    },
    },

]
