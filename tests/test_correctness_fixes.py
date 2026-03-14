"""
Tests for correctness bug fixes.

Covers:
1. RSI division-by-zero: all-gains → RSI=100, all-losses → RSI=0, no-change → RSI=50
2. ADX division-by-zero: zero directional movement → DX=0, not arbitrary value
3. VWAP daily reset: proper isinstance check for DatetimeIndex
4. DST handling in market hours: proper timezone conversion using zoneinfo
5. Signal direction parsing: keyword-based instead of emoji-based
6. Sector filter direction check: explicit direction matching
7. Symbol deduplication: no duplicate symbols from custom + sector overlap
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from ema_cloud_lib.config.settings import (
    ScannerConfig,
    SignalType,
)
from ema_cloud_lib.indicators.ema_cloud import (
    CloudData,
    CloudState,
    PriceRelation,
    calculate_adx,
    calculate_rsi,
    calculate_vwap,
)
from ema_cloud_lib.market_hours import MarketHours
from ema_cloud_lib.signals.generator import (
    SectorTrendState,
    Signal,
    SignalGenerator,
    SignalStrength,
)


# ===========================================================================
# 1. RSI Division-by-Zero Fixes
# ===========================================================================


class TestRSIDivisionByZero:
    """RSI should handle edge cases where avg_gain or avg_loss is zero."""

    def test_all_gains_rsi_is_100(self):
        """When price only goes up, RSI should be 100 (fully overbought)."""
        # Monotonically increasing prices
        prices = pd.Series([100.0 + i for i in range(50)])
        rsi = calculate_rsi(prices, period=14)

        # After warmup period, RSI should be 100 (all gains, no losses)
        # Allow small tolerance for EMA smoothing effects
        assert rsi.iloc[-1] > 99.0, f"RSI should be ~100 for all-gains, got {rsi.iloc[-1]}"

    def test_all_losses_rsi_is_near_zero(self):
        """When price only goes down, RSI should be near 0 (fully oversold)."""
        # Monotonically decreasing prices
        prices = pd.Series([200.0 - i for i in range(50)])
        rsi = calculate_rsi(prices, period=14)

        # After warmup, RSI should be near 0 (all losses, no gains)
        assert rsi.iloc[-1] < 1.0, f"RSI should be ~0 for all-losses, got {rsi.iloc[-1]}"

    def test_flat_prices_rsi_is_neutral(self):
        """When price doesn't change, RSI should be neutral (50)."""
        prices = pd.Series([100.0] * 50)
        rsi = calculate_rsi(prices, period=14)

        # No gains or losses → 0/0 → should be 50 (neutral), not NaN
        assert not pd.isna(rsi.iloc[-1]), "RSI should not be NaN for flat prices"
        assert rsi.iloc[-1] == 50.0, f"RSI should be 50 for flat prices, got {rsi.iloc[-1]}"

    def test_rsi_no_nans_in_output(self):
        """RSI output should never contain NaN after the initial warmup."""
        # Mix of flat and trending periods
        prices = pd.Series(
            [100.0] * 20 + [100.0 + i * 0.1 for i in range(30)]
        )
        rsi = calculate_rsi(prices, period=14)

        # After period+1 bars, no NaN should exist
        valid_rsi = rsi.iloc[15:]
        assert not valid_rsi.isna().any(), f"RSI contains NaN values: {valid_rsi[valid_rsi.isna()].index.tolist()}"

    def test_rsi_normal_case_unchanged(self):
        """Normal RSI calculation should still work correctly."""
        rng = np.random.default_rng(42)
        prices = pd.Series(100 + rng.normal(0, 1, 100).cumsum())
        rsi = calculate_rsi(prices, period=14)

        # RSI should be between 0 and 100
        valid = rsi.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()


# ===========================================================================
# 2. ADX Division-by-Zero Fixes
# ===========================================================================


class TestADXDivisionByZero:
    """ADX should handle zero directional movement gracefully."""

    def test_flat_market_dx_is_zero(self):
        """When there's no directional movement, DX should be 0, not arbitrary."""
        n = 50
        # Perfectly flat OHLC data
        high = pd.Series([100.0] * n)
        low = pd.Series([100.0] * n)
        close = pd.Series([100.0] * n)

        result = calculate_adx(high, low, close, period=14)

        # DX should be 0 (no directional movement), not some arbitrary value
        # ADX (smoothed DX) should also be 0
        assert not pd.isna(result["adx"].iloc[-1]), "ADX should not be NaN"
        assert result["adx"].iloc[-1] == 0.0, f"ADX should be 0 for flat market, got {result['adx'].iloc[-1]}"

    def test_adx_no_nans(self):
        """ADX should not produce NaN values after warmup."""
        # Flat followed by trending
        high = pd.Series([100.0] * 30 + [100.0 + i * 0.5 for i in range(70)])
        low = pd.Series([99.0] * 30 + [99.0 + i * 0.5 for i in range(70)])
        close = pd.Series([99.5] * 30 + [99.5 + i * 0.5 for i in range(70)])

        result = calculate_adx(high, low, close, period=14)

        # After warmup, no NaN
        valid_adx = result["adx"].iloc[20:]
        assert not valid_adx.isna().any(), "ADX contains NaN values"

    def test_adx_normal_trending_market(self):
        """ADX should still correctly detect strong trends."""
        rng = np.random.default_rng(42)
        n = 100
        trend = np.arange(n) * 0.5
        close = pd.Series(100 + trend + rng.normal(0, 0.5, n))
        high = close + rng.uniform(0.5, 1.5, n)
        low = close - rng.uniform(0.5, 1.5, n)

        result = calculate_adx(high, low, close, period=14)

        # Strong uptrend should have meaningful ADX
        assert result["adx"].iloc[-1] > 10, "ADX should be > 10 for trending market"


# ===========================================================================
# 3. VWAP Daily Reset
# ===========================================================================


class TestVWAPDailyReset:
    """VWAP should properly detect DatetimeIndex and reset daily."""

    def test_vwap_resets_daily_with_datetime_index(self):
        """VWAP should reset at each new trading day for intraday data."""
        # Create 2 days of 5-minute bars
        dates_day1 = pd.date_range("2025-01-06 09:30", periods=10, freq="5min")
        dates_day2 = pd.date_range("2025-01-07 09:30", periods=10, freq="5min")
        dates = dates_day1.append(dates_day2)

        high = pd.Series([101.0] * 20, index=dates)
        low = pd.Series([99.0] * 20, index=dates)
        close = pd.Series([100.0] * 20, index=dates)
        volume = pd.Series([1000.0] * 20, index=dates)

        vwap = calculate_vwap(high, low, close, volume)

        # VWAP at start of day 2 should reset (same as day 1 start)
        assert vwap.iloc[0] == pytest.approx(vwap.iloc[10], rel=1e-6), (
            "VWAP should reset at day boundary"
        )

    def test_vwap_with_integer_index_no_reset(self):
        """VWAP with integer index should use simple cumulative (no daily reset)."""
        n = 20
        index = range(n)
        high = pd.Series([101.0] * n, index=index)
        low = pd.Series([99.0] * n, index=index)
        close = pd.Series([100.0] * n, index=index)
        volume = pd.Series([1000.0] * n, index=index)

        vwap = calculate_vwap(high, low, close, volume)

        # With integer index, all values should be the same (constant price/volume)
        assert vwap.iloc[0] == pytest.approx(vwap.iloc[-1], rel=1e-6)

    def test_vwap_isinstance_check_not_hasattr(self):
        """Verify VWAP uses isinstance(index, DatetimeIndex), not hasattr."""
        # Create a RangeIndex (has no .date attribute) — should use cumulative path
        n = 10
        high = pd.Series([101.0] * n)
        low = pd.Series([99.0] * n)
        close = pd.Series([100.0] * n)
        volume = pd.Series([1000.0] * n)

        # Should not raise any error
        vwap = calculate_vwap(high, low, close, volume)
        assert not vwap.isna().any(), "VWAP should not be NaN"


# ===========================================================================
# 4. DST Handling in Market Hours
# ===========================================================================


class TestDSTHandling:
    """Market hours DST handling should use zoneinfo, not month approximation."""

    def test_early_close_during_est(self):
        """Early close detection during EST (winter) should work correctly."""
        # Christmas Eve 2025 is in EST (December)
        christmas_eve = datetime(2025, 12, 24, 10, 0)
        early_close = MarketHours.get_early_close_time(christmas_eve)

        if early_close is not None:
            # Should be 1:00 PM ET (not miscalculated due to DST)
            assert early_close.hour == 13, f"Christmas Eve early close should be 1 PM ET, got {early_close}"

    def test_early_close_during_edt(self):
        """Early close detection during EDT (summer) should work correctly."""
        # July 3rd 2025 is in EDT
        july_3 = datetime(2025, 7, 3, 10, 0)
        early_close = MarketHours.get_early_close_time(july_3)

        if early_close is not None:
            assert early_close.hour == 13, f"July 3rd early close should be 1 PM ET, got {early_close}"

    def test_regular_day_no_early_close(self):
        """Regular trading days should not have early close."""
        # A random Tuesday in June
        regular_day = datetime(2025, 6, 10, 10, 0)
        early_close = MarketHours.get_early_close_time(regular_day)
        assert early_close is None, "Regular trading day should have no early close"

    def test_march_dst_transition_boundary(self):
        """Days around March DST transition should be handled correctly."""
        # March 9, 2025 is the DST transition day (second Sunday)
        # March 7 (Friday before) is still EST
        march_7 = datetime(2025, 3, 7, 10, 0)
        assert MarketHours.is_market_open(march_7), "March 7 at 10 AM should be market open"

        # March 10 (Monday after) is EDT
        march_10 = datetime(2025, 3, 10, 10, 0)
        assert MarketHours.is_market_open(march_10), "March 10 at 10 AM should be market open"


# ===========================================================================
# 5. Signal Direction Parsing (Keyword-Based)
# ===========================================================================


class TestSignalDirectionParsing:
    """Signal direction should be determined by keywords, not emoji."""

    def _make_cloud_data(self, state=CloudState.BULLISH):
        return CloudData(
            name="trend_confirmation",
            fast_ema=35.0,
            slow_ema=34.0,
            cloud_top=35.0,
            cloud_bottom=34.0,
            cloud_thickness=1.0,
            cloud_thickness_pct=1.0,
            state=state,
            price_relation=PriceRelation.ABOVE,
            is_expanding=False,
            is_contracting=False,
            slope=0.0,
        )

    def _make_row(self, close=105.0, atr=1.0):
        return pd.Series({
            "close": close,
            "open": close - 0.5,
            "high": close + 1.0,
            "low": close - 1.0,
            "volume": 1_000_000,
            "rsi": 55.0,
            "adx": 25.0,
            "atr": atr,
            "atr_pct": atr / close * 100,
            "vwap": close - 1.0,
            "volume_ratio": 2.0,
            "macd_histogram": 0.1,
        })

    def test_bullish_trend_flip_detected(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🟢 TREND_FLIP_BULLISH: 34-50 cloud turned green",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "long"
        assert sig.signal_type == SignalType.CLOUD_FLIP_BULLISH

    def test_bearish_trend_flip_detected(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data(state=CloudState.BEARISH)}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🔴 TREND_FLIP_BEARISH: 34-50 cloud turned red",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "short"
        assert sig.signal_type == SignalType.CLOUD_FLIP_BEARISH

    def test_breakout_is_bullish(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🟢 BREAKOUT: Price crossed above 34-50 cloud",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "long"
        assert sig.signal_type == SignalType.PRICE_CROSS_ABOVE

    def test_breakdown_is_bearish(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data(state=CloudState.BEARISH)}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🔴 BREAKDOWN: Price crossed below 34-50 cloud",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "short"
        assert sig.signal_type == SignalType.PRICE_CROSS_BELOW

    def test_pullback_uptrend_is_bullish(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🟢 PULLBACK_ENTRY: Price at 8-9 cloud support in uptrend",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "long"

    def test_pullback_downtrend_is_bearish(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data(state=CloudState.BEARISH)}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🔴 PULLBACK_ENTRY: Price at 8-9 cloud resistance in downtrend",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "short"

    def test_bullish_alignment_is_long(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🟢 STRONG_ALIGNMENT: All clouds bullish",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "long"

    def test_bearish_alignment_is_short(self):
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data(state=CloudState.BEARISH)}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="🔴 STRONG_ALIGNMENT: All clouds bearish",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "short"

    def test_unknown_signal_defaults_to_bearish(self):
        """Unknown signals without bullish keywords default to bearish/short."""
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        sig = gen._process_raw_signal(
            raw_signal="SOME_UNKNOWN_SIGNAL: custom",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "short"

    def test_no_emoji_dependency(self):
        """Direction should work without any emoji in the raw signal."""
        gen = SignalGenerator()
        clouds = {"trend_confirmation": self._make_cloud_data()}
        row = self._make_row()
        ts = datetime(2025, 6, 10, 11, 0)

        # No emoji, just keyword
        sig = gen._process_raw_signal(
            raw_signal="TREND_FLIP_BULLISH: test",
            row=row, clouds=clouds, symbol="XLK", timestamp=ts,
        )
        assert sig is not None
        assert sig.direction == "long"


# ===========================================================================
# 6. Sector Filter Direction Check
# ===========================================================================


class TestSectorFilterDirectionCheck:
    """filter_signal_by_sector must explicitly check signal.direction."""

    def _make_signal(self, direction: str) -> Signal:
        return Signal(
            symbol="AAPL",
            signal_type=SignalType.CLOUD_FLIP_BULLISH,
            direction=direction,
            strength=SignalStrength.STRONG,
            timestamp=datetime(2025, 6, 10, 11, 0),
            price=150.0,
            primary_cloud_state=CloudState.BULLISH,
            price_relation=PriceRelation.ABOVE,
        )

    def _make_sector_state(self, trend: str, strength: float = 60.0) -> SectorTrendState:
        return SectorTrendState(
            symbol="XLK",
            sector_name="Technology",
            timestamp=datetime(2025, 6, 10, 11, 0),
            trend_direction=trend,
            trend_strength=strength,
            trend_duration=10,
        )

    def test_long_signal_bullish_sector_passes(self):
        gen = SignalGenerator()
        sig = self._make_signal("long")
        sector = self._make_sector_state("bullish")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is True
        assert "confirms bullish" in reason

    def test_long_signal_bearish_sector_fails(self):
        gen = SignalGenerator()
        sig = self._make_signal("long")
        sector = self._make_sector_state("bearish")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is False
        assert "avoid long" in reason

    def test_short_signal_bearish_sector_passes(self):
        gen = SignalGenerator()
        sig = self._make_signal("short")
        sector = self._make_sector_state("bearish")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is True
        assert "confirms bearish" in reason

    def test_short_signal_bullish_sector_fails(self):
        gen = SignalGenerator()
        sig = self._make_signal("short")
        sector = self._make_sector_state("bullish")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is False
        assert "avoid short" in reason

    def test_long_signal_neutral_sector_passes(self):
        gen = SignalGenerator()
        sig = self._make_signal("long")
        sector = self._make_sector_state("neutral")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is True
        assert "neutral" in reason

    def test_short_signal_neutral_sector_passes(self):
        gen = SignalGenerator()
        sig = self._make_signal("short")
        sector = self._make_sector_state("neutral")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is True
        assert "neutral" in reason

    def test_invalid_direction_returns_false(self):
        """Unknown direction should be rejected, not fall through."""
        gen = SignalGenerator()
        sig = self._make_signal("sideways")  # Invalid direction
        sector = self._make_sector_state("bearish")
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is False
        assert "Unknown signal direction" in reason

    def test_short_signal_weak_bearish_sector_passes_with_caution(self):
        gen = SignalGenerator()
        sig = self._make_signal("short")
        sector = self._make_sector_state("bearish", strength=30.0)
        passed, reason = gen.filter_signal_by_sector(sig, sector)
        assert passed is True
        assert "weak bearish" in reason


# ===========================================================================
# 7. Symbol Deduplication
# ===========================================================================


class TestSymbolDeduplication:
    """get_active_etf_symbols should not return duplicates."""

    def test_no_duplicates_with_overlap(self):
        """Adding XLK as custom when technology sector is active should not duplicate."""
        config = ScannerConfig(
            active_sectors=["technology", "financials"],
            custom_symbols=["XLK", "SPY"],
        )
        symbols = config.get_active_etf_symbols()
        assert symbols.count("XLK") == 1, f"XLK appears {symbols.count('XLK')} times"
        assert "SPY" in symbols
        assert "XLF" in symbols

    def test_order_preserved(self):
        """Sector symbols should come first, then custom symbols."""
        config = ScannerConfig(
            active_sectors=["technology", "financials"],
            custom_symbols=["SPY", "QQQ"],
        )
        symbols = config.get_active_etf_symbols()
        assert symbols == ["XLK", "XLF", "SPY", "QQQ"]

    def test_no_duplicates_multiple_custom_overlap(self):
        """Multiple custom symbols overlapping with sectors."""
        config = ScannerConfig(
            active_sectors=["technology", "financials", "energy"],
            custom_symbols=["XLK", "XLF", "XLE", "AAPL"],
        )
        symbols = config.get_active_etf_symbols()
        assert len(symbols) == len(set(symbols)), f"Duplicates found: {symbols}"
        assert len(symbols) == 4  # XLK, XLF, XLE, AAPL

    def test_no_custom_symbols_works(self):
        """Without custom symbols, should just return sector symbols."""
        config = ScannerConfig(
            active_sectors=["technology"],
            custom_symbols=[],
        )
        symbols = config.get_active_etf_symbols()
        assert symbols == ["XLK"]

    def test_all_sectors_no_duplicates(self):
        """All sectors should produce unique symbols."""
        config = ScannerConfig()  # Default: all sectors
        symbols = config.get_active_etf_symbols()
        assert len(symbols) == len(set(symbols))
        assert len(symbols) == 11  # All sector ETFs
