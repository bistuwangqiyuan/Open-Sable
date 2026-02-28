# Open-Sable Trading Bot Guide

## Overview

Open-Sable includes a full multi-market trading system that can trade crypto, stocks, prediction markets, memecoins, and commodities , all managed by the AI agent with built-in risk controls.

## Quick Start

### 1. Enable Trading (Paper Mode)

Add to your `.env` file:

```bash
TRADING_ENABLED=true
TRADING_PAPER_MODE=true      # Default , uses simulated money
```

That's it! The agent now has trading tools and starts with $10,000 in paper money.

### 2. Talk to Your Agent

```
You: "What's the price of Bitcoin?"
Sable: 💰 BTC/USDT: $67,234.50 ...

You: "Analyze Ethereum for me"
Sable: 📊 Market Analysis: ETH/USDT
  🟢 [momentum] LONG , conf: 72% , RSI oversold, MACD bullish crossover
  🟢 [mean_reversion] LONG , conf: 65% , Price below lower Bollinger Band
  Consensus: 🟢 LONG (confidence: 69%)

You: "Buy 0.5 ETH"
Sable: ✅ Order placed (📝 PAPER)
  BUY 0.5 ETH/USDT @ ~$3,456.78
  Exchange: paper
  Value: ~$1,728.39

You: "Show me my portfolio"
Sable: 📊 Portfolio Summary
  Total Value: $10,012.34
  ...
```

### 3. Connect Live Exchanges

When you're ready for real trading, add exchange API keys:

```bash
# Crypto
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
BINANCE_TESTNET=false

COINBASE_API_KEY=your_key
COINBASE_API_SECRET=your_secret

# Solana / Memecoins (Jupiter DEX)
JUPITER_PRIVATE_KEY=your_base58_key
JUPITER_RPC_URL=https://api.mainnet-beta.solana.com

# DeFi Perpetuals
HYPERLIQUID_PRIVATE_KEY=your_key
HYPERLIQUID_TESTNET=false

# Prediction Markets
POLYMARKET_PRIVATE_KEY=your_evm_key
POLYMARKET_FUNDER=your_address

# US Stocks & ETFs
ALPACA_API_KEY=your_key
ALPACA_API_SECRET=your_secret
ALPACA_PAPER=false

# THEN disable paper mode
TRADING_PAPER_MODE=false
```

## Architecture

```
opensable/skills/trading/
├── __init__.py              # Package exports
├── base.py                  # Data models: Order, Position, Balance, OHLCV, etc.
├── portfolio.py             # Portfolio aggregation, P&L tracking, SQLite persistence
├── risk_manager.py          # Pre-trade risk checks, position limits, emergency halt
├── market_data.py           # Unified price feeds, CoinGecko fallback
├── strategy_engine.py       # Strategy ABC, signal generation engine
├── signals.py               # Signal aggregator (multi-strategy consensus)
├── trading_skill.py         # Top-level orchestrator (called by ToolRegistry)
├── backtest.py              # Walk-forward backtesting engine
├── guardrails.py            # Trading-specific guardrails
├── connectors/
│   ├── paper.py             # Paper trading simulator (default)
│   ├── binance_connector.py # Binance spot + futures via ccxt
│   ├── coinbase_connector.py# Coinbase spot via ccxt
│   ├── alpaca_connector.py  # US stocks/ETFs via alpaca-py
│   ├── polymarket_connector.py # Prediction markets
│   ├── hyperliquid_connector.py # On-chain perps
│   └── jupiter_connector.py # Solana DEX (memecoins)
└── strategies/
    ├── momentum.py          # RSI + MACD + volume
    ├── mean_reversion.py    # Bollinger Bands + z-score
    ├── sentiment.py         # LLM-powered news/social analysis
    ├── arbitrage.py         # Cross-exchange price differences
    └── polymarket_edge.py   # LLM probability vs market odds
```

## Supported Markets

| Market         | Exchange        | Assets                     |
|---------------|-----------------|----------------------------|
| Crypto Spot   | Binance         | BTC, ETH, SOL, 500+ pairs |
| Crypto Spot   | Coinbase        | BTC, ETH, major pairs     |
| DeFi Perps    | Hyperliquid     | BTC, ETH, on-chain perps  |
| Memecoins     | Jupiter (Solana)| Any SPL token              |
| Predictions   | Polymarket      | Elections, events, sports  |
| US Stocks     | Alpaca          | AAPL, TSLA, SPY, etc.     |
| Commodities   | Alpaca (ETFs)   | GLD, USO, SLV, UNG        |

## Trading Tools

The agent has 10 trading tools available:

| Tool | Description |
|------|-------------|
| `trading_portfolio` | View portfolio, positions, P&L |
| `trading_price` | Get current price of any asset |
| `trading_analyze` | Run all strategies on a symbol |
| `trading_place_trade` | Execute a buy/sell order |
| `trading_cancel_order` | Cancel an open order |
| `trading_history` | View recent trade log |
| `trading_signals` | Scan entire watchlist for signals |
| `trading_start_scan` | Start background market monitor |
| `trading_stop_scan` | Stop background scanning |
| `trading_risk_status` | Check risk limits and daily P&L |

## Strategies

### Momentum (momentum)
- RSI + MACD + volume analysis
- Best for: trending markets
- Signals: BUY when RSI oversold + MACD bullish, SELL when overbought

### Mean Reversion (mean_reversion)
- Bollinger Bands + statistical z-score
- Best for: ranging markets
- Signals: BUY when price below lower band, SELL when above upper band

### Sentiment (sentiment)
- **Open-Sable's unique edge** , uses the LLM to read news and social media
- Best for: memecoins, event-driven markets
- Requires: LLM configured (automatically injected)

### Arbitrage (arbitrage)
- Cross-exchange price difference detection
- Best for: BTC, ETH on multiple exchanges
- Near-instant trades when spread exceeds fees

### Polymarket Edge (polymarket_edge)
- LLM estimates true probability vs market price
- Best for: prediction markets
- Signals: BUY when LLM sees >8% edge over market odds

## Risk Management

### Hard Limits (enforced before every trade)

| Limit | Default | Env Var |
|-------|---------|---------|
| Max position size | 5% of portfolio | `TRADING_MAX_POSITION_PCT` |
| Max daily loss | 2% | `TRADING_MAX_DAILY_LOSS_PCT` |
| Max drawdown | 10% | `TRADING_MAX_DRAWDOWN_PCT` |
| Max open positions | 10 | `TRADING_MAX_OPEN_POSITIONS` |
| Max order value | $10,000 | `TRADING_MAX_ORDER_USD` |
| HITL approval above | $100 | `TRADING_REQUIRE_APPROVAL_ABOVE_USD` |
| Banned assets | none | `TRADING_BANNED_ASSETS` |

### Safety Layers

1. **Paper mode by default** , no real money until explicitly enabled
2. **Risk manager** , rejects/reduces orders that violate limits
3. **HITL approval** , trade execution requires human approval (CRITICAL risk level)
4. **Trading guardrails** , blocks known scam tokens, warns on live trades
5. **Emergency halt** , automatically stops all trading if limits are breached

## Configuration Reference

```bash
# Core
TRADING_ENABLED=true|false           # Enable trading tools
TRADING_PAPER_MODE=true|false        # Paper (simulated) or live trading
TRADING_AUTO_TRADE=true|false        # Auto-execute on strong signals
TRADING_SCAN_INTERVAL=60             # Seconds between market scans

# Strategies
TRADING_STRATEGIES=momentum,mean_reversion,sentiment
TRADING_WATCHLIST=BTC/USDT,ETH/USDT,SOL/USDT

# Risk (see table above)
TRADING_MAX_POSITION_PCT=5.0
TRADING_MAX_DAILY_LOSS_PCT=2.0
TRADING_MAX_DRAWDOWN_PCT=10.0
TRADING_MAX_OPEN_POSITIONS=10
TRADING_MAX_ORDER_USD=10000
TRADING_REQUIRE_APPROVAL_ABOVE_USD=100
TRADING_BANNED_ASSETS=SQUID,SAFEMOON
```

## Dashboard

A web dashboard is available at `static/trading_dashboard.html`. It shows:
- Portfolio value and P&L
- Open positions
- Active signals
- Risk status
- Recent trades

## Dependencies

Install trading dependencies:
```bash
pip install -r requirements-trading.txt
```
