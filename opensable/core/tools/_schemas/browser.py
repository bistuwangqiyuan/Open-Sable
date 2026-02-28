"""
Tool schemas for Browser domain.
"""

SCHEMAS = [
    {
    "type": "function",
    "function": {
    "name": "browser_search",
    "description": "Search the web for information about any topic, person, place, news, etc.",
    "parameters": {
    "type": "object",
    "properties": {
    "query": {"type": "string", "description": "The search query"},
    "num_results": {
    "type": "integer",
    "description": "Number of results (default 5)",
    "default": 5,
    },
    },
    "required": ["query"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "browser_scrape",
    "description": "Fetch and read the content of a specific web page URL",
    "parameters": {
    "type": "object",
    "properties": {
    "url": {
    "type": "string",
    "description": "The full URL to scrape (must start with http:// or https://)",
    }
    },
    "required": ["url"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "browser_snapshot",
    "description": "Take an accessibility snapshot of a web page to see interactive elements (buttons, inputs, links) with stable refs for automation",
    "parameters": {
    "type": "object",
    "properties": {
    "url": {"type": "string", "description": "The URL to snapshot"}
    },
    "required": ["url"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "browser_action",
    "description": "Interact with a web page: click buttons, type text, submit forms. Use after browser_snapshot to get refs.",
    "parameters": {
    "type": "object",
    "properties": {
    "action": {
    "type": "string",
    "description": "Action: click, type, hover, select, press, submit, evaluate, wait",
    },
    "ref": {
    "type": "string",
    "description": "Element ref from snapshot (e.g. 'e3')",
    },
    "selector": {
    "type": "string",
    "description": "CSS selector (alternative to ref)",
    },
    "value": {
    "type": "string",
    "description": "Value for type/fill/select actions",
    },
    "url": {
    "type": "string",
    "description": "URL to navigate to before action (optional)",
    },
    },
    "required": ["action"],
    },
    },
    },

]
