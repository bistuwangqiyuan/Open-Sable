"""
Paper Trading Connector — Simulated exchange for risk-free testing.

Mimics real exchange behavior (fills, slippage, fees) without using
real money.  This is the DEFAULT connector — Sable starts here.
"""

from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, AsyncIterator, Dict, List, Optional

from ..base import (
    Balance,
    ExchangeConnector,
    MarketInfo,
    MarketType,
    OHLCV,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    PriceTick,
    TradeRecord,
)

logger = logging.getLogger(__name__)

# Default paper trading starting balance
_DEFAULT_BALANCE = Decimal("10000")  # $10,000 USDT


class PaperTradingConnector(ExchangeConnector):
    """
    Simulated exchange for paper trading.

    Features:
    - Configurable starting balance
    - Realistic fill simulation (market + limit)
    - Slippage simulation
    - Fee simulation (0.1% default)
    - Synthetic price generation for testing
    """

    name = "paper"

    def __init__(self, config: Any = None, starting_balance: Decimal = _DEFAULT_BALANCE):
        super().__init__(config)
        self._balances: Dict[str, Balance] = {
            "USDT": Balance(asset="USDT", free=starting_balance, exchange="paper"),
        }
        self._orders: Dict[str, Order] = {}
        self._positions: Dict[str, Position] = {}  # symbol → Position
        self._trades: List[TradeRecord] = []
        self._prices: Dict[str, Decimal] = {}
        self._fee_rate = Decimal("0.001")  # 0.1%
        self._slippage_bps = 5  # 5 basis points

    # ── Lifecycle ──

    async def connect(self) -> None:
        self._connected = True
        logger.info(f"📄 Paper trading connected (balance: ${self._balances['USDT'].free})")

    async def disconnect(self) -> None:
        self._connected = False
        logger.info("Paper trading disconnected")

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        return [b for b in self._balances.values() if b.total > 0]

    async def get_balance(self, asset: str) -> Balance:
        return self._balances.get(asset.upper(), Balance(asset=asset.upper(), exchange="paper"))

    # ── Market data ──

    def set_price(self, symbol: str, price: Decimal) -> None:
        """Manually set a price (for testing or feeding from external source)."""
        self._prices[symbol.upper()] = price

    async def get_price(self, symbol: str) -> PriceTick:
        sym = symbol.upper()
        if sym in self._prices:
            price = self._prices[sym]
        else:
            # Generate synthetic price for testing
            price = self._synthetic_price(sym)
            self._prices[sym] = price

        spread = price * Decimal("0.001")  # 0.1% spread
        return PriceTick(
            symbol=sym,
            price=price,
            bid=price - spread / 2,
            ask=price + spread / 2,
            volume_24h=Decimal("1000000"),
            exchange="paper",
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        """Generate synthetic candles based on current price."""
        price = self._prices.get(symbol.upper(), self._synthetic_price(symbol.upper()))
        candles = []
        for i in range(limit):
            noise = Decimal(str(random.uniform(-0.02, 0.02)))
            o = price * (1 + noise)
            h = o * Decimal(str(random.uniform(1.0, 1.03)))
            l = o * Decimal(str(random.uniform(0.97, 1.0)))
            c = (o + h + l) / 3
            candles.append(OHLCV(
                symbol=symbol.upper(),
                open=o, high=h, low=l, close=c,
                volume=Decimal(str(random.uniform(100, 10000))),
                interval=interval,
            ))
        return candles

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        price = self._prices.get(symbol.upper(), Decimal("100"))
        bids = []
        asks = []
        for i in range(depth):
            offset = Decimal(str(0.01 * (i + 1)))
            bids.append([str(price - offset), str(random.uniform(0.1, 10))])
            asks.append([str(price + offset), str(random.uniform(0.1, 10))])
        return {"bids": bids, "asks": asks}

    async def get_markets(self) -> List[MarketInfo]:
        return [
            MarketInfo(symbol=sym, base_asset=sym.replace("USDT", "").replace("/USDT", ""),
                       quote_asset="USDT", exchange="paper")
            for sym in (list(self._prices.keys()) or ["BTCUSDT", "ETHUSDT", "SOLUSDT"])
        ]

    # ── Orders ──

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
        sym = symbol.upper()
        current_price = self._prices.get(sym, self._synthetic_price(sym))

        # Apply slippage for market orders
        fill_price = current_price
        if order_type == OrderType.MARKET:
            slippage = current_price * Decimal(str(self._slippage_bps)) / Decimal("10000")
            if side == OrderSide.BUY:
                fill_price = current_price + slippage
            else:
                fill_price = current_price - slippage
        elif price:
            fill_price = price

        # Calculate fee
        fee = quantity * fill_price * self._fee_rate

        order = Order(
            order_id=str(uuid.uuid4())[:12],
            symbol=sym,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=fill_price,
            stop_price=stop_price,
            exchange="paper",
            strategy=metadata.get("strategy", "") if metadata else "",
            metadata=metadata or {},
        )

        # Execute immediately for market orders
        if order_type == OrderType.MARKET:
            order = await self._fill_order(order, fill_price, fee)
        else:
            # Limit orders: store as open, simulate fill check later
            order.status = OrderStatus.OPEN
            self._orders[order.order_id] = order

        logger.info(
            f"📄 Paper {side.value} {quantity} {sym} @ ${fill_price} "
            f"(fee: ${fee:.4f}) [{order.status.value}]"
        )
        return order

    async def _fill_order(self, order: Order, fill_price: Decimal, fee: Decimal) -> Order:
        """Simulate order fill."""
        sym = order.symbol
        qty = order.quantity

        if order.side == OrderSide.BUY:
            cost = qty * fill_price + fee
            usdt = self._balances.get("USDT", Balance(asset="USDT", exchange="paper"))
            if usdt.free < cost:
                order.status = OrderStatus.REJECTED
                order.metadata["rejection_reason"] = f"Insufficient USDT: have ${usdt.free}, need ${cost}"
                return order

            # Deduct USDT
            usdt.free -= cost

            # Add to position
            if sym in self._positions:
                pos = self._positions[sym]
                total_qty = pos.quantity + qty
                pos.entry_price = (
                    (pos.entry_price * pos.quantity + fill_price * qty) / total_qty
                )
                pos.quantity = total_qty
                pos.current_price = fill_price
            else:
                self._positions[sym] = Position(
                    symbol=sym,
                    side=PositionSide.LONG,
                    quantity=qty,
                    entry_price=fill_price,
                    current_price=fill_price,
                    exchange="paper",
                    strategy=order.strategy,
                )

            # Add asset balance
            base = sym.replace("USDT", "").replace("/USDT", "")
            if base not in self._balances:
                self._balances[base] = Balance(asset=base, exchange="paper")
            self._balances[base].free += qty

        else:  # SELL
            base = sym.replace("USDT", "").replace("/USDT", "")
            bal = self._balances.get(base, Balance(asset=base, exchange="paper"))
            if bal.free < qty:
                order.status = OrderStatus.REJECTED
                order.metadata["rejection_reason"] = f"Insufficient {base}: have {bal.free}, need {qty}"
                return order

            # Deduct asset
            bal.free -= qty

            # Add USDT
            proceeds = qty * fill_price - fee
            usdt = self._balances.get("USDT", Balance(asset="USDT", exchange="paper"))
            usdt.free += proceeds

            # Update/close position
            if sym in self._positions:
                pos = self._positions[sym]
                pnl = (fill_price - pos.entry_price) * qty
                pnl_pct = ((fill_price - pos.entry_price) / pos.entry_price * 100) if pos.entry_price > 0 else Decimal("0")

                # Record trade
                self._trades.append(TradeRecord(
                    symbol=sym,
                    side=OrderSide.SELL,
                    quantity=qty,
                    entry_price=pos.entry_price,
                    exit_price=fill_price,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    fees=fee,
                    exchange="paper",
                    strategy=order.strategy,
                    entry_time=pos.opened_at,
                    exit_time=datetime.utcnow(),
                ))

                pos.quantity -= qty
                if pos.quantity <= 0:
                    del self._positions[sym]
                    # Clean up zero balance
                    if base in self._balances and self._balances[base].total <= 0:
                        del self._balances[base]

        order.status = OrderStatus.FILLED
        order.filled_quantity = qty
        order.average_fill_price = fill_price
        order.fee = fee
        order.fee_asset = "USDT"
        order.updated_at = datetime.utcnow()
        self._orders[order.order_id] = order
        return order

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        if order_id in self._orders:
            order = self._orders[order_id]
            if order.is_open:
                order.status = OrderStatus.CANCELLED
                order.updated_at = datetime.utcnow()
                return True
        return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        if order_id in self._orders:
            return self._orders[order_id]
        raise ValueError(f"Order not found: {order_id}")

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        return [
            o for o in self._orders.values()
            if o.is_open and (not symbol or o.symbol == symbol.upper())
        ]

    # ── Positions ──

    async def get_positions(self) -> List[Position]:
        # Update current prices
        for sym, pos in self._positions.items():
            if sym in self._prices:
                pos.current_price = self._prices[sym]
        return list(self._positions.values())

    # ── Streaming ──

    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[PriceTick]:
        """Simulate price stream with small random walks."""
        while True:
            for sym in symbols:
                sym_upper = sym.upper()
                if sym_upper not in self._prices:
                    self._prices[sym_upper] = self._synthetic_price(sym_upper)

                # Random walk
                change = Decimal(str(random.uniform(-0.005, 0.005)))
                self._prices[sym_upper] *= (1 + change)

                yield PriceTick(
                    symbol=sym_upper,
                    price=self._prices[sym_upper],
                    exchange="paper",
                )
            await asyncio.sleep(1)

    # ── Trade history ──

    async def get_trade_history(self, symbol: str = "", limit: int = 50) -> List[TradeRecord]:
        trades = self._trades
        if symbol:
            trades = [t for t in trades if t.symbol == symbol.upper()]
        return trades[-limit:]

    # ── Helpers ──

    def _synthetic_price(self, symbol: str) -> Decimal:
        """Generate a realistic-ish price for well-known symbols."""
        defaults = {
            "BTCUSDT": "67000", "ETHUSDT": "3500", "SOLUSDT": "180",
            "BNBUSDT": "600", "XRPUSDT": "0.60", "DOGEUSDT": "0.15",
            "ADAUSDT": "0.45", "AVAXUSDT": "35", "DOTUSDT": "7",
            "LINKUSDT": "15", "UNIUSDT": "10", "ATOMUSDT": "9",
            "NEARUSDT": "5", "ARBUSDT": "1.20", "OPUSDT": "2.50",
            "SUIUSDT": "1.50", "WIFUSDT": "2.50", "PEPEUSDT": "0.00001",
            "SHIBUSDT": "0.000025", "BONKUSDT": "0.00002",
        }
        return Decimal(defaults.get(symbol.upper(), "100"))

    def reset(self, starting_balance: Decimal = _DEFAULT_BALANCE) -> None:
        """Reset paper trading to initial state."""
        self._balances = {"USDT": Balance(asset="USDT", free=starting_balance, exchange="paper")}
        self._orders.clear()
        self._positions.clear()
        self._trades.clear()
        self._prices.clear()
        logger.info(f"📄 Paper trading reset (balance: ${starting_balance})")
