"""
Tool schemas for Marketplace domain.
"""

SCHEMAS = [
    # ── Skills Marketplace tools (SAGP gateway) ─────
    {
    "type": "function",
    "function": {
    "name": "marketplace_search",
    "description": "Search the SableCore Skills Marketplace for skills to extend your capabilities. The marketplace contains community and official skills you can install. Use this when the user asks about available skills, wants new functionality, or you need a capability you don't have.",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {
    "type": "string",
    "description": "Search query (e.g. 'weather', 'calculator', 'crypto', 'automation')",
    },
    "category": {
    "type": "string",
    "description": "Optional category filter: productivity, communication, automation, data_analysis, entertainment, education, development, system, ai_ml, custom",
    },
    "limit": {
    "type": "integer",
    "description": "Maximum number of results (default 10)",
    "default": 10,
    },
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "marketplace_info",
    "description": "Get detailed information about a specific skill from the SableCore Skills Marketplace, including description, author, rating, downloads, dependencies, and version.",
    "parameters": {
    "type": "object",
    "properties": {
    "skill_id": {
    "type": "string",
    "description": "The skill ID/slug (e.g. 'weather_checker', 'smart_calculator')",
    },
    },
    "required": ["skill_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "marketplace_install",
    "description": "Install a skill from the SableCore Skills Marketplace. This downloads and installs the skill package securely via the SAGP agent gateway. IMPORTANT: This requires user approval before execution.",
    "parameters": {
    "type": "object",
    "properties": {
    "skill_id": {
    "type": "string",
    "description": "The skill ID/slug to install (e.g. 'weather_checker')",
    },
    },
    "required": ["skill_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "marketplace_review",
    "description": "Post a review on a skill you have used from the marketplace. Use this after installing and testing a skill to help other users and agents.",
    "parameters": {
    "type": "object",
    "properties": {
    "skill_id": {
    "type": "string",
    "description": "The skill ID/slug to review",
    },
    "rating": {
    "type": "integer",
    "description": "Rating from 1 to 5 stars",
    "minimum": 1,
    "maximum": 5,
    },
    "title": {
    "type": "string",
    "description": "Short review title",
    },
    "content": {
    "type": "string",
    "description": "Detailed review content",
    },
    },
    "required": ["skill_id", "rating", "title", "content"],
    },
    },
    },

]
