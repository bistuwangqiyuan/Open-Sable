"""
Coinbase Connector — Spot trading via ccxt.

Requires: COINBASE_API_KEY and COINBASE_API_SECRET env vars.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from datetime import datetime
from typing import Any, Dict, List, Optional

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
    PriceTick,
)

logger = logging.getLogger(__name__)


class CoinbaseConnector(ExchangeConnector):
    """Coinbase Advanced Trade connector via ccxt."""

    name = "coinbase"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._exchange = None
        self._api_key = getattr(config, "coinbase_api_key", None) if config else None
        self._api_secret = getattr(config, "coinbase_api_secret", None) if config else None

    async def connect(self) -> None:
        try:
            import ccxt.async_support as ccxt
        except ImportError:
            raise ImportError("Install ccxt: pip install ccxt")

        self._exchange = ccxt.coinbase({
            "apiKey": self._api_key,
            "secret": self._api_secret,
            "enableRateLimit": True,
        })
        await self._exchange.load_markets()
        self._connected = True
        logger.info(f"✅ Coinbase connected ({len(self._exchange.markets)} markets)")

    async def disconnect(self) -> None:
        if self._exchange:
            await self._exchange.close()
        self._connected = False

    async def get_balances(self) -> List[Balance]:
        balance = await self._exchange.fetch_balance()
        result = []
        for asset, total in balance.get("total", {}).items():
            if total and float(total) > 0:
                result.append(Balance(
                    asset=asset,
                    free=Decimal(str(balance["free"].get(asset, 0))),
                    locked=Decimal(str(balance["used"].get(asset, 0))),
                    exchange="coinbase",
                ))
        return result

    async def get_balance(self, asset: str) -> Balance:
        balance = await self._exchange.fetch_balance()
        return Balance(
            asset=asset,
            free=Decimal(str(balance["free"].get(asset, 0))),
            locked=Decimal(str(balance["used"].get(asset, 0))),
            exchange="coinbase",
        )

    async def get_price(self, symbol: str) -> PriceTick:
        ticker = await self._exchange.fetch_ticker(symbol)
        return PriceTick(
            symbol=symbol,
            price=Decimal(str(ticker["last"])),
            bid=Decimal(str(ticker["bid"])) if ticker.get("bid") else None,
            ask=Decimal(str(ticker["ask"])) if ticker.get("ask") else None,
            volume_24h=Decimal(str(ticker.get("quoteVolume", 0))),
            exchange="coinbase",
        )

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        candles = await self._exchange.fetch_ohlcv(symbol, interval, limit=limit)
        return [
            OHLCV(
                symbol=symbol,
                open=Decimal(str(c[1])), high=Decimal(str(c[2])),
                low=Decimal(str(c[3])), close=Decimal(str(c[4])),
                volume=Decimal(str(c[5])),
                timestamp=datetime.utcfromtimestamp(c[0] / 1000),
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
        return [
            MarketInfo(
                symbol=sym, base_asset=info.get("base", ""),
                quote_asset=info.get("quote", ""),
                market_type=MarketType.SPOT, exchange="coinbase",
                is_active=info.get("active", True),
            )
            for sym, info in self._exchange.markets.items()
        ]

    async def place_order(
        self, symbol: str, side: OrderSide, order_type: OrderType,
        quantity: Decimal, price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Order:
        ccxt_type = "market" if order_type == OrderType.MARKET else "limit"
        result = await self._exchange.create_order(
            symbol=symbol, type=ccxt_type, side=side.value,
            amount=float(quantity),
            price=float(price) if price else None,
        )
        return Order(
            order_id=str(result.get("id", "")),
            symbol=symbol, side=side, order_type=order_type,
            quantity=quantity, price=price,
            status=OrderStatus.FILLED if result.get("status") == "closed" else OrderStatus.OPEN,
            filled_quantity=Decimal(str(result.get("filled", 0))),
            average_fill_price=Decimal(str(result["average"])) if result.get("average") else None,
            exchange="coinbase",
        )

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            await self._exchange.cancel_order(order_id, symbol or None)
            return True
        except Exception:
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        r = await self._exchange.fetch_order(order_id, symbol or None)
        return Order(
            order_id=str(r["id"]), symbol=r.get("symbol", ""),
            side=OrderSide.BUY if r.get("side") == "buy" else OrderSide.SELL,
            status=OrderStatus.FILLED if r.get("status") == "closed" else OrderStatus.OPEN,
            quantity=Decimal(str(r.get("amount", 0))),
            filled_quantity=Decimal(str(r.get("filled", 0))),
            exchange="coinbase",
        )

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        orders = await self._exchange.fetch_open_orders(symbol or None)
        return [
            Order(
                order_id=str(o["id"]), symbol=o.get("symbol", ""),
                side=OrderSide.BUY if o.get("side") == "buy" else OrderSide.SELL,
                status=OrderStatus.OPEN,
                quantity=Decimal(str(o.get("amount", 0))),
                exchange="coinbase",
            )
            for o in orders
        ]

    async def get_positions(self) -> List[Position]:
        # Coinbase spot — derive from balances
        return []
