"""
Backtesting Engine for Open-Sable Trading.

Replays historical price data through strategies and simulates trades
to evaluate performance before risking real capital.

Usage:
    from opensable.skills.trading.backtest import BacktestEngine

    engine = BacktestEngine(strategies=[MomentumStrategy()])
    result = await engine.run(symbol="BTC/USDT", days=30)
    print(result.summary())
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from .base import OHLCV, OrderSide, PriceTick
from .signals import SignalAggregator
from .strategy_engine import Signal, SignalDirection, Strategy

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """A simulated trade in the backtest."""
    symbol: str
    side: str          # "buy" or "sell"
    amount: Decimal
    entry_price: Decimal
    exit_price: Optional[Decimal] = None
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    pnl: Decimal = Decimal("0")
    pnl_pct: Decimal = Decimal("0")
    reason_entry: str = ""
    reason_exit: str = ""


@dataclass
class BacktestResult:
    """Results from a backtest run."""
    symbol: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    initial_capital: Decimal = Decimal("10000")
    final_capital: Decimal = Decimal("10000")
    total_return_pct: Decimal = Decimal("0")
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    profit_factor: float = 0.0
    avg_trade_pnl: Decimal = Decimal("0")
    best_trade_pnl: Decimal = Decimal("0")
    worst_trade_pnl: Decimal = Decimal("0")
    trades: List[BacktestTrade] = field(default_factory=list)
    equity_curve: List[float] = field(default_factory=list)
    strategies_used: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """Human-readable summary."""
        lines = [
            f"📊 **Backtest Results: {self.symbol}**",
            f"Period: {self.start_date} → {self.end_date}" if self.start_date else "",
            f"Initial Capital: ${self.initial_capital:,.2f}",
            f"Final Capital: ${self.final_capital:,.2f}",
            f"Return: {self.total_return_pct:+.2f}%",
            "",
            f"Total Trades: {self.total_trades}",
            f"Win Rate: {self.win_rate:.1%}",
            f"Profit Factor: {self.profit_factor:.2f}",
            f"Sharpe Ratio: {self.sharpe_ratio:.2f}",
            f"Max Drawdown: {self.max_drawdown_pct:.1%}",
            "",
            f"Avg Trade P&L: ${self.avg_trade_pnl:,.2f}",
            f"Best Trade: ${self.best_trade_pnl:,.2f}",
            f"Worst Trade: ${self.worst_trade_pnl:,.2f}",
            "",
            f"Strategies: {', '.join(self.strategies_used)}",
        ]
        return "\n".join(l for l in lines if l is not None)


class BacktestEngine:
    """
    Walk-forward backtesting engine.

    Iterates over OHLCV candles, feeds them to strategies, and simulates
    order execution at close prices.
    """

    def __init__(
        self,
        strategies: Optional[List[Strategy]] = None,
        initial_capital: float = 10000.0,
        trade_size_pct: float = 5.0,  # % of capital per trade
        commission_pct: float = 0.1,
        slippage_pct: float = 0.05,
        max_open_positions: int = 3,
    ):
        self.strategies = strategies or []
        self.initial_capital = Decimal(str(initial_capital))
        self.trade_size_pct = trade_size_pct
        self.commission_pct = Decimal(str(commission_pct))
        self.slippage_pct = Decimal(str(slippage_pct))
        self.max_open_positions = max_open_positions
        self.signal_aggregator = SignalAggregator()

    async def run(
        self,
        candles: List[OHLCV],
        symbol: str = "BTC/USDT",
        warmup_periods: int = 30,
    ) -> BacktestResult:
        """
        Run backtest on historical candles.

        Args:
            candles: List of OHLCV data (oldest first)
            symbol: Trading pair name
            warmup_periods: Number of candles to use as warmup (no trading)

        Returns:
            BacktestResult with full analytics
        """
        if len(candles) < warmup_periods + 10:
            return BacktestResult(
                symbol=symbol,
                strategies_used=[s.name for s in self.strategies],
            )

        capital = self.initial_capital
        peak_capital = capital
        open_positions: List[Dict[str, Any]] = []
        closed_trades: List[BacktestTrade] = []
        equity_curve: List[float] = [float(capital)]
        max_dd = Decimal("0")

        for i in range(warmup_periods, len(candles)):
            current = candles[i]
            history = candles[:i + 1]

            price_tick = PriceTick(
                symbol=symbol,
                price=current.close,
                bid=current.close * Decimal("0.9999"),
                ask=current.close * Decimal("1.0001"),
                timestamp=current.timestamp,
                exchange="backtest",
            )

            # Check exits on open positions
            positions_to_close = []
            for pos_idx, pos in enumerate(open_positions):
                holding_secs = int((current.timestamp - pos["entry_time"]).total_seconds())
                entry_price = pos["entry_price"]
                if pos["side"] == "long":
                    pnl_pct = ((current.close - entry_price) / entry_price) * 100
                else:
                    pnl_pct = ((entry_price - current.close) / entry_price) * 100

                # Check all strategies for exit signal
                should_exit = False
                for strat in self.strategies:
                    try:
                        if await strat.should_exit(
                            symbol, entry_price, current.close, pnl_pct, holding_secs
                        ):
                            should_exit = True
                            break
                    except Exception:
                        pass

                if should_exit:
                    positions_to_close.append(pos_idx)

            # Close positions (reverse order to preserve indices)
            for pos_idx in reversed(positions_to_close):
                pos = open_positions.pop(pos_idx)
                exit_price = current.close

                # Apply slippage
                if pos["side"] == "long":
                    exit_price = exit_price * (1 - self.slippage_pct / 100)
                    raw_pnl = (exit_price - pos["entry_price"]) * pos["amount"]
                else:
                    exit_price = exit_price * (1 + self.slippage_pct / 100)
                    raw_pnl = (pos["entry_price"] - exit_price) * pos["amount"]

                commission = abs(raw_pnl) * self.commission_pct / 100
                net_pnl = raw_pnl - commission
                pnl_pct = (net_pnl / (pos["entry_price"] * pos["amount"])) * 100

                capital += net_pnl

                trade = BacktestTrade(
                    symbol=symbol,
                    side=pos["side"],
                    amount=pos["amount"],
                    entry_price=pos["entry_price"],
                    exit_price=exit_price,
                    entry_time=pos["entry_time"],
                    exit_time=current.timestamp,
                    pnl=net_pnl,
                    pnl_pct=pnl_pct,
                    reason_entry=pos.get("reason", ""),
                    reason_exit="strategy_exit",
                )
                closed_trades.append(trade)

            # Generate new signals if we have capacity
            if len(open_positions) < self.max_open_positions:
                all_signals: List[Signal] = []
                for strat in self.strategies:
                    try:
                        sigs = await strat.analyze(symbol, history, price_tick)
                        all_signals.extend(sigs)
                    except Exception as e:
                        logger.debug(f"Backtest strategy error: {e}")

                if all_signals:
                    consensus = self.signal_aggregator.aggregate(all_signals)
                    if consensus and consensus.confidence >= 0.6:
                        # Calculate position size
                        trade_value = capital * Decimal(str(self.trade_size_pct)) / 100
                        if trade_value > 0 and current.close > 0:
                            amount = trade_value / current.close

                            # Apply entry slippage
                            entry_price = current.close
                            if consensus.direction == SignalDirection.LONG:
                                entry_price = entry_price * (1 + self.slippage_pct / 100)
                            else:
                                entry_price = entry_price * (1 - self.slippage_pct / 100)

                            pos = {
                                "side": "long" if consensus.direction == SignalDirection.LONG else "short",
                                "amount": amount,
                                "entry_price": entry_price,
                                "entry_time": current.timestamp,
                                "reason": consensus.reason[:200],
                            }
                            open_positions.append(pos)

            # Track equity
            unrealized = Decimal("0")
            for pos in open_positions:
                if pos["side"] == "long":
                    unrealized += (current.close - pos["entry_price"]) * pos["amount"]
                else:
                    unrealized += (pos["entry_price"] - current.close) * pos["amount"]

            equity = capital + unrealized
            equity_curve.append(float(equity))

            # Track drawdown
            if equity > peak_capital:
                peak_capital = equity
            dd = (peak_capital - equity) / peak_capital if peak_capital > 0 else Decimal("0")
            if dd > max_dd:
                max_dd = dd

        # Close any remaining positions at last price
        last_price = candles[-1].close
        for pos in open_positions:
            if pos["side"] == "long":
                raw_pnl = (last_price - pos["entry_price"]) * pos["amount"]
            else:
                raw_pnl = (pos["entry_price"] - last_price) * pos["amount"]
            commission = abs(raw_pnl) * self.commission_pct / 100
            net_pnl = raw_pnl - commission

            capital += net_pnl
            closed_trades.append(BacktestTrade(
                symbol=symbol,
                side=pos["side"],
                amount=pos["amount"],
                entry_price=pos["entry_price"],
                exit_price=last_price,
                entry_time=pos["entry_time"],
                exit_time=candles[-1].timestamp,
                pnl=net_pnl,
                pnl_pct=(net_pnl / (pos["entry_price"] * pos["amount"])) * 100 if pos["entry_price"] * pos["amount"] > 0 else Decimal("0"),
                reason_entry=pos.get("reason", ""),
                reason_exit="backtest_end",
            ))

        # Compute statistics
        total_trades = len(closed_trades)
        winning = [t for t in closed_trades if t.pnl > 0]
        losing = [t for t in closed_trades if t.pnl <= 0]
        total_return = ((capital - self.initial_capital) / self.initial_capital) * 100

        gross_profit = sum(t.pnl for t in winning) if winning else Decimal("0")
        gross_loss = abs(sum(t.pnl for t in losing)) if losing else Decimal("1")
        profit_factor = float(gross_profit / gross_loss) if gross_loss > 0 else 0.0

        # Sharpe ratio (simplified)
        if len(equity_curve) > 1:
            returns = [
                (equity_curve[i] - equity_curve[i - 1]) / equity_curve[i - 1]
                for i in range(1, len(equity_curve))
                if equity_curve[i - 1] > 0
            ]
            if returns:
                import statistics
                mean_ret = statistics.mean(returns)
                std_ret = statistics.stdev(returns) if len(returns) > 1 else 1
                sharpe = (mean_ret / std_ret) * (252 ** 0.5) if std_ret > 0 else 0
            else:
                sharpe = 0
        else:
            sharpe = 0

        return BacktestResult(
            symbol=symbol,
            start_date=candles[0].timestamp if candles else None,
            end_date=candles[-1].timestamp if candles else None,
            initial_capital=self.initial_capital,
            final_capital=capital,
            total_return_pct=total_return,
            total_trades=total_trades,
            winning_trades=len(winning),
            losing_trades=len(losing),
            win_rate=len(winning) / total_trades if total_trades > 0 else 0,
            max_drawdown_pct=float(max_dd),
            sharpe_ratio=float(sharpe),
            profit_factor=profit_factor,
            avg_trade_pnl=sum(t.pnl for t in closed_trades) / total_trades if total_trades > 0 else Decimal("0"),
            best_trade_pnl=max((t.pnl for t in closed_trades), default=Decimal("0")),
            worst_trade_pnl=min((t.pnl for t in closed_trades), default=Decimal("0")),
            trades=closed_trades,
            equity_curve=equity_curve,
            strategies_used=[s.name for s in self.strategies],
        )
