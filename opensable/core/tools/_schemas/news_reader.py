"""
Tool schemas for the News Reader skill (news.zunvra.com / WorldMonitor).
"""

SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "news_get_world_news",
            "description": (
                "Get the latest world news headlines from multiple RSS sources "
                "(BBC, Reuters, Al Jazeera, CNN, Hacker News, TechCrunch, etc.). "
                "Results are cached to avoid excessive requests."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum number of headlines to return (default: 15)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": (
                "Search for news articles on a specific topic using GDELT. "
                "Good for tracking specific events, countries, or themes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (e.g. 'Ukraine conflict', 'AI regulation', 'earthquake')",
                    },
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum results (default: 15)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_country_brief",
            "description": (
                "Get an intelligence brief for a specific country. Includes "
                "instability index, threat classification, and situation analysis. "
                "Use ISO 3166-1 alpha-2 country codes (US, CN, UA, RU, etc.)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "country_code": {
                        "type": "string",
                        "description": "ISO 3166-1 alpha-2 country code (e.g. 'US', 'CN', 'UA')",
                    },
                },
                "required": ["country_code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_get_conflicts",
            "description": (
                "Get recent armed conflict events worldwide from ACLED database. "
                "Includes event type, country, location, fatalities, and notes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "max_items": {
                        "type": "integer",
                        "description": "Maximum events to return (default: 20)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_get_macro_signals",
            "description": (
                "Get macroeconomic signals,  GDP trends, inflation rates, "
                "central bank decisions, trade balances, and other indicators."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_get_market_quotes",
            "description": (
                "Get stock market quotes for specific symbols or defaults "
                "(SPY, QQQ, DIA, AAPL, MSFT)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Stock ticker symbols (e.g. ['AAPL', 'MSFT', 'TSLA'])",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_get_crypto_quotes",
            "description": (
                "Get cryptocurrency price quotes (default: bitcoin, ethereum, solana)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Crypto IDs (e.g. ['bitcoin', 'ethereum', 'solana'])",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "news_digest",
            "description": (
                "Get a complete news digest combining top headlines, conflict events, "
                "and macroeconomic signals in a single plain-text summary. "
                "Best for getting a quick overview of the world situation."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]
