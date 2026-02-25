"""
Alpaca Connector — Commission-free US stocks, ETFs, and crypto.

Supports paper trading (sandbox) and live trading.
Ideal for stock/commodity exposure (via ETFs like GLD, USO, SPY).

Requires: ALPACA_API_KEY and ALPACA_API_SECRET env vars.
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
    PositionSide,
    PriceTick,
)

logger = logging.getLogger(__name__)


class AlpacaConnector(ExchangeConnector):
    """
    Alpaca Markets connector for stocks and crypto.

    Supports:
    - US equities (stocks, ETFs) — commission-free
    - Crypto (via Alpaca Crypto)
    - Paper trading mode (sandbox)

    Commodity exposure via ETFs: GLD (gold), SLV (silver),
    USO (oil), UNG (natural gas), DBA (agriculture).
    """

    name = "alpaca"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._api = None
        self._api_key = getattr(config, "alpaca_api_key", None) if config else None
        self._api_secret = getattr(config, "alpaca_api_secret", None) if config else None
        self._paper = getattr(config, "alpaca_paper", True) if config else True

    async def connect(self) -> None:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.data.historical import StockHistoricalDataClient
        except ImportError:
            raise ImportError(
                "alpaca-py required: pip install alpaca-py"
            )

        self._api = TradingClient(
            self._api_key,
            self._api_secret,
            paper=self._paper,
        )
        self._data_client = StockHistoricalDataClient(
            self._api_key,
            self._api_secret,
        )
        self._connected = True
        mode = "paper" if self._paper else "live"
        logger.info(f"✅ Alpaca connected ({mode} trading)")

    async def disconnect(self) -> None:
        self._connected = False

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        if not self._api:
            return []
        try:
            account = self._api.get_account()
            return [
                Balance(
                    asset="USD",
                    free=Decimal(str(account.cash)),
                    locked=Decimal(str(float(account.portfolio_value) - float(account.cash))),
                    exchange="alpaca",
                )
            ]
        except Exception as e:
            logger.error(f"Failed to get Alpaca balance: {e}")
            return []

    async def get_balance(self, asset: str) -> Balance:
        balances = await self.get_balances()
        return balances[0] if balances else Balance(asset="USD", exchange="alpaca")

    # ── Market data ──

    async def get_price(self, symbol: str) -> PriceTick:
        if not self._api:
            raise ConnectionError("Alpaca not connected")
        try:
            from alpaca.data.requests import StockLatestQuoteRequest

            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = self._data_client.get_stock_latest_quote(request)
            quote = quotes.get(symbol)
            if quote:
                mid = (Decimal(str(quote.bid_price)) + Decimal(str(quote.ask_price))) / 2
                return PriceTick(
                    symbol=symbol,
                    price=mid,
                    bid=Decimal(str(quote.bid_price)),
                    ask=Decimal(str(quote.ask_price)),
                    exchange="alpaca",
                )
            raise ValueError(f"No quote for {symbol}")
        except Exception as e:
            raise ValueError(f"Alpaca price fetch failed: {e}")

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        if not self._data_client:
            return []
        try:
            from alpaca.data.requests import StockBarsRequest
            from alpaca.data.timeframe import TimeFrame

            tf_map = {
                "1m": TimeFrame.Minute, "5m": TimeFrame(5, "Min"),
                "15m": TimeFrame(15, "Min"), "1h": TimeFrame.Hour,
                "1d": TimeFrame.Day, "1w": TimeFrame.Week,
            }
            tf = tf_map.get(interval, TimeFrame.Hour)

            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=tf,
                limit=limit,
            )
            bars = self._data_client.get_stock_bars(request)
            return [
                OHLCV(
                    symbol=symbol,
                    open=Decimal(str(bar.open)),
                    high=Decimal(str(bar.high)),
                    low=Decimal(str(bar.low)),
                    close=Decimal(str(bar.close)),
                    volume=Decimal(str(bar.volume)),
                    timestamp=bar.timestamp,
                    interval=interval,
                )
                for bar in bars.get(symbol, [])
            ]
        except Exception as e:
            logger.error(f"Alpaca OHLCV failed: {e}")
            return []

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        # Alpaca doesn't expose full order book
        try:
            tick = await self.get_price(symbol)
            return {
                "bids": [[str(tick.bid), "N/A"]] if tick.bid else [],
                "asks": [[str(tick.ask), "N/A"]] if tick.ask else [],
            }
        except Exception:
            return {"bids": [], "asks": []}

    async def get_markets(self) -> List[MarketInfo]:
        if not self._api:
            return []
        try:
            from alpaca.trading.requests import GetAssetsRequest
            from alpaca.trading.enums import AssetClass

            request = GetAssetsRequest(asset_class=AssetClass.US_EQUITY)
            assets = self._api.get_all_assets(request)
            return [
                MarketInfo(
                    symbol=a.symbol,
                    base_asset=a.symbol,
                    quote_asset="USD",
                    market_type=MarketType.SPOT,
                    exchange="alpaca",
                    is_active=a.tradable,
                )
                for a in assets[:500]  # Limit to avoid memory issues
                if a.tradable
            ]
        except Exception:
            return []

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
        if not self._api:
            raise ConnectionError("Alpaca not connected")

        try:
            from alpaca.trading.requests import (
                MarketOrderRequest, LimitOrderRequest, StopOrderRequest,
            )
            from alpaca.trading.enums import OrderSide as AlpacaSide, TimeInForce

            alp_side = AlpacaSide.BUY if side == OrderSide.BUY else AlpacaSide.SELL

            if order_type == OrderType.MARKET:
                req = MarketOrderRequest(
                    symbol=symbol, qty=float(quantity),
                    side=alp_side, time_in_force=TimeInForce.DAY,
                )
            elif order_type == OrderType.LIMIT and price:
                req = LimitOrderRequest(
                    symbol=symbol, qty=float(quantity), limit_price=float(price),
                    side=alp_side, time_in_force=TimeInForce.GTC,
                )
            elif order_type in (OrderType.STOP_LOSS, OrderType.STOP_LIMIT) and stop_price:
                req = StopOrderRequest(
                    symbol=symbol, qty=float(quantity), stop_price=float(stop_price),
                    side=alp_side, time_in_force=TimeInForce.GTC,
                )
            else:
                req = MarketOrderRequest(
                    symbol=symbol, qty=float(quantity),
                    side=alp_side, time_in_force=TimeInForce.DAY,
                )

            result = self._api.submit_order(req)

            return Order(
                order_id=str(result.id),
                symbol=symbol, side=side, order_type=order_type,
                quantity=quantity, price=price,
                status=OrderStatus.OPEN,
                exchange="alpaca",
                strategy=metadata.get("strategy", "") if metadata else "",
            )
        except Exception as e:
            logger.error(f"Alpaca order failed: {e}")
            return Order(
                symbol=symbol, side=side, quantity=quantity,
                status=OrderStatus.REJECTED, exchange="alpaca",
                metadata={"error": str(e)},
            )

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        try:
            self._api.cancel_order_by_id(order_id)
            return True
        except Exception:
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        result = self._api.get_order_by_id(order_id)
        return self._parse_alpaca_order(result)

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        from alpaca.trading.requests import GetOrdersRequest
        request = GetOrdersRequest(status="open")
        orders = self._api.get_orders(request)
        return [self._parse_alpaca_order(o) for o in orders]

    # ── Positions ──

    async def get_positions(self) -> List[Position]:
        if not self._api:
            return []
        try:
            positions = self._api.get_all_positions()
            return [
                Position(
                    symbol=p.symbol,
                    side=PositionSide.LONG if float(p.qty) > 0 else PositionSide.SHORT,
                    quantity=Decimal(str(abs(float(p.qty)))),
                    entry_price=Decimal(str(p.avg_entry_price)),
                    current_price=Decimal(str(p.current_price)),
                    exchange="alpaca",
                )
                for p in positions
            ]
        except Exception:
            return []

    # ── Helpers ──

    def _parse_alpaca_order(self, o: Any) -> Order:
        status_map = {
            "new": OrderStatus.OPEN, "accepted": OrderStatus.OPEN,
            "filled": OrderStatus.FILLED, "canceled": OrderStatus.CANCELLED,
            "expired": OrderStatus.EXPIRED, "rejected": OrderStatus.REJECTED,
            "partially_filled": OrderStatus.PARTIALLY_FILLED,
        }
        return Order(
            order_id=str(o.id),
            symbol=o.symbol,
            side=OrderSide.BUY if str(o.side) == "buy" else OrderSide.SELL,
            quantity=Decimal(str(o.qty)) if o.qty else Decimal("0"),
            price=Decimal(str(o.limit_price)) if o.limit_price else None,
            status=status_map.get(str(o.status), OrderStatus.PENDING),
            filled_quantity=Decimal(str(o.filled_qty)) if o.filled_qty else Decimal("0"),
            average_fill_price=Decimal(str(o.filled_avg_price)) if o.filled_avg_price else None,
            exchange="alpaca",
        )
