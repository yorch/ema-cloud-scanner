"""
Tests for EMA Cloud Indicator calculations.
"""

import numpy as np
import pandas as pd
import pytest

from ema_cloud_lib.indicators.ema_cloud import (
    CloudData,
    CloudState,
    EMACloudIndicator,
    PriceRelation,
    TechnicalIndicators,
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_true_range,
    calculate_vwap,
)


def make_ohlcv(n=100, base_price=100.0, trend=0.0, seed=42):
    """Create a realistic OHLCV DataFrame for testing."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = base_price + trend * np.arange(n) + rng.normal(0, 1, n).cumsum()
    high = close + rng.uniform(0.5, 2.0, n)
    low = close - rng.uniform(0.5, 2.0, n)
    open_ = close + rng.normal(0, 0.5, n)
    volume = rng.integers(100000, 1000000, n).astype(float)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=dates,
    )


def make_intraday_ohlcv(days=2, bars_per_day=78, base_price=100.0, seed=42):
    """Create intraday OHLCV data spanning multiple days."""
    rng = np.random.default_rng(seed)
    timestamps = []
    for d in range(days):
        day = pd.Timestamp(f"2024-01-{d + 1:02d} 09:30:00")
        for b in range(bars_per_day):
            timestamps.append(day + pd.Timedelta(minutes=5 * b))
    n = len(timestamps)
    idx = pd.DatetimeIndex(timestamps)
    close = base_price + rng.normal(0, 0.3, n).cumsum()
    high = close + rng.uniform(0.1, 0.5, n)
    low = close - rng.uniform(0.1, 0.5, n)
    volume = rng.integers(10000, 100000, n).astype(float)
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.1, n),
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


# --- EMA / SMA ---


class TestCalculateEma:
    def test_basic_ema(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calculate_ema(s, 3)
        assert len(result) == 5
        assert not result.isna().any()

    def test_ema_follows_trend(self):
        s = pd.Series(range(1, 21), dtype=float)
        ema = calculate_ema(s, 5)
        # EMA should be increasing for an increasing series
        assert all(ema.diff().dropna() > 0)

    def test_ema_lag(self):
        s = pd.Series(range(1, 21), dtype=float)
        ema = calculate_ema(s, 5)
        # EMA lags behind the actual values for a trending series
        assert ema.iloc[-1] < s.iloc[-1]

    def test_constant_series(self):
        s = pd.Series([50.0] * 20)
        ema = calculate_ema(s, 10)
        np.testing.assert_allclose(ema.values, 50.0, atol=1e-10)


class TestCalculateSma:
    def test_basic_sma(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calculate_sma(s, 3)
        assert result.iloc[-1] == pytest.approx(4.0)
        assert pd.isna(result.iloc[0])


# --- RSI ---


class TestCalculateRsi:
    def test_rsi_range(self):
        df = make_ohlcv(100)
        rsi = calculate_rsi(df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_uptrend(self):
        # Use real-world-like data with mostly up days and some down days
        df = make_ohlcv(100, trend=0.5, seed=10)
        rsi = calculate_rsi(df["close"], 14)
        # In a strong uptrend, RSI should be elevated (above 50)
        assert rsi.iloc[-1] > 50

    def test_rsi_downtrend(self):
        s = pd.Series(np.linspace(200, 100, 50))
        rsi = calculate_rsi(s, 14)
        assert rsi.iloc[-1] < 30


# --- True Range / ATR ---


class TestTrueRangeAndAtr:
    def test_true_range_basic(self):
        df = make_ohlcv(20)
        tr = calculate_true_range(df["high"], df["low"], df["close"])
        assert len(tr) == 20
        # TR should always be positive
        assert (tr.dropna() >= 0).all()

    def test_atr_smoothness(self):
        df = make_ohlcv(100)
        atr = calculate_atr(df["high"], df["low"], df["close"], 14)
        assert len(atr) == 100
        # ATR should be positive
        assert (atr.dropna() > 0).all()


# --- VWAP ---


class TestCalculateVwap:
    def test_vwap_daily_data(self):
        df = make_ohlcv(30)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert len(vwap) == 30
        assert not vwap.isna().all()

    def test_vwap_intraday_resets(self):
        """VWAP should reset at day boundaries for intraday data."""
        df = make_intraday_ohlcv(days=2, bars_per_day=10)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])

        # First bar of each day: VWAP == typical price
        day1_first = df.index[0]
        day2_first = df.index[10]

        tp1 = (
            df.loc[day1_first, "high"] + df.loc[day1_first, "low"] + df.loc[day1_first, "close"]
        ) / 3
        tp2 = (
            df.loc[day2_first, "high"] + df.loc[day2_first, "low"] + df.loc[day2_first, "close"]
        ) / 3

        assert vwap.loc[day1_first] == pytest.approx(tp1, rel=1e-6)
        assert vwap.loc[day2_first] == pytest.approx(tp2, rel=1e-6)

    def test_vwap_zero_volume(self):
        df = make_ohlcv(10)
        df["volume"] = 0.0
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert vwap.isna().all()


# --- MACD ---


class TestCalculateMacd:
    def test_macd_columns(self):
        df = make_ohlcv(50)
        macd = calculate_macd(df["close"])
        assert set(macd.columns) == {"macd", "signal", "histogram"}
        assert len(macd) == 50

    def test_macd_uptrend(self):
        s = pd.Series(np.linspace(100, 150, 60))
        macd = calculate_macd(s, 12, 26, 9)
        # In an uptrend, MACD line should be positive
        assert macd["macd"].iloc[-1] > 0

    def test_macd_histogram_identity(self):
        df = make_ohlcv(50)
        macd = calculate_macd(df["close"])
        np.testing.assert_allclose(
            macd["histogram"].values,
            (macd["macd"] - macd["signal"]).values,
            atol=1e-10,
        )


# --- EMACloudIndicator ---


class TestEMACloudIndicator:
    def test_calculate_adds_columns(self):
        df = make_ohlcv(300)
        indicator = EMACloudIndicator()
        result = indicator.calculate(df)
        # Should have columns for each cloud
        for name in indicator.clouds_config:
            assert f"{name}_fast" in result.columns
            assert f"{name}_slow" in result.columns
            assert f"{name}_bullish" in result.columns

    def test_custom_clouds(self):
        indicator = EMACloudIndicator({"custom": (10, 20)})
        df = make_ohlcv(50)
        result = indicator.calculate(df)
        assert "custom_fast" in result.columns

    def test_cloud_state_bullish(self):
        indicator = EMACloudIndicator({"test": (5, 20)})
        # Uptrend: fast EMA > slow EMA
        df = make_ohlcv(100, trend=0.5)
        result = indicator.calculate(df)
        state = indicator.get_cloud_state(result.iloc[-1], "test")
        assert state == CloudState.BULLISH

    def test_cloud_state_bearish(self):
        indicator = EMACloudIndicator({"test": (5, 20)})
        df = make_ohlcv(100, trend=-0.5)
        result = indicator.calculate(df)
        state = indicator.get_cloud_state(result.iloc[-1], "test")
        assert state == CloudState.BEARISH

    def test_price_relation_above(self):
        indicator = EMACloudIndicator()
        rel = indicator.get_price_relation(105.0, 100.0, 98.0)
        assert rel == PriceRelation.ABOVE

    def test_price_relation_below(self):
        indicator = EMACloudIndicator()
        rel = indicator.get_price_relation(95.0, 100.0, 98.0)
        assert rel == PriceRelation.BELOW

    def test_price_relation_inside(self):
        indicator = EMACloudIndicator()
        rel = indicator.get_price_relation(99.0, 100.0, 98.0)
        assert rel == PriceRelation.INSIDE

    def test_analyze_single(self):
        df = make_ohlcv(300)
        indicator = EMACloudIndicator()
        result = indicator.calculate(df)
        clouds = indicator.analyze_single(result)
        assert "trend_confirmation" in clouds
        assert isinstance(clouds["trend_confirmation"], CloudData)

    def test_detect_signals_returns_list(self):
        df = make_ohlcv(300)
        indicator = EMACloudIndicator()
        result = indicator.calculate(df)
        signals = indicator.detect_signals(result)
        assert isinstance(signals, list)

    def test_add_remove_cloud(self):
        indicator = EMACloudIndicator()
        indicator.add_cloud("custom", 15, 30)
        assert "custom" in indicator.clouds_config
        indicator.remove_cloud("custom")
        assert "custom" not in indicator.clouds_config


# --- TechnicalIndicators ---


class TestTechnicalIndicators:
    def test_calculate_all(self):
        df = make_ohlcv(100)
        ti = TechnicalIndicators()
        result = ti.calculate_all(df)
        assert "rsi" in result.columns
        assert "adx" in result.columns
        assert "atr" in result.columns
        assert "vwap" in result.columns
        assert "macd" in result.columns
        assert "volume_ratio" in result.columns

    def test_get_analysis(self):
        df = make_ohlcv(100)
        ti = TechnicalIndicators()
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert "rsi" in analysis
        assert "adx" in analysis
        assert "rsi_signal" in analysis

    def test_custom_config(self):
        ti = TechnicalIndicators({"rsi_period": 7, "adx_period": 7})
        df = make_ohlcv(50)
        result = ti.calculate_all(df)
        assert "rsi" in result.columns
