"""
Jupiter / Solana DEX Connector — Memecoin and token swaps.

Uses the Jupiter Aggregator API for best-price routing across Solana DEXes.
Ideal for memecoin trading (BONK, WIF, PEPE on Solana, etc.).

Requires: JUPITER_PRIVATE_KEY (Solana wallet private key, base58).
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

# Jupiter API endpoints
JUPITER_API = "https://quote-api.jup.ag/v6"
JUPITER_PRICE_API = "https://price.jup.ag/v6"

# Well-known Solana token mints
KNOWN_MINTS = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "USDT": "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
    "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
    "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
    "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
}


class JupiterConnector(ExchangeConnector):
    """
    Jupiter DEX aggregator on Solana.

    Provides token swaps with best-price routing across all Solana DEXes.
    Particularly useful for memecoin trading.
    """

    name = "jupiter"

    def __init__(self, config: Any = None):
        super().__init__(config)
        self._private_key = getattr(config, "jupiter_private_key", None) if config else None
        self._wallet_address = None
        self._httpx_client = None

    async def connect(self) -> None:
        try:
            import httpx
            self._httpx_client = httpx.AsyncClient(timeout=30)
        except ImportError:
            raise ImportError("httpx required: pip install httpx")

        if self._private_key:
            try:
                from solders.keypair import Keypair
                kp = Keypair.from_base58_string(self._private_key)
                self._wallet_address = str(kp.pubkey())
            except ImportError:
                logger.warning("solders not installed — read-only mode")
            except Exception as e:
                logger.error(f"Invalid Solana private key: {e}")

        self._connected = True
        logger.info(f"✅ Jupiter/Solana connected (wallet: {self._wallet_address or 'read-only'})")

    async def disconnect(self) -> None:
        if self._httpx_client:
            await self._httpx_client.aclose()
        self._connected = False

    # ── Market data ──

    async def get_price(self, symbol: str) -> PriceTick:
        """Get token price via Jupiter Price API."""
        mint = KNOWN_MINTS.get(symbol.upper(), symbol)
        try:
            resp = await self._httpx_client.get(
                f"{JUPITER_PRICE_API}/price",
                params={"ids": mint},
            )
            data = resp.json().get("data", {})
            if mint in data:
                price = Decimal(str(data[mint]["price"]))
                return PriceTick(symbol=symbol, price=price, exchange="jupiter")
            raise ValueError(f"No price for {symbol}")
        except Exception as e:
            raise ValueError(f"Jupiter price fetch failed: {e}")

    async def get_ohlcv(self, symbol: str, interval: str = "1h", limit: int = 100) -> List[OHLCV]:
        # Jupiter doesn't provide candles — use Birdeye or DexScreener as fallback
        return []

    async def get_orderbook(self, symbol: str, depth: int = 20) -> Dict[str, Any]:
        # DEX swaps don't have traditional order books
        return {"bids": [], "asks": [], "note": "DEX — use get_quote for swap pricing"}

    async def get_markets(self) -> List[MarketInfo]:
        """Return known token markets."""
        return [
            MarketInfo(
                symbol=name,
                base_asset=name,
                quote_asset="USDC",
                market_type=MarketType.SPOT,
                exchange="jupiter",
            )
            for name in KNOWN_MINTS.keys()
        ]

    # ── Account ──

    async def get_balances(self) -> List[Balance]:
        if not self._wallet_address:
            return []
        try:
            # Use Solana RPC to get token accounts
            import httpx
            rpc = "https://api.mainnet-beta.solana.com"
            resp = await self._httpx_client.post(rpc, json={
                "jsonrpc": "2.0", "id": 1,
                "method": "getTokenAccountsByOwner",
                "params": [
                    self._wallet_address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"},
                ],
            })
            data = resp.json()
            balances = []
            for acc in data.get("result", {}).get("value", []):
                info = acc.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                mint = info.get("mint", "")
                amount = info.get("tokenAmount", {})
                ui_amount = amount.get("uiAmount", 0)
                if ui_amount and ui_amount > 0:
                    # Reverse lookup mint to symbol
                    sym = next((k for k, v in KNOWN_MINTS.items() if v == mint), mint[:8])
                    balances.append(Balance(
                        asset=sym,
                        free=Decimal(str(ui_amount)),
                        exchange="jupiter",
                    ))
            return balances
        except Exception as e:
            logger.error(f"Failed to fetch Solana balances: {e}")
            return []

    async def get_balance(self, asset: str) -> Balance:
        balances = await self.get_balances()
        for b in balances:
            if b.asset.upper() == asset.upper():
                return b
        return Balance(asset=asset, exchange="jupiter")

    # ── Swap (Order Placement) ──

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
        Execute a token swap via Jupiter.

        For BUY: swap USDC → token
        For SELL: swap token → USDC
        """
        if not self._wallet_address:
            raise ConnectionError("No wallet configured for Jupiter trading")

        token_mint = KNOWN_MINTS.get(symbol.upper(), symbol)
        usdc_mint = KNOWN_MINTS["USDC"]

        if side == OrderSide.BUY:
            input_mint = usdc_mint
            output_mint = token_mint
            # Calculate USDC amount from quantity * price
            amount_raw = int(float(quantity * (price or Decimal("1"))) * 1_000_000)  # USDC has 6 decimals
        else:
            input_mint = token_mint
            output_mint = usdc_mint
            amount_raw = int(float(quantity) * 1_000_000_000)  # Most tokens have 9 decimals

        try:
            # Get quote
            quote_resp = await self._httpx_client.get(
                f"{JUPITER_API}/quote",
                params={
                    "inputMint": input_mint,
                    "outputMint": output_mint,
                    "amount": amount_raw,
                    "slippageBps": 100,  # 1% slippage
                },
            )
            quote = quote_resp.json()

            if "error" in quote:
                return Order(
                    symbol=symbol, side=side, quantity=quantity,
                    status=OrderStatus.REJECTED, exchange="jupiter",
                    metadata={"error": quote["error"]},
                )

            # Get swap transaction
            swap_resp = await self._httpx_client.post(
                f"{JUPITER_API}/swap",
                json={
                    "quoteResponse": quote,
                    "userPublicKey": self._wallet_address,
                    "wrapAndUnwrapSol": True,
                },
            )
            swap_data = swap_resp.json()

            # Sign and send transaction
            if self._private_key and "swapTransaction" in swap_data:
                tx_sig = await self._sign_and_send(swap_data["swapTransaction"])
                return Order(
                    order_id=tx_sig or "pending",
                    symbol=symbol, side=side, order_type=order_type,
                    quantity=quantity, price=price,
                    status=OrderStatus.FILLED if tx_sig else OrderStatus.PENDING,
                    exchange="jupiter",
                    strategy=metadata.get("strategy", "") if metadata else "",
                    metadata={"tx": tx_sig, "quote": quote.get("outAmount")},
                )
            else:
                return Order(
                    symbol=symbol, side=side, quantity=quantity,
                    status=OrderStatus.REJECTED, exchange="jupiter",
                    metadata={"error": "No private key or missing swap transaction"},
                )

        except Exception as e:
            logger.error(f"Jupiter swap failed: {e}")
            return Order(
                symbol=symbol, side=side, quantity=quantity,
                status=OrderStatus.REJECTED, exchange="jupiter",
                metadata={"error": str(e)},
            )

    async def _sign_and_send(self, swap_transaction: str) -> Optional[str]:
        """Sign and submit a Jupiter swap transaction."""
        try:
            import base64
            from solders.keypair import Keypair
            from solders.transaction import VersionedTransaction

            kp = Keypair.from_base58_string(self._private_key)
            raw_tx = base64.b64decode(swap_transaction)
            tx = VersionedTransaction.from_bytes(raw_tx)
            tx.sign([kp])

            # Send via RPC
            resp = await self._httpx_client.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "sendTransaction",
                    "params": [
                        base64.b64encode(bytes(tx)).decode(),
                        {"skipPreflight": True, "maxRetries": 3},
                    ],
                },
            )
            result = resp.json()
            return result.get("result")
        except Exception as e:
            logger.error(f"Failed to sign/send Solana tx: {e}")
            return None

    async def cancel_order(self, order_id: str, symbol: str = "") -> bool:
        # DEX swaps are atomic — can't cancel after submission
        return False

    async def get_order(self, order_id: str, symbol: str = "") -> Order:
        # Check transaction status on Solana
        try:
            resp = await self._httpx_client.post(
                "https://api.mainnet-beta.solana.com",
                json={
                    "jsonrpc": "2.0", "id": 1,
                    "method": "getTransaction",
                    "params": [order_id, {"encoding": "jsonParsed"}],
                },
            )
            result = resp.json().get("result")
            if result:
                err = result.get("meta", {}).get("err")
                return Order(
                    order_id=order_id,
                    status=OrderStatus.REJECTED if err else OrderStatus.FILLED,
                    exchange="jupiter",
                )
        except Exception:
            pass
        raise ValueError(f"Transaction not found: {order_id}")

    async def get_open_orders(self, symbol: str = "") -> List[Order]:
        # DEX swaps don't have open orders
        return []

    async def get_positions(self) -> List[Position]:
        # Derive from balances
        return []

    # ── Jupiter-specific ──

    async def get_quote(
        self, input_token: str, output_token: str, amount: Decimal, slippage_bps: int = 100
    ) -> Dict[str, Any]:
        """Get a swap quote without executing."""
        input_mint = KNOWN_MINTS.get(input_token.upper(), input_token)
        output_mint = KNOWN_MINTS.get(output_token.upper(), output_token)
        amount_raw = int(float(amount) * 1_000_000)  # Assume 6 decimals

        resp = await self._httpx_client.get(
            f"{JUPITER_API}/quote",
            params={
                "inputMint": input_mint,
                "outputMint": output_mint,
                "amount": amount_raw,
                "slippageBps": slippage_bps,
            },
        )
        return resp.json()
