"""
Tool schemas for X Twitter domain.
"""

SCHEMAS = [
    # ── X (Twitter) tools ─────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "x_post_tweet",
    "description": "Post a tweet on X (Twitter). Can include text and optional images/video.",
    "parameters": {
    "type": "object",
    "properties": {
    "text": {"type": "string", "description": "Tweet text (max 280 chars)"},
    "media_paths": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Optional list of image/video file paths to attach",
    },
    "reply_to": {"type": "string", "description": "Tweet ID to reply to (optional)"},
    },
    "required": ["text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_post_thread",
    "description": "Post a thread (multiple connected tweets) on X. Provide a list of tweet texts in order.",
    "parameters": {
    "type": "object",
    "properties": {
    "tweets": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of tweet texts in thread order",
    },
    },
    "required": ["tweets"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_search",
    "description": "Search for tweets on X by keyword or phrase",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Search query"},
    "search_type": {"type": "string", "description": "'Latest', 'Top', 'People', or 'Media' (default: Latest)"},
    "count": {"type": "integer", "description": "Max results (default 10)"},
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_get_trends",
    "description": "Get trending topics on X (Twitter)",
    "parameters": {
    "type": "object",
    "properties": {
    "category": {"type": "string", "description": "'trending', 'news', 'sports', or 'entertainment'"},
    },
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_like",
    "description": "Like a tweet on X",
    "parameters": {
    "type": "object",
    "properties": {
    "tweet_id": {"type": "string", "description": "Tweet ID to like"},
    },
    "required": ["tweet_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_retweet",
    "description": "Retweet a tweet on X",
    "parameters": {
    "type": "object",
    "properties": {
    "tweet_id": {"type": "string", "description": "Tweet ID to retweet"},
    },
    "required": ["tweet_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_reply",
    "description": "Reply to a tweet on X",
    "parameters": {
    "type": "object",
    "properties": {
    "tweet_id": {"type": "string", "description": "Tweet ID to reply to"},
    "text": {"type": "string", "description": "Reply text"},
    },
    "required": ["tweet_id", "text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_get_user",
    "description": "Get a user's profile information on X (followers, bio, etc.)",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "X username (without @)"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_get_user_tweets",
    "description": "Get recent tweets from a specific X user",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "X username (without @)"},
    "tweet_type": {"type": "string", "description": "'Tweets', 'Replies', 'Media', or 'Likes'"},
    "count": {"type": "integer", "description": "Max tweets to return (default 10)"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_follow",
    "description": "Follow a user on X",
    "parameters": {
    "type": "object",
    "properties": {
    "username": {"type": "string", "description": "X username to follow (without @)"},
    },
    "required": ["username"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_send_dm",
    "description": "Send a direct message to a user on X",
    "parameters": {
    "type": "object",
    "properties": {
    "user_id": {"type": "string", "description": "User ID (numeric) to DM"},
    "text": {"type": "string", "description": "Message text"},
    },
    "required": ["user_id", "text"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "x_delete_tweet",
    "description": "Delete one of your own tweets on X",
    "parameters": {
    "type": "object",
    "properties": {
    "tweet_id": {"type": "string", "description": "Tweet ID to delete"},
    },
    "required": ["tweet_id"],
    },
    },
    },

]
