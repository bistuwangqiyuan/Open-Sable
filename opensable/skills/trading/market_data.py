"""
Market Data Service,  Unified price feeds, candles, and order books.

Aggregates data from multiple exchanges and free APIs (CoinGecko, etc.).
Provides caching to avoid hammering rate-limited APIs.
"""

from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional

from .base import ExchangeConnector, MarketInfo, OHLCV, PriceTick

logger = logging.getLogger(__name__)


class MarketDataService:
    """
    Aggregated, cached market data from all connected exchanges.

    Features:
    - Price cache with configurable TTL
    - Automatic fallback: exchange API → CoinGecko → cached
    - Subscription support for live tickers
    """

    def __init__(self, connectors: Optional[Dict[str, ExchangeConnector]] = None, cache_ttl: int = 10):
        self._connectors: Dict[str, ExchangeConnector] = connectors or {}
        self._cache_ttl = cache_ttl  # seconds
        self._price_cache: Dict[str, _CacheEntry] = {}
        self._ohlcv_cache: Dict[str, _CacheEntry] = {}
        self._subscribers: Dict[str, List[Callable]] = {}

    def add_connector(self, connector: ExchangeConnector) -> None:
        self._connectors[connector.name] = connector

    # ── Prices ──

    async def get_price(self, symbol: str, exchange: str = "") -> PriceTick:
        """
        Get latest price. Checks cache first, then exchange, then CoinGecko.
        """
        cache_key = f"{exchange or 'any'}:{symbol}"

        # Check cache
        cached = self._price_cache.get(cache_key)
        if cached and not cached.is_expired(self._cache_ttl):
            return cached.value

        # Try specific exchange
        if exchange and exchange in self._connectors:
            try:
                tick = await self._connectors[exchange].get_price(symbol)
                self._price_cache[cache_key] = _CacheEntry(tick)
                return tick
            except Exception as e:
                logger.warning(f"Price fetch from {exchange} failed: {e}")

        # Try real (non-paper) connected exchanges first
        paper_conn = None
        for name, conn in self._connectors.items():
            if name == "paper":
                paper_conn = conn
                continue
            if not conn.is_connected:
                continue
            try:
                tick = await conn.get_price(symbol)
                self._price_cache[cache_key] = _CacheEntry(tick)
                return tick
            except Exception:
                continue

        # CoinGecko free API,  preferred over paper for real prices
        try:
            tick = await self._fetch_coingecko_price(symbol)
            if tick:
                self._price_cache[cache_key] = _CacheEntry(tick)
                return tick
        except Exception as e:
            logger.warning(f"CoinGecko fallback failed: {e}")

        # Last resort: paper connector (synthetic prices)
        if paper_conn and paper_conn.is_connected:
            try:
                tick = await paper_conn.get_price(symbol)
                self._price_cache[cache_key] = _CacheEntry(tick)
                return tick
            except Exception:
                pass

        # Return stale cache if available
        if cached:
            logger.warning(f"Returning stale price for {symbol}")
            return cached.value

        raise ValueError(f"No price data available for {symbol}")

    async def get_prices(self, symbols: List[str], exchange: str = "") -> Dict[str, PriceTick]:
        """Get prices for multiple symbols in parallel."""
        tasks = [self.get_price(s, exchange) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        prices = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, PriceTick):
                prices[symbol] = result
            else:
                logger.warning(f"Failed to get price for {symbol}: {result}")
        return prices

    # ── Candles ──

    async def get_ohlcv(
        self, symbol: str, interval: str = "1h", limit: int = 100, exchange: str = ""
    ) -> List[OHLCV]:
        """Get OHLCV candles."""
        cache_key = f"{exchange or 'any'}:{symbol}:{interval}:{limit}"
        cached = self._ohlcv_cache.get(cache_key)
        if cached and not cached.is_expired(self._cache_ttl * 6):  # Longer TTL for candles
            return cached.value

        # Try exchanges
        connectors = (
            [self._connectors[exchange]] if exchange and exchange in self._connectors
            else list(self._connectors.values())
        )
        for conn in connectors:
            if not conn.is_connected:
                continue
            try:
                candles = await conn.get_ohlcv(symbol, interval, limit)
                self._ohlcv_cache[cache_key] = _CacheEntry(candles)
                return candles
            except Exception:
                continue

        if cached:
            return cached.value
        raise ValueError(f"No OHLCV data available for {symbol}")

    # ── Order book ──

    async def get_orderbook(self, symbol: str, exchange: str = "", depth: int = 20) -> Dict[str, Any]:
        """Get order book."""
        connectors = (
            [self._connectors[exchange]] if exchange and exchange in self._connectors
            else list(self._connectors.values())
        )
        for conn in connectors:
            if not conn.is_connected:
                continue
            try:
                return await conn.get_orderbook(symbol, depth)
            except Exception:
                continue
        return {"bids": [], "asks": []}

    # ── Markets catalog ──

    async def get_all_markets(self) -> Dict[str, List[MarketInfo]]:
        """Get all tradeable markets grouped by exchange."""
        result: Dict[str, List[MarketInfo]] = {}
        for name, conn in self._connectors.items():
            if not conn.is_connected:
                continue
            try:
                markets = await conn.get_markets()
                result[name] = markets
            except Exception as e:
                logger.error(f"Failed to list markets from {name}: {e}")
                result[name] = []
        return result

    # ── CoinGecko fallback ──

    async def _fetch_coingecko_price(self, symbol: str) -> Optional[PriceTick]:
        """Fetch price from CoinGecko free API."""
        try:
            import httpx

            # Map common symbols to CoinGecko IDs
            cg_map = {
                "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
                "BNB": "binancecoin", "XRP": "ripple", "DOGE": "dogecoin",
                "ADA": "cardano", "AVAX": "avalanche-2", "DOT": "polkadot",
                "MATIC": "matic-network", "LINK": "chainlink",
                "UNI": "uniswap", "ATOM": "cosmos", "LTC": "litecoin",
                "NEAR": "near", "APT": "aptos", "ARB": "arbitrum",
                "OP": "optimism", "SUI": "sui", "SEI": "sei-network",
                "TIA": "celestia", "JUP": "jupiter-exchange-solana",
                "WIF": "dogwifcoin", "PEPE": "pepe", "SHIB": "shiba-inu",
                "BONK": "bonk", "FLOKI": "floki",
            }

            # Parse symbol,  handle BTC/USDT, BTCUSDT, BTC
            base = symbol.upper().replace("/USDT", "").replace("/USD", "").replace("USDT", "").replace("USD", "")
            cg_id = cg_map.get(base, base.lower())

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"https://api.coingecko.com/api/v3/simple/price",
                    params={"ids": cg_id, "vs_currencies": "usd", "include_24hr_vol": "true"},
                )
                data = resp.json()

            if cg_id in data:
                price = Decimal(str(data[cg_id]["usd"]))
                vol = data[cg_id].get("usd_24h_vol")
                return PriceTick(
                    symbol=symbol,
                    price=price,
                    volume_24h=Decimal(str(vol)) if vol else None,
                    exchange="coingecko",
                )
        except Exception as e:
            logger.debug(f"CoinGecko price fetch failed for {symbol}: {e}")
        return None

    # ── Cache ──

    def clear_cache(self) -> None:
        self._price_cache.clear()
        self._ohlcv_cache.clear()


class _CacheEntry:
    """Simple TTL cache entry."""
    __slots__ = ("value", "created_at")

    def __init__(self, value: Any):
        self.value = value
        self.created_at = time.time()

    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.created_at) > ttl
