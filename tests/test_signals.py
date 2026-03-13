"""
Tests for Signal generation, filtering, and strength rating.
"""

from datetime import datetime

import numpy as np
import pandas as pd

from ema_cloud_lib.config.settings import FilterConfig, SignalType
from ema_cloud_lib.indicators.ema_cloud import CloudData, CloudState, PriceRelation
from ema_cloud_lib.signals.generator import (
    FilterResult,
    Signal,
    SignalFilter,
    SignalGenerator,
    SignalStrength,
    count_bullish_clouds,
)


def make_ohlcv(n=300, base_price=100.0, trend=0.0, seed=42):
    """Create realistic OHLCV data."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = base_price + trend * np.arange(n) + rng.normal(0, 1, n).cumsum()
    high = close + rng.uniform(0.5, 2.0, n)
    low = close - rng.uniform(0.5, 2.0, n)
    volume = rng.integers(100000, 1000000, n).astype(float)
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.5, n),
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )


# --- Signal model ---


class TestSignalModel:
    def _make_signal(self, **overrides):
        defaults = {
            "symbol": "XLK",
            "signal_type": SignalType.CLOUD_FLIP_BULLISH,
            "direction": "long",
            "strength": SignalStrength.STRONG,
            "timestamp": datetime(2024, 6, 1, 10, 0),
            "price": 150.0,
            "primary_cloud_state": CloudState.BULLISH,
            "price_relation": PriceRelation.ABOVE,
            "rsi": 55.0,
            "adx": 28.0,
            "volume_ratio": 1.8,
            "suggested_stop": 145.0,
            "suggested_target": 160.0,
            "risk_reward_ratio": 2.0,
        }
        defaults.update(overrides)
        return Signal(**defaults)

    def test_is_valid_no_failures(self):
        sig = self._make_signal()
        assert sig.is_valid()

    def test_is_valid_with_failures(self):
        sig = self._make_signal(filters_failed=["volume: too low"])
        assert not sig.is_valid()

    def test_validate_bad_price(self):
        sig = self._make_signal(price=-10.0)
        issues = sig.validate()
        assert any("Invalid price" in i for i in issues)

    def test_validate_stop_above_entry_for_long(self):
        sig = self._make_signal(direction="long", suggested_stop=155.0, price=150.0)
        issues = sig.validate()
        assert any("Stop loss" in i for i in issues)

    def test_validate_poor_rr(self):
        sig = self._make_signal(risk_reward_ratio=0.5)
        issues = sig.validate()
        assert any("risk/reward" in i for i in issues)

    def test_is_actionable(self):
        sig = self._make_signal(strength=SignalStrength.STRONG, risk_reward_ratio=2.0)
        assert sig.is_actionable()

    def test_not_actionable_weak(self):
        sig = self._make_signal(strength=SignalStrength.WEAK)
        assert not sig.is_actionable()

    def test_to_dict(self):
        sig = self._make_signal()
        d = sig.to_dict()
        assert d["symbol"] == "XLK"
        assert d["direction"] == "long"
        assert d["is_valid"] is True


# --- FilterResult ---


class TestFilterResult:
    def test_bool_pass(self):
        r = FilterResult(passed=True, reason="ok", filter_name="vol")
        assert bool(r) is True

    def test_bool_fail(self):
        r = FilterResult(passed=False, reason="fail", filter_name="vol")
        assert bool(r) is False


# --- SignalFilter ---


class TestSignalFilter:
    def _make_row(self, **overrides):
        data = {
            "close": 150.0,
            "volume_ratio": 2.0,
            "rsi": 55.0,
            "adx": 25.0,
            "vwap": 148.0,
            "atr_pct": 1.5,
            "macd_histogram": 0.5,
        }
        data.update(overrides)
        return pd.Series(data)

    def test_volume_pass(self):
        f = SignalFilter(FilterConfig(volume_multiplier=1.5))
        result = f.filter_volume(self._make_row(volume_ratio=2.0))
        assert result.passed

    def test_volume_fail(self):
        f = SignalFilter(FilterConfig(volume_multiplier=1.5))
        result = f.filter_volume(self._make_row(volume_ratio=0.8))
        assert not result.passed

    def test_volume_disabled(self):
        f = SignalFilter(FilterConfig(volume_enabled=False))
        result = f.filter_volume(self._make_row(volume_ratio=0.1))
        assert result.passed

    def test_rsi_long_overbought(self):
        f = SignalFilter(FilterConfig(rsi_overbought=70.0))
        result = f.filter_rsi(self._make_row(rsi=75.0), "long")
        assert not result.passed

    def test_rsi_long_ok(self):
        f = SignalFilter(FilterConfig())
        result = f.filter_rsi(self._make_row(rsi=55.0), "long")
        assert result.passed

    def test_rsi_short_oversold(self):
        f = SignalFilter(FilterConfig(rsi_oversold=30.0))
        result = f.filter_rsi(self._make_row(rsi=25.0), "short")
        assert not result.passed

    def test_adx_strong(self):
        f = SignalFilter(FilterConfig(adx_strong_trend=30.0))
        result = f.filter_adx(self._make_row(adx=35.0))
        assert result.passed

    def test_adx_weak(self):
        f = SignalFilter(FilterConfig(adx_min_strength=20.0))
        result = f.filter_adx(self._make_row(adx=15.0))
        assert not result.passed

    def test_vwap_long_above(self):
        f = SignalFilter(FilterConfig())
        result = f.filter_vwap(self._make_row(close=150.0, vwap=148.0), "long")
        assert result.passed

    def test_vwap_long_below(self):
        f = SignalFilter(FilterConfig())
        result = f.filter_vwap(self._make_row(close=145.0, vwap=148.0), "long")
        assert not result.passed

    def test_atr_within_range(self):
        f = SignalFilter(FilterConfig(atr_min_threshold=0.5, atr_max_threshold=5.0))
        result = f.filter_atr(self._make_row(atr_pct=1.5))
        assert result.passed

    def test_atr_too_low(self):
        f = SignalFilter(FilterConfig(atr_min_threshold=0.5))
        result = f.filter_atr(self._make_row(atr_pct=0.1))
        assert not result.passed

    def test_macd_long_positive(self):
        f = SignalFilter(FilterConfig())
        result = f.filter_macd(self._make_row(macd_histogram=0.5), "long")
        assert result.passed

    def test_macd_long_negative(self):
        f = SignalFilter(FilterConfig(macd_enabled=True))
        result = f.filter_macd(self._make_row(macd_histogram=-0.5), "long")
        assert not result.passed

    def test_time_filter_within_hours(self):
        f = SignalFilter(
            FilterConfig(
                time_filter_enabled=True,
                trading_start_time="09:30",
                trading_end_time="16:00",
                avoid_first_minutes=15,
                avoid_last_minutes=15,
            )
        )
        ts = datetime(2024, 6, 1, 10, 30)
        result = f.filter_time_of_day(ts)
        assert result.passed

    def test_time_filter_too_early(self):
        f = SignalFilter(
            FilterConfig(
                time_filter_enabled=True,
                trading_start_time="09:30",
                trading_end_time="16:00",
                avoid_first_minutes=15,
                avoid_last_minutes=15,
            )
        )
        ts = datetime(2024, 6, 1, 9, 35)
        result = f.filter_time_of_day(ts)
        assert not result.passed

    def test_apply_all_filters(self):
        f = SignalFilter(FilterConfig())
        row = self._make_row()
        ts = datetime(2024, 6, 1, 10, 30)
        passed, failed = f.apply_all_filters(row, "long", ts)
        assert isinstance(passed, list)
        assert isinstance(failed, list)


# --- count_bullish_clouds ---


class TestCountBullishClouds:
    def _make_cloud(self, state):
        return CloudData(
            name="test",
            fast_ema=100.0,
            slow_ema=99.0,
            cloud_top=100.0,
            cloud_bottom=99.0,
            cloud_thickness=1.0,
            cloud_thickness_pct=1.0,
            state=state,
            price_relation=PriceRelation.ABOVE,
            is_expanding=False,
            is_contracting=False,
            slope=0.0,
        )

    def test_all_bullish(self):
        clouds = {
            "a": self._make_cloud(CloudState.BULLISH),
            "b": self._make_cloud(CloudState.CROSSING_UP),
        }
        assert count_bullish_clouds(clouds) == 2

    def test_none_bullish(self):
        clouds = {
            "a": self._make_cloud(CloudState.BEARISH),
            "b": self._make_cloud(CloudState.CROSSING_DOWN),
        }
        assert count_bullish_clouds(clouds) == 0


# --- SignalGenerator ---


class TestSignalGenerator:
    def test_prepare_data(self):
        gen = SignalGenerator()
        df = make_ohlcv(300)
        result = gen.prepare_data(df)
        assert "rsi" in result.columns
        assert "trend_confirmation_fast" in result.columns

    def test_analyze_trend(self):
        gen = SignalGenerator()
        df = make_ohlcv(300)
        prepared = gen.prepare_data(df)
        analysis = gen.analyze_trend(prepared, "XLK")
        assert analysis.symbol == "XLK"
        assert analysis.overall_trend in ("bullish", "bearish", "neutral")
        assert 0 <= analysis.trend_strength <= 100

    def test_generate_signals_returns_list(self):
        gen = SignalGenerator()
        df = make_ohlcv(300)
        signals = gen.generate_signals(df, "XLK")
        assert isinstance(signals, list)

    def test_signal_strength_enum_ordering(self):
        assert SignalStrength.VERY_STRONG.value > SignalStrength.STRONG.value
        assert SignalStrength.STRONG.value > SignalStrength.MODERATE.value
        assert SignalStrength.MODERATE.value > SignalStrength.WEAK.value
        assert SignalStrength.WEAK.value > SignalStrength.VERY_WEAK.value
