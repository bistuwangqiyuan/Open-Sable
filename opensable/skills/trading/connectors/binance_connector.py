"""
Binance Connector,  Spot and futures trading via the ccxt library.

Supports: spot, USDT-M futures, COIN-M futures.
Requires: BINANCE_API_KEY and BINANCE_API_SECRET env vars.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from datetime import datetime, timezone
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

# Map our OrderType to ccxt
_ORDER_TYPE_MAP = {
    OrderType.MARKET: "market",
    OrderType.LIMIT: "limit",
    OrderType.STOP_LOSS: "stop_market",
    OrderType.STOP_LIMIT: "stop",
    OrderType.TAKE_PROFIT: "take_profit_market",
}

_ORDER_STATUS_MAP = {
    "open": OrderStatus.OPEN,
    "closed": OrderStatus.FILLED,
    "canceled": OrderStatus.CANCELLED,
    "expired": OrderStatus.EXPIRED,
    "rejected": OrderStatus.REJECTED,
}


class BinanceConnector(ExchangeConnector):
    """
    Binance exchange connector using ccxt.

    Usage:
        conn = BinanceConnector(config)
        await conn.connect()
        tick = await conn.get_price("BTC/USDT")
        order = await conn.place_order("BTC/USDT", OrderSide.BUY, OrderType.MARKET, Decimal("0.001"))
    """

    name = "binance"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._exchange = None
        self._api_key = getattr(config, "binance_api_key", None) if config else None
        self._api_secret = getattr(config, "binance_api_secret", None) if config else None
        self._testnet = getattr(config, "binance_testnet", False) if config else False

    async def connect(self) -> None:
        try:
            import ccxt.async_support as ccxt
        except ImportError:
            raise ImportError("Install ccxt: pip install ccxt")

        options = {
            "defaultType": "spot",
            "adjustForTimeDifference": True,
        }
        if self._testnet:
            options["sandboxMode"] = True

        self._exchange = ccxt.binance({
            "apiKey": self._api_key,
            "secret": self._api_secret,
            "options": options,
            "enableRateLimit": True,
        })

        if self._testnet:
            self._exchange.set_sandbox_mode(True)

        await self._exchange.load_markets()
        self._connected = True
        mode = "testnet" if self._testnet else "live"
        logger.info(f"✅ Binance connected ({mode}, {len(self._exchange.markets)} markets)")

    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
        self._connected = False

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        balance = await self._exchange.fetch_balance()
        result = []
        for asset, info in balance.get("total", {}).items():
            if info and float(info) > 0:
                result.append(Balance(
                    asset=asset,
                    free=Decimal(str(balance["free"].get(asset, 0))),
                    locked=Decimal(str(balance["used"].get(asset, 0))),
                    exchange="binance",
                ))
        return result

    async def get_balance(self, asset: str) -> Balance:
        balance = await self._exchange.fetch_balance()
        return Balance(
            asset=asset,
            free=Decimal(str(balance["free"].get(asset, 0))),
            locked=Decimal(str(balance["used"].get(asset, 0))),
            exchange="binance",
        )

    # ── Market data ──

    async def get_price(self, symbol: str) -> PriceTick:
        ticker = await self._exchange.fetch_ticker(symbol)
        return PriceTick(
            symbol=symbol,
            price=Decimal(str(ticker["last"])),
            bid=Decimal(str(ticker["bid"])) if ticker.get("bid") else None,
            ask=Decimal(str(ticker["ask"])) if ticker.get("ask") else None,
            volume_24h=Decimal(str(ticker.get("quoteVolume", 0))),
            exchange="binance",
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        candles = await self._exchange.fetch_ohlcv(symbol, interval, limit=limit)
        return [
            OHLCV(
                symbol=symbol,
                open=Decimal(str(c[1])),
                high=Decimal(str(c[2])),
                low=Decimal(str(c[3])),
                close=Decimal(str(c[4])),
                volume=Decimal(str(c[5])),
                timestamp=datetime.fromtimestamp(c[0] / 1000, tz=timezone.utc),
                interval=interval,
            )
            for c in candles
        ]

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        book = await self._exchange.fetch_order_book(symbol, depth)
        return {
            "bids": [[str(p), str(q)] for p, q in book["bids"]],
            "asks": [[str(p), str(q)] for p, q in book["asks"]],
        }

    async def get_markets(self) -> List[MarketInfo]:
        result = []
        for sym, info in self._exchange.markets.items():
            mtype = MarketType.SPOT
            if info.get("swap"):
                mtype = MarketType.PERPETUAL
            elif info.get("future"):
                mtype = MarketType.FUTURES
            result.append(MarketInfo(
                symbol=sym,
                base_asset=info.get("base", ""),
                quote_asset=info.get("quote", ""),
                market_type=mtype,
                min_order_size=Decimal(str(info.get("limits", {}).get("amount", {}).get("min", 0) or 0)),
                maker_fee=Decimal(str(info.get("maker", 0.001))),
                taker_fee=Decimal(str(info.get("taker", 0.001))),
                exchange="binance",
                is_active=info.get("active", True),
            ))
        return result

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
        ccxt_type = _ORDER_TYPE_MAP.get(order_type, "market")
        params = {}
        if stop_price:
            params["stopPrice"] = float(stop_price)

        result = await self._exchange.create_order(
            symbol=symbol,
            type=ccxt_type,
            side=side.value,
            amount=float(quantity),
            price=float(price) if price else None,
            params=params,
        )

        return self._parse_order(result)

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            await self._exchange.cancel_order(order_id, symbol or None)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        result = await self._exchange.fetch_order(order_id, symbol or None)
        return self._parse_order(result)

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        orders = await self._exchange.fetch_open_orders(symbol or None)
        return [self._parse_order(o) for o in orders]

    # ── Positions ──

    async def get_positions(self) -> List[Position]:
        """Get futures positions (spot doesn't have 'positions')."""
        try:
            positions = await self._exchange.fetch_positions()
            result = []
            for p in positions:
                qty = abs(float(p.get("contracts", 0) or 0))
                if qty <= 0:
                    continue
                result.append(Position(
                    symbol=p.get("symbol", ""),
                    side=PositionSide.LONG if p.get("side") == "long" else PositionSide.SHORT,
                    quantity=Decimal(str(qty)),
                    entry_price=Decimal(str(p.get("entryPrice", 0) or 0)),
                    current_price=Decimal(str(p.get("markPrice", 0) or 0)),
                    exchange="binance",
                ))
            return result
        except Exception:
            # Spot mode,  derive positions from balances
            return []

    # ── Streaming ──

    async def stream_prices(self, symbols: List[str]) -> AsyncIterator[PriceTick]:
        """Stream via ccxt watch_ticker (WebSocket)."""
        if not hasattr(self._exchange, "watch_ticker"):
            raise NotImplementedError("Binance WS requires ccxt pro")
        while True:
            for sym in symbols:
                try:
                    ticker = await self._exchange.watch_ticker(sym)
                    yield PriceTick(
                        symbol=sym,
                        price=Decimal(str(ticker["last"])),
                        bid=Decimal(str(ticker["bid"])) if ticker.get("bid") else None,
                        ask=Decimal(str(ticker["ask"])) if ticker.get("ask") else None,
                        volume_24h=Decimal(str(ticker.get("quoteVolume", 0))),
                        exchange="binance",
                    )
                except Exception as e:
                    logger.error(f"WS error for {sym}: {e}")

    # ── Helpers ──

    def _parse_order(self, data: Dict) -> Order:
        status = _ORDER_STATUS_MAP.get(data.get("status", ""), OrderStatus.PENDING)
        return Order(
            order_id=str(data.get("id", "")),
            symbol=data.get("symbol", ""),
            side=OrderSide.BUY if data.get("side") == "buy" else OrderSide.SELL,
            order_type=OrderType.MARKET if data.get("type") == "market" else OrderType.LIMIT,
            quantity=Decimal(str(data.get("amount", 0))),
            price=Decimal(str(data["price"])) if data.get("price") else None,
            status=status,
            filled_quantity=Decimal(str(data.get("filled", 0))),
            average_fill_price=Decimal(str(data["average"])) if data.get("average") else None,
            fee=Decimal(str(data.get("fee", {}).get("cost", 0) or 0)),
            fee_asset=data.get("fee", {}).get("currency", ""),
            exchange="binance",
            created_at=datetime.fromtimestamp(data["timestamp"] / 1000, tz=timezone.utc) if data.get("timestamp") else datetime.now(timezone.utc),
        )
