"""
Open-Sable Trading Skill — Multi-exchange automated trading.

Supports crypto (Binance, Coinbase, Hyperliquid, Jupiter/Solana),
prediction markets (Polymarket), and traditional markets (Alpaca, IBKR).

Safety-first: paper trading by default, HITL approval for real trades,
hard risk limits enforced before every order.
"""

from .base import (
    ExchangeConnector,
    Order,
    OrderSide,
    OrderType,
    OrderStatus,
    Position,
    PriceTick,
    OHLCV,
    Balance,
    MarketInfo,
    TradeRecord,
)
from .portfolio import PortfolioManager, PortfolioSnapshot
from .risk_manager import RiskManager, RiskDecision, RiskAction
from .market_data import MarketDataService
from .strategy_engine import Strategy, Signal, SignalDirection, StrategyEngine
from .signals import SignalAggregator
from .trading_skill import TradingSkill
from .backtest import BacktestEngine, BacktestResult

__all__ = [
    "ExchangeConnector",
    "Order",
    "OrderSide",
    "OrderType",
    "OrderStatus",
    "Position",
    "PriceTick",
    "OHLCV",
    "Balance",
    "MarketInfo",
    "TradeRecord",
    "PortfolioManager",
    "PortfolioSnapshot",
    "RiskManager",
    "RiskDecision",
    "RiskAction",
    "MarketDataService",
    "Strategy",
    "Signal",
    "SignalDirection",
    "StrategyEngine",
    "SignalAggregator",
    "TradingSkill",
    "BacktestEngine",
    "BacktestResult",
]
