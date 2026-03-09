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
    "description": "Create a new dynamic skill that is auto-wired into the tool system. The generated Python code should follow the Dynamic Skill Protocol: (1) Define TOOL_SCHEMAS — a list of OpenAI function-calling schema dicts, each with type/function/name/description/parameters. (2) Define TOOL_PERMISSIONS — a dict mapping tool_name to a permission string like 'dynamic_skill'. (3) Define async handler functions named handle_<tool_name>(params: dict) that return a string or dict. (4) Optionally define async initialize() for one-time setup (DB tables, config, etc.). (5) Use DATA_DIR = Path(globals().get('__skill_data_dir__', '.')) for persistent file/DB storage. All defined tools are immediately available after creation.",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {
    "type": "string",
    "description": "Skill name (snake_case, e.g. 'inventory_tracker')",
    },
    "description": {"type": "string", "description": "What the skill does"},
    "code": {"type": "string", "description": "Python code following the Dynamic Skill Protocol (TOOL_SCHEMAS, TOOL_PERMISSIONS, handle_<name> functions, optional initialize)"},
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
    "description": "List all custom dynamic skills created by the agent, including their registered tool names and status",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "delete_skill",
    "description": "Delete a dynamic skill and unregister all its tools from the system",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {"type": "string", "description": "Name of the skill to delete"},
    },
    "required": ["name"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "disable_skill",
    "description": "Temporarily disable a dynamic skill (keeps it on disk but unregisters its tools)",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {"type": "string", "description": "Name of the skill to disable"},
    },
    "required": ["name"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "enable_skill",
    "description": "Re-enable a previously disabled dynamic skill and re-register its tools",
    "parameters": {
    "type": "object",
    "properties": {
    "name": {"type": "string", "description": "Name of the skill to enable"},
    },
    "required": ["name"],
    },
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
