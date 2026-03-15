"""
Backtesting Module

Provides backtesting capabilities for the EMA Cloud strategy.
Tests signals against historical data to evaluate performance.
"""

import logging
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Trade(BaseModel):
    """Represents a single trade"""

    entry_time: datetime = Field(..., description="Trade entry timestamp")
    entry_price: float = Field(..., description="Entry price")
    direction: str = Field(..., description="Trade direction: long or short")
    signal_type: str = Field(..., description="Signal type that triggered trade")
    signal_strength: str = Field(..., description="Signal strength rating")

    exit_time: datetime | None = Field(default=None, description="Trade exit timestamp")
    exit_price: float | None = Field(default=None, description="Exit price")
    exit_reason: str | None = Field(default=None, description="Reason for exit")

    stop_loss: float | None = Field(default=None, description="Stop loss price")
    take_profit: float | None = Field(default=None, description="Take profit price")

    pnl: float = Field(default=0.0, description="Profit/loss amount")
    pnl_pct: float = Field(default=0.0, description="Profit/loss percentage")
    is_winner: bool = Field(default=False, description="Whether trade was profitable")
    bars_held: int = Field(default=0, description="Number of bars trade was held")

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


class BacktestResult(BaseModel):
    """Results from a backtest run"""

    symbol: str = Field(..., description="Symbol tested")
    start_date: datetime = Field(..., description="Backtest start date")
    end_date: datetime = Field(..., description="Backtest end date")
    initial_capital: float = Field(..., description="Starting capital")
    final_capital: float = Field(..., description="Ending capital")

    trades: list[Trade] = Field(default_factory=list, description="List of all trades")

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

    def format_summary(self) -> str:
        """Format a summary of results as a string."""
        lines = [
            f"\n{'=' * 60}",
            f"BACKTEST RESULTS: {self.symbol}",
            f"{'=' * 60}",
        ]
        if self.start_date and self.end_date:
            lines.append(
                f"Period: {self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')}"
            )
        lines.extend(
            [
                f"Initial Capital: ${self.initial_capital:,.2f}",
                f"Final Capital: ${self.final_capital:,.2f}",
                f"Total Return: ${self.total_return:,.2f} ({self.total_return_pct:+.2f}%)",
                f"\n{'-' * 60}",
                "TRADE STATISTICS",
                f"{'-' * 60}",
                f"Total Trades: {self.total_trades}",
                f"Winning Trades: {self.winning_trades} ({self.win_rate:.1f}%)",
                f"Losing Trades: {self.losing_trades}",
                f"Average Win: ${self.avg_win:.2f}",
                f"Average Loss: ${self.avg_loss:.2f}",
            ]
        )
        pf_str = f"{self.profit_factor:.2f}" if self.profit_factor != float("inf") else "∞"
        lines.extend(
            [
                f"Profit Factor: {pf_str}",
                f"Expectancy: ${self.expectancy:.2f}",
                f"\n{'-' * 60}",
                "RISK METRICS",
                f"{'-' * 60}",
                f"Max Drawdown: ${self.max_drawdown:,.2f} ({self.max_drawdown_pct:.2f}%)",
                f"Sharpe Ratio: {self.sharpe_ratio:.2f}",
                f"Avg Bars Held: {self.avg_bars_held:.1f}",
                f"{'=' * 60}\n",
            ]
        )
        return "\n".join(lines)

    def log_summary(self):
        """Log a formatted summary of results via the logging system."""
        logger.info(self.format_summary())


class Backtester:
    """
    Backtesting engine for EMA Cloud strategy.
    """

    # Annualization factors for Sharpe ratio by timeframe
    ANNUALIZATION_FACTORS = {
        "1m": 252 * 390,  # Trading minutes per year
        "5m": 252 * 78,
        "10m": 252 * 39,
        "15m": 252 * 26,
        "30m": 252 * 13,
        "1h": 252 * 6.5,
        "4h": 252 * 1.625,
        "1d": 252,
        "1wk": 52,
        "1mo": 12,
    }

    def __init__(
        self,
        initial_capital: float = 100000.0,
        position_size_pct: float = 10.0,
        commission: float = 0.0,
        slippage_pct: float = 0.05,
        timeframe: str = "1d",
    ):
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.timeframe = timeframe

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
        # Calculate warmup period from indicator requirements
        # Longest EMA used is 200; ADX/ATR use 14-bar rolling windows
        warmup_bars = 233  # Longest EMA pair (200-233 cloud) needs 233 bars
        if signals_df is not None:
            # When pre-computed signals are provided, we only need enough
            # bars for the signal generation to have stabilized
            warmup_bars = min(warmup_bars, 50)

        if len(df) < warmup_bars + 1:
            logger.warning(
                f"Insufficient data for backtest: {len(df)} bars "
                f"(need {warmup_bars + 1} for indicator warmup)"
            )
            return BacktestResult(
                symbol=symbol,
                start_date=datetime.now(UTC),
                end_date=datetime.now(UTC),
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

        # Walk through data (skip warmup period for indicator stabilization)
        for i in range(warmup_bars, len(df)):
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
                if exit_reason and exit_price is not None:
                    # Apply slippage
                    if position.direction == "long":
                        exit_price = exit_price * (1 - self.slippage_pct / 100)
                    else:
                        exit_price = exit_price * (1 + self.slippage_pct / 100)

                    position.close(idx, exit_price, exit_reason)

                    # Update capital (commission already deducted at entry)
                    position_value = capital * (self.position_size_pct / 100)
                    shares = position_value / position.entry_price
                    capital += position.pnl * shares

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
            # Apply slippage to end-of-data exit consistently
            if position.direction == "long":
                final_price = final_price * (1 - self.slippage_pct / 100)
            else:
                final_price = final_price * (1 + self.slippage_pct / 100)
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

        # Calculate Sharpe Ratio (annualized by timeframe)
        returns = equity_series.pct_change().dropna()
        annualization_factor = self.ANNUALIZATION_FACTORS.get(self.timeframe, 252)
        if len(returns) > 1 and returns.std() > 0:
            sharpe = (returns.mean() / returns.std()) * np.sqrt(annualization_factor)
        else:
            sharpe = 0

        # Get date range
        start_date = df.index[0] if hasattr(df.index[0], "strftime") else datetime.now(UTC)
        end_date = df.index[-1] if hasattr(df.index[-1], "strftime") else datetime.now(UTC)

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
            except (ValueError, KeyError, IndexError) as e:
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


class WalkForwardWindow(BaseModel):
    """Result from a single walk-forward window."""

    window_index: int = Field(..., description="Window number (0-based)")
    in_sample_start: datetime = Field(..., description="In-sample period start")
    in_sample_end: datetime = Field(..., description="In-sample period end")
    out_of_sample_start: datetime = Field(..., description="Out-of-sample period start")
    out_of_sample_end: datetime = Field(..., description="Out-of-sample period end")
    in_sample_bars: int = Field(default=0, description="Number of in-sample bars")
    out_of_sample_bars: int = Field(default=0, description="Number of out-of-sample bars")
    in_sample_result: BacktestResult | None = Field(
        default=None, description="In-sample backtest result"
    )
    out_of_sample_result: BacktestResult | None = Field(
        default=None, description="Out-of-sample backtest result"
    )


class WalkForwardResult(BaseModel):
    """Aggregated walk-forward backtest results."""

    symbol: str = Field(..., description="Symbol tested")
    windows: list[WalkForwardWindow] = Field(
        default_factory=list, description="Individual window results"
    )
    total_windows: int = Field(default=0, description="Number of walk-forward windows")
    in_sample_size: int = Field(..., description="In-sample window size (bars)")
    out_of_sample_size: int = Field(..., description="Out-of-sample window size (bars)")
    step_size: int = Field(..., description="Step size between windows (bars)")

    # Aggregated out-of-sample metrics
    oos_total_trades: int = Field(default=0, description="Total out-of-sample trades")
    oos_win_rate: float = Field(default=0.0, description="Average OOS win rate %")
    oos_total_return_pct: float = Field(default=0.0, description="Cumulative OOS return %")
    oos_avg_return_pct: float = Field(default=0.0, description="Average per-window OOS return %")
    oos_max_drawdown_pct: float = Field(default=0.0, description="Worst OOS max drawdown %")
    oos_avg_sharpe: float = Field(default=0.0, description="Average OOS Sharpe ratio")
    robustness_ratio: float = Field(
        default=0.0,
        description="OOS / IS return ratio — values near 1.0 suggest the strategy is robust",
    )

    def calculate_aggregate_metrics(self) -> None:
        """Calculate aggregate metrics from individual windows."""
        oos_results = [
            w.out_of_sample_result for w in self.windows if w.out_of_sample_result is not None
        ]
        is_results = [w.in_sample_result for w in self.windows if w.in_sample_result is not None]

        if not oos_results:
            return

        self.total_windows = len(self.windows)
        self.oos_total_trades = sum(r.total_trades for r in oos_results)

        win_rates = [r.win_rate for r in oos_results if r.total_trades > 0]
        self.oos_win_rate = float(np.mean(win_rates)) if win_rates else 0.0

        returns = [r.total_return_pct for r in oos_results]
        self.oos_avg_return_pct = float(np.mean(returns)) if returns else 0.0

        # Compound OOS returns
        cumulative = 1.0
        for r in returns:
            cumulative *= 1 + r / 100
        self.oos_total_return_pct = (cumulative - 1) * 100

        drawdowns = [r.max_drawdown_pct for r in oos_results]
        self.oos_max_drawdown_pct = max(drawdowns) if drawdowns else 0.0

        sharpes = [r.sharpe_ratio for r in oos_results if r.total_trades > 0]
        self.oos_avg_sharpe = float(np.mean(sharpes)) if sharpes else 0.0

        # Robustness ratio: avg OOS return / avg IS return
        if is_results:
            is_returns = [r.total_return_pct for r in is_results]
            avg_is = float(np.mean(is_returns)) if is_returns else 0.0
            if avg_is != 0:
                self.robustness_ratio = self.oos_avg_return_pct / avg_is
            else:
                self.robustness_ratio = 0.0

    def format_summary(self) -> str:
        """Format a summary of walk-forward results."""
        lines = [
            f"\n{'=' * 60}",
            f"WALK-FORWARD RESULTS: {self.symbol}",
            f"{'=' * 60}",
            f"Windows: {self.total_windows} "
            f"(IS={self.in_sample_size} bars, OOS={self.out_of_sample_size} bars, "
            f"step={self.step_size} bars)",
            f"\n{'-' * 60}",
            "OUT-OF-SAMPLE PERFORMANCE",
            f"{'-' * 60}",
            f"Total OOS Trades: {self.oos_total_trades}",
            f"Average Win Rate: {self.oos_win_rate:.1f}%",
            f"Cumulative Return: {self.oos_total_return_pct:+.2f}%",
            f"Average Return/Window: {self.oos_avg_return_pct:+.2f}%",
            f"Worst Max Drawdown: {self.oos_max_drawdown_pct:.2f}%",
            f"Average Sharpe: {self.oos_avg_sharpe:.2f}",
            f"Robustness Ratio: {self.robustness_ratio:.2f} (IS→OOS consistency)",
            f"{'=' * 60}\n",
        ]
        return "\n".join(lines)


class WalkForwardBacktester:
    """Walk-forward backtesting engine.

    Divides data into rolling in-sample (training) and out-of-sample (testing)
    windows to evaluate strategy robustness without look-ahead bias.
    """

    def __init__(
        self,
        in_sample_size: int = 500,
        out_of_sample_size: int = 100,
        step_size: int | None = None,
        initial_capital: float = 100000.0,
        position_size_pct: float = 10.0,
        commission: float = 0.0,
        slippage_pct: float = 0.05,
        timeframe: str = "1d",
    ):
        """
        Args:
            in_sample_size: Bars in each in-sample window
            out_of_sample_size: Bars in each out-of-sample window
            step_size: Bars to advance between windows (defaults to out_of_sample_size)
            initial_capital: Starting capital for each OOS window
            position_size_pct: Position size as % of capital
            commission: Commission per trade
            slippage_pct: Slippage as % of price
            timeframe: Timeframe for Sharpe annualization
        """
        self.in_sample_size = in_sample_size
        self.out_of_sample_size = out_of_sample_size
        self.step_size = step_size or out_of_sample_size
        self.initial_capital = initial_capital
        self.position_size_pct = position_size_pct
        self.commission = commission
        self.slippage_pct = slippage_pct
        self.timeframe = timeframe

    def run(
        self,
        df: pd.DataFrame,
        symbol: str,
        signals_df: pd.DataFrame | None = None,
        **backtest_kwargs,
    ) -> WalkForwardResult:
        """Run walk-forward backtest.

        Args:
            df: Full OHLCV DataFrame
            symbol: Symbol being tested
            signals_df: Optional pre-computed signals (will be sliced per window)
            **backtest_kwargs: Additional kwargs passed to Backtester.run()

        Returns:
            WalkForwardResult with per-window and aggregate metrics
        """
        total_bars = len(df)
        window_size = self.in_sample_size + self.out_of_sample_size

        if total_bars < window_size:
            logger.warning(
                f"Insufficient data for walk-forward: {total_bars} bars "
                f"(need {window_size} for first window)"
            )
            return WalkForwardResult(
                symbol=symbol,
                in_sample_size=self.in_sample_size,
                out_of_sample_size=self.out_of_sample_size,
                step_size=self.step_size,
            )

        windows: list[WalkForwardWindow] = []
        start = 0
        window_idx = 0

        while start + window_size <= total_bars:
            is_start = start
            is_end = start + self.in_sample_size
            oos_start = is_end
            oos_end = min(is_end + self.out_of_sample_size, total_bars)

            is_df = df.iloc[is_start:is_end]
            oos_df = df.iloc[oos_start:oos_end]

            # Slice signals if provided
            is_signals = None
            oos_signals = None
            if signals_df is not None and not signals_df.empty:
                is_signals = signals_df[
                    (signals_df.index >= is_df.index[0]) & (signals_df.index <= is_df.index[-1])
                ]
                oos_signals = signals_df[
                    (signals_df.index >= oos_df.index[0]) & (signals_df.index <= oos_df.index[-1])
                ]

            backtester = Backtester(
                initial_capital=self.initial_capital,
                position_size_pct=self.position_size_pct,
                commission=self.commission,
                slippage_pct=self.slippage_pct,
                timeframe=self.timeframe,
            )

            # In-sample run
            is_result = backtester.run(is_df, symbol, signals_df=is_signals, **backtest_kwargs)

            # Out-of-sample run
            oos_result = backtester.run(oos_df, symbol, signals_df=oos_signals, **backtest_kwargs)

            window = WalkForwardWindow(
                window_index=window_idx,
                in_sample_start=is_df.index[0]
                if hasattr(is_df.index[0], "isoformat")
                else datetime.now(UTC),
                in_sample_end=is_df.index[-1]
                if hasattr(is_df.index[-1], "isoformat")
                else datetime.now(UTC),
                out_of_sample_start=oos_df.index[0]
                if hasattr(oos_df.index[0], "isoformat")
                else datetime.now(UTC),
                out_of_sample_end=oos_df.index[-1]
                if hasattr(oos_df.index[-1], "isoformat")
                else datetime.now(UTC),
                in_sample_bars=len(is_df),
                out_of_sample_bars=len(oos_df),
                in_sample_result=is_result,
                out_of_sample_result=oos_result,
            )
            windows.append(window)

            start += self.step_size
            window_idx += 1

        result = WalkForwardResult(
            symbol=symbol,
            windows=windows,
            in_sample_size=self.in_sample_size,
            out_of_sample_size=self.out_of_sample_size,
            step_size=self.step_size,
        )
        result.calculate_aggregate_metrics()
        return result


def run_quick_backtest(
    df: pd.DataFrame,
    symbol: str,
    initial_capital: float = 100000.0,
    log_results: bool = True,
    timeframe: str = "1d",
) -> BacktestResult:
    """
    Convenience function to run a quick backtest.
    """
    backtester = Backtester(initial_capital=initial_capital, timeframe=timeframe)
    result = backtester.run(df, symbol)

    if log_results:
        result.log_summary()

    return result
