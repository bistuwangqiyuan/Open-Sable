"""
Tool schemas for Core domain.
"""

SCHEMAS = [
    {
    "type": "function",
    "function": {
    "name": "weather",
    "description": "Get current weather for a location",
    "parameters": {
    "type": "object",
    "properties": {
    "location": {
    "type": "string",
    "description": "City name, country, or address",
    }
    },
    "required": ["location"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "calendar",
    "description": "Manage calendar events: list upcoming events, add new events, or delete events",
    "parameters": {
    "type": "object",
    "properties": {
    "action": {"type": "string", "description": "list, add, or delete"},
    "title": {"type": "string", "description": "Event title (for add)"},
    "date": {
    "type": "string",
    "description": "Date/time in YYYY-MM-DD HH:MM format (for add)",
    },
    "description": {
    "type": "string",
    "description": "Event description (optional)",
    },
    "id": {"type": "integer", "description": "Event ID (for delete)"},
    },
    "required": ["action"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "execute_code",
    "description": "Execute Python or other code in a sandbox",
    "parameters": {
    "type": "object",
    "properties": {
    "code": {"type": "string", "description": "Code to execute"},
    "language": {
    "type": "string",
    "description": "Programming language (default: python)",
    },
    },
    "required": ["code"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "vector_search",
    "description": "Semantic search through stored documents and knowledge base",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "Search query"},
    "top_k": {
    "type": "integer",
    "description": "Number of results (default 5)",
    },
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "create_skill",
    "description": "Create a new dynamic skill/extension for the agent. The skill will be validated, saved, and loaded automatically.",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {
    "type": "string",
    "description": "Skill name (snake_case, e.g. 'weather_check')",
    },
    "description": {"type": "string", "description": "What the skill does"},
    "code": {"type": "string", "description": "Python code for the skill"},
    "author": {
    "type": "string",
    "description": "Author name (default: 'sable')",
    },
    },
    "required": ["name", "description", "code"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "list_skills",
    "description": "List all custom skills created by the agent",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "load_tool_details",
    "description": "Load the full parameter schema for one or more tools so you can call them with the correct arguments. Use this when you need to call a tool whose parameters you haven't seen yet.",
    "parameters": {
    "type": "object",
    "properties": {
    "tool_names": {
    "type": "array",
    "items": {"type": "string"},
    "description": "List of tool names to load full schemas for (e.g. ['x_post_tweet', 'trading_place_trade'])",
    }
    },
    "required": ["tool_names"],
    },
    },
    },

]
