"""
Backtesting Module

Provides backtesting capabilities for the EMA Cloud strategy.
Tests signals against historical data to evaluate performance.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass
class Trade:
    """Represents a single trade"""

    entry_time: datetime
    entry_price: float
    direction: str  # "long" or "short"
    signal_type: str
    signal_strength: str

    exit_time: datetime | None = None
    exit_price: float | None = None
    exit_reason: str | None = None

    stop_loss: float | None = None
    take_profit: float | None = None

    pnl: float = 0.0
    pnl_pct: float = 0.0
    is_winner: bool = False
    bars_held: int = 0

    def close(self, exit_time: datetime, exit_price: float, exit_reason: str):
        """Close the trade"""
        self.exit_time = exit_time
        self.exit_price = exit_price
        self.exit_reason = exit_reason

        if self.direction == "long":
            self.pnl = exit_price - self.entry_price
        else:
            self.pnl = self.entry_price - exit_price

        self.pnl_pct = (self.pnl / self.entry_price) * 100
        self.is_winner = self.pnl > 0


@dataclass
class BacktestResult:
    """Results from a backtest run"""

    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float

    trades: list[Trade] = field(default_factory=list)

    # Performance metrics
    total_return: float = 0.0
    total_return_pct: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0

    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0

    avg_bars_held: float = 0.0
    avg_winner_bars: float = 0.0
    avg_loser_bars: float = 0.0

    def calculate_metrics(self):
        """Calculate all performance metrics"""
        if not self.trades:
            return

        self.total_trades = len(self.trades)
        self.winning_trades = sum(1 for t in self.trades if t.is_winner)
        self.losing_trades = self.total_trades - self.winning_trades

        self.win_rate = (
            (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        )

        # P&L calculations
        winners = [t for t in self.trades if t.is_winner]
        losers = [t for t in self.trades if not t.is_winner]

        total_win = sum(t.pnl for t in winners) if winners else 0
        total_loss = abs(sum(t.pnl for t in losers)) if losers else 0

        self.avg_win = (total_win / len(winners)) if winners else 0
        self.avg_loss = (total_loss / len(losers)) if losers else 0

        self.profit_factor = (total_win / total_loss) if total_loss > 0 else float("inf")

        # Expectancy = (Win Rate × Avg Win) - (Loss Rate × Avg Loss)
        win_rate_decimal = self.win_rate / 100
        self.expectancy = (win_rate_decimal * self.avg_win) - (
            (1 - win_rate_decimal) * self.avg_loss
        )

        # Total return
        self.total_return = self.final_capital - self.initial_capital
        self.total_return_pct = (self.total_return / self.initial_capital) * 100

        # Average bars held
        self.avg_bars_held = np.mean([t.bars_held for t in self.trades])
        self.avg_winner_bars = np.mean([t.bars_held for t in winners]) if winners else 0
        self.avg_loser_bars = np.mean([t.bars_held for t in losers]) if losers else 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "initial_capital": self.initial_capital,
            "final_capital": self.final_capital,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "avg_win": self.avg_win,
            "avg_loss": self.avg_loss,
            "profit_factor": self.profit_factor,
            "expectancy": self.expectancy,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_pct": self.max_drawdown_pct,
            "sharpe_ratio": self.sharpe_ratio,
            "avg_bars_held": self.avg_bars_held,
        }

    def print_summary(self):
        """Print a formatted summary of results"""
        print(f"\n{'=' * 60}")
        print(f"BACKTEST RESULTS: {self.symbol}")
        print(f"{'=' * 60}")
        if self.start_date and self.end_date:
            print(
                f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}"
            )
        print(f"Initial Capital: ${self.initial_capital:,.2f}")
        print(f"Final Capital: ${self.final_capital:,.2f}")
        print(f"Total Return: ${self.total_return:,.2f} ({self.total_return_pct:+.2f}%)")
        print(f"\n{'-' * 60}")
        print("TRADE STATISTICS")
        print(f"{'-' * 60}")
        print(f"Total Trades: {self.total_trades}")
        print(f"Winning Trades: {self.winning_trades} ({self.win_rate:.1f}%)")
        print(f"Losing Trades: {self.losing_trades}")
        print(f"Average Win: ${self.avg_win:.2f}")
        print(f"Average Loss: ${self.avg_loss:.2f}")
        pf_str = f"{self.profit_factor:.2f}" if self.profit_factor != float("inf") else "∞"
        print(f"Profit Factor: {pf_str}")
        print(f"Expectancy: ${self.expectancy:.2f}")
        print(f"\n{'-' * 60}")
        print("RISK METRICS")
        print(f"{'-' * 60}")
        print(f"Max Drawdown: ${self.max_drawdown:,.2f} ({self.max_drawdown_pct:.2f}%)")
        print(f"Sharpe Ratio: {self.sharpe_ratio:.2f}")
        print(f"Avg Bars Held: {self.avg_bars_held:.1f}")
        print(f"{'=' * 60}\n")


class Backtester:
    """
    Backtesting engine for EMA Cloud strategy.
    """

    def __init__(
        self,
        initial_capital: float = 100000.0,
        position_size_pct: float = 10.0,
        commission: float = 0.0,
        slippage_pct: float = 0.05,
    ):
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.commission = commission
        self.slippage_pct = slippage_pct

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        signals_df: pd.DataFrame | None = None,
        exit_on_opposite_signal: bool = True,
        use_stop_loss: bool = True,
        use_take_profit: bool = True,
        max_bars_held: int = 50,
        min_signal_strength: int = 3,  # MODERATE
    ) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            df: OHLCV DataFrame with datetime index
            symbol: Symbol being tested
            signals_df: Optional pre-computed signals DataFrame with columns:
                        direction, signal_type, strength, stop_loss, take_profit
            exit_on_opposite_signal: Exit when opposite signal generated
            use_stop_loss: Use stop loss from signal
            use_take_profit: Use take profit from signal
            max_bars_held: Maximum bars to hold a position
            min_signal_strength: Minimum strength value (1-5) to enter

        Returns:
            BacktestResult with all metrics
        """
        if len(df) < 50:
            logger.warning(f"Insufficient data for backtest: {len(df)} bars")
            return BacktestResult(
                symbol=symbol,
                start_date=datetime.now(),
                end_date=datetime.now(),
                initial_capital=self.initial_capital,
                final_capital=self.initial_capital,
            )

        # Initialize tracking
        capital = self.initial_capital
        position: Trade | None = None
        trades: list[Trade] = []
        equity_curve = [capital]

        # If no signals provided, generate simple trend-based signals
        if signals_df is None:
            signals_df = self._generate_simple_signals(df)

        # Walk through data
        for i in range(50, len(df)):
            idx = df.index[i]
            row = df.iloc[i]
            current_price = row["close"]
            high = row["high"]
            low = row["low"]

            # Get signal for this bar if exists
            current_signal = None
            if idx in signals_df.index:
                current_signal = signals_df.loc[idx]

            # Check for exit conditions if in position
            if position is not None:
                position.bars_held += 1
                exit_reason = None
                exit_price = None

                # Check stop loss
                if use_stop_loss and position.stop_loss:
                    if (position.direction == "long" and low <= position.stop_loss) or (
                        position.direction == "short" and high >= position.stop_loss
                    ):
                        exit_reason = "stop_loss"
                        exit_price = position.stop_loss

                # Check take profit
                if use_take_profit and position.take_profit and exit_reason is None:
                    if (position.direction == "long" and high >= position.take_profit) or (
                        position.direction == "short" and low <= position.take_profit
                    ):
                        exit_reason = "take_profit"
                        exit_price = position.take_profit

                # Check max bars
                if position.bars_held >= max_bars_held and exit_reason is None:
                    exit_reason = "max_bars"
                    exit_price = current_price

                # Check for exit on opposite signal
                if exit_on_opposite_signal and exit_reason is None and current_signal is not None:
                    sig_direction = current_signal.get("direction", "")
                    if sig_direction and sig_direction != position.direction:
                        exit_reason = "opposite_signal"
                        exit_price = current_price

                # Execute exit
                if exit_reason:
                    # Apply slippage
                    if position.direction == "long":
                        exit_price = exit_price * (1 - self.slippage_pct / 100)
                    else:
                        exit_price = exit_price * (1 + self.slippage_pct / 100)

                    position.close(idx, exit_price, exit_reason)

                    # Update capital
                    position_value = capital * (self.position_size_pct / 100)
                    shares = position_value / position.entry_price
                    capital += position.pnl * shares - self.commission

                    trades.append(position)
                    position = None

            # Check for entry signals if not in position
            if position is None and current_signal is not None:
                sig_direction = current_signal.get("direction", "")
                sig_strength = current_signal.get("strength", 0)

                # Convert strength if it's a string
                if isinstance(sig_strength, str):
                    strength_map = {
                        "VERY_STRONG": 5,
                        "STRONG": 4,
                        "MODERATE": 3,
                        "WEAK": 2,
                        "VERY_WEAK": 1,
                    }
                    sig_strength = strength_map.get(sig_strength, 0)

                if sig_direction and sig_strength >= min_signal_strength:
                    # Apply slippage to entry
                    entry_price = current_price
                    if sig_direction == "long":
                        entry_price = entry_price * (1 + self.slippage_pct / 100)
                    else:
                        entry_price = entry_price * (1 - self.slippage_pct / 100)

                    position = Trade(
                        entry_time=idx,
                        entry_price=entry_price,
                        direction=sig_direction,
                        signal_type=str(current_signal.get("signal_type", "unknown")),
                        signal_strength=str(sig_strength),
                        stop_loss=current_signal.get("stop_loss"),
                        take_profit=current_signal.get("take_profit"),
                    )

                    capital -= self.commission

            # Track equity
            if position:
                position_value = capital * (self.position_size_pct / 100)
                shares = position_value / position.entry_price
                if position.direction == "long":
                    unrealized_pnl = (current_price - position.entry_price) * shares
                else:
                    unrealized_pnl = (position.entry_price - current_price) * shares
                equity_curve.append(capital + unrealized_pnl)
            else:
                equity_curve.append(capital)

        # Close any open position at end
        if position is not None:
            final_price = df.iloc[-1]["close"]
            position.close(df.index[-1], final_price, "end_of_data")
            position_value = capital * (self.position_size_pct / 100)
            shares = position_value / position.entry_price
            capital += position.pnl * shares
            trades.append(position)

        # Calculate max drawdown
        equity_series = pd.Series(equity_curve)
        rolling_max = equity_series.expanding().max()
        drawdowns = equity_series - rolling_max
        max_dd = drawdowns.min()
        max_dd_idx = drawdowns.idxmin()
        max_dd_pct = (
            (max_dd / rolling_max[max_dd_idx]) * 100
            if max_dd_idx and rolling_max[max_dd_idx] > 0
            else 0
        )

        # Calculate Sharpe Ratio (simplified - annualized)
        returns = equity_series.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(252)
        else:
            sharpe = 0

        # Get date range
        start_date = df.index[0] if hasattr(df.index[0], "strftime") else None
        end_date = df.index[-1] if hasattr(df.index[-1], "strftime") else None

        # Create result
        result = BacktestResult(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_capital=capital,
            trades=trades,
            max_drawdown=abs(max_dd),
            max_drawdown_pct=abs(max_dd_pct),
            sharpe_ratio=sharpe,
        )

        result.calculate_metrics()
        return result

    def _generate_simple_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate simple EMA crossover signals for backtesting.
        Uses 34/50 EMA cross as primary signal.
        """
        signals = []

        # Calculate EMAs
        df = df.copy()
        df["ema_34"] = df["close"].ewm(span=34, adjust=False).mean()
        df["ema_50"] = df["close"].ewm(span=50, adjust=False).mean()
        df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

        # Calculate ATR for stops
        df["tr"] = np.maximum(
            df["high"] - df["low"],
            np.maximum(
                abs(df["high"] - df["close"].shift(1)), abs(df["low"] - df["close"].shift(1))
            ),
        )
        df["atr"] = df["tr"].rolling(14).mean()

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            signal = None

            # Bullish cross
            if prev["ema_34"] <= prev["ema_50"] and row["ema_34"] > row["ema_50"]:
                if row["close"] > row["ema_200"]:  # Above long-term trend
                    signal = {
                        "direction": "long",
                        "signal_type": "ema_cross_bullish",
                        "strength": 4,  # STRONG
                        "stop_loss": row["close"] - (2 * row["atr"]),
                        "take_profit": row["close"] + (3 * row["atr"]),
                    }

            # Bearish cross
            elif prev["ema_34"] >= prev["ema_50"] and row["ema_34"] < row["ema_50"]:
                if row["close"] < row["ema_200"]:  # Below long-term trend
                    signal = {
                        "direction": "short",
                        "signal_type": "ema_cross_bearish",
                        "strength": 4,  # STRONG
                        "stop_loss": row["close"] + (2 * row["atr"]),
                        "take_profit": row["close"] - (3 * row["atr"]),
                    }

            if signal:
                signal["timestamp"] = df.index[i]
                signals.append(signal)

        if signals:
            signals_df = pd.DataFrame(signals)
            signals_df.set_index("timestamp", inplace=True)
            return signals_df

        return pd.DataFrame()

    def run_multiple(
        self, data_dict: dict[str, pd.DataFrame], **kwargs
    ) -> dict[str, BacktestResult]:
        """
        Run backtest on multiple symbols.
        """
        results = {}
        for symbol, df in data_dict.items():
            try:
                results[symbol] = self.run(df, symbol, **kwargs)
            except Exception as e:
                logger.error(f"Backtest failed for {symbol}: {e}")

        return results

    def compare_results(self, results: dict[str, BacktestResult]) -> pd.DataFrame:
        """
        Create comparison DataFrame of multiple backtest results.
        """
        rows = []
        for symbol, result in results.items():
            rows.append(
                {
                    "Symbol": symbol,
                    "Return %": result.total_return_pct,
                    "Trades": result.total_trades,
                    "Win Rate %": result.win_rate,
                    "Profit Factor": result.profit_factor
                    if result.profit_factor != float("inf")
                    else 999,
                    "Max DD %": result.max_drawdown_pct,
                    "Sharpe": result.sharpe_ratio,
                    "Expectancy": result.expectancy,
                }
            )

        df = pd.DataFrame(rows)
        df = df.sort_values("Return %", ascending=False)
        return df


def run_quick_backtest(
    df: pd.DataFrame, symbol: str, initial_capital: float = 100000.0, print_results: bool = True
) -> BacktestResult:
    """
    Convenience function to run a quick backtest.
    """
    backtester = Backtester(initial_capital=initial_capital)
    result = backtester.run(df, symbol)

    if print_results:
        result.print_summary()

    return result
