"""
Hyperliquid Connector,  On-chain perpetual futures.

Hyperliquid is a decentralized perps exchange with a central order book.
No KYC, fast execution, popular for degen/memecoin futures.

Requires: HYPERLIQUID_PRIVATE_KEY env var (Ethereum private key).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from datetime import datetime, timezone
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


class HyperliquidConnector(ExchangeConnector):
    """
    Hyperliquid decentralized perpetual futures exchange.

    Uses the Hyperliquid Python SDK for API calls.
    All trading is on-chain on the Hyperliquid L1.
    """

    name = "hyperliquid"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._info = None
        self._exchange = None
        self._private_key = getattr(config, "hyperliquid_private_key", None) if config else None
        self._address = None

    async def connect(self) -> None:
        try:
            from hyperliquid.info import Info
            from hyperliquid.exchange import Exchange
            from hyperliquid.utils import constants as hl_constants
            from eth_account import Account
        except ImportError:
            logger.warning(
                "hyperliquid-python-sdk not installed. "
                "Install with: pip install hyperliquid-python-sdk eth-account"
            )
            self._connected = False
            return

        try:
            self._info = Info(hl_constants.MAINNET_API_URL, skip_ws=True)

            if self._private_key:
                account = Account.from_key(self._private_key)
                self._address = account.address
                self._exchange = Exchange(account, hl_constants.MAINNET_API_URL)

            self._connected = True
            logger.info(f"✅ Hyperliquid connected (address: {self._address or 'read-only'})")
        except Exception as e:
            logger.error(f"Failed to connect to Hyperliquid: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        self._connected = False

    # ── Market data ──

    async def get_price(self, symbol: str) -> PriceTick:
        if not self._info:
            raise ConnectionError("Hyperliquid not connected")
        try:
            meta = self._info.meta()
            all_mids = self._info.all_mids()
            price = Decimal(str(all_mids.get(symbol, 0)))
            return PriceTick(symbol=symbol, price=price, exchange="hyperliquid")
        except Exception as e:
            raise ValueError(f"Failed to get price for {symbol}: {e}")

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        if not self._info:
            return []
        try:
            # Hyperliquid candle snapshot
            end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
            interval_map = {
                "1m": 60000, "5m": 300000, "15m": 900000,
                "1h": 3600000, "4h": 14400000, "1d": 86400000,
            }
            interval_ms = interval_map.get(interval, 3600000)
            start_time = end_time - (interval_ms * limit)

            candles = self._info.candles_snapshot(symbol, interval, start_time, end_time)
            return [
                OHLCV(
                    symbol=symbol,
                    open=Decimal(str(c["o"])),
                    high=Decimal(str(c["h"])),
                    low=Decimal(str(c["l"])),
                    close=Decimal(str(c["c"])),
                    volume=Decimal(str(c["v"])),
                    timestamp=datetime.fromtimestamp(c["t"] / 1000, tz=timezone.utc),
                    interval=interval,
                )
                for c in candles[:limit]
            ]
        except Exception as e:
            logger.error(f"Failed to get Hyperliquid candles: {e}")
            return []

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        if not self._info:
            return {"bids": [], "asks": []}
        try:
            book = self._info.l2_snapshot(symbol)
            bids = [[str(b["px"]), str(b["sz"])] for b in book.get("levels", [[]])[0][:depth]]
            asks = [[str(a["px"]), str(a["sz"])] for a in book.get("levels", [[], []])[1][:depth]]
            return {"bids": bids, "asks": asks}
        except Exception:
            return {"bids": [], "asks": []}

    async def get_markets(self) -> List[MarketInfo]:
        if not self._info:
            return []
        try:
            meta = self._info.meta()
            return [
                MarketInfo(
                    symbol=asset["name"],
                    base_asset=asset["name"],
                    quote_asset="USDC",
                    market_type=MarketType.PERPETUAL,
                    min_order_size=Decimal(str(asset.get("szDecimals", 0))),
                    exchange="hyperliquid",
                )
                for asset in meta.get("universe", [])
            ]
        except Exception:
            return []

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        if not self._info or not self._address:
            return []
        try:
            state = self._info.user_state(self._address)
            margin = state.get("marginSummary", {})
            return [Balance(
                asset="USDC",
                free=Decimal(str(margin.get("totalRawUsd", 0))),
                exchange="hyperliquid",
            )]
        except Exception:
            return []

    async def get_balance(self, asset: str) -> Balance:
        balances = await self.get_balances()
        for b in balances:
            if b.asset == asset:
                return b
        return Balance(asset=asset, exchange="hyperliquid")

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
        if not self._exchange:
            raise ConnectionError("Hyperliquid not connected with trading key")

        try:
            is_buy = side == OrderSide.BUY
            px = float(price) if price else None

            if order_type == OrderType.MARKET:
                # Market order: use aggressive limit
                tick = await self.get_price(symbol)
                slippage = float(tick.price) * 0.005  # 0.5% slippage
                px = float(tick.price) + slippage if is_buy else float(tick.price) - slippage

            order_result = self._exchange.order(
                symbol, is_buy, float(quantity), px,
                {"limit": {"tif": "Gtc"}},
            )

            status = order_result.get("status", "")
            resting = order_result.get("response", {}).get("data", {}).get("statuses", [{}])
            oid = ""
            if resting:
                oid = str(resting[0].get("resting", {}).get("oid", ""))
                if not oid:
                    oid = str(resting[0].get("filled", {}).get("oid", ""))

            return Order(
                order_id=oid or str(hash(str(order_result)))[:12],
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=Decimal(str(px)) if px else None,
                status=OrderStatus.FILLED if "filled" in str(resting) else OrderStatus.OPEN,
                exchange="hyperliquid",
                strategy=metadata.get("strategy", "") if metadata else "",
            )
        except Exception as e:
            logger.error(f"Hyperliquid order failed: {e}")
            return Order(
                symbol=symbol, side=side, quantity=quantity,
                status=OrderStatus.REJECTED, exchange="hyperliquid",
                metadata={"error": str(e)},
            )

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        if not self._exchange:
            return False
        try:
            self._exchange.cancel(symbol, int(order_id))
            return True
        except Exception:
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        # Hyperliquid doesn't have a direct get_order,  check open orders
        open_orders = await self.get_open_orders(symbol)
        for o in open_orders:
            if o.order_id == order_id:
                return o
        raise ValueError(f"Order not found: {order_id}")

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        if not self._info or not self._address:
            return []
        try:
            orders = self._info.open_orders(self._address)
            result = []
            for o in orders:
                if symbol and o.get("coin") != symbol:
                    continue
                result.append(Order(
                    order_id=str(o.get("oid", "")),
                    symbol=o.get("coin", ""),
                    side=OrderSide.BUY if o.get("side") == "B" else OrderSide.SELL,
                    quantity=Decimal(str(o.get("sz", 0))),
                    price=Decimal(str(o.get("limitPx", 0))),
                    status=OrderStatus.OPEN,
                    exchange="hyperliquid",
                ))
            return result
        except Exception:
            return []

    # ── Positions ──

    async def get_positions(self) -> List[Position]:
        if not self._info or not self._address:
            return []
        try:
            state = self._info.user_state(self._address)
            result = []
            for p in state.get("assetPositions", []):
                pos = p.get("position", {})
                sz = float(pos.get("szi", 0))
                if abs(sz) <= 0:
                    continue
                result.append(Position(
                    symbol=pos.get("coin", ""),
                    side=PositionSide.LONG if sz > 0 else PositionSide.SHORT,
                    quantity=Decimal(str(abs(sz))),
                    entry_price=Decimal(str(pos.get("entryPx", 0))),
                    current_price=Decimal(str(pos.get("positionValue", 0))),
                    exchange="hyperliquid",
                ))
            return result
        except Exception:
            return []
