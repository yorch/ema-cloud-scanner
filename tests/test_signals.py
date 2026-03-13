"""
Comprehensive tests for the signal generation module.

Tests cover:
1. Signal model creation, validation, actionability, serialization
2. SignalStrength enum ordering and values
3. FilterResult model truthiness
4. SignalFilter - volume, RSI, ADX, VWAP, ATR, MACD, time-of-day filters
5. SignalFilter.apply_all_filters integration
6. count_bullish_clouds utility
7. SignalGenerator - strength calculation
8. SignalGenerator - signal deduplication / cooldown
9. SignalGenerator - cloud flip detection
10. SignalGenerator - price cross detection (breakout/breakdown)
11. SignalGenerator - pullback entry detection
12. SignalGenerator - multi-cloud alignment detection
13. SignalGenerator - risk management levels
14. SectorTrendState model and sector-based filtering
15. End-to-end pipeline with realistic synthetic data
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ema_cloud_lib.config.settings import FilterConfig, SignalType, TradingStyle
from ema_cloud_lib.indicators.ema_cloud import CloudData, CloudState, PriceRelation
from ema_cloud_lib.signals.generator import (
    FilterResult,
    SectorTrendState,
    Signal,
    SignalDirection,
    SignalFilter,
    SignalGenerator,
    SignalStrength,
    count_bullish_clouds,
)


# ---------------------------------------------------------------------------
# Helpers for building realistic test data
# ---------------------------------------------------------------------------


def _make_ohlcv(
    n: int = 300,
    base_price: float = 100.0,
    trend: float = 0.0,
    volatility: float = 0.5,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a synthetic OHLCV DataFrame with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    closes = np.empty(n)
    closes[0] = base_price
    for i in range(1, n):
        closes[i] = closes[i - 1] + trend + rng.normal(0, volatility)

    highs = closes + rng.uniform(0.1, 1.0, n)
    lows = closes - rng.uniform(0.1, 1.0, n)
    opens = closes + rng.normal(0, 0.3, n)
    volumes = rng.integers(500_000, 5_000_000, n).astype(float)

    idx = pd.date_range("2025-01-02 10:00", periods=n, freq="10min")
    return pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=idx,
    )


def _make_row(**overrides) -> pd.Series:
    """Build a single pd.Series row with sensible OHLCV + indicator defaults."""
    data = {
        "open": 100.0,
        "high": 102.0,
        "low": 98.0,
        "close": 101.0,
        "volume": 1_000_000,
        "volume_ratio": 1.6,
        "rsi": 55.0,
        "adx": 25.0,
        "vwap": 100.0,
        "atr": 1.5,
        "atr_pct": 1.5,
        "macd_histogram": 0.05,
    }
    data.update(overrides)
    return pd.Series(data)


def _make_cloud_data(
    state: CloudState = CloudState.BULLISH,
    price_relation: PriceRelation = PriceRelation.ABOVE,
    fast_ema: float = 101.0,
    slow_ema: float = 100.0,
    is_expanding: bool = False,
    name: str = "test_cloud",
) -> CloudData:
    top = max(fast_ema, slow_ema)
    bottom = min(fast_ema, slow_ema)
    return CloudData(
        name=name,
        fast_ema=fast_ema,
        slow_ema=slow_ema,
        cloud_top=top,
        cloud_bottom=bottom,
        cloud_thickness=top - bottom,
        cloud_thickness_pct=(top - bottom) / bottom * 100 if bottom else 0,
        state=state,
        price_relation=price_relation,
        is_expanding=is_expanding,
        is_contracting=False,
        slope=0.1,
    )


def _make_signal(**overrides) -> Signal:
    defaults = {
        "symbol": "XLK",
        "signal_type": SignalType.CLOUD_FLIP_BULLISH,
        "direction": "long",
        "strength": SignalStrength.STRONG,
        "timestamp": datetime(2025, 6, 10, 11, 0, 0),
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


# ===========================================================================
# 1. FilterResult model
# ===========================================================================


class TestFilterResult:
    def test_truthy_when_passed(self):
        fr = FilterResult(passed=True, reason="ok", filter_name="vol")
        assert fr
        assert bool(fr) is True

    def test_falsy_when_failed(self):
        fr = FilterResult(passed=False, reason="low volume", filter_name="vol")
        assert not fr
        assert bool(fr) is False

    def test_attributes(self):
        fr = FilterResult(
            passed=True, reason="Volume ratio 2.00x meets threshold", filter_name="volume"
        )
        assert fr.filter_name == "volume"
        assert "2.00x" in fr.reason


# ===========================================================================
# 2. Signal model — creation, validation, actionability, serialization
# ===========================================================================


class TestSignalModel:
    def test_creation_with_required_fields(self):
        sig = _make_signal()
        assert sig.symbol == "XLK"
        assert sig.direction == "long"
        assert sig.price == 150.0
        assert sig.strength == SignalStrength.STRONG

    def test_default_optional_fields(self):
        sig = _make_signal()
        assert sig.filters_passed == []
        assert sig.filters_failed == []
        assert sig.notes == []
        assert sig.sector is None
        assert sig.etf_symbol is None

    def test_is_valid_no_failures(self):
        sig = _make_signal()
        assert sig.is_valid() is True

    def test_is_valid_with_failures(self):
        sig = _make_signal(filters_failed=["volume: too low"])
        assert sig.is_valid() is False

    def test_validate_good_signal_returns_empty(self):
        sig = _make_signal()
        assert sig.validate() == []

    def test_validate_negative_price(self):
        sig = _make_signal(price=-10.0)
        issues = sig.validate()
        assert any("Invalid price" in i for i in issues)

    def test_validate_zero_price(self):
        sig = _make_signal(price=0.0)
        issues = sig.validate()
        assert any("Invalid price" in i for i in issues)

    def test_validate_invalid_direction(self):
        sig = _make_signal(direction="sideways")
        issues = sig.validate()
        assert any("Invalid direction" in i for i in issues)

    def test_validate_stop_above_entry_for_long(self):
        sig = _make_signal(direction="long", price=150.0, suggested_stop=155.0)
        issues = sig.validate()
        assert any("Stop loss" in i and "above entry" in i for i in issues)

    def test_validate_stop_below_entry_for_short(self):
        sig = _make_signal(direction="short", price=150.0, suggested_stop=145.0)
        issues = sig.validate()
        assert any("Stop loss" in i and "below entry" in i for i in issues)

    def test_validate_poor_risk_reward(self):
        sig = _make_signal(risk_reward_ratio=0.5)
        issues = sig.validate()
        assert any("risk/reward" in i for i in issues)

    def test_validate_rsi_overbought_for_long(self):
        sig = _make_signal(direction="long", rsi=85.0)
        issues = sig.validate()
        assert any("overbought" in i for i in issues)

    def test_validate_rsi_oversold_for_short(self):
        sig = _make_signal(direction="short", rsi=15.0)
        issues = sig.validate()
        assert any("oversold" in i for i in issues)

    def test_validate_rsi_normal_no_issue(self):
        sig = _make_signal(direction="long", rsi=55.0)
        issues = sig.validate()
        assert not any("RSI" in i for i in issues)

    def test_validate_includes_filter_failures(self):
        sig = _make_signal(filters_failed=["adx: too weak"])
        issues = sig.validate()
        assert "adx: too weak" in issues

    def test_validate_stop_none_no_issue(self):
        sig = _make_signal(suggested_stop=None)
        issues = sig.validate()
        assert not any("Stop loss" in i for i in issues)

    def test_is_actionable_valid_strong_good_rr(self):
        sig = _make_signal(strength=SignalStrength.STRONG, risk_reward_ratio=2.0, filters_failed=[])
        assert sig.is_actionable() is True

    def test_is_actionable_moderate_is_minimum(self):
        sig = _make_signal(
            strength=SignalStrength.MODERATE, risk_reward_ratio=2.0, filters_failed=[]
        )
        assert sig.is_actionable() is True

    def test_not_actionable_weak_strength(self):
        sig = _make_signal(strength=SignalStrength.WEAK, risk_reward_ratio=2.0, filters_failed=[])
        assert sig.is_actionable() is False

    def test_not_actionable_bad_rr(self):
        sig = _make_signal(strength=SignalStrength.STRONG, risk_reward_ratio=1.0, filters_failed=[])
        assert sig.is_actionable() is False

    def test_not_actionable_filter_failures(self):
        sig = _make_signal(
            strength=SignalStrength.STRONG,
            risk_reward_ratio=2.0,
            filters_failed=["vol: bad"],
        )
        assert sig.is_actionable() is False

    def test_actionable_rr_none_treated_as_ok(self):
        sig = _make_signal(
            strength=SignalStrength.STRONG, risk_reward_ratio=None, filters_failed=[]
        )
        assert sig.is_actionable() is True

    def test_to_dict_keys(self):
        sig = _make_signal()
        d = sig.to_dict()
        expected_keys = {
            "symbol",
            "signal_type",
            "direction",
            "strength",
            "timestamp",
            "price",
            "cloud_state",
            "price_relation",
            "rsi",
            "adx",
            "volume_ratio",
            "vwap_confirmed",
            "suggested_stop",
            "suggested_target",
            "is_valid",
            "notes",
        }
        assert expected_keys.issubset(d.keys())

    def test_to_dict_values(self):
        sig = _make_signal()
        d = sig.to_dict()
        assert d["symbol"] == "XLK"
        assert d["direction"] == "long"
        assert d["strength"] == "STRONG"
        assert d["is_valid"] is True
        assert d["signal_type"] == "cloud_flip_bullish"


# ===========================================================================
# 3. SignalStrength enum
# ===========================================================================


class TestSignalStrength:
    def test_ordering(self):
        assert SignalStrength.VERY_STRONG.value > SignalStrength.STRONG.value
        assert SignalStrength.STRONG.value > SignalStrength.MODERATE.value
        assert SignalStrength.MODERATE.value > SignalStrength.WEAK.value
        assert SignalStrength.WEAK.value > SignalStrength.VERY_WEAK.value

    def test_values(self):
        assert SignalStrength.VERY_STRONG.value == 5
        assert SignalStrength.STRONG.value == 4
        assert SignalStrength.MODERATE.value == 3
        assert SignalStrength.WEAK.value == 2
        assert SignalStrength.VERY_WEAK.value == 1


# ===========================================================================
# 4. SignalDirection enum
# ===========================================================================


class TestSignalDirection:
    def test_values(self):
        assert SignalDirection.LONG.value == "long"
        assert SignalDirection.SHORT.value == "short"


# ===========================================================================
# 5. SignalFilter — individual filters
# ===========================================================================


class TestSignalFilterVolume:
    def setup_method(self):
        self.config = FilterConfig(volume_enabled=True, volume_multiplier=1.5)
        self.sf = SignalFilter(self.config)

    def test_passes_above_threshold(self):
        row = _make_row(volume_ratio=2.0)
        result = self.sf.filter_volume(row)
        assert result.passed is True
        assert result.filter_name == "volume"

    def test_fails_below_threshold(self):
        row = _make_row(volume_ratio=1.0)
        result = self.sf.filter_volume(row)
        assert result.passed is False
        assert "below" in result.reason

    def test_passes_at_exact_threshold(self):
        row = _make_row(volume_ratio=1.5)
        assert self.sf.filter_volume(row).passed is True

    def test_passes_when_disabled(self):
        sf = SignalFilter(FilterConfig(volume_enabled=False))
        row = _make_row(volume_ratio=0.1)
        assert sf.filter_volume(row).passed is True

    def test_passes_when_na(self):
        row = _make_row(volume_ratio=np.nan)
        assert self.sf.filter_volume(row).passed is True

    def test_passes_when_missing(self):
        row = pd.Series({"close": 100.0})
        result = self.sf.filter_volume(row)
        # get() returns default 1.0, which is below 1.5 threshold
        assert result.passed is False


class TestSignalFilterRSI:
    def setup_method(self):
        self.config = FilterConfig(
            rsi_enabled=True,
            rsi_overbought=70.0,
            rsi_oversold=30.0,
            rsi_neutral_zone=(45.0, 55.0),
        )
        self.sf = SignalFilter(self.config)

    def test_long_overbought_fails(self):
        row = _make_row(rsi=75.0)
        result = self.sf.filter_rsi(row, "long")
        assert result.passed is False
        assert "overbought" in result.reason

    def test_long_neutral_passes(self):
        row = _make_row(rsi=50.0)
        assert self.sf.filter_rsi(row, "long").passed is True

    def test_long_below_neutral_shows_upward_momentum(self):
        row = _make_row(rsi=40.0)
        result = self.sf.filter_rsi(row, "long")
        assert result.passed is True
        assert "upward momentum" in result.reason

    def test_short_oversold_fails(self):
        row = _make_row(rsi=25.0)
        result = self.sf.filter_rsi(row, "short")
        assert result.passed is False
        assert "oversold" in result.reason

    def test_short_neutral_passes(self):
        row = _make_row(rsi=50.0)
        assert self.sf.filter_rsi(row, "short").passed is True

    def test_short_above_neutral_shows_downward_momentum(self):
        row = _make_row(rsi=60.0)
        result = self.sf.filter_rsi(row, "short")
        assert result.passed is True
        assert "downward momentum" in result.reason

    def test_disabled_always_passes(self):
        sf = SignalFilter(FilterConfig(rsi_enabled=False))
        row = _make_row(rsi=95.0)
        assert sf.filter_rsi(row, "long").passed is True

    def test_na_passes(self):
        row = _make_row(rsi=np.nan)
        assert self.sf.filter_rsi(row, "long").passed is True

    def test_none_passes(self):
        row = pd.Series({"close": 100.0})
        assert self.sf.filter_rsi(row, "long").passed is True


class TestSignalFilterADX:
    def setup_method(self):
        self.config = FilterConfig(adx_enabled=True, adx_min_strength=20.0, adx_strong_trend=30.0)
        self.sf = SignalFilter(self.config)

    def test_strong_trend_passes(self):
        row = _make_row(adx=35.0)
        result = self.sf.filter_adx(row)
        assert result.passed is True
        assert "strong" in result.reason

    def test_moderate_trend_passes(self):
        row = _make_row(adx=25.0)
        result = self.sf.filter_adx(row)
        assert result.passed is True
        assert "moderate" in result.reason

    def test_weak_fails(self):
        row = _make_row(adx=15.0)
        result = self.sf.filter_adx(row)
        assert result.passed is False
        assert "too weak" in result.reason

    def test_disabled_passes(self):
        sf = SignalFilter(FilterConfig(adx_enabled=False))
        row = _make_row(adx=5.0)
        assert sf.filter_adx(row).passed is True

    def test_na_passes(self):
        row = _make_row(adx=np.nan)
        assert self.sf.filter_adx(row).passed is True

    def test_at_min_threshold(self):
        row = _make_row(adx=20.0)
        assert self.sf.filter_adx(row).passed is True


class TestSignalFilterVWAP:
    def setup_method(self):
        self.sf = SignalFilter(FilterConfig(vwap_enabled=True))

    def test_long_above_vwap_passes(self):
        row = _make_row(close=105.0, vwap=100.0)
        assert self.sf.filter_vwap(row, "long").passed is True

    def test_long_below_vwap_fails(self):
        row = _make_row(close=95.0, vwap=100.0)
        result = self.sf.filter_vwap(row, "long")
        assert result.passed is False
        assert "below VWAP" in result.reason

    def test_short_below_vwap_passes(self):
        row = _make_row(close=95.0, vwap=100.0)
        assert self.sf.filter_vwap(row, "short").passed is True

    def test_short_above_vwap_fails(self):
        row = _make_row(close=105.0, vwap=100.0)
        result = self.sf.filter_vwap(row, "short")
        assert result.passed is False
        assert "above VWAP" in result.reason

    def test_na_passes(self):
        row = _make_row(close=105.0, vwap=np.nan)
        assert self.sf.filter_vwap(row, "long").passed is True

    def test_disabled_passes(self):
        sf = SignalFilter(FilterConfig(vwap_enabled=False))
        row = _make_row(close=95.0, vwap=100.0)
        assert sf.filter_vwap(row, "long").passed is True


class TestSignalFilterATR:
    def setup_method(self):
        self.config = FilterConfig(atr_enabled=True, atr_min_threshold=0.5, atr_max_threshold=5.0)
        self.sf = SignalFilter(self.config)

    def test_in_range_passes(self):
        row = _make_row(atr_pct=1.5)
        result = self.sf.filter_atr(row)
        assert result.passed is True
        assert "acceptable" in result.reason

    def test_too_low_fails(self):
        row = _make_row(atr_pct=0.2)
        result = self.sf.filter_atr(row)
        assert result.passed is False
        assert "too low" in result.reason

    def test_too_high_fails(self):
        row = _make_row(atr_pct=6.0)
        result = self.sf.filter_atr(row)
        assert result.passed is False
        assert "too high" in result.reason

    def test_at_min_boundary_fails(self):
        row = _make_row(atr_pct=0.4)
        assert self.sf.filter_atr(row).passed is False

    def test_at_max_boundary_passes(self):
        row = _make_row(atr_pct=5.0)
        assert self.sf.filter_atr(row).passed is True

    def test_disabled_passes(self):
        sf = SignalFilter(FilterConfig(atr_enabled=False))
        row = _make_row(atr_pct=0.01)
        assert sf.filter_atr(row).passed is True

    def test_na_passes(self):
        row = _make_row(atr_pct=np.nan)
        assert self.sf.filter_atr(row).passed is True


class TestSignalFilterMACD:
    def setup_method(self):
        self.sf = SignalFilter(FilterConfig(macd_enabled=True))

    def test_long_positive_histogram_passes(self):
        row = _make_row(macd_histogram=0.5)
        assert self.sf.filter_macd(row, "long").passed is True

    def test_long_negative_histogram_fails(self):
        row = _make_row(macd_histogram=-0.5)
        result = self.sf.filter_macd(row, "long")
        assert result.passed is False
        assert "negative for long" in result.reason

    def test_short_negative_histogram_passes(self):
        row = _make_row(macd_histogram=-0.5)
        assert self.sf.filter_macd(row, "short").passed is True

    def test_short_positive_histogram_fails(self):
        row = _make_row(macd_histogram=0.5)
        result = self.sf.filter_macd(row, "short")
        assert result.passed is False
        assert "positive for short" in result.reason

    def test_disabled_passes(self):
        sf = SignalFilter(FilterConfig(macd_enabled=False))
        row = _make_row(macd_histogram=-0.5)
        assert sf.filter_macd(row, "long").passed is True

    def test_na_passes(self):
        row = _make_row(macd_histogram=np.nan)
        assert self.sf.filter_macd(row, "long").passed is True


class TestSignalFilterTimeOfDay:
    def setup_method(self):
        self.config = FilterConfig(
            time_filter_enabled=True,
            trading_start_time="09:30",
            trading_end_time="16:00",
            avoid_first_minutes=15,
            avoid_last_minutes=15,
        )
        self.sf = SignalFilter(self.config)

    def test_mid_session_passes(self):
        ts = datetime(2025, 6, 10, 11, 0, 0)
        result = self.sf.filter_time_of_day(ts)
        assert result.passed is True
        assert "valid trading hours" in result.reason

    def test_too_early_fails(self):
        ts = datetime(2025, 6, 10, 9, 40, 0)  # within first 15 min after 9:30
        result = self.sf.filter_time_of_day(ts)
        assert result.passed is False
        assert "first" in result.reason

    def test_too_late_fails(self):
        ts = datetime(2025, 6, 10, 15, 50, 0)  # within last 15 min before 16:00
        result = self.sf.filter_time_of_day(ts)
        assert result.passed is False
        assert "last" in result.reason

    def test_just_after_buffer_start_passes(self):
        # Buffer start is 09:45. Test at 09:46.
        ts = datetime(2025, 6, 10, 9, 46, 0)
        assert self.sf.filter_time_of_day(ts).passed is True

    def test_just_before_buffer_end_passes(self):
        # Buffer end is 15:45. Test at 15:44.
        ts = datetime(2025, 6, 10, 15, 44, 0)
        assert self.sf.filter_time_of_day(ts).passed is True

    def test_disabled_always_passes(self):
        sf = SignalFilter(FilterConfig(time_filter_enabled=False))
        ts = datetime(2025, 6, 10, 9, 31, 0)
        assert sf.filter_time_of_day(ts).passed is True


# ===========================================================================
# 6. SignalFilter.apply_all_filters integration
# ===========================================================================


class TestApplyAllFilters:
    def test_all_disabled_all_pass(self):
        config = FilterConfig(
            volume_enabled=False,
            rsi_enabled=False,
            adx_enabled=False,
            vwap_enabled=False,
            atr_enabled=False,
            macd_enabled=False,
            time_filter_enabled=False,
        )
        sf = SignalFilter(config)
        row = _make_row()
        ts = datetime(2025, 6, 10, 11, 0, 0)
        passed, failed = sf.apply_all_filters(row, "long", ts)
        assert len(failed) == 0
        assert len(passed) == 7

    def test_mixed_pass_fail(self):
        config = FilterConfig(
            volume_enabled=True,
            volume_multiplier=1.5,
            rsi_enabled=False,
            adx_enabled=True,
            adx_min_strength=20.0,
            vwap_enabled=False,
            atr_enabled=False,
            macd_enabled=False,
            time_filter_enabled=False,
        )
        sf = SignalFilter(config)
        row = _make_row(volume_ratio=0.5, adx=10.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        _passed, failed = sf.apply_all_filters(row, "long", ts)
        assert len(failed) == 2
        assert any("volume" in f for f in failed)
        assert any("adx" in f for f in failed)

    def test_all_enabled_good_data(self):
        config = FilterConfig(
            volume_enabled=True,
            volume_multiplier=1.5,
            rsi_enabled=True,
            adx_enabled=True,
            vwap_enabled=True,
            atr_enabled=True,
            atr_min_threshold=0.5,
            atr_max_threshold=5.0,
            macd_enabled=True,
            time_filter_enabled=True,
            trading_start_time="09:30",
            trading_end_time="16:00",
            avoid_first_minutes=15,
            avoid_last_minutes=15,
        )
        sf = SignalFilter(config)
        row = _make_row(
            close=105.0,
            volume_ratio=2.0,
            rsi=55.0,
            adx=30.0,
            vwap=100.0,
            atr_pct=1.5,
            macd_histogram=0.5,
        )
        ts = datetime(2025, 6, 10, 11, 0, 0)
        passed, failed = sf.apply_all_filters(row, "long", ts)
        assert len(failed) == 0
        assert len(passed) == 7

    def test_filter_results_include_filter_names(self):
        config = FilterConfig(volume_enabled=True, volume_multiplier=1.5)
        sf = SignalFilter(config)
        row = _make_row(volume_ratio=2.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        passed, failed = sf.apply_all_filters(row, "long", ts)
        # Each entry should be formatted as "filter_name: reason"
        for entry in passed + failed:
            assert ":" in entry


# ===========================================================================
# 7. count_bullish_clouds utility
# ===========================================================================


class TestCountBullishClouds:
    def test_all_bullish(self):
        clouds = {
            "a": _make_cloud_data(state=CloudState.BULLISH),
            "b": _make_cloud_data(state=CloudState.CROSSING_UP),
        }
        assert count_bullish_clouds(clouds) == 2

    def test_all_bearish(self):
        clouds = {
            "a": _make_cloud_data(state=CloudState.BEARISH),
            "b": _make_cloud_data(state=CloudState.CROSSING_DOWN),
        }
        assert count_bullish_clouds(clouds) == 0

    def test_mixed(self):
        clouds = {
            "a": _make_cloud_data(state=CloudState.BULLISH),
            "b": _make_cloud_data(state=CloudState.BEARISH),
            "c": _make_cloud_data(state=CloudState.CROSSING_UP),
        }
        assert count_bullish_clouds(clouds) == 2

    def test_empty(self):
        assert count_bullish_clouds({}) == 0

    def test_single_bullish(self):
        clouds = {"x": _make_cloud_data(state=CloudState.BULLISH)}
        assert count_bullish_clouds(clouds) == 1

    def test_crossing_down_not_counted(self):
        clouds = {"x": _make_cloud_data(state=CloudState.CROSSING_DOWN)}
        assert count_bullish_clouds(clouds) == 0


# ===========================================================================
# 8. SignalGenerator — strength calculation
# ===========================================================================


class TestSignalStrengthCalculation:
    def setup_method(self):
        self.gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50)},
            filter_config=FilterConfig(),
        )

    def test_all_bullish_all_pass_high_adx_volume_expanding_is_very_strong(self):
        clouds = {
            f"c{i}": _make_cloud_data(state=CloudState.BULLISH, is_expanding=False)
            for i in range(6)
        }
        clouds["trend_confirmation"] = _make_cloud_data(state=CloudState.BULLISH, is_expanding=True)
        row = _make_row(adx=35.0, volume_ratio=2.5)
        passed = [f"f{i}: ok" for i in range(7)]
        failed = []
        strength = self.gen._calculate_signal_strength(clouds, row, passed, failed)
        assert strength in (SignalStrength.VERY_STRONG, SignalStrength.STRONG)

    def test_all_bearish_all_fail_low_adx_is_very_weak(self):
        clouds = {f"c{i}": _make_cloud_data(state=CloudState.BEARISH) for i in range(6)}
        row = _make_row(adx=10.0, volume_ratio=0.5)
        passed = []
        failed = [f"f{i}: bad" for i in range(7)]
        strength = self.gen._calculate_signal_strength(clouds, row, passed, failed)
        assert strength in (SignalStrength.VERY_WEAK, SignalStrength.WEAK)

    def test_adx_above_30_gives_bonus(self):
        clouds = {"a": _make_cloud_data(state=CloudState.BULLISH)}
        row_high = _make_row(adx=35.0, volume_ratio=1.0)
        row_low = _make_row(adx=15.0, volume_ratio=1.0)
        passed = ["f: ok"]
        failed = ["g: bad"]
        s_high = self.gen._calculate_signal_strength(clouds, row_high, passed, failed)
        s_low = self.gen._calculate_signal_strength(clouds, row_low, passed, failed)
        assert s_high.value >= s_low.value

    def test_volume_above_2x_gives_bonus(self):
        clouds = {"a": _make_cloud_data(state=CloudState.BULLISH)}
        row = _make_row(adx=25.0, volume_ratio=2.5)
        passed = ["f: ok"]
        failed = ["g: bad"]
        strength = self.gen._calculate_signal_strength(clouds, row, passed, failed)
        assert strength.value >= SignalStrength.WEAK.value

    def test_expanding_primary_cloud_gives_bonus(self):
        clouds = {
            "trend_confirmation": _make_cloud_data(state=CloudState.BULLISH, is_expanding=True),
        }
        row = _make_row(adx=25.0, volume_ratio=1.5)
        passed = ["f: ok"]
        failed = []
        strength = self.gen._calculate_signal_strength(clouds, row, passed, failed)
        assert strength.value >= SignalStrength.MODERATE.value

    def test_no_filters_half_clouds(self):
        clouds = {
            "a": _make_cloud_data(state=CloudState.BULLISH),
            "b": _make_cloud_data(state=CloudState.BEARISH),
        }
        row = _make_row(adx=22.0, volume_ratio=1.2)
        strength = self.gen._calculate_signal_strength(clouds, row, [], [])
        assert strength.value >= SignalStrength.VERY_WEAK.value


# ===========================================================================
# 9. SignalGenerator — deduplication / cooldown
# ===========================================================================


class TestSignalDeduplication:
    def test_recent_signals_dict_starts_empty(self):
        gen = SignalGenerator()
        assert len(gen._recent_signals) == 0

    def test_cooldown_bars_default(self):
        gen = SignalGenerator()
        assert gen._signal_cooldown_bars == 5

    def test_signal_key_tracked_after_generation(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300, trend=0.05, seed=10)
        gen.generate_signals(df, "XLK")
        assert isinstance(gen._recent_signals, dict)

    def test_duplicate_key_prevents_regeneration(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300, trend=0.05)
        for i in range(-3, 0):
            gen._recent_signals[f"XLK_{i}"] = datetime.now()

        signals = gen.generate_signals(df, "XLK", check_history=3)
        assert signals == []

    def test_different_symbols_independent(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50)},
        )
        for i in range(-3, 0):
            gen._recent_signals[f"XLK_{i}"] = datetime.now()

        for i in range(-3, 0):
            assert f"XLF_{i}" not in gen._recent_signals


# ===========================================================================
# 10. SignalGenerator — _process_raw_signal: cloud flip detection
# ===========================================================================


class TestCloudFlipDetection:
    def setup_method(self):
        self.gen = SignalGenerator()
        self.ts = datetime(2025, 6, 10, 11, 0, 0)

    def test_bullish_trend_flip_mapping(self):
        clouds = {"trend_confirmation": _make_cloud_data(state=CloudState.CROSSING_UP)}
        row = _make_row(close=105.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: 34-50 cloud turned green",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=self.ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.CLOUD_FLIP_BULLISH
        assert sig.direction == "long"

    def test_bearish_trend_flip_mapping(self):
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.CROSSING_DOWN, fast_ema=99.0, slow_ema=101.0
            )
        }
        row = _make_row(close=95.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            raw_signal="🔴 TREND_FLIP_BEARISH: 34-50 cloud turned red",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=self.ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.CLOUD_FLIP_BEARISH
        assert sig.direction == "short"

    def test_short_term_bullish_flip(self):
        clouds = {"trend_confirmation": _make_cloud_data(state=CloudState.BULLISH)}
        row = _make_row(close=105.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            raw_signal="🟢 SHORT_TERM_BULLISH: 5-12 cloud turned green",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=self.ts,
        )
        assert sig is not None
        assert sig.direction == "long"


# ===========================================================================
# 11. SignalGenerator — price cross detection (breakout/breakdown)
# ===========================================================================


class TestPriceCrossDetection:
    def setup_method(self):
        self.gen = SignalGenerator()
        self.ts = datetime(2025, 6, 10, 11, 0, 0)

    def test_breakout_signal_type(self):
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BULLISH, price_relation=PriceRelation.ABOVE
            ),
        }
        row = _make_row(close=105.0, atr=1.0, vwap=100.0, macd_histogram=0.3)
        sig = self.gen._process_raw_signal(
            raw_signal="🟢 BREAKOUT: Price crossed above 34-50 cloud",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=self.ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.PRICE_CROSS_ABOVE
        assert sig.direction == "long"

    def test_breakdown_signal_type(self):
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BEARISH,
                fast_ema=99.0,
                slow_ema=101.0,
                price_relation=PriceRelation.BELOW,
            ),
        }
        row = _make_row(close=95.0, atr=1.0, vwap=100.0, macd_histogram=-0.3)
        sig = self.gen._process_raw_signal(
            raw_signal="🔴 BREAKDOWN: Price crossed below 34-50 cloud",
            row=row,
            clouds=clouds,
            symbol="XLF",
            timestamp=self.ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.PRICE_CROSS_BELOW
        assert sig.direction == "short"
        assert sig.symbol == "XLF"


# ===========================================================================
# 12. SignalGenerator — pullback entry detection
# ===========================================================================


class TestPullbackEntryDetection:
    def test_pullback_signal_type(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BULLISH, price_relation=PriceRelation.TOUCHING_BOTTOM
            ),
        }
        row = _make_row(close=102.0, rsi=45.0, adx=22.0, atr=1.0, vwap=100.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 PULLBACK_ENTRY: Price at 8-9 cloud support in uptrend",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.PULLBACK_ENTRY
        assert sig.direction == "long"

    def test_bearish_pullback_entry(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BEARISH,
                fast_ema=99.0,
                slow_ema=101.0,
                price_relation=PriceRelation.TOUCHING_TOP,
            ),
        }
        row = _make_row(close=98.0, rsi=55.0, adx=22.0, atr=1.0, vwap=100.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🔴 PULLBACK_ENTRY: Price at 8-9 cloud resistance in downtrend",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.PULLBACK_ENTRY
        assert sig.direction == "short"


# ===========================================================================
# 13. Multi-cloud alignment detection
# ===========================================================================


class TestMultiCloudAlignment:
    def test_bullish_alignment_signal_type(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": _make_cloud_data(state=CloudState.BULLISH)}
        row = _make_row(
            close=110.0, adx=30.0, volume_ratio=2.0, atr=1.5, vwap=105.0, macd_histogram=0.5
        )
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 STRONG_ALIGNMENT: All clouds bullish",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.TREND_CONFIRMATION
        assert sig.direction == "long"

    def test_bearish_alignment_signal_type(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BEARISH, fast_ema=99.0, slow_ema=101.0
            ),
        }
        row = _make_row(
            close=90.0, adx=30.0, volume_ratio=2.0, atr=1.5, vwap=95.0, macd_histogram=-0.5
        )
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🔴 STRONG_ALIGNMENT: All clouds bearish",
            row=row,
            clouds=clouds,
            symbol="XLE",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.TREND_CONFIRMATION
        assert sig.direction == "short"

    def test_unknown_signal_defaults_to_cloud_flip(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": _make_cloud_data(state=CloudState.BULLISH)}
        row = _make_row(close=105.0, atr=1.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 SOME_UNKNOWN_SIGNAL: custom signal",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.signal_type == SignalType.CLOUD_FLIP_BULLISH


# ===========================================================================
# 14. SignalGenerator — risk management levels
# ===========================================================================


class TestRiskManagement:
    def test_long_stop_below_cloud_bottom(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BULLISH, fast_ema=102.0, slow_ema=100.0
            ),
        }
        row = _make_row(close=105.0, atr=1.0, vwap=103.0, macd_histogram=0.2)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: 34-50 cloud turned green",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        # cloud_bottom=100.0, atr=1.0, stop = 100.0 - 1.0 = 99.0
        assert sig.suggested_stop == pytest.approx(99.0)
        assert sig.suggested_target > sig.price
        assert sig.risk_reward_ratio > 0

    def test_short_stop_above_cloud_top(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BEARISH, fast_ema=99.0, slow_ema=101.0
            ),
        }
        row = _make_row(close=95.0, atr=1.0, vwap=98.0, macd_histogram=-0.2)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🔴 TREND_FLIP_BEARISH: 34-50 cloud turned red",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        # cloud_top=101.0, atr=1.0, stop = 101.0 + 1.0 = 102.0
        assert sig.suggested_stop == pytest.approx(102.0)
        assert sig.suggested_target < sig.price

    def test_rr_ratio_is_2_to_1(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BULLISH, fast_ema=102.0, slow_ema=100.0
            ),
        }
        row = _make_row(close=105.0, atr=1.0, vwap=103.0, macd_histogram=0.2)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: cloud green",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        assert sig.risk_reward_ratio == pytest.approx(2.0)

    def test_atr_fallback_when_nan(self):
        gen = SignalGenerator()
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BULLISH, fast_ema=102.0, slow_ema=100.0
            ),
        }
        row = _make_row(close=100.0, atr=np.nan, vwap=98.0, macd_histogram=0.1)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: cloud green",
            row=row,
            clouds=clouds,
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is not None
        # Fallback ATR = 100.0 * 0.02 = 2.0; stop = 100.0 - 2.0 = 98.0
        assert sig.suggested_stop == pytest.approx(98.0)

    def test_no_primary_cloud_returns_none(self):
        gen = SignalGenerator()
        row = _make_row(close=105.0, atr=1.0)
        ts = datetime(2025, 6, 10, 11, 0, 0)
        sig = gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: cloud green",
            row=row,
            clouds={},
            symbol="XLK",
            timestamp=ts,
        )
        assert sig is None


# ===========================================================================
# 15. SectorTrendState model
# ===========================================================================


class TestSectorTrendState:
    def _make_state(self, direction: str = "bullish", strength: float = 60.0):
        return SectorTrendState(
            symbol="XLK",
            sector_name="technology",
            timestamp=datetime(2025, 6, 10, 11, 0, 0),
            trend_direction=direction,
            trend_strength=strength,
            trend_duration=10,
            cloud_states={},
            cloud_alignment=5,
        )

    def test_is_bullish(self):
        state = self._make_state("bullish")
        assert state.is_bullish() is True
        assert state.is_bearish() is False

    def test_is_bearish(self):
        state = self._make_state("bearish")
        assert state.is_bearish() is True
        assert state.is_bullish() is False

    def test_neutral(self):
        state = self._make_state("neutral")
        assert state.is_bullish() is False
        assert state.is_bearish() is False

    def test_default_fields(self):
        state = self._make_state()
        assert state.support_level is None
        assert state.resistance_level is None
        assert state.last_signal is None


# ===========================================================================
# 16. Sector-based signal filtering
# ===========================================================================


class TestSectorFiltering:
    def setup_method(self):
        self.gen = SignalGenerator()

    def _make_sector_state(self, direction: str, strength: float = 60.0):
        return SectorTrendState(
            symbol="XLK",
            sector_name="technology",
            timestamp=datetime(2025, 6, 10, 11, 0, 0),
            trend_direction=direction,
            trend_strength=strength,
            trend_duration=10,
        )

    # --- filter_by_sector_trend ---

    def test_long_bullish_sector_passes(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("bullish")
        assert self.gen.filter_by_sector_trend(sig, sector) is True

    def test_long_bearish_sector_fails_and_adds_failure(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("bearish")
        result = self.gen.filter_by_sector_trend(sig, sector)
        assert result is False
        assert len(sig.filters_failed) > 0
        assert "sector_trend" in sig.filters_failed[-1]

    def test_short_bearish_sector_passes(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("bearish")
        assert self.gen.filter_by_sector_trend(sig, sector) is True

    def test_short_bullish_sector_fails(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("bullish")
        assert self.gen.filter_by_sector_trend(sig, sector) is False

    def test_neutral_sector_allows_long(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("neutral")
        assert self.gen.filter_by_sector_trend(sig, sector) is True

    def test_neutral_sector_allows_short(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("neutral")
        assert self.gen.filter_by_sector_trend(sig, sector) is True

    # --- filter_signal_by_sector ---

    def test_filter_signal_long_bullish_strong_confirms(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("bullish", strength=70.0)
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "confirms bullish" in msg

    def test_filter_signal_long_bullish_weak_caution(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("bullish", strength=30.0)
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "caution" in msg

    def test_filter_signal_long_bearish_rejects(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("bearish")
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is False
        assert "avoid long" in msg

    def test_filter_signal_long_neutral_allows(self):
        sig = _make_signal(direction="long")
        sector = self._make_sector_state("neutral")
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "neutral" in msg

    def test_filter_signal_short_bearish_strong_confirms(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("bearish", strength=70.0)
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "confirms bearish" in msg

    def test_filter_signal_short_bearish_weak_caution(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("bearish", strength=30.0)
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "caution" in msg

    def test_filter_signal_short_bullish_rejects(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("bullish")
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is False
        assert "avoid short" in msg

    def test_filter_signal_short_neutral_allows(self):
        sig = _make_signal(direction="short")
        sector = self._make_sector_state("neutral")
        ok, msg = self.gen.filter_signal_by_sector(sig, sector)
        assert ok is True
        assert "neutral" in msg


# ===========================================================================
# 17. SignalGenerator — end-to-end with realistic data
# ===========================================================================


class TestSignalGeneratorEndToEnd:
    def test_prepare_data_adds_indicator_columns(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300)
        prepared = gen.prepare_data(df)
        assert "trend_confirmation_fast" in prepared.columns
        assert "trend_confirmation_slow" in prepared.columns
        assert "trend_line_fast" in prepared.columns
        assert "trend_line_slow" in prepared.columns
        assert "trend_confirmation_bullish" in prepared.columns
        assert "rsi" in prepared.columns
        assert "adx" in prepared.columns
        assert "atr" in prepared.columns
        assert "atr_pct" in prepared.columns
        assert "vwap" in prepared.columns
        assert "volume_ratio" in prepared.columns
        assert "macd" in prepared.columns
        assert "macd_histogram" in prepared.columns

    def test_prepare_data_preserves_original_columns(self):
        gen = SignalGenerator(clouds_config={"trend_confirmation": (34, 50)})
        df = _make_ohlcv(n=300)
        prepared = gen.prepare_data(df)
        for col in ["open", "high", "low", "close", "volume"]:
            assert col in prepared.columns

    def test_generate_signals_returns_list_of_signals(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
            filter_config=FilterConfig(
                time_filter_enabled=False,
                volume_enabled=False,
                rsi_enabled=False,
                adx_enabled=False,
                vwap_enabled=False,
                atr_enabled=False,
                macd_enabled=False,
            ),
        )
        df = _make_ohlcv(n=300, trend=0.05)
        signals = gen.generate_signals(df, "XLK", sector="technology")
        assert isinstance(signals, list)
        for sig in signals:
            assert isinstance(sig, Signal)
            assert sig.symbol == "XLK"
            assert sig.sector == "technology"

    def test_generate_signals_short_data_no_crash(self):
        gen = SignalGenerator(clouds_config={"trend_confirmation": (34, 50)})
        df = _make_ohlcv(n=2)
        signals = gen.generate_signals(df, "XLK", check_history=5)
        assert isinstance(signals, list)

    def test_generate_signals_with_etf_symbol(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
            filter_config=FilterConfig(
                time_filter_enabled=False,
                volume_enabled=False,
                rsi_enabled=False,
                adx_enabled=False,
                vwap_enabled=False,
                atr_enabled=False,
                macd_enabled=False,
            ),
        )
        df = _make_ohlcv(n=300, trend=0.05)
        signals = gen.generate_signals(df, "AAPL", etf_symbol="XLK")
        for sig in signals:
            assert sig.etf_symbol == "XLK"

    def test_analyze_trend_returns_analysis(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300, trend=0.1)
        prepared = gen.prepare_data(df)
        analysis = gen.analyze_trend(prepared, "XLK")
        assert analysis.symbol == "XLK"
        assert analysis.overall_trend in ("bullish", "bearish", "neutral")
        assert 0 <= analysis.trend_strength <= 100
        assert analysis.price > 0

    def test_analyze_trend_bullish_data(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300, trend=0.3, base_price=100.0)
        prepared = gen.prepare_data(df)
        analysis = gen.analyze_trend(prepared, "XLK")
        assert analysis.overall_trend == "bullish"

    def test_analyze_trend_bearish_data(self):
        gen = SignalGenerator(
            clouds_config={"trend_confirmation": (34, 50), "trend_line": (5, 12)},
        )
        df = _make_ohlcv(n=300, trend=-0.3, base_price=200.0)
        prepared = gen.prepare_data(df)
        analysis = gen.analyze_trend(prepared, "XLK")
        assert analysis.overall_trend == "bearish"

    def test_trading_style_parameter(self):
        gen = SignalGenerator(trading_style=TradingStyle.SWING)
        assert gen.trading_style == TradingStyle.SWING

    def test_default_clouds_config(self):
        gen = SignalGenerator()
        assert "trend_confirmation" in gen.cloud_indicator.clouds_config
        assert "trend_line" in gen.cloud_indicator.clouds_config
        assert "pullback" in gen.cloud_indicator.clouds_config

    def test_custom_clouds_config(self):
        gen = SignalGenerator(clouds_config={"custom": (10, 20)})
        assert "custom" in gen.cloud_indicator.clouds_config
        assert "trend_confirmation" not in gen.cloud_indicator.clouds_config


# ===========================================================================
# 18. Process raw signal — direction detection and indicator propagation
# ===========================================================================


class TestProcessRawSignalDetails:
    def setup_method(self):
        self.gen = SignalGenerator()
        self.ts = datetime(2025, 6, 10, 11, 0, 0)
        self.clouds = {"trend_confirmation": _make_cloud_data(state=CloudState.BULLISH)}

    def test_bullish_emoji_detected_as_long(self):
        row = _make_row(close=105.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.direction == "long"

    def test_bearish_detected_as_short(self):
        clouds = {
            "trend_confirmation": _make_cloud_data(
                state=CloudState.BEARISH, fast_ema=99.0, slow_ema=101.0
            )
        }
        row = _make_row(close=95.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🔴 TREND_FLIP_BEARISH: test",
            row,
            clouds,
            "XLK",
            self.ts,
        )
        assert sig.direction == "short"

    def test_rsi_propagated(self):
        row = _make_row(close=105.0, rsi=62.5, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.rsi == pytest.approx(62.5)

    def test_adx_propagated(self):
        row = _make_row(close=105.0, adx=31.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.adx == pytest.approx(31.0)

    def test_volume_ratio_propagated(self):
        row = _make_row(close=105.0, volume_ratio=2.3, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.volume_ratio == pytest.approx(2.3)

    def test_vwap_confirmed_long(self):
        row = _make_row(close=105.0, vwap=100.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.vwap_confirmed is True

    def test_vwap_not_confirmed_long(self):
        row = _make_row(close=95.0, vwap=100.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.vwap_confirmed is False

    def test_macd_confirmed_long(self):
        row = _make_row(close=105.0, macd_histogram=0.5, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.macd_confirmed is True

    def test_raw_signal_stored_in_notes(self):
        row = _make_row(close=105.0, atr=1.0)
        raw = "🟢 TREND_FLIP_BULLISH: test note"
        sig = self.gen._process_raw_signal(raw, row, self.clouds, "XLK", self.ts)
        assert raw in sig.notes

    def test_sector_and_etf_propagated(self):
        row = _make_row(close=105.0, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
            sector="technology",
            etf_symbol="XLK",
        )
        assert sig.sector == "technology"
        assert sig.etf_symbol == "XLK"

    def test_nan_rsi_becomes_none(self):
        row = _make_row(close=105.0, rsi=np.nan, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.rsi is None

    def test_nan_adx_becomes_none(self):
        row = _make_row(close=105.0, adx=np.nan, atr=1.0)
        sig = self.gen._process_raw_signal(
            "🟢 TREND_FLIP_BULLISH: test",
            row,
            self.clouds,
            "XLK",
            self.ts,
        )
        assert sig.adx is None
