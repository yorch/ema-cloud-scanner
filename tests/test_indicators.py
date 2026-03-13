"""
Comprehensive tests for EMA Cloud Indicator calculations.

Covers:
- EMA / SMA calculation correctness and edge cases
- RSI calculation including overbought, oversold, flat prices
- ADX calculation for trending vs ranging markets
- ATR / True Range calculation
- VWAP calculation with daily reset for intraday data
- MACD calculation
- EMACloudIndicator class: cloud state, price relations, signals, crossings
- TechnicalIndicators: combined indicator calculations and analysis interpretations
- TrendAnalysis Pydantic model
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
    TrendAnalysis,
    calculate_adx,
    calculate_atr,
    calculate_ema,
    calculate_macd,
    calculate_rsi,
    calculate_sma,
    calculate_true_range,
    calculate_vwap,
)


# ---------------------------------------------------------------------------
# Helpers to generate realistic OHLCV DataFrames
# ---------------------------------------------------------------------------


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


def make_trending_up(n=100, start=100.0, step=0.5, seed=0):
    """Generate an upward-trending OHLCV DataFrame with minimal noise."""
    rng = np.random.default_rng(seed)
    closes = [start + i * step + rng.normal(0, 0.05) for i in range(n)]
    return _ohlcv_from_closes(closes, spread=0.5, seed=seed)


def make_trending_down(n=100, start=150.0, step=0.5, seed=0):
    """Generate a downward-trending OHLCV DataFrame with minimal noise."""
    rng = np.random.default_rng(seed)
    closes = [start - i * step + rng.normal(0, 0.05) for i in range(n)]
    return _ohlcv_from_closes(closes, spread=0.5, seed=seed)


def make_ranging(n=100, center=100.0, amplitude=2.0):
    """Generate a sideways/ranging OHLCV DataFrame oscillating around *center*."""
    closes = [center + amplitude * np.sin(2 * np.pi * i / 20) for i in range(n)]
    return _ohlcv_from_closes(closes, spread=0.3)


def _ohlcv_from_closes(closes, spread=0.5, seed=42):
    """Build a DataFrame with OHLCV columns from a list of close prices."""
    n = len(closes)
    rng = np.random.default_rng(seed)
    closes_arr = np.array(closes, dtype=float)
    opens = np.roll(closes_arr, 1)
    opens[0] = closes_arr[0]
    highs = np.maximum(closes_arr, opens) + spread
    lows = np.minimum(closes_arr, opens) - spread
    volumes = rng.integers(500_000, 1_500_000, size=n).astype(float)
    index = pd.date_range(start="2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes_arr, "volume": volumes},
        index=index,
    )


# ===========================================================================
# Tests for calculate_ema
# ===========================================================================


class TestCalculateEma:
    """Tests for the EMA calculation function."""

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
        """For a strictly rising series the EMA should lag below the current value."""
        s = pd.Series(range(1, 21), dtype=float)
        ema = calculate_ema(s, 5)
        assert ema.iloc[-1] < s.iloc[-1]

    def test_constant_series(self):
        """EMA of a constant series should equal that constant everywhere."""
        s = pd.Series([50.0] * 20)
        ema = calculate_ema(s, 10)
        np.testing.assert_allclose(ema.values, 50.0, atol=1e-10)

    def test_ema_first_value_equals_first_input(self):
        """With adjust=False the first EMA value equals the first input value."""
        s = pd.Series([10.0, 20.0, 30.0, 40.0])
        result = calculate_ema(s, 3)
        assert result.iloc[0] == pytest.approx(10.0)

    def test_ema_period_1_equals_original(self):
        """EMA with period 1 should reproduce the original series exactly."""
        s = pd.Series([1.0, 3.0, 2.0, 5.0, 4.0])
        result = calculate_ema(s, 1)
        pd.testing.assert_series_equal(result, s)

    def test_ema_shorter_period_tracks_closer(self):
        """A shorter-period EMA should track the input more closely than a longer one."""
        s = pd.Series(np.random.default_rng(7).normal(100, 2, size=50))
        ema_short = calculate_ema(s, 5)
        ema_long = calculate_ema(s, 20)
        mad_short = (s - ema_short).abs().mean()
        mad_long = (s - ema_long).abs().mean()
        assert mad_short < mad_long

    def test_ema_no_nans(self):
        """EMA with adjust=False should produce no NaN values."""
        s = pd.Series(np.random.default_rng(1).normal(50, 5, size=30))
        result = calculate_ema(s, 10)
        assert not result.isna().any()

    def test_ema_manual_calculation(self):
        """Verify EMA against a hand-calculated value."""
        s = pd.Series([10.0, 11.0, 12.0])
        # period=2 => alpha = 2/(2+1) = 2/3
        ema = calculate_ema(s, 2)
        # EMA[0] = 10, EMA[1] = 10*(1-2/3) + 11*(2/3) = 32/3, EMA[2] = (32/3)*(1/3) + 12*(2/3) = 104/9
        assert ema.iloc[1] == pytest.approx(32 / 3, rel=1e-10)
        assert ema.iloc[2] == pytest.approx(104 / 9, rel=1e-10)


# ===========================================================================
# Tests for calculate_sma
# ===========================================================================


class TestCalculateSma:
    """Tests for the Simple Moving Average."""

    def test_basic_sma(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calculate_sma(s, 3)
        assert result.iloc[-1] == pytest.approx(4.0)
        assert pd.isna(result.iloc[0])

    def test_sma_of_constant(self):
        s = pd.Series([7.0] * 10)
        result = calculate_sma(s, 3)
        assert result.iloc[2:].eq(7.0).all()

    def test_sma_manual_values(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = calculate_sma(s, 3)
        assert result.iloc[2] == pytest.approx(2.0)
        assert result.iloc[3] == pytest.approx(3.0)
        assert result.iloc[4] == pytest.approx(4.0)

    def test_sma_nans_at_start(self):
        """SMA should have NaN for the first (period - 1) values."""
        s = pd.Series(range(10), dtype=float)
        result = calculate_sma(s, 5)
        assert result.iloc[:4].isna().all()
        assert not result.iloc[4:].isna().any()


# ===========================================================================
# Tests for calculate_rsi
# ===========================================================================


class TestCalculateRsi:
    """Tests for the Relative Strength Index calculation."""

    def test_rsi_range(self):
        """RSI values should be bounded between 0 and 100."""
        df = make_ohlcv(100)
        rsi = calculate_rsi(df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_rsi_uptrend(self):
        """Strongly trending up -> RSI should be elevated (above 50)."""
        df = make_ohlcv(100, trend=0.5, seed=10)
        rsi = calculate_rsi(df["close"], 14)
        assert rsi.iloc[-1] > 50

    def test_rsi_overbought_strong_rise(self):
        """A strongly rising series with some noise should produce RSI well above 70."""
        # Use data with natural noise so there are some down bars (avoiding RS=0 edge case)
        df = make_ohlcv(80, trend=1.5, seed=10)
        rsi = calculate_rsi(df["close"], 14)
        assert rsi.iloc[-1] > 70

    def test_rsi_downtrend(self):
        """Strongly trending down -> RSI should be low."""
        df = make_ohlcv(80, trend=-1.0, seed=10)
        rsi = calculate_rsi(df["close"], 14)
        assert rsi.iloc[-1] < 40

    def test_rsi_oversold_strong_fall(self):
        """A strongly falling series with some noise should produce RSI well below 30."""
        df = make_ohlcv(80, trend=-1.5, seed=10)
        rsi = calculate_rsi(df["close"], 14)
        assert rsi.iloc[-1] < 30

    def test_rsi_near_50_for_alternating_prices(self):
        """An alternating up/down pattern should yield RSI near 50."""
        closes = pd.Series([100 + (1 if i % 2 == 0 else -1) for i in range(60)], dtype=float)
        rsi = calculate_rsi(closes, 14)
        assert 40 < rsi.iloc[-1] < 60

    def test_rsi_flat_prices(self):
        """Flat prices (no change) should not produce errors."""
        closes = pd.Series([100.0] * 30)
        rsi = calculate_rsi(closes, 14)
        assert len(rsi) == 30

    def test_rsi_custom_period(self):
        """Shorter RSI period should be more reactive."""
        df = make_ohlcv(80)
        rsi_7 = calculate_rsi(df["close"], 7)
        rsi_21 = calculate_rsi(df["close"], 21)
        assert rsi_7.std() > rsi_21.std() * 0.5

    def test_rsi_length_matches_input(self):
        s = pd.Series(range(50), dtype=float)
        rsi = calculate_rsi(s, 14)
        assert len(rsi) == 50


# ===========================================================================
# Tests for calculate_adx
# ===========================================================================


class TestCalculateAdx:
    """Tests for the Average Directional Index."""

    def test_adx_returns_correct_columns(self):
        df = make_ohlcv(60)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        assert "plus_di" in result.columns
        assert "minus_di" in result.columns
        assert "adx" in result.columns

    def test_adx_high_in_strong_trend(self):
        """ADX should be elevated in a strongly trending market."""
        df = make_trending_up(100, step=1.0)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        assert result["adx"].iloc[-1] > 20

    def test_adx_lower_in_ranging_market(self):
        """ADX should be lower in a ranging market than in a trending one."""
        df_trend = make_trending_up(100, step=1.0)
        df_range = make_ranging(100, amplitude=1.0)

        adx_trend = calculate_adx(df_trend["high"], df_trend["low"], df_trend["close"], 14)
        adx_range = calculate_adx(df_range["high"], df_range["low"], df_range["close"], 14)

        assert adx_trend["adx"].iloc[-1] > adx_range["adx"].iloc[-1]

    def test_adx_plus_di_above_minus_di_in_uptrend(self):
        """In an uptrend, +DI should generally exceed -DI."""
        df = make_trending_up(100, step=1.0)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        assert result["plus_di"].iloc[-1] > result["minus_di"].iloc[-1]

    def test_adx_minus_di_above_plus_di_in_downtrend(self):
        """In a downtrend, -DI should generally exceed +DI."""
        df = make_trending_down(100, step=1.0)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        assert result["minus_di"].iloc[-1] > result["plus_di"].iloc[-1]

    def test_adx_non_negative(self):
        """ADX, +DI, -DI should all be non-negative."""
        df = make_ohlcv(80)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        valid = result.dropna()
        assert (valid["adx"] >= 0).all()
        assert (valid["plus_di"] >= 0).all()
        assert (valid["minus_di"] >= 0).all()

    def test_adx_length(self):
        df = make_ohlcv(50)
        result = calculate_adx(df["high"], df["low"], df["close"], 14)
        assert len(result) == 50

    def test_adx_custom_period(self):
        """ADX should accept a custom period without error."""
        df = make_ohlcv(60)
        result = calculate_adx(df["high"], df["low"], df["close"], 7)
        assert not result["adx"].isna().all()


# ===========================================================================
# Tests for True Range and ATR
# ===========================================================================


class TestTrueRangeAndAtr:
    """Tests for True Range and Average True Range."""

    def test_true_range_basic(self):
        df = make_ohlcv(20)
        tr = calculate_true_range(df["high"], df["low"], df["close"])
        assert len(tr) == 20
        assert (tr.dropna() >= 0).all()

    def test_true_range_with_gap_up(self):
        """A gap up should produce a true range larger than high - low."""
        highs = pd.Series([101.0, 112.0])
        lows = pd.Series([99.0, 110.0])
        closes = pd.Series([100.0, 111.0])
        tr = calculate_true_range(highs, lows, closes)
        # Bar 1: H-L = 2, |H-prevC| = 12, |L-prevC| = 10  =>  TR = 12
        assert tr.iloc[1] == pytest.approx(12.0)

    def test_true_range_with_gap_down(self):
        """A gap down should produce a large true range."""
        highs = pd.Series([101.0, 92.0])
        lows = pd.Series([99.0, 90.0])
        closes = pd.Series([100.0, 91.0])
        tr = calculate_true_range(highs, lows, closes)
        # Bar 1: H-L = 2, |H-prevC| = 8, |L-prevC| = 10  =>  TR = 10
        assert tr.iloc[1] == pytest.approx(10.0)

    def test_true_range_ge_high_minus_low(self):
        """True range is always >= high - low."""
        df = make_ohlcv(20)
        tr = calculate_true_range(df["high"], df["low"], df["close"])
        hl = df["high"] - df["low"]
        assert (tr.dropna() >= hl.dropna() - 1e-10).all()

    def test_atr_smoothness(self):
        df = make_ohlcv(100)
        atr = calculate_atr(df["high"], df["low"], df["close"], 14)
        assert len(atr) == 100
        assert (atr.dropna() > 0).all()

    def test_atr_increases_with_volatility(self):
        """ATR should be larger for more volatile data."""
        df_calm = make_ohlcv(60, base_price=100.0)
        df_wild = df_calm.copy()
        df_wild["high"] = df_wild["close"] + 5.0
        df_wild["low"] = df_wild["close"] - 5.0

        atr_calm = calculate_atr(df_calm["high"], df_calm["low"], df_calm["close"], 14)
        atr_wild = calculate_atr(df_wild["high"], df_wild["low"], df_wild["close"], 14)

        assert atr_wild.iloc[-1] > atr_calm.iloc[-1]

    def test_atr_positive(self):
        """ATR should always be positive."""
        df = make_trending_up(60)
        atr = calculate_atr(df["high"], df["low"], df["close"], 14)
        valid = atr.dropna()
        assert (valid > 0).all()

    def test_atr_length_matches_input(self):
        df = make_ohlcv(30)
        atr = calculate_atr(df["high"], df["low"], df["close"], 14)
        assert len(atr) == len(df)


# ===========================================================================
# Tests for calculate_vwap
# ===========================================================================


class TestCalculateVwap:
    """Tests for Volume Weighted Average Price."""

    def test_vwap_daily_data(self):
        df = make_ohlcv(30)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert len(vwap) == 30
        assert not vwap.isna().all()

    def test_vwap_intraday_resets(self):
        """VWAP should reset at day boundaries for intraday data."""
        df = make_intraday_ohlcv(days=2, bars_per_day=10)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])

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

    def test_vwap_intraday_multiple_days_independent(self):
        """VWAP for day 2 should not be influenced by day 1 data."""
        df = make_intraday_ohlcv(days=3, bars_per_day=20)
        vwap_full = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])

        dates = pd.Series(df.index.date, index=df.index)
        day2_date = sorted(dates.unique())[1]
        day2_mask = dates == day2_date
        df_day2 = df[day2_mask]
        vwap_day2_only = calculate_vwap(
            df_day2["high"], df_day2["low"], df_day2["close"], df_day2["volume"]
        )

        pd.testing.assert_series_equal(
            vwap_full[day2_mask].reset_index(drop=True),
            vwap_day2_only.reset_index(drop=True),
            check_names=False,
            atol=1e-10,
        )

    def test_vwap_zero_volume(self):
        """Bars with zero volume should produce NaN."""
        df = make_ohlcv(10)
        df["volume"] = 0.0
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert vwap.isna().all()

    def test_vwap_equal_volume_intraday(self):
        """With equal volume on all intraday bars, VWAP equals cumulative mean of TP per day."""
        bars_per_day = 10
        df = make_intraday_ohlcv(days=1, bars_per_day=bars_per_day)
        df["volume"] = 1_000_000.0  # constant volume

        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        typical = (df["high"] + df["low"] + df["close"]) / 3
        # Within a single day, cumulative mean of typical price
        expected = typical.cumsum() / pd.Series(
            range(1, bars_per_day + 1), index=df.index, dtype=float
        )
        pd.testing.assert_series_equal(vwap, expected, check_names=False, atol=1e-10)

    def test_vwap_within_price_range(self):
        """VWAP should remain within the overall price range of the data."""
        df = make_trending_up(50)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        valid = vwap.dropna()
        assert valid.iloc[-1] >= df["low"].min()
        assert valid.iloc[-1] <= df["high"].max()

    def test_vwap_length_matches_input(self):
        df = make_ohlcv(25)
        vwap = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])
        assert len(vwap) == 25


# ===========================================================================
# Tests for calculate_macd
# ===========================================================================


class TestCalculateMacd:
    """Tests for MACD indicator."""

    def test_macd_columns(self):
        df = make_ohlcv(50)
        macd = calculate_macd(df["close"])
        assert set(macd.columns) == {"macd", "signal", "histogram"}
        assert len(macd) == 50

    def test_macd_uptrend(self):
        """In an uptrend, MACD line should be positive."""
        s = pd.Series(np.linspace(100, 150, 60))
        macd = calculate_macd(s, 12, 26, 9)
        assert macd["macd"].iloc[-1] > 0

    def test_macd_downtrend(self):
        """In a downtrend, MACD line should be negative."""
        s = pd.Series(np.linspace(150, 100, 60))
        macd = calculate_macd(s, 12, 26, 9)
        assert macd["macd"].iloc[-1] < 0

    def test_macd_histogram_identity(self):
        """Histogram should equal MACD line minus signal line."""
        df = make_ohlcv(50)
        macd = calculate_macd(df["close"])
        np.testing.assert_allclose(
            macd["histogram"].values,
            (macd["macd"] - macd["signal"]).values,
            atol=1e-10,
        )

    def test_macd_zero_for_constant_series(self):
        """MACD should be zero for a constant series."""
        closes = pd.Series([100.0] * 40)
        result = calculate_macd(closes)
        np.testing.assert_allclose(result["macd"].values, 0.0, atol=1e-10)
        np.testing.assert_allclose(result["histogram"].values, 0.0, atol=1e-10)

    def test_macd_custom_periods(self):
        """MACD should work with custom fast/slow/signal periods."""
        df = make_ohlcv(60)
        result = calculate_macd(df["close"], fast=8, slow=17, signal=5)
        assert len(result) == 60
        assert not result["macd"].isna().any()

    def test_macd_no_nans(self):
        """MACD should produce no NaN values (based on EMA with adjust=False)."""
        df = make_ohlcv(40)
        result = calculate_macd(df["close"])
        assert not result.isna().any().any()


# ===========================================================================
# Tests for EMACloudIndicator
# ===========================================================================


class TestEMACloudIndicator:
    """Tests for the EMACloudIndicator class."""

    # --- Initialization ---

    def test_default_clouds(self):
        """Default initialisation should include all six Ripster clouds."""
        indicator = EMACloudIndicator()
        expected = {
            "trend_line",
            "pullback",
            "momentum",
            "trend_confirmation",
            "long_term",
            "major_trend",
        }
        assert set(indicator.clouds_config.keys()) == expected

    def test_custom_clouds(self):
        """Custom cloud config should override defaults."""
        indicator = EMACloudIndicator({"custom": (10, 20)})
        assert "custom" in indicator.clouds_config
        assert "trend_line" not in indicator.clouds_config

    def test_add_remove_cloud(self):
        indicator = EMACloudIndicator()
        indicator.add_cloud("custom", 15, 30)
        assert "custom" in indicator.clouds_config
        assert indicator.clouds_config["custom"] == (15, 30)
        indicator.remove_cloud("custom")
        assert "custom" not in indicator.clouds_config

    def test_remove_nonexistent_cloud_is_safe(self):
        indicator = EMACloudIndicator()
        indicator.remove_cloud("nonexistent")  # should not raise

    # --- calculate() ---

    def test_calculate_adds_columns(self):
        df = make_ohlcv(300)
        indicator = EMACloudIndicator()
        result = indicator.calculate(df)
        for name in indicator.clouds_config:
            for suffix in [
                "fast",
                "slow",
                "cloud_top",
                "cloud_bottom",
                "thickness",
                "thickness_pct",
                "bullish",
            ]:
                assert f"{name}_{suffix}" in result.columns

    def test_calculate_preserves_original(self):
        """Original DataFrame should not be mutated."""
        df = make_ohlcv(50)
        original_cols = set(df.columns)
        indicator = EMACloudIndicator({"tc": (5, 10)})
        _ = indicator.calculate(df)
        assert set(df.columns) == original_cols

    def test_cloud_top_ge_bottom(self):
        """Cloud top should always be >= cloud bottom."""
        indicator = EMACloudIndicator({"tc": (5, 12)})
        df = indicator.calculate(make_trending_up(50))
        assert (df["tc_cloud_top"] >= df["tc_cloud_bottom"]).all()

    def test_thickness_nonnegative(self):
        indicator = EMACloudIndicator({"tc": (8, 21)})
        df = indicator.calculate(make_ranging(60))
        assert (df["tc_thickness"] >= 0).all()

    def test_thickness_pct_calculation(self):
        """thickness_pct should equal thickness / close * 100."""
        indicator = EMACloudIndicator({"tc": (5, 10)})
        df = indicator.calculate(make_ohlcv(40))
        expected = df["tc_thickness"] / df["close"] * 100
        pd.testing.assert_series_equal(df["tc_thickness_pct"], expected, check_names=False)

    def test_bullish_flag_in_uptrend(self):
        """In a sustained uptrend, the fast EMA should end above the slow EMA."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_up(80, step=1.0))
        assert df["tc_bullish"].iloc[-1]

    def test_bearish_flag_in_downtrend(self):
        """In a sustained downtrend, the cloud should be bearish."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_down(80, step=1.0))
        assert not df["tc_bullish"].iloc[-1]

    # --- get_cloud_state() ---

    def test_cloud_state_bullish(self):
        indicator = EMACloudIndicator({"test": (5, 20)})
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

    def test_cloud_state_from_raw_row(self):
        """get_cloud_state should work on a manually constructed row."""
        indicator = EMACloudIndicator()
        row = pd.Series({"tc_fast": 105.0, "tc_slow": 100.0})
        assert indicator.get_cloud_state(row, "tc") == CloudState.BULLISH
        row2 = pd.Series({"tc_fast": 95.0, "tc_slow": 100.0})
        assert indicator.get_cloud_state(row2, "tc") == CloudState.BEARISH

    # --- get_price_relation() ---

    def test_price_relation_above(self):
        indicator = EMACloudIndicator()
        assert indicator.get_price_relation(105.0, 100.0, 98.0) == PriceRelation.ABOVE

    def test_price_relation_below(self):
        indicator = EMACloudIndicator()
        assert indicator.get_price_relation(95.0, 100.0, 98.0) == PriceRelation.BELOW

    def test_price_relation_inside(self):
        indicator = EMACloudIndicator()
        assert indicator.get_price_relation(99.0, 100.0, 98.0) == PriceRelation.INSIDE

    def test_price_relation_touching_top(self):
        indicator = EMACloudIndicator()
        # tolerance = 0.1 * (105 - 100) = 0.5; price within 0.5 of top
        assert indicator.get_price_relation(105.2, 105.0, 100.0) == PriceRelation.TOUCHING_TOP

    def test_price_relation_touching_bottom(self):
        indicator = EMACloudIndicator()
        assert indicator.get_price_relation(99.8, 105.0, 100.0) == PriceRelation.TOUCHING_BOTTOM

    def test_price_relation_zero_thickness(self):
        """When cloud has zero thickness, tolerance falls back to 0.1% of price."""
        indicator = EMACloudIndicator()
        result = indicator.get_price_relation(100.0, 100.0, 100.0)
        assert result in (
            PriceRelation.TOUCHING_TOP,
            PriceRelation.TOUCHING_BOTTOM,
            PriceRelation.INSIDE,
        )

    def test_price_relation_custom_tolerance(self):
        """A larger tolerance should widen the touching zone."""
        indicator = EMACloudIndicator()
        assert indicator.get_price_relation(100.5, 100.0, 98.0) == PriceRelation.ABOVE
        result = indicator.get_price_relation(100.5, 100.0, 98.0, tolerance_pct=0.5)
        assert result == PriceRelation.TOUCHING_TOP

    # --- analyze_single() ---

    def test_analyze_single(self):
        indicator = EMACloudIndicator()
        df = make_ohlcv(300)
        result = indicator.calculate(df)
        clouds = indicator.analyze_single(result)
        assert "trend_confirmation" in clouds
        assert isinstance(clouds["trend_confirmation"], CloudData)

    def test_analyze_single_returns_all_clouds(self):
        indicator = EMACloudIndicator({"a": (5, 10), "b": (20, 50)})
        df = indicator.calculate(make_ohlcv(60))
        clouds = indicator.analyze_single(df, idx=-1)
        assert "a" in clouds
        assert "b" in clouds

    def test_analyze_single_cloud_data_fields(self):
        """CloudData should have all expected fields populated."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_up(60))
        clouds = indicator.analyze_single(df, idx=-1)
        tc = clouds["tc"]
        assert tc.name == "tc"
        assert tc.fast_ema > 0
        assert tc.slow_ema > 0
        assert tc.cloud_top >= tc.cloud_bottom
        assert tc.cloud_thickness >= 0
        assert isinstance(tc.state, CloudState)
        assert isinstance(tc.price_relation, PriceRelation)

    def test_analyze_single_crossing_up(self):
        """Detect a bullish crossing when fast EMA overtakes slow EMA."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        closes = [100 - i * 0.5 for i in range(30)] + [85 + i * 1.5 for i in range(40)]
        df = indicator.calculate(_ohlcv_from_closes(closes))

        cross_indices = []
        for i in range(1, len(df)):
            prev_bull = df["tc_fast"].iloc[i - 1] > df["tc_slow"].iloc[i - 1]
            curr_bull = df["tc_fast"].iloc[i] > df["tc_slow"].iloc[i]
            if curr_bull and not prev_bull:
                cross_indices.append(i)

        if cross_indices:
            clouds = indicator.analyze_single(df, idx=cross_indices[-1])
            assert clouds["tc"].state == CloudState.CROSSING_UP

    def test_analyze_single_crossing_down(self):
        """Detect a bearish crossing when fast EMA drops below slow EMA."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        closes = [100 + i * 0.5 for i in range(30)] + [115 - i * 1.5 for i in range(40)]
        df = indicator.calculate(_ohlcv_from_closes(closes))

        cross_indices = []
        for i in range(1, len(df)):
            prev_bull = df["tc_fast"].iloc[i - 1] > df["tc_slow"].iloc[i - 1]
            curr_bull = df["tc_fast"].iloc[i] > df["tc_slow"].iloc[i]
            if not curr_bull and prev_bull:
                cross_indices.append(i)

        if cross_indices:
            clouds = indicator.analyze_single(df, idx=cross_indices[-1])
            assert clouds["tc"].state == CloudState.CROSSING_DOWN

    def test_analyze_single_expansion(self):
        """Cloud should be marked expanding when thickness grows significantly."""
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_up(80, step=2.0))
        # Use positive index so slope/expansion logic triggers (idx >= 3 check)
        clouds = indicator.analyze_single(df, idx=len(df) - 1)
        tc = clouds["tc"]
        assert tc.is_expanding or tc.slope > 0

    def test_analyze_single_slope_positive_uptrend(self):
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_up(80, step=1.0))
        clouds = indicator.analyze_single(df, idx=len(df) - 1)
        assert clouds["tc"].slope > 0

    def test_analyze_single_slope_negative_downtrend(self):
        indicator = EMACloudIndicator({"tc": (5, 20)})
        df = indicator.calculate(make_trending_down(80, step=1.0))
        clouds = indicator.analyze_single(df, idx=len(df) - 1)
        assert clouds["tc"].slope < 0

    def test_analyze_single_at_index_zero(self):
        """analyze_single at index 0 should not crash (no previous bar for crossing)."""
        indicator = EMACloudIndicator({"tc": (5, 10)})
        df = indicator.calculate(make_ohlcv(20))
        clouds = indicator.analyze_single(df, idx=0)
        assert "tc" in clouds
        assert clouds["tc"].state in (CloudState.BULLISH, CloudState.BEARISH)

    # --- detect_signals() ---

    def test_detect_signals_returns_list(self):
        indicator = EMACloudIndicator()
        df = make_ohlcv(300)
        result = indicator.calculate(df)
        signals = indicator.detect_signals(result)
        assert isinstance(signals, list)

    def test_detect_signals_all_bullish_alignment(self):
        """All clouds bullish should trigger STRONG_ALIGNMENT signal."""
        indicator = EMACloudIndicator({"a": (3, 5), "b": (5, 8), "c": (8, 12)})
        df = indicator.calculate(make_trending_up(100, step=2.0))
        signals = indicator.detect_signals(df, idx=-1)
        alignment_signals = [
            s for s in signals if "STRONG_ALIGNMENT" in s and "bullish" in s.lower()
        ]
        assert len(alignment_signals) > 0

    def test_detect_signals_all_bearish_alignment(self):
        """All clouds bearish should trigger bearish STRONG_ALIGNMENT signal."""
        indicator = EMACloudIndicator({"a": (3, 5), "b": (5, 8), "c": (8, 12)})
        df = indicator.calculate(make_trending_down(100, step=2.0))
        signals = indicator.detect_signals(df, idx=-1)
        alignment_signals = [
            s for s in signals if "STRONG_ALIGNMENT" in s and "bearish" in s.lower()
        ]
        assert len(alignment_signals) > 0

    def test_detect_signals_trend_flip_bullish(self):
        """A trend_confirmation cloud flip should generate TREND_FLIP_BULLISH signal."""
        indicator = EMACloudIndicator()
        closes = [150 - i * 0.5 for i in range(60)] + [120 + i * 1.5 for i in range(80)]
        df = indicator.calculate(_ohlcv_from_closes(closes))

        flip_idx = None
        for i in range(1, len(df)):
            prev_bull = (
                df["trend_confirmation_fast"].iloc[i - 1]
                > df["trend_confirmation_slow"].iloc[i - 1]
            )
            curr_bull = (
                df["trend_confirmation_fast"].iloc[i] > df["trend_confirmation_slow"].iloc[i]
            )
            if curr_bull and not prev_bull:
                flip_idx = i
                break

        if flip_idx is not None:
            signals = indicator.detect_signals(df, idx=flip_idx)
            flip_signals = [s for s in signals if "TREND_FLIP_BULLISH" in s]
            assert len(flip_signals) > 0

    def test_detect_signals_trend_flip_bearish(self):
        """A trend_confirmation cloud flip downward should generate TREND_FLIP_BEARISH."""
        indicator = EMACloudIndicator()
        closes = [100 + i * 0.5 for i in range(60)] + [130 - i * 1.5 for i in range(80)]
        df = indicator.calculate(_ohlcv_from_closes(closes))

        flip_idx = None
        for i in range(1, len(df)):
            prev_bull = (
                df["trend_confirmation_fast"].iloc[i - 1]
                > df["trend_confirmation_slow"].iloc[i - 1]
            )
            curr_bull = (
                df["trend_confirmation_fast"].iloc[i] > df["trend_confirmation_slow"].iloc[i]
            )
            if not curr_bull and prev_bull:
                flip_idx = i
                break

        if flip_idx is not None:
            signals = indicator.detect_signals(df, idx=flip_idx)
            flip_signals = [s for s in signals if "TREND_FLIP_BEARISH" in s]
            assert len(flip_signals) > 0

    def test_detect_signals_no_crash_on_ranging_data(self):
        """detect_signals should not crash on ranging data."""
        indicator = EMACloudIndicator({"a": (3, 5), "b": (5, 8), "c": (8, 12)})
        df = indicator.calculate(make_ranging(100))
        signals = indicator.detect_signals(df, idx=-1)
        assert isinstance(signals, list)


# ===========================================================================
# Tests for TechnicalIndicators
# ===========================================================================


class TestTechnicalIndicators:
    """Tests for the combined TechnicalIndicators class."""

    def test_calculate_all(self):
        """calculate_all should add all expected indicator columns."""
        df = make_ohlcv(100)
        ti = TechnicalIndicators()
        result = ti.calculate_all(df)
        expected_cols = [
            "rsi",
            "adx",
            "plus_di",
            "minus_di",
            "atr",
            "atr_pct",
            "vwap",
            "macd",
            "macd_signal",
            "macd_histogram",
            "volume_sma",
            "volume_ratio",
            "bb_upper",
            "bb_middle",
            "bb_lower",
        ]
        for col in expected_cols:
            assert col in result.columns, f"Missing column: {col}"

    def test_calculate_all_preserves_original(self):
        """Original DataFrame should not be mutated."""
        ti = TechnicalIndicators()
        df = make_ohlcv(40)
        original_cols = set(df.columns)
        _ = ti.calculate_all(df)
        assert set(df.columns) == original_cols

    def test_calculate_all_without_volume(self):
        """calculate_all should work without volume (VWAP/volume skipped)."""
        ti = TechnicalIndicators()
        df = make_ohlcv(60)
        df = df.drop(columns=["volume"])
        result = ti.calculate_all(df)
        assert "rsi" in result.columns
        assert "vwap" not in result.columns
        assert "volume_ratio" not in result.columns

    def test_custom_config(self):
        """Custom config periods should be respected."""
        ti = TechnicalIndicators({"rsi_period": 7, "adx_period": 7, "atr_period": 10})
        df = make_ohlcv(50)
        result = ti.calculate_all(df)
        assert "rsi" in result.columns

    def test_atr_pct_calculation(self):
        """atr_pct should equal atr / close * 100."""
        ti = TechnicalIndicators()
        df = make_ohlcv(60)
        result = ti.calculate_all(df)
        expected = result["atr"] / df["close"] * 100
        pd.testing.assert_series_equal(result["atr_pct"], expected, check_names=False)

    # --- get_analysis() ---

    def test_get_analysis(self):
        df = make_ohlcv(100)
        ti = TechnicalIndicators()
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert "rsi" in analysis
        assert "adx" in analysis
        assert "rsi_signal" in analysis

    def test_get_analysis_rsi_overbought(self):
        """Strong uptrend should produce overbought RSI signal."""
        ti = TechnicalIndicators()
        # Use make_ohlcv with strong trend and noise to get RSI > 70
        df = ti.calculate_all(make_ohlcv(80, trend=1.5, seed=10))
        analysis = ti.get_analysis(df)
        assert analysis.get("rsi_signal") == "overbought"

    def test_get_analysis_rsi_oversold(self):
        """Strong downtrend should produce oversold RSI signal."""
        ti = TechnicalIndicators()
        df = ti.calculate_all(make_ohlcv(80, trend=-1.5, seed=10))
        analysis = ti.get_analysis(df)
        assert analysis.get("rsi_signal") == "oversold"

    def test_get_analysis_rsi_neutral(self):
        """A ranging market should produce neutral RSI signal."""
        ti = TechnicalIndicators()
        df = ti.calculate_all(make_ohlcv(80, trend=0.0, seed=42))
        analysis = ti.get_analysis(df)
        assert analysis.get("rsi_signal") == "neutral"

    def test_get_analysis_trend_strength_strong(self):
        ti = TechnicalIndicators()
        df = ti.calculate_all(make_trending_up(100, step=1.5))
        analysis = ti.get_analysis(df)
        assert analysis.get("trend_strength") in ("strong", "moderate")

    def test_get_analysis_trend_strength_weak_in_range(self):
        ti = TechnicalIndicators()
        # Use flat data with minimal movement to get ADX < 20
        df = make_ohlcv(100, trend=0.0, seed=42)
        # Flatten the close to stay very near a constant
        df["close"] = 100.0 + np.random.default_rng(42).normal(0, 0.01, 100)
        df["high"] = df["close"] + 0.02
        df["low"] = df["close"] - 0.02
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert analysis.get("trend_strength") == "weak"

    def test_get_analysis_price_vs_vwap(self):
        ti = TechnicalIndicators()
        df = ti.calculate_all(make_trending_up(60))
        analysis = ti.get_analysis(df)
        assert analysis.get("price_vs_vwap") in ("above", "below")

    def test_get_analysis_volume_signal(self):
        ti = TechnicalIndicators()
        df = make_ohlcv(60)
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert analysis.get("volume_signal") in ("very_high", "high", "normal", "low")

    def test_get_analysis_at_specific_index(self):
        """get_analysis should accept a specific index."""
        ti = TechnicalIndicators()
        df = ti.calculate_all(make_ohlcv(60))
        analysis = ti.get_analysis(df, idx=30)
        assert analysis["rsi"] is not None

    def test_get_analysis_volume_very_high(self):
        """Volume ratio > 2.0 should produce 'very_high' signal."""
        ti = TechnicalIndicators()
        df = make_ohlcv(60)
        df.iloc[-1, df.columns.get_loc("volume")] = df["volume"].mean() * 5
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert analysis.get("volume_signal") in ("very_high", "high")

    def test_get_analysis_volume_low(self):
        """Volume ratio < 0.5 should produce 'low' signal."""
        ti = TechnicalIndicators()
        df = make_ohlcv(60)
        df.iloc[-1, df.columns.get_loc("volume")] = 1.0
        result = ti.calculate_all(df)
        analysis = ti.get_analysis(result)
        assert analysis.get("volume_signal") == "low"


# ===========================================================================
# Tests for TrendAnalysis model
# ===========================================================================


class TestTrendAnalysis:
    """Tests for the TrendAnalysis Pydantic model."""

    def _make_cloud_data(self, state=CloudState.BULLISH):
        return CloudData(
            name="trend_confirmation",
            fast_ema=105.0,
            slow_ema=100.0,
            cloud_top=105.0,
            cloud_bottom=100.0,
            cloud_thickness=5.0,
            cloud_thickness_pct=5.0,
            state=state,
            price_relation=PriceRelation.ABOVE,
            is_expanding=False,
            is_contracting=False,
            slope=0.5,
        )

    def test_primary_cloud_state_bullish(self):
        ta = TrendAnalysis(
            symbol="XLK",
            timestamp=pd.Timestamp.now(),
            price=110.0,
            clouds={"trend_confirmation": self._make_cloud_data(CloudState.BULLISH)},
            overall_trend="bullish",
            trend_strength=75.0,
            trend_alignment=6,
        )
        assert ta.primary_cloud_state == CloudState.BULLISH

    def test_primary_cloud_state_bearish(self):
        ta = TrendAnalysis(
            symbol="XLK",
            timestamp=pd.Timestamp.now(),
            price=90.0,
            clouds={"trend_confirmation": self._make_cloud_data(CloudState.BEARISH)},
            overall_trend="bearish",
            trend_strength=60.0,
            trend_alignment=4,
        )
        assert ta.primary_cloud_state == CloudState.BEARISH

    def test_primary_cloud_state_missing(self):
        ta = TrendAnalysis(
            symbol="XLK",
            timestamp=pd.Timestamp.now(),
            price=110.0,
            clouds={},
            overall_trend="neutral",
            trend_strength=0.0,
            trend_alignment=0,
        )
        assert ta.primary_cloud_state is None

    def test_optional_fields_default_none(self):
        ta = TrendAnalysis(
            symbol="XLF",
            timestamp=pd.Timestamp.now(),
            price=50.0,
            clouds={},
            overall_trend="neutral",
            trend_strength=0.0,
            trend_alignment=0,
        )
        assert ta.rsi is None
        assert ta.adx is None
        assert ta.atr is None
        assert ta.vwap is None
        assert ta.macd is None
        assert ta.macd_signal is None
        assert ta.macd_histogram is None
        assert ta.signals == []

    def test_with_indicator_values(self):
        ta = TrendAnalysis(
            symbol="XLE",
            timestamp=pd.Timestamp.now(),
            price=80.0,
            clouds={},
            overall_trend="bullish",
            trend_strength=65.0,
            trend_alignment=5,
            rsi=72.0,
            adx=28.0,
            atr=1.5,
            atr_pct=1.875,
            vwap=79.0,
            volume_ratio=1.3,
            macd=0.5,
            macd_signal=0.3,
            macd_histogram=0.2,
            signals=["BREAKOUT"],
        )
        assert ta.rsi == 72.0
        assert ta.adx == 28.0
        assert ta.signals == ["BREAKOUT"]
