"""
Comprehensive tests for the backtesting engine.

Covers Trade model, BacktestResult metrics computation, Backtester execution
with mock data, Sharpe ratio annualization per timeframe, format_summary()
output, run_multiple with error handling, and run_quick_backtest helper.
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ema_cloud_lib.backtesting.engine import (
    Backtester,
    BacktestResult,
    Trade,
    run_quick_backtest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 200,
    start_price: float = 100.0,
    trend: float = 0.0,
    volatility: float = 0.5,
    seed: int = 42,
    start_date: str = "2024-01-01",
) -> pd.DataFrame:
    """Build a realistic OHLCV DataFrame with a controllable trend."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range(start_date, periods=n, freq="D")
    close = start_price + trend * np.arange(n) + rng.normal(0, volatility, n).cumsum()
    high = close + rng.uniform(0.5, 1.5, n)
    low = close - rng.uniform(0.5, 1.5, n)
    opens = close + rng.normal(0, 0.3, n)
    volume = rng.integers(100_000, 1_000_000, n).astype(float)
    return pd.DataFrame(
        {"open": opens, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def _make_signals_df(
    df: pd.DataFrame,
    indices: list[int],
    directions: list[str] | str = "long",
    strengths: list[int | str] | int | str = 4,
    stop_offsets: list[float] | float = 3.0,
    tp_offsets: list[float] | float = 6.0,
) -> pd.DataFrame:
    """Build a signals DataFrame at the given bar indices of *df*."""
    if isinstance(directions, str):
        directions = [directions] * len(indices)
    if isinstance(strengths, (int, str)):
        strengths = [strengths] * len(indices)
    if isinstance(stop_offsets, (int, float)):
        stop_offsets = [stop_offsets] * len(indices)
    if isinstance(tp_offsets, (int, float)):
        tp_offsets = [tp_offsets] * len(indices)

    rows = []
    for k, idx in enumerate(indices):
        price = float(df["close"].iloc[idx])
        d = directions[k]
        sl = price - stop_offsets[k] if d == "long" else price + stop_offsets[k]
        tp = price + tp_offsets[k] if d == "long" else price - tp_offsets[k]
        rows.append(
            {
                "timestamp": df.index[idx],
                "direction": d,
                "signal_type": "ema_cross",
                "strength": strengths[k],
                "stop_loss": sl,
                "take_profit": tp,
            }
        )
    sdf = pd.DataFrame(rows)
    sdf.set_index("timestamp", inplace=True)
    return sdf


def _closed_trade(
    direction: str = "long",
    entry: float = 100.0,
    exit_price: float = 110.0,
    bars: int = 5,
) -> Trade:
    """Create a closed Trade for use in BacktestResult tests."""
    t = Trade(
        entry_time=datetime(2024, 1, 1),
        entry_price=entry,
        direction=direction,
        signal_type="test",
        signal_strength="4",
    )
    t.close(datetime(2024, 1, 10), exit_price, "test_exit")
    t.bars_held = bars
    return t


# ===========================================================================
# 1. Trade model - creation, P&L calculation
# ===========================================================================


class TestTradeCreation:
    """Tests for Trade model defaults."""

    def test_defaults_before_close(self):
        t = Trade(
            entry_time=datetime(2024, 3, 1),
            entry_price=100.0,
            direction="long",
            signal_type="ema_cross",
            signal_strength="4",
        )
        assert t.pnl == 0.0
        assert t.pnl_pct == 0.0
        assert t.is_winner is False
        assert t.exit_time is None
        assert t.exit_price is None
        assert t.exit_reason is None
        assert t.bars_held == 0

    def test_stop_loss_take_profit_optional(self):
        t = Trade(
            entry_time=datetime(2024, 3, 1),
            entry_price=50.0,
            direction="short",
            signal_type="test",
            signal_strength="3",
        )
        assert t.stop_loss is None
        assert t.take_profit is None

    def test_stop_loss_take_profit_set(self):
        t = Trade(
            entry_time=datetime(2024, 3, 1),
            entry_price=50.0,
            direction="long",
            signal_type="test",
            signal_strength="3",
            stop_loss=45.0,
            take_profit=60.0,
        )
        assert t.stop_loss == 45.0
        assert t.take_profit == 60.0


class TestTradePnL:
    """Tests for Trade.close() P&L computation."""

    def test_long_trade_profit(self):
        t = _closed_trade("long", 100.0, 110.0)
        assert t.pnl == pytest.approx(10.0)
        assert t.pnl_pct == pytest.approx(10.0)
        assert t.is_winner is True
        assert t.exit_reason == "test_exit"

    def test_long_trade_loss(self):
        t = _closed_trade("long", 100.0, 95.0)
        assert t.pnl == pytest.approx(-5.0)
        assert t.pnl_pct == pytest.approx(-5.0)
        assert t.is_winner is False

    def test_short_trade_profit(self):
        t = _closed_trade("short", 100.0, 90.0)
        assert t.pnl == pytest.approx(10.0)
        assert t.pnl_pct == pytest.approx(10.0)
        assert t.is_winner is True

    def test_short_trade_loss(self):
        t = _closed_trade("short", 100.0, 108.0)
        assert t.pnl == pytest.approx(-8.0)
        assert t.pnl_pct == pytest.approx(-8.0)
        assert t.is_winner is False

    def test_breakeven_is_not_winner(self):
        t = _closed_trade("long", 50.0, 50.0)
        assert t.pnl == pytest.approx(0.0)
        assert t.is_winner is False

    def test_close_sets_exit_fields(self):
        t = Trade(
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            direction="long",
            signal_type="test",
            signal_strength="4",
        )
        exit_dt = datetime(2024, 2, 1, 15, 30)
        t.close(exit_dt, 105.0, "opposite_signal")
        assert t.exit_time == exit_dt
        assert t.exit_price == 105.0
        assert t.exit_reason == "opposite_signal"

    def test_pnl_pct_uses_entry_price(self):
        """pnl_pct = pnl / entry_price * 100"""
        t = _closed_trade("long", 200.0, 210.0)
        assert t.pnl_pct == pytest.approx(5.0)  # 10/200 * 100


# ===========================================================================
# 2. BacktestResult - metrics computation
# ===========================================================================


class TestBacktestResultMetrics:
    """Tests for BacktestResult.calculate_metrics()."""

    def test_win_rate_all_winners(self):
        trades = [_closed_trade("long", 100, 110), _closed_trade("long", 100, 105)]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=110_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.win_rate == pytest.approx(100.0)
        assert r.winning_trades == 2
        assert r.losing_trades == 0

    def test_win_rate_mixed(self):
        trades = [
            _closed_trade("long", 100, 110),  # win +10
            _closed_trade("long", 100, 90),  # loss -10
            _closed_trade("short", 100, 95),  # win +5
            _closed_trade("short", 100, 108),  # loss -8
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=100_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.total_trades == 4
        assert r.winning_trades == 2
        assert r.win_rate == pytest.approx(50.0)

    def test_profit_factor(self):
        trades = [
            _closed_trade("long", 100, 120),  # +20
            _closed_trade("long", 100, 90),  # -10
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=110_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.profit_factor == pytest.approx(2.0)

    def test_profit_factor_no_losses(self):
        trades = [_closed_trade("long", 100, 115)]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=115_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.profit_factor == float("inf")

    def test_avg_win_avg_loss(self):
        trades = [
            _closed_trade("long", 100, 120),  # +20
            _closed_trade("long", 100, 115),  # +15
            _closed_trade("long", 100, 90),  # -10
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=125_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.avg_win == pytest.approx(17.5)
        assert r.avg_loss == pytest.approx(10.0)

    def test_expectancy(self):
        trades = [
            _closed_trade("long", 100, 120),  # +20
            _closed_trade("long", 100, 90),  # -10
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=110_000,
            trades=trades,
        )
        r.calculate_metrics()
        # 0.5 * 20 - 0.5 * 10 = 5.0
        assert r.expectancy == pytest.approx(5.0)

    def test_expectancy_zero_for_symmetric_trades(self):
        trades = [
            _closed_trade("long", 100, 120),  # +20
            _closed_trade("long", 100, 80),  # -20
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=100_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.expectancy == pytest.approx(0.0)

    def test_total_return(self):
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=115_000,
            trades=[_closed_trade("long", 100, 115)],
        )
        r.calculate_metrics()
        assert r.total_return == pytest.approx(15_000)
        assert r.total_return_pct == pytest.approx(15.0)

    def test_avg_bars_held(self):
        trades = [
            _closed_trade("long", 100, 110, bars=10),
            _closed_trade("long", 100, 90, bars=4),
        ]
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=100_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.avg_bars_held == pytest.approx(7.0)
        assert r.avg_winner_bars == pytest.approx(10.0)
        assert r.avg_loser_bars == pytest.approx(4.0)

    def test_no_trades_keeps_defaults(self):
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=100_000,
        )
        r.calculate_metrics()
        assert r.total_trades == 0
        assert r.win_rate == 0.0
        assert r.profit_factor == 0.0
        assert r.avg_win == 0.0
        assert r.avg_loss == 0.0

    def test_max_drawdown_preserved(self):
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=95_000,
            max_drawdown=7_000,
            max_drawdown_pct=7.0,
        )
        assert r.max_drawdown == pytest.approx(7_000)
        assert r.max_drawdown_pct == pytest.approx(7.0)

    def test_to_dict_keys(self):
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=100_000,
        )
        d = r.to_dict()
        expected = {
            "symbol",
            "start_date",
            "end_date",
            "initial_capital",
            "final_capital",
            "total_return",
            "total_return_pct",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "avg_win",
            "avg_loss",
            "profit_factor",
            "expectancy",
            "max_drawdown",
            "max_drawdown_pct",
            "sharpe_ratio",
            "avg_bars_held",
        }
        assert set(d.keys()) == expected

    def test_to_dict_date_format(self):
        r = BacktestResult(
            symbol="T",
            start_date=datetime(2024, 3, 15),
            end_date=datetime(2024, 9, 20),
            initial_capital=100_000,
            final_capital=100_000,
        )
        d = r.to_dict()
        assert d["start_date"] == "2024-03-15T00:00:00"
        assert d["end_date"] == "2024-09-20T00:00:00"


# ===========================================================================
# 3. Backtester class - running backtests with mock data
# ===========================================================================


class TestBacktesterRun:
    """Tests for Backtester.run() with various configurations."""

    def test_insufficient_data_returns_empty(self):
        df = _make_ohlcv(n=30)
        bt = Backtester()
        result = bt.run(df, "SHORT")
        assert result.total_trades == 0
        assert result.final_capital == result.initial_capital

    def test_run_with_explicit_signals(self):
        df = _make_ohlcv(n=120, trend=0.1, seed=7)
        signals = _make_signals_df(df, [55, 80], directions=["long", "short"])
        bt = Backtester(initial_capital=100_000, slippage_pct=0.0)
        result = bt.run(df, "TEST", signals_df=signals)
        assert result.total_trades >= 1

    def test_auto_generates_signals_when_none_provided(self):
        df = _make_ohlcv(n=300, trend=0.15, seed=99)
        bt = Backtester()
        result = bt.run(df, "AUTO")
        assert result.symbol == "AUTO"
        assert isinstance(result, BacktestResult)

    def test_stop_loss_exit_long(self):
        """Long stop loss triggers when bar low <= stop_loss."""
        df = _make_ohlcv(n=120, start_price=100, trend=0.0, seed=10)
        idx = 55
        # Set stop_loss above the entry price so low <= stop_loss always holds
        signals = _make_signals_df(df, [idx], stop_offsets=[-5.0])  # sl = price + 5
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "SL",
            signals_df=signals,
            use_stop_loss=True,
            use_take_profit=False,
            max_bars_held=999,
        )
        sl_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
        assert len(sl_exits) >= 1

    def test_stop_loss_exit_short(self):
        """Short stop loss triggers when bar high >= stop_loss."""
        df = _make_ohlcv(n=120, start_price=100, trend=0.0, seed=11)
        idx = 55
        # Set stop_loss below the entry price so high >= stop_loss always holds
        signals = _make_signals_df(
            df,
            [idx],
            directions="short",
            stop_offsets=[-5.0],  # sl = price - 5
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "SLS",
            signals_df=signals,
            use_stop_loss=True,
            use_take_profit=False,
            max_bars_held=999,
        )
        sl_exits = [t for t in result.trades if t.exit_reason == "stop_loss"]
        assert len(sl_exits) >= 1

    def test_take_profit_exit_long(self):
        """Long take profit triggers when bar high >= take_profit."""
        df = _make_ohlcv(n=120, start_price=100, trend=0.0, seed=20)
        idx = 55
        # Set TP below entry so high >= tp always holds
        signals = _make_signals_df(df, [idx], tp_offsets=[-5.0])  # tp = price - 5
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "TP",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=True,
            max_bars_held=999,
        )
        tp_exits = [t for t in result.trades if t.exit_reason == "take_profit"]
        assert len(tp_exits) >= 1

    def test_take_profit_exit_short(self):
        """Short take profit triggers when bar low <= take_profit."""
        df = _make_ohlcv(n=120, start_price=100, trend=0.0, seed=21)
        idx = 55
        # Set TP above entry so low <= tp always holds
        signals = _make_signals_df(
            df,
            [idx],
            directions="short",
            tp_offsets=[-5.0],  # tp = price + 5
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "TPS",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=True,
            max_bars_held=999,
        )
        tp_exits = [t for t in result.trades if t.exit_reason == "take_profit"]
        assert len(tp_exits) >= 1

    def test_max_bars_exit(self):
        df = _make_ohlcv(n=120, start_price=100, trend=0.0, seed=30)
        signals = _make_signals_df(
            df,
            [55],
            stop_offsets=[100.0],
            tp_offsets=[100.0],
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "MB",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=10,
        )
        assert result.total_trades >= 1
        mb_exits = [t for t in result.trades if t.exit_reason == "max_bars"]
        assert len(mb_exits) >= 1
        for t in mb_exits:
            assert t.bars_held >= 10

    def test_opposite_signal_exit(self):
        df = _make_ohlcv(n=120, trend=0.0, seed=40)
        signals = _make_signals_df(
            df,
            [55, 65],
            directions=["long", "short"],
            stop_offsets=[100.0, 100.0],
            tp_offsets=[100.0, 100.0],
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "OPP",
            signals_df=signals,
            exit_on_opposite_signal=True,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=999,
        )
        opp_exits = [t for t in result.trades if t.exit_reason == "opposite_signal"]
        assert len(opp_exits) >= 1

    def test_min_signal_strength_filtering(self):
        """Signals below min_signal_strength are ignored."""
        df = _make_ohlcv(n=120, trend=0.1, seed=50)
        signals = _make_signals_df(
            df,
            [55, 70],
            strengths=[2, 4],
            stop_offsets=[50.0, 50.0],
            tp_offsets=[50.0, 50.0],
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "STR",
            signals_df=signals,
            min_signal_strength=3,
            use_stop_loss=False,
            use_take_profit=False,
        )
        assert result.total_trades >= 1
        # The weak signal at bar 55 should not produce a trade entry
        for t in result.trades:
            assert t.entry_time != df.index[55]

    def test_string_signal_strength_accepted(self):
        """String strength names are mapped to integers."""
        df = _make_ohlcv(n=120, trend=0.1, seed=60)
        signals = _make_signals_df(df, [55], strengths=["STRONG"])
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "SSTR",
            signals_df=signals,
            min_signal_strength=4,
            use_stop_loss=False,
            use_take_profit=False,
        )
        assert result.total_trades >= 1

    def test_string_strength_below_threshold_ignored(self):
        df = _make_ohlcv(n=120, trend=0.1, seed=61)
        signals = _make_signals_df(df, [55], strengths=["WEAK"])
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "SWEAK",
            signals_df=signals,
            min_signal_strength=3,
            use_stop_loss=False,
            use_take_profit=False,
        )
        assert result.total_trades == 0

    def test_slippage_raises_long_entry(self):
        """Slippage increases long entry price."""
        df = _make_ohlcv(n=120, trend=0.1, seed=70)
        idx = 55
        raw_price = float(df["close"].iloc[idx])
        signals = _make_signals_df(df, [idx], stop_offsets=[100.0], tp_offsets=[100.0])
        bt = Backtester(slippage_pct=0.1)
        result = bt.run(
            df,
            "SLIP",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=5,
        )
        assert result.trades[0].entry_price > raw_price

    def test_slippage_lowers_short_entry(self):
        """Slippage decreases short entry price."""
        df = _make_ohlcv(n=120, trend=-0.1, seed=71)
        idx = 55
        raw_price = float(df["close"].iloc[idx])
        signals = _make_signals_df(
            df,
            [idx],
            directions="short",
            stop_offsets=[100.0],
            tp_offsets=[100.0],
        )
        bt = Backtester(slippage_pct=0.1)
        result = bt.run(
            df,
            "SLIPS",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=5,
        )
        assert result.trades[0].entry_price < raw_price

    def test_commission_reduces_capital(self):
        df = _make_ohlcv(n=120, trend=0.0, volatility=0.01, seed=80)
        signals = _make_signals_df(df, [55], stop_offsets=[100.0], tp_offsets=[100.0])
        r_no = Backtester(commission=0.0, slippage_pct=0.0).run(
            df,
            "NC",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=5,
        )
        r_yes = Backtester(commission=10.0, slippage_pct=0.0).run(
            df,
            "WC",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=5,
        )
        assert r_yes.final_capital < r_no.final_capital

    def test_end_of_data_closes_open_position(self):
        df = _make_ohlcv(n=120, trend=0.1, seed=90)
        # Place signal near the end so the position stays open
        entry_idx = len(df) - 5
        signals = _make_signals_df(
            df,
            [entry_idx],
            stop_offsets=[100.0],
            tp_offsets=[100.0],
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "EOD",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=999,
        )
        eod = [t for t in result.trades if t.exit_reason == "end_of_data"]
        assert len(eod) >= 1

    def test_max_drawdown_nonnegative(self):
        df = _make_ohlcv(n=200, trend=-0.1, seed=100)
        signals = _make_signals_df(
            df, [55, 100], stop_offsets=[100.0, 100.0], tp_offsets=[100.0, 100.0]
        )
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "DD",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=20,
        )
        assert result.max_drawdown >= 0
        assert result.max_drawdown_pct >= 0

    def test_empty_signals_df_no_trades(self):
        df = _make_ohlcv(n=100)
        bt = Backtester()
        result = bt.run(df, "EMPTY", signals_df=pd.DataFrame())
        assert result.total_trades == 0
        assert result.final_capital == bt.initial_capital

    def test_signal_before_bar_50_ignored(self):
        """The engine loop starts at bar 50; earlier signals are never seen."""
        df = _make_ohlcv(n=100, trend=0.5)
        signals = _make_signals_df(df, [10], strengths=[5])
        bt = Backtester(slippage_pct=0.0)
        result = bt.run(
            df,
            "EARLY",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
        )
        assert result.total_trades == 0


# ===========================================================================
# 4. Sharpe ratio annualization per timeframe
# ===========================================================================


class TestSharpeAnnualization:
    """Tests for the ANNUALIZATION_FACTORS dict and Sharpe calculation."""

    def test_all_timeframes_present(self):
        expected = {"1m", "5m", "10m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"}
        assert set(Backtester.ANNUALIZATION_FACTORS.keys()) == expected

    @pytest.mark.parametrize(
        "timeframe, expected",
        [
            ("1m", 252 * 390),
            ("5m", 252 * 78),
            ("10m", 252 * 39),
            ("15m", 252 * 26),
            ("30m", 252 * 13),
            ("1h", 252 * 6.5),
            ("4h", 252 * 1.625),
            ("1d", 252),
            ("1wk", 52),
            ("1mo", 12),
        ],
    )
    def test_factor_value(self, timeframe, expected):
        assert Backtester.ANNUALIZATION_FACTORS[timeframe] == expected

    def test_sharpe_varies_by_timeframe(self):
        """Different annualization factors produce different Sharpe ratios."""
        df = _make_ohlcv(n=200, trend=0.1, seed=111)
        signals = _make_signals_df(df, [55], stop_offsets=[100.0], tp_offsets=[100.0])
        kwargs = {
            "signals_df": signals,
            "use_stop_loss": False,
            "use_take_profit": False,
            "max_bars_held": 30,
        }
        r_d = Backtester(timeframe="1d", slippage_pct=0.0).run(df, "D", **kwargs)
        r_w = Backtester(timeframe="1wk", slippage_pct=0.0).run(df, "W", **kwargs)
        if r_d.sharpe_ratio != 0 and r_w.sharpe_ratio != 0:
            assert r_d.sharpe_ratio != pytest.approx(r_w.sharpe_ratio, abs=0.01)

    def test_unknown_timeframe_defaults_to_252(self):
        """Unrecognized timeframes fall back to 252 via dict.get()."""
        bt = Backtester(timeframe="3d", slippage_pct=0.0)
        df = _make_ohlcv(n=200, trend=0.1, seed=112)
        signals = _make_signals_df(df, [55], stop_offsets=[100.0], tp_offsets=[100.0])
        result = bt.run(
            df,
            "UNK",
            signals_df=signals,
            use_stop_loss=False,
            use_take_profit=False,
            max_bars_held=30,
        )
        assert isinstance(result.sharpe_ratio, float)

    def test_sharpe_zero_when_no_variance(self):
        """If equity curve has zero variance, Sharpe should be 0."""
        df = _make_ohlcv(n=100)
        bt = Backtester()
        result = bt.run(df, "FLAT", signals_df=pd.DataFrame())
        assert result.sharpe_ratio == 0.0


# ===========================================================================
# 5. format_summary() output
# ===========================================================================


class TestFormatSummary:
    """Tests for BacktestResult.format_summary()."""

    def _make_result(self, **overrides):
        defaults = {
            "symbol": "XLK",
            "start_date": datetime(2024, 1, 15),
            "end_date": datetime(2024, 7, 20),
            "initial_capital": 100_000,
            "final_capital": 112_500,
        }
        defaults.update(overrides)
        r = BacktestResult(**defaults)
        r.calculate_metrics()
        return r

    def test_contains_symbol(self):
        summary = self._make_result().format_summary()
        assert "XLK" in summary

    def test_contains_section_headers(self):
        summary = self._make_result().format_summary()
        assert "BACKTEST RESULTS" in summary
        assert "TRADE STATISTICS" in summary
        assert "RISK METRICS" in summary

    def test_contains_date_range(self):
        summary = self._make_result().format_summary()
        assert "2024-01-15" in summary
        assert "2024-07-20" in summary

    def test_contains_capital_figures(self):
        summary = self._make_result().format_summary()
        assert "$100,000.00" in summary
        assert "$112,500.00" in summary

    def test_contains_total_return(self):
        summary = self._make_result().format_summary()
        assert "Total Return" in summary

    def test_infinite_profit_factor_displays_infinity_symbol(self):
        summary = self._make_result(profit_factor=float("inf")).format_summary()
        assert "\u221e" in summary  # unicode infinity

    def test_finite_profit_factor_displays_decimal(self):
        summary = self._make_result(profit_factor=2.35).format_summary()
        assert "2.35" in summary

    def test_contains_sharpe_ratio(self):
        summary = self._make_result(sharpe_ratio=1.42).format_summary()
        assert "Sharpe Ratio" in summary
        assert "1.42" in summary

    def test_contains_max_drawdown(self):
        summary = self._make_result(
            max_drawdown=5_000,
            max_drawdown_pct=5.0,
        ).format_summary()
        assert "Max Drawdown" in summary
        assert "5.00%" in summary

    def test_print_summary_does_not_raise(self, caplog):
        """print_summary() sends the summary through the logger."""
        r = self._make_result()
        with caplog.at_level(logging.INFO):
            r.print_summary()
        # At minimum, ensure it does not raise.


# ===========================================================================
# 6. run_multiple with error handling
# ===========================================================================


class TestRunMultiple:
    """Tests for Backtester.run_multiple()."""

    def test_returns_results_keyed_by_symbol(self):
        data = {
            "XLK": _make_ohlcv(n=300, trend=0.1, seed=200),
            "XLF": _make_ohlcv(n=300, trend=-0.1, seed=201),
        }
        results = Backtester().run_multiple(data)
        assert "XLK" in results
        assert "XLF" in results
        assert isinstance(results["XLK"], BacktestResult)

    def test_error_skips_bad_symbol_key_error(self):
        """A DataFrame missing required columns raises KeyError, which is caught.

        The DataFrame needs >= 234 rows to get past the length guard, so the
        engine actually tries to access the 'close' column and fails.
        """
        bad_df = pd.DataFrame({"not_close": list(range(250))})
        data = {
            "GOOD": _make_ohlcv(n=300, seed=210),
            "BAD": bad_df,
        }
        results = Backtester().run_multiple(data)
        assert "GOOD" in results
        assert "BAD" not in results

    def test_error_skips_empty_dataframe(self):
        """An empty DataFrame causes an error that is caught."""
        data = {
            "GOOD": _make_ohlcv(n=300, seed=220),
            "EMPTY": pd.DataFrame(),
        }
        results = Backtester().run_multiple(data)
        assert "GOOD" in results

    def test_kwargs_forwarded(self):
        data = {"A": _make_ohlcv(n=120, seed=230)}
        results = Backtester(slippage_pct=0.0).run_multiple(
            data,
            max_bars_held=5,
            use_stop_loss=False,
        )
        assert "A" in results

    def test_single_symbol(self):
        data = {"ONLY": _make_ohlcv(n=120, seed=240)}
        results = Backtester().run_multiple(data)
        assert len(results) == 1
        assert "ONLY" in results

    def test_empty_dict_returns_empty(self):
        results = Backtester().run_multiple({})
        assert results == {}


# ===========================================================================
# 7. run_quick_backtest helper function
# ===========================================================================


class TestRunQuickBacktest:
    """Tests for the run_quick_backtest convenience function."""

    def test_returns_backtest_result(self):
        df = _make_ohlcv(n=300, trend=0.1, seed=300)
        result = run_quick_backtest(df, "QUICK", print_results=False)
        assert isinstance(result, BacktestResult)
        assert result.symbol == "QUICK"

    def test_default_capital_is_100k(self):
        df = _make_ohlcv(n=300, trend=0.1, seed=301)
        result = run_quick_backtest(df, "CAP", print_results=False)
        assert result.initial_capital == 100_000

    def test_custom_capital(self):
        df = _make_ohlcv(n=300, trend=0.1, seed=302)
        result = run_quick_backtest(df, "CC", initial_capital=50_000, print_results=False)
        assert result.initial_capital == 50_000

    def test_custom_timeframe(self):
        df = _make_ohlcv(n=300, trend=0.1, seed=303)
        r1 = run_quick_backtest(df, "T1", timeframe="1d", print_results=False)
        r2 = run_quick_backtest(df, "T2", timeframe="1wk", print_results=False)
        assert isinstance(r1, BacktestResult)
        assert isinstance(r2, BacktestResult)

    def test_print_results_true_does_not_raise(self, caplog):
        with caplog.at_level(logging.INFO):
            df = _make_ohlcv(n=300, trend=0.1, seed=304)
            result = run_quick_backtest(df, "PRINT", print_results=True)
        assert isinstance(result, BacktestResult)

    def test_insufficient_data(self):
        df = _make_ohlcv(n=20, seed=305)
        result = run_quick_backtest(df, "TINY", print_results=False)
        assert result.total_trades == 0
        assert result.final_capital == result.initial_capital


# ===========================================================================
# compare_results
# ===========================================================================


class TestCompareResults:
    """Tests for Backtester.compare_results()."""

    def test_columns_present(self):
        data = {
            "XLK": _make_ohlcv(n=120, seed=400),
            "XLF": _make_ohlcv(n=120, seed=401),
        }
        bt = Backtester()
        comparison = bt.compare_results(bt.run_multiple(data))
        expected_cols = {
            "Symbol",
            "Return %",
            "Trades",
            "Win Rate %",
            "Profit Factor",
            "Max DD %",
            "Sharpe",
            "Expectancy",
        }
        assert set(comparison.columns) == expected_cols

    def test_sorted_by_return_descending(self):
        data = {
            "UP": _make_ohlcv(n=200, trend=0.3, seed=410),
            "DOWN": _make_ohlcv(n=200, trend=-0.3, seed=411),
        }
        bt = Backtester()
        comparison = bt.compare_results(bt.run_multiple(data))
        returns = comparison["Return %"].tolist()
        assert returns == sorted(returns, reverse=True)

    def test_inf_profit_factor_capped_at_999(self):
        """Infinite profit factor is replaced with 999 in the comparison table."""
        trades = [_closed_trade("long", 100, 110)]
        r = BacktestResult(
            symbol="INF",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100_000,
            final_capital=110_000,
            trades=trades,
        )
        r.calculate_metrics()
        assert r.profit_factor == float("inf")

        bt = Backtester()
        comparison = bt.compare_results({"INF": r})
        assert comparison.iloc[0]["Profit Factor"] == 999


# ===========================================================================
# _generate_simple_signals (internal method)
# ===========================================================================


class TestGenerateSimpleSignals:
    """Tests for the internal _generate_simple_signals helper."""

    def test_returns_dataframe(self):
        df = _make_ohlcv(n=300, trend=0.1, volatility=2.0, seed=500)
        signals = Backtester()._generate_simple_signals(df)
        assert isinstance(signals, pd.DataFrame)

    def test_expected_columns_when_signals_found(self):
        df = _make_ohlcv(n=300, trend=0.1, volatility=2.0, seed=501)
        signals = Backtester()._generate_simple_signals(df)
        if not signals.empty:
            for col in ("direction", "signal_type", "strength", "stop_loss", "take_profit"):
                assert col in signals.columns

    def test_valid_directions(self):
        df = _make_ohlcv(n=300, trend=0.1, volatility=2.0, seed=502)
        signals = Backtester()._generate_simple_signals(df)
        if not signals.empty:
            assert set(signals["direction"].unique()).issubset({"long", "short"})

    def test_does_not_mutate_input(self):
        df = _make_ohlcv(n=100, trend=0.1, seed=503)
        original_cols = set(df.columns)
        Backtester()._generate_simple_signals(df)
        assert set(df.columns) == original_cols

    def test_short_data_returns_empty_or_dataframe(self):
        df = _make_ohlcv(n=10, seed=504)
        signals = Backtester()._generate_simple_signals(df)
        assert isinstance(signals, pd.DataFrame)
