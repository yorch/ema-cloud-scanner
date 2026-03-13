"""
Tests for the Backtesting engine.
"""

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


def make_ohlcv(n=200, base_price=100.0, trend=0.0, seed=42):
    """Create realistic OHLCV data with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = base_price + trend * np.arange(n) + rng.normal(0, 0.5, n).cumsum()
    high = close + rng.uniform(0.5, 1.5, n)
    low = close - rng.uniform(0.5, 1.5, n)
    volume = rng.integers(100000, 1000000, n).astype(float)
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.3, n),
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


def make_signals_df(df, indices, direction="long", strength=4):
    """Create a signals DataFrame at given bar indices."""
    rows = []
    for i in indices:
        row = df.iloc[i]
        rows.append(
            {
                "timestamp": df.index[i],
                "direction": direction,
                "signal_type": "ema_cross_bullish",
                "strength": strength,
                "stop_loss": row["close"] - 3.0 if direction == "long" else row["close"] + 3.0,
                "take_profit": row["close"] + 6.0 if direction == "long" else row["close"] - 6.0,
            }
        )
    signals = pd.DataFrame(rows)
    signals.set_index("timestamp", inplace=True)
    return signals


# --- Trade model ---


class TestTrade:
    def test_close_long_winner(self):
        t = Trade(
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            direction="long",
            signal_type="test",
            signal_strength="4",
        )
        t.close(datetime(2024, 1, 5), 110.0, "take_profit")
        assert t.pnl == pytest.approx(10.0)
        assert t.pnl_pct == pytest.approx(10.0)
        assert t.is_winner is True

    def test_close_long_loser(self):
        t = Trade(
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            direction="long",
            signal_type="test",
            signal_strength="4",
        )
        t.close(datetime(2024, 1, 5), 95.0, "stop_loss")
        assert t.pnl == pytest.approx(-5.0)
        assert t.is_winner is False

    def test_close_short_winner(self):
        t = Trade(
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            direction="short",
            signal_type="test",
            signal_strength="4",
        )
        t.close(datetime(2024, 1, 5), 90.0, "take_profit")
        assert t.pnl == pytest.approx(10.0)
        assert t.is_winner is True

    def test_close_short_loser(self):
        t = Trade(
            entry_time=datetime(2024, 1, 1),
            entry_price=100.0,
            direction="short",
            signal_type="test",
            signal_strength="4",
        )
        t.close(datetime(2024, 1, 5), 105.0, "stop_loss")
        assert t.pnl == pytest.approx(-5.0)
        assert t.is_winner is False


# --- BacktestResult ---


class TestBacktestResult:
    def _make_result_with_trades(self):
        trades = []
        # 3 winners, 2 losers
        for i, (pnl, bars) in enumerate([(5.0, 3), (10.0, 5), (3.0, 2), (-4.0, 4), (-2.0, 3)]):
            t = Trade(
                entry_time=datetime(2024, 1, i + 1),
                entry_price=100.0,
                direction="long",
                signal_type="test",
                signal_strength="4",
                exit_time=datetime(2024, 1, i + 5),
                exit_price=100.0 + pnl,
                exit_reason="test",
                pnl=pnl,
                pnl_pct=pnl,
                is_winner=pnl > 0,
                bars_held=bars,
            )
            trades.append(t)

        result = BacktestResult(
            symbol="XLK",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100000.0,
            final_capital=100012.0,
            trades=trades,
        )
        result.calculate_metrics()
        return result

    def test_metrics(self):
        r = self._make_result_with_trades()
        assert r.total_trades == 5
        assert r.winning_trades == 3
        assert r.losing_trades == 2
        assert r.win_rate == pytest.approx(60.0)

    def test_avg_win_loss(self):
        r = self._make_result_with_trades()
        assert r.avg_win == pytest.approx(6.0)  # (5+10+3)/3
        assert r.avg_loss == pytest.approx(3.0)  # (4+2)/2

    def test_profit_factor(self):
        r = self._make_result_with_trades()
        # total_win=18, total_loss=6
        assert r.profit_factor == pytest.approx(3.0)

    def test_no_trades(self):
        r = BacktestResult(
            symbol="XLK",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
            initial_capital=100000.0,
            final_capital=100000.0,
        )
        r.calculate_metrics()
        assert r.total_trades == 0
        assert r.win_rate == 0

    def test_format_summary(self):
        r = self._make_result_with_trades()
        summary = r.format_summary()
        assert "BACKTEST RESULTS" in summary
        assert "XLK" in summary
        assert "Winning Trades" in summary

    def test_to_dict(self):
        r = self._make_result_with_trades()
        d = r.to_dict()
        assert d["symbol"] == "XLK"
        assert d["total_trades"] == 5


# --- Backtester ---


class TestBacktester:
    def test_annualization_factors(self):
        assert Backtester.ANNUALIZATION_FACTORS["1d"] == 252
        assert Backtester.ANNUALIZATION_FACTORS["1wk"] == 52
        assert Backtester.ANNUALIZATION_FACTORS["1mo"] == 12
        assert Backtester.ANNUALIZATION_FACTORS["1m"] == 252 * 390

    def test_run_insufficient_data(self):
        bt = Backtester()
        df = make_ohlcv(30)
        result = bt.run(df, "XLK")
        assert result.total_trades == 0

    def test_run_with_auto_signals(self):
        df = make_ohlcv(300, trend=0.1)
        bt = Backtester(initial_capital=100000.0, timeframe="1d")
        result = bt.run(df, "XLK")
        assert isinstance(result, BacktestResult)
        assert result.initial_capital == 100000.0

    def test_run_with_provided_signals(self):
        df = make_ohlcv(200)
        signals = make_signals_df(df, [60, 100, 140])
        bt = Backtester(initial_capital=100000.0)
        result = bt.run(df, "XLK", signals_df=signals)
        assert isinstance(result, BacktestResult)

    def test_run_multiple(self):
        data = {
            "XLK": make_ohlcv(200, seed=1),
            "XLF": make_ohlcv(200, seed=2),
        }
        bt = Backtester()
        results = bt.run_multiple(data)
        assert "XLK" in results
        assert "XLF" in results

    def test_compare_results(self):
        data = {
            "XLK": make_ohlcv(200, seed=1),
            "XLF": make_ohlcv(200, seed=2),
        }
        bt = Backtester()
        results = bt.run_multiple(data)
        comparison = bt.compare_results(results)
        assert isinstance(comparison, pd.DataFrame)
        assert "Symbol" in comparison.columns

    def test_timeframe_affects_sharpe(self):
        df = make_ohlcv(300, trend=0.1)
        bt_daily = Backtester(timeframe="1d")
        bt_weekly = Backtester(timeframe="1wk")
        r_daily = bt_daily.run(df, "XLK")
        r_weekly = bt_weekly.run(df, "XLK")
        assert isinstance(r_daily.sharpe_ratio, float)
        assert isinstance(r_weekly.sharpe_ratio, float)


# --- run_quick_backtest ---


class TestRunQuickBacktest:
    def test_basic(self):
        df = make_ohlcv(200)
        result = run_quick_backtest(df, "XLK", print_results=False)
        assert isinstance(result, BacktestResult)

    def test_with_timeframe(self):
        df = make_ohlcv(200)
        result = run_quick_backtest(df, "XLK", print_results=False, timeframe="1h")
        assert isinstance(result, BacktestResult)
