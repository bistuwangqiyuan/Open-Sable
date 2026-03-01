"""
Portfolio Manager — Aggregates positions and balances across all exchanges.

Tracks P&L per position, per strategy, and overall.  Persists state to
a local SQLite database so nothing is lost on restart.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensable.core.paths import opensable_home

from .base import (
    Balance,
    ExchangeConnector,
    Order,
    OrderSide,
    Position,
    PositionSide,
    TradeRecord,
)

logger = logging.getLogger(__name__)

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    trade_id    TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    quantity    TEXT NOT NULL,
    entry_price TEXT NOT NULL,
    exit_price  TEXT,
    pnl         TEXT DEFAULT '0',
    pnl_pct     TEXT DEFAULT '0',
    fees        TEXT DEFAULT '0',
    exchange    TEXT DEFAULT '',
    strategy    TEXT DEFAULT '',
    entry_time  TEXT NOT NULL,
    exit_time   TEXT,
    duration_seconds INTEGER DEFAULT 0,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    total_value TEXT NOT NULL,
    cash_value  TEXT NOT NULL,
    positions_value TEXT NOT NULL,
    unrealized_pnl TEXT NOT NULL,
    realized_pnl TEXT NOT NULL,
    data        TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL,
    order_type  TEXT NOT NULL,
    quantity    TEXT NOT NULL,
    price       TEXT,
    stop_price  TEXT,
    status      TEXT NOT NULL,
    filled_quantity TEXT DEFAULT '0',
    average_fill_price TEXT,
    fee         TEXT DEFAULT '0',
    fee_asset   TEXT DEFAULT '',
    exchange    TEXT DEFAULT '',
    strategy    TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    metadata    TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_strategy ON trades(strategy);
CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON trades(entry_time);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON portfolio_snapshots(timestamp);
"""


@dataclass
class PortfolioSnapshot:
    """Point-in-time snapshot of the entire portfolio."""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_value_usd: Decimal = Decimal("0")
    cash_value_usd: Decimal = Decimal("0")
    positions_value_usd: Decimal = Decimal("0")
    unrealized_pnl_usd: Decimal = Decimal("0")
    realized_pnl_usd: Decimal = Decimal("0")
    positions: List[Position] = field(default_factory=list)
    balances: List[Balance] = field(default_factory=list)

    # Analytics
    win_rate: float = 0.0
    total_trades: int = 0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    best_trade_pnl: Decimal = Decimal("0")
    worst_trade_pnl: Decimal = Decimal("0")


class PortfolioManager:
    """
    Aggregates balances and positions across multiple exchanges.

    Responsibilities:
    - Track all positions and their live P&L
    - Record every completed trade
    - Periodic snapshots for equity curve / analytics
    - Provide portfolio metrics (Sharpe, drawdown, win rate)
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or str(
            opensable_home() / "trading" / "portfolio.db"
        )
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connectors: Dict[str, ExchangeConnector] = {}
        self._positions: List[Position] = []
        self._open_orders: List[Order] = []
        self._trade_journal: List[TradeRecord] = []
        self._snapshots: List[PortfolioSnapshot] = []
        self._realized_pnl: Decimal = Decimal("0")

        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.executescript(DB_SCHEMA)
            conn.close()
            logger.info(f"Portfolio DB initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to init portfolio DB: {e}")

    # ── Connector management ──

    def add_connector(self, connector: ExchangeConnector) -> None:
        """Register an exchange connector."""
        self._connectors[connector.name] = connector
        logger.info(f"Added exchange connector: {connector.name}")

    def remove_connector(self, name: str) -> None:
        """Remove a connector."""
        self._connectors.pop(name, None)

    @property
    def connectors(self) -> Dict[str, ExchangeConnector]:
        return dict(self._connectors)

    # ── Live data ──

    async def refresh(self) -> PortfolioSnapshot:
        """Refresh all positions and balances from connected exchanges."""
        all_balances: List[Balance] = []
        all_positions: List[Position] = []

        for name, conn in self._connectors.items():
            if not conn.is_connected:
                continue
            try:
                balances = await conn.get_balances()
                for b in balances:
                    b.exchange = name
                all_balances.extend(balances)
            except Exception as e:
                logger.error(f"Failed to fetch balances from {name}: {e}")

            try:
                positions = await conn.get_positions()
                for p in positions:
                    p.exchange = name
                all_positions.extend(positions)
            except Exception as e:
                logger.error(f"Failed to fetch positions from {name}: {e}")

        self._positions = all_positions

        # Calculate portfolio value
        cash_value = sum(
            (b.total for b in all_balances if b.asset.upper() in ("USD", "USDT", "USDC", "BUSD", "DAI")),
            Decimal("0"),
        )
        positions_value = sum((p.notional_value for p in all_positions), Decimal("0"))
        unrealized = sum((p.unrealized_pnl for p in all_positions), Decimal("0"))

        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_value_usd=cash_value + positions_value,
            cash_value_usd=cash_value,
            positions_value_usd=positions_value,
            unrealized_pnl_usd=unrealized,
            realized_pnl_usd=self._realized_pnl,
            positions=all_positions,
            balances=all_balances,
        )

        # Compute analytics
        self._compute_analytics(snapshot)
        self._snapshots.append(snapshot)

        # Persist snapshot
        self._save_snapshot(snapshot)

        return snapshot

    def _compute_analytics(self, snapshot: PortfolioSnapshot) -> None:
        """Compute win rate, Sharpe, drawdown from trade journal."""
        trades = self._load_trades()
        if not trades:
            return

        winners = [t for t in trades if t.pnl > 0]
        snapshot.total_trades = len(trades)
        snapshot.win_rate = len(winners) / len(trades) if trades else 0.0

        pnls = [float(t.pnl) for t in trades]
        if pnls:
            snapshot.best_trade_pnl = Decimal(str(max(pnls)))
            snapshot.worst_trade_pnl = Decimal(str(min(pnls)))

        # Sharpe ratio (simplified: mean / std of trade returns)
        if len(pnls) > 1:
            import statistics
            mean_pnl = statistics.mean(pnls)
            std_pnl = statistics.stdev(pnls)
            snapshot.sharpe_ratio = (mean_pnl / std_pnl) if std_pnl > 0 else 0.0

        # Max drawdown from equity curve
        snapshots = self._load_snapshots_from_db(limit=500)
        if len(snapshots) >= 2:
            equities = [float(s["total_value"]) for s in snapshots]
            peak = equities[0]
            max_dd = 0.0
            for eq in equities:
                if eq > peak:
                    peak = eq
                dd = (peak - eq) / peak if peak > 0 else 0.0
                max_dd = max(max_dd, dd)
            snapshot.max_drawdown_pct = max_dd * 100

    # ── Positions ──

    @property
    def positions(self) -> List[Position]:
        return list(self._positions)

    async def get_position(self, symbol: str, exchange: str = "") -> Optional[Position]:
        """Find an open position by symbol."""
        for p in self._positions:
            if p.symbol == symbol and (not exchange or p.exchange == exchange):
                return p
        return None

    # ── Trade recording ──

    def record_trade(self, trade: TradeRecord) -> None:
        """Record a completed trade in the journal."""
        self._trade_journal.append(trade)
        self._realized_pnl += trade.pnl
        self._save_trade(trade)
        logger.info(
            f"Trade recorded: {trade.side.value} {trade.symbol} "
            f"PnL={trade.pnl} ({trade.pnl_pct}%)"
        )

    def record_order(self, order: Order) -> None:
        """Persist an order to the database."""
        self._save_order(order)

    # ── Persistence ──

    def _save_trade(self, t: TradeRecord) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT OR REPLACE INTO trades 
                   (trade_id, symbol, side, quantity, entry_price, exit_price,
                    pnl, pnl_pct, fees, exchange, strategy, entry_time,
                    exit_time, duration_seconds, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    t.trade_id, t.symbol, t.side.value, str(t.quantity),
                    str(t.entry_price), str(t.exit_price) if t.exit_price else None,
                    str(t.pnl), str(t.pnl_pct), str(t.fees), t.exchange,
                    t.strategy, t.entry_time.isoformat(),
                    t.exit_time.isoformat() if t.exit_time else None,
                    t.duration_seconds, json.dumps(t.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save trade: {e}")

    def _save_order(self, o: Order) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT OR REPLACE INTO orders
                   (order_id, symbol, side, order_type, quantity, price,
                    stop_price, status, filled_quantity, average_fill_price,
                    fee, fee_asset, exchange, strategy, created_at,
                    updated_at, metadata)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    o.order_id, o.symbol, o.side.value, o.order_type.value,
                    str(o.quantity), str(o.price) if o.price else None,
                    str(o.stop_price) if o.stop_price else None,
                    o.status.value, str(o.filled_quantity),
                    str(o.average_fill_price) if o.average_fill_price else None,
                    str(o.fee), o.fee_asset, o.exchange, o.strategy,
                    o.created_at.isoformat(), o.updated_at.isoformat(),
                    json.dumps(o.metadata),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save order: {e}")

    def _save_snapshot(self, s: PortfolioSnapshot) -> None:
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO portfolio_snapshots
                   (timestamp, total_value, cash_value, positions_value,
                    unrealized_pnl, realized_pnl, data)
                   VALUES (?,?,?,?,?,?,?)""",
                (
                    s.timestamp.isoformat(),
                    str(s.total_value_usd),
                    str(s.cash_value_usd),
                    str(s.positions_value_usd),
                    str(s.unrealized_pnl_usd),
                    str(s.realized_pnl_usd),
                    json.dumps({
                        "win_rate": s.win_rate,
                        "total_trades": s.total_trades,
                        "sharpe_ratio": s.sharpe_ratio,
                        "max_drawdown_pct": s.max_drawdown_pct,
                    }),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to save snapshot: {e}")

    def _load_trades(self, limit: int = 500) -> List[TradeRecord]:
        """Load recent trades from DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT * FROM trades ORDER BY entry_time DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            trades = []
            for r in rows:
                trades.append(TradeRecord(
                    trade_id=r[0], symbol=r[1],
                    side=OrderSide(r[2]), quantity=Decimal(r[3]),
                    entry_price=Decimal(r[4]),
                    exit_price=Decimal(r[5]) if r[5] else None,
                    pnl=Decimal(r[6]), pnl_pct=Decimal(r[7]),
                    fees=Decimal(r[8]), exchange=r[9], strategy=r[10],
                    entry_time=datetime.fromisoformat(r[11]),
                    exit_time=datetime.fromisoformat(r[12]) if r[12] else None,
                    duration_seconds=r[13],
                    metadata=json.loads(r[14]) if r[14] else {},
                ))
            return trades
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            return []

    def _load_snapshots_from_db(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Load recent snapshots from DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT timestamp, total_value, cash_value, positions_value, "
                "unrealized_pnl, realized_pnl FROM portfolio_snapshots "
                "ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            conn.close()
            return [
                {
                    "timestamp": r[0], "total_value": r[1], "cash_value": r[2],
                    "positions_value": r[3], "unrealized_pnl": r[4],
                    "realized_pnl": r[5],
                }
                for r in rows
            ]
        except Exception as e:
            logger.error(f"Failed to load snapshots: {e}")
            return []

    # ── Summary ──

    def get_trade_history(self, limit: int = 50) -> List[TradeRecord]:
        """Return recent trades."""
        return self._load_trades(limit)

    def get_summary(self) -> Dict[str, Any]:
        """Return a human-readable portfolio summary."""
        latest = self._snapshots[-1] if self._snapshots else None
        return {
            "total_value_usd": str(latest.total_value_usd) if latest else "0",
            "cash_usd": str(latest.cash_value_usd) if latest else "0",
            "positions_value_usd": str(latest.positions_value_usd) if latest else "0",
            "unrealized_pnl": str(latest.unrealized_pnl_usd) if latest else "0",
            "realized_pnl": str(latest.realized_pnl_usd) if latest else "0",
            "open_positions": len(self._positions),
            "connected_exchanges": list(self._connectors.keys()),
            "win_rate": f"{latest.win_rate:.1%}" if latest else "N/A",
            "total_trades": latest.total_trades if latest else 0,
            "sharpe_ratio": f"{latest.sharpe_ratio:.2f}" if latest else "N/A",
            "max_drawdown": f"{latest.max_drawdown_pct:.1f}%" if latest else "N/A",
        }
