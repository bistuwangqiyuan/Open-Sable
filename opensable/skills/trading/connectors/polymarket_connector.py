"""
Polymarket Connector,  Prediction market trading.

Uses py-clob-client for the Polymarket CLOB (Central Limit Order Book).
Falls back to browser automation (Playwright) for web-only flows.

Requires: POLYMARKET_PRIVATE_KEY (Ethereum private key for signing).
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


class PolymarketConnector(ExchangeConnector):
    """
    Polymarket prediction market connector.

    Markets are binary outcomes (YES/NO shares priced 0-1 USDC).
    Buying YES at $0.40 means you think the probability is >40%.
    If the event resolves YES, each share pays $1.00.

    Usage:
        conn = PolymarketConnector(config)
        await conn.connect()
        markets = await conn.get_markets()
        order = await conn.place_order("will-bitcoin-hit-100k-2026", OrderSide.BUY, ...)
    """

    name = "polymarket"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._client = None
        self._private_key = getattr(config, "polymarket_private_key", None) if config else None
        self._api_key = getattr(config, "polymarket_api_key", None) if config else None
        self._markets_cache: Dict[str, Dict] = {}

    async def connect(self) -> None:
        try:
            from py_clob_client.client import ClobClient
            from py_clob_client.clob_types import ApiCreds
        except ImportError:
            logger.warning(
                "py-clob-client not installed. Install with: pip install py-clob-client"
            )
            self._connected = False
            return

        try:
            host = "https://clob.polymarket.com"
            chain_id = 137  # Polygon

            if self._private_key:
                self._client = ClobClient(
                    host,
                    key=self._private_key,
                    chain_id=chain_id,
                )
                # Derive API creds from signature
                self._client.set_api_creds(self._client.create_or_derive_api_creds())

            self._connected = True
            logger.info("✅ Polymarket connected")
        except Exception as e:
            logger.error(f"Failed to connect to Polymarket: {e}")
            self._connected = False

    async def disconnect(self) -> None:
        self._connected = False

    # ── Market data ──

    async def get_markets(self) -> List[MarketInfo]:
        """Fetch active prediction markets."""
        if not self._client:
            return []
        try:
            markets = self._client.get_markets()
            result = []
            for m in markets:
                condition_id = m.get("condition_id", "")
                question = m.get("question", "Unknown")
                self._markets_cache[condition_id] = m
                result.append(MarketInfo(
                    symbol=condition_id,
                    base_asset=question[:80],
                    quote_asset="USDC",
                    market_type=MarketType.PREDICTION,
                    exchange="polymarket",
                    is_active=m.get("active", True),
                ))
            return result
        except Exception as e:
            logger.error(f"Failed to fetch Polymarket markets: {e}")
            return []

    async def get_price(self, symbol: str) -> PriceTick:
        """Get midpoint price for a market (condition_id or token_id)."""
        if not self._client:
            raise ConnectionError("Polymarket not connected")
        try:
            book = self._client.get_order_book(symbol)
            bids = book.get("bids", [])
            asks = book.get("asks", [])

            best_bid = Decimal(str(bids[0]["price"])) if bids else Decimal("0")
            best_ask = Decimal(str(asks[0]["price"])) if asks else Decimal("1")
            mid = (best_bid + best_ask) / 2

            return PriceTick(
                symbol=symbol,
                price=mid,
                bid=best_bid,
                ask=best_ask,
                exchange="polymarket",
            )
        except Exception as e:
            logger.error(f"Failed to get Polymarket price: {e}")
            raise

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        # Polymarket doesn't have traditional OHLCV,  return empty
        return []

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        if not self._client:
            return {"bids": [], "asks": []}
        try:
            book = self._client.get_order_book(symbol)
            return {
                "bids": [[str(b["price"]), str(b["size"])] for b in book.get("bids", [])[:depth]],
                "asks": [[str(a["price"]), str(a["size"])] for a in book.get("asks", [])[:depth]],
            }
        except Exception:
            return {"bids": [], "asks": []}

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        # Polymarket balance is the USDC on Polygon
        # This requires web3 to check on-chain balance
        try:
            import httpx
            # Simplified,  in production, use web3 to check USDC balance
            return [Balance(asset="USDC", free=Decimal("0"), exchange="polymarket")]
        except Exception:
            return []

    async def get_balance(self, asset: str) -> Balance:
        balances = await self.get_balances()
        for b in balances:
            if b.asset == asset:
                return b
        return Balance(asset=asset, exchange="polymarket")

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
        """
        Place a bet on Polymarket.

        For prediction markets:
        - BUY = buy YES shares (you think the event WILL happen)
        - SELL = buy NO shares or sell YES shares
        - price = 0.00 to 1.00 (probability)
        - quantity = number of shares
        """
        if not self._client:
            raise ConnectionError("Polymarket not connected")

        try:
            from py_clob_client.order_builder.constants import BUY, SELL

            pm_side = BUY if side == OrderSide.BUY else SELL

            signed_order = self._client.create_and_post_order({
                "token_id": symbol,
                "price": float(price) if price else 0.5,
                "size": float(quantity),
                "side": pm_side,
            })

            return Order(
                order_id=signed_order.get("orderID", str(hash(str(signed_order)))[:12]),
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                status=OrderStatus.OPEN,
                exchange="polymarket",
                strategy=metadata.get("strategy", "") if metadata else "",
                metadata=metadata or {},
            )
        except Exception as e:
            logger.error(f"Failed to place Polymarket order: {e}")
            return Order(
                symbol=symbol, side=side, quantity=quantity, price=price,
                status=OrderStatus.REJECTED, exchange="polymarket",
                metadata={"error": str(e)},
            )

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        if not self._client:
            return False
        try:
            self._client.cancel(order_id)
            return True
        except Exception as e:
            logger.error(f"Failed to cancel Polymarket order: {e}")
            return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        if not self._client:
            raise ConnectionError("Polymarket not connected")
        try:
            result = self._client.get_order(order_id)
            return Order(
                order_id=order_id,
                symbol=result.get("asset_id", symbol),
                status=OrderStatus.FILLED if result.get("status") == "MATCHED" else OrderStatus.OPEN,
                exchange="polymarket",
            )
        except Exception as e:
            raise ValueError(f"Order not found: {e}")

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        if not self._client:
            return []
        try:
            orders = self._client.get_orders()
            return [
                Order(
                    order_id=o.get("id", ""),
                    symbol=o.get("asset_id", ""),
                    side=OrderSide.BUY if o.get("side") == "BUY" else OrderSide.SELL,
                    quantity=Decimal(str(o.get("original_size", 0))),
                    price=Decimal(str(o.get("price", 0))),
                    status=OrderStatus.OPEN,
                    exchange="polymarket",
                )
                for o in orders
                if o.get("status") in ("LIVE", "ACTIVE")
            ]
        except Exception:
            return []

    async def get_positions(self) -> List[Position]:
        """Get current Polymarket positions (shares held)."""
        # This would need on-chain data or Polymarket's positions endpoint
        return []

    # ── Polymarket-specific ──

    async def search_markets(self, query: str) -> List[Dict[str, Any]]:
        """Search for prediction markets by keyword."""
        if not self._client:
            return []
        try:
            markets = self._client.get_markets()
            results = []
            query_lower = query.lower()
            for m in markets:
                if query_lower in m.get("question", "").lower() or query_lower in m.get("description", "").lower():
                    results.append({
                        "condition_id": m.get("condition_id"),
                        "question": m.get("question"),
                        "description": m.get("description", "")[:200],
                        "active": m.get("active"),
                        "tokens": m.get("tokens", []),
                    })
            return results[:20]
        except Exception as e:
            logger.error(f"Polymarket search failed: {e}")
            return []

    async def get_market_details(self, condition_id: str) -> Dict[str, Any]:
        """Get full details for a specific market."""
        if not self._client:
            return {}
        try:
            market = self._client.get_market(condition_id)
            return {
                "condition_id": market.get("condition_id"),
                "question": market.get("question"),
                "description": market.get("description"),
                "outcomes": market.get("outcomes"),
                "tokens": market.get("tokens"),
                "active": market.get("active"),
                "end_date": market.get("end_date_iso"),
                "volume": market.get("volume_num_fmt"),
                "liquidity": market.get("liquidity_num_fmt"),
            }
        except Exception as e:
            logger.error(f"Failed to get market details: {e}")
            return {}
