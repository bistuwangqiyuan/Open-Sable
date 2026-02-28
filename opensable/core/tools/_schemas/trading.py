"""
Tool schemas for Trading domain.
"""

SCHEMAS = [
    # ── Trading tools ─────────────────────────────────
    {
    "type": "function",
    "function": {
    "name": "trading_portfolio",
    "description": "Get the current trading portfolio summary — balances, positions, P&L, performance stats",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_price",
    "description": "Get the current price of a trading pair (crypto, stock, prediction market)",
    "parameters": {
    "type": "object",
    "properties": {
    "symbol": {"type": "string", "description": "Trading pair, e.g. BTC/USDT, ETH/USDT, AAPL"},
    },
    "required": ["symbol"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_analyze",
    "description": "Analyze a market/asset using all active strategies. Returns trading signals with confidence levels.",
    "parameters": {
    "type": "object",
    "properties": {
    "symbol": {"type": "string", "description": "Trading pair to analyze, e.g. BTC/USDT"},
    },
    "required": ["symbol"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_place_trade",
    "description": "Place a buy or sell trade. Goes through risk checks and requires approval for large amounts.",
    "parameters": {
    "type": "object",
    "properties": {
    "symbol": {"type": "string", "description": "Trading pair, e.g. BTC/USDT"},
    "side": {"type": "string", "enum": ["buy", "sell"], "description": "Buy or sell"},
    "amount": {"type": "string", "description": "Amount to trade (in base currency)"},
    "type": {"type": "string", "enum": ["market", "limit"], "description": "Order type (default: market)"},
    "price": {"type": "string", "description": "Limit price (only for limit orders)"},
    "exchange": {"type": "string", "description": "Exchange to use: paper, binance, coinbase, alpaca, etc. (default: paper)"},
    },
    "required": ["symbol", "side", "amount"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_cancel_order",
    "description": "Cancel an open order on an exchange",
    "parameters": {
    "type": "object",
    "properties": {
    "order_id": {"type": "string", "description": "The order ID to cancel"},
    "exchange": {"type": "string", "description": "Exchange name (default: paper)"},
    "symbol": {"type": "string", "description": "Trading pair (some exchanges require it)"},
    },
    "required": ["order_id"],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_history",
    "description": "Get recent trade history and execution log",
    "parameters": {
    "type": "object",
    "properties": {
    "limit": {"type": "integer", "description": "Number of trades to return (default: 20)"},
    },
    "required": [],
    },
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_signals",
    "description": "Scan all assets on the watchlist and return current trading signals from all strategies",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_start_scan",
    "description": "Start background market scanning — continuously monitors watchlist for trading opportunities",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_stop_scan",
    "description": "Stop the background market scanning loop",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

    {
    "type": "function",
    "function": {
    "name": "trading_risk_status",
    "description": "Show the current risk manager status — limits, daily P&L, drawdown, emergency halt status",
    "parameters": {"type": "object", "properties": {}, "required": []},
    },
    },

]
