"""
Base abstractions for trading — data models and the ExchangeConnector ABC.

Every exchange connector (Binance, Polymarket, Alpaca …) implements
the ExchangeConnector interface so the rest of the system (portfolio,
risk manager, strategies, tools) is exchange-agnostic.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional


# ── Enums ─────────────────────────────────────────────────────

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    STOP_LIMIT = "stop_limit"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class MarketType(str, Enum):
    SPOT = "spot"
    FUTURES = "futures"
    PERPETUAL = "perpetual"
    PREDICTION = "prediction"  # Polymarket-style
    OPTIONS = "options"


# ── Data classes ──────────────────────────────────────────────

@dataclass
class Balance:
    """Balance for a single asset on one exchange."""
    asset: str
    free: Decimal = Decimal("0")
    locked: Decimal = Decimal("0")
    exchange: str = ""

    @property
    def total(self) -> Decimal:
        return self.free + self.locked


@dataclass
class PriceTick:
    """Real-time price tick."""
    symbol: str
    price: Decimal
    bid: Optional[Decimal] = None
    ask: Optional[Decimal] = None
    volume_24h: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    exchange: str = ""


@dataclass
class OHLCV:
    """Candlestick bar."""
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime = field(default_factory=datetime.utcnow)
    interval: str = "1h"  # 1m, 5m, 15m, 1h, 4h, 1d


@dataclass
class MarketInfo:
    """Metadata about a tradeable market/pair."""
    symbol: str
    base_asset: str
    quote_asset: str
    market_type: MarketType = MarketType.SPOT
    min_order_size: Decimal = Decimal("0")
    max_order_size: Optional[Decimal] = None
    tick_size: Decimal = Decimal("0.01")
    lot_size: Decimal = Decimal("0.001")
    maker_fee: Decimal = Decimal("0.001")
    taker_fee: Decimal = Decimal("0.001")
    exchange: str = ""
    is_active: bool = True


@dataclass
class Order:
    """An order placed on an exchange."""
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.MARKET
    quantity: Decimal = Decimal("0")
    price: Optional[Decimal] = None  # None for market orders
    stop_price: Optional[Decimal] = None
    status: OrderStatus = OrderStatus.PENDING
    filled_quantity: Decimal = Decimal("0")
    average_fill_price: Optional[Decimal] = None
    fee: Decimal = Decimal("0")
    fee_asset: str = ""
    exchange: str = ""
    strategy: str = ""  # Which strategy created this order
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_open(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED)

    @property
    def notional_value(self) -> Decimal:
        """Approximate notional value of the order."""
        p = self.average_fill_price or self.price or Decimal("0")
        return self.quantity * p


@dataclass
class Position:
    """An open position."""
    position_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    symbol: str = ""
    side: PositionSide = PositionSide.LONG
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")
    current_price: Decimal = Decimal("0")
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    exchange: str = ""
    strategy: str = ""
    opened_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def unrealized_pnl(self) -> Decimal:
        if self.side == PositionSide.LONG:
            return (self.current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_pct(self) -> Decimal:
        if self.entry_price == 0:
            return Decimal("0")
        if self.side == PositionSide.LONG:
            return ((self.current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - self.current_price) / self.entry_price) * 100

    @property
    def notional_value(self) -> Decimal:
        return self.quantity * self.current_price


@dataclass
class TradeRecord:
    """A completed trade for the trade journal."""
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: Decimal = Decimal("0")
    entry_price: Decimal = Decimal("0")
    exit_price: Optional[Decimal] = None
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    fees: Decimal = Decimal("0")
    exchange: str = ""
    strategy: str = ""
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    duration_seconds: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_winner(self) -> bool:
        return self.pnl > 0


# ── Abstract Exchange Connector ───────────────────────────────

class ExchangeConnector(ABC):
    """
    Unified interface for all exchange integrations.

    Every connector must implement these methods so the portfolio manager,
    risk manager, and strategy engine can work exchange-agnostically.
    """

    name: str = "base"  # Override in subclass: "binance", "polymarket", etc.

    def __init__(self, config: Any):
        self.config = config
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── Lifecycle ──

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection and authenticate with the exchange."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close connections."""
        ...

    # ── Account ──

    @abstractmethod
    async def get_balances(self) -> List[Balance]:
        """Return all non-zero balances."""
        ...

    @abstractmethod
    async def get_balance(self, asset: str) -> Balance:
        """Return balance for a single asset."""
        ...

    # ── Market data ──

    @abstractmethod
    async def get_price(self, symbol: str) -> PriceTick:
        """Get latest price tick for a symbol."""
        ...

    @abstractmethod
    async def get_ohlcv(
        self, symbol: str, interval: str = "1h", limit: int = 100
    ) -> List[OHLCV]:
        """Get historical OHLCV candles."""
        ...

    @abstractmethod
    async def get_orderbook(
        self, symbol: str, depth: int = 20
    ) -> Dict[str, Any]:
        """Get order book. Returns {'bids': [...], 'asks': [...]}."""
        ...

    @abstractmethod
    async def get_markets(self) -> List[MarketInfo]:
        """List all available tradeable markets."""
        ...

    # ── Orders ──

    @abstractmethod
    async def place_order(
        self,
        symbol: str,
        side: OrderSide,
        order_type: OrderType,
        quantity: Decimal,
        price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        """Place a new order. Returns the created Order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        """Cancel an open order. Returns True on success."""
        ...

    @abstractmethod
    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        """Get status of a specific order."""
        ...

    @abstractmethod
    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        """Get all open orders (optionally for a specific symbol)."""
        ...

    # ── Positions ──

    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """Get all open positions."""
        ...

    # ── Streaming ──

    async def stream_prices(
        self, symbols: List[str]
    ) -> AsyncIterator[PriceTick]:
        """Stream real-time price ticks. Override for WebSocket support."""
        raise NotImplementedError(f"{self.name} does not support price streaming")
        # Make it an async generator so callers can `async for tick in ...`
        yield  # pragma: no cover — unreachable, makes this an async generator

    # ── Trade history ──

    async def get_trade_history(
        self, symbol: str = "", limit: int = 50
    ) -> List[TradeRecord]:
        """Get recent trade history. Override in subclass."""
        return []

    # ── Utilities ──

    def __repr__(self) -> str:
        status = "connected" if self._connected else "disconnected"
        return f"<{self.__class__.__name__} ({self.name}) [{status}]>"
