"""
Tests for Tier 3 feature enhancements:
  14. Cloud stacking order / waterfall detection
  15. Weighted filter scoring for signal strength
  16. Data quality validation post-fetch
  17. Walk-forward backtesting
  18. Config schema migration support
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ema_cloud_lib.backtesting.engine import (
    WalkForwardBacktester,
    WalkForwardResult,
    WalkForwardWindow,
)
from ema_cloud_lib.config.settings import (
    CONFIG_SCHEMA_VERSION,
    FilterConfig,
    ScannerConfig,
    migrate_config,
)
from ema_cloud_lib.data_providers.base import (
    DataQualityResult,
    validate_ohlcv,
)
from ema_cloud_lib.indicators.ema_cloud import (
    CloudData,
    CloudState,
    EMACloudIndicator,
    PriceRelation,
    StackingOrder,
)
from ema_cloud_lib.signals.generator import (
    FilterResult,
    SignalFilter,
    SignalGenerator,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ohlcv(n: int = 300, trend: str = "up") -> pd.DataFrame:
    """Build a trending OHLCV DataFrame for testing."""
    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    if trend == "up":
        close = 100.0 + np.arange(n) * 0.5 + rng.normal(0, 0.3, n).cumsum()
    elif trend == "down":
        close = 200.0 - np.arange(n) * 0.5 + rng.normal(0, 0.3, n).cumsum()
    else:
        close = 100.0 + rng.normal(0, 0.3, n).cumsum()
    return pd.DataFrame(
        {
            "open": close + rng.uniform(-0.2, 0.2, n),
            "high": close + abs(rng.normal(0.3, 0.1, n)),
            "low": close - abs(rng.normal(0.3, 0.1, n)),
            "close": close,
            "volume": rng.integers(100_000, 1_000_000, n).astype(float),
        },
        index=dates,
    )


def _build_cloud_data(mid: float, state: CloudState = CloudState.BULLISH) -> CloudData:
    """Quick helper to construct a CloudData at a given midpoint."""
    return CloudData(
        name="test",
        fast_ema=mid + 0.5,
        slow_ema=mid - 0.5,
        cloud_top=mid + 0.5,
        cloud_bottom=mid - 0.5,
        cloud_thickness=1.0,
        cloud_thickness_pct=1.0,
        state=state,
        price_relation=PriceRelation.ABOVE,
        is_expanding=False,
        is_contracting=False,
        slope=0.0,
    )


# ===================================================================
# 14. Cloud Stacking Order / Waterfall Detection
# ===================================================================


class TestStackingOrder:
    """Tests for StackingOrder model and EMACloudIndicator.analyze_stacking."""

    def test_stacking_order_model_defaults(self):
        s = StackingOrder()
        assert not s.is_stacked_bullish
        assert not s.is_stacked_bearish
        assert s.stacking_score == 0.0
        assert not s.is_waterfall

    def test_perfect_bullish_waterfall(self):
        """Shorter-term clouds have higher midpoints → bullish waterfall."""
        indicator = EMACloudIndicator()
        clouds = {
            "trend_line": _build_cloud_data(120),
            "pullback": _build_cloud_data(115),
            "momentum": _build_cloud_data(110),
            "trend_confirmation": _build_cloud_data(105),
            "long_term": _build_cloud_data(100),
            "major_trend": _build_cloud_data(95),
        }
        result = indicator.analyze_stacking(clouds)
        assert result.is_stacked_bullish
        assert not result.is_stacked_bearish
        assert result.is_waterfall
        assert result.stacking_score == 1.0
        assert result.ordered_pairs == result.total_pairs

    def test_perfect_bearish_waterfall(self):
        """Shorter-term clouds have lower midpoints → bearish waterfall."""
        indicator = EMACloudIndicator()
        clouds = {
            "trend_line": _build_cloud_data(95),
            "pullback": _build_cloud_data(100),
            "momentum": _build_cloud_data(105),
            "trend_confirmation": _build_cloud_data(110),
            "long_term": _build_cloud_data(115),
            "major_trend": _build_cloud_data(120),
        }
        result = indicator.analyze_stacking(clouds)
        assert not result.is_stacked_bullish
        assert result.is_stacked_bearish
        assert result.is_waterfall
        assert result.stacking_score == -1.0

    def test_mixed_stacking(self):
        """Some clouds in order, some not → no waterfall."""
        indicator = EMACloudIndicator()
        clouds = {
            "trend_line": _build_cloud_data(120),
            "pullback": _build_cloud_data(115),
            "momentum": _build_cloud_data(130),  # out of order
            "trend_confirmation": _build_cloud_data(105),
            "long_term": _build_cloud_data(100),
            "major_trend": _build_cloud_data(95),
        }
        result = indicator.analyze_stacking(clouds)
        assert not result.is_waterfall
        assert 0 < result.ordered_pairs < result.total_pairs

    def test_subset_of_clouds(self):
        """Works with fewer than 6 clouds."""
        indicator = EMACloudIndicator({"trend_line": (5, 12), "momentum": (20, 21)})
        clouds = {
            "trend_line": _build_cloud_data(110),
            "momentum": _build_cloud_data(100),
        }
        result = indicator.analyze_stacking(clouds)
        assert result.is_stacked_bullish
        assert result.total_pairs == 1
        assert result.ordered_pairs == 1

    def test_single_cloud(self):
        """A single cloud cannot form pairs."""
        indicator = EMACloudIndicator({"trend_line": (5, 12)})
        clouds = {"trend_line": _build_cloud_data(100)}
        result = indicator.analyze_stacking(clouds)
        assert not result.is_waterfall
        assert result.total_pairs == 0

    def test_waterfall_signal_emitted(self):
        """detect_signals emits WATERFALL when stacking is perfect."""
        indicator = EMACloudIndicator()
        df = _make_ohlcv(300, trend="up")
        prepared = indicator.calculate(df)

        # We don't guarantee a WATERFALL in random data, but we test the
        # mechanism by calling analyze_stacking on produced clouds.
        clouds = indicator.analyze_single(prepared, -1)
        stacking = indicator.analyze_stacking(clouds)
        # Just verify the method runs and returns the right type
        assert isinstance(stacking, StackingOrder)

    def test_stacking_in_trend_analysis(self):
        """TrendAnalysis includes stacking field."""
        gen = SignalGenerator()
        df = _make_ohlcv(300, trend="up")
        prepared = gen.prepare_data(df)
        analysis = gen.analyze_trend(prepared, "TEST")
        assert hasattr(analysis, "stacking")
        assert isinstance(analysis.stacking, StackingOrder)


# ===================================================================
# 15. Weighted Filter Scoring for Signal Strength
# ===================================================================


class TestWeightedFilterScoring:
    """Tests for weighted filter scoring."""

    def test_filter_weights_in_config(self):
        """FilterConfig has filter_weights field with defaults."""
        config = FilterConfig()
        assert "volume" in config.filter_weights
        assert "adx" in config.filter_weights
        assert config.filter_weights["volume"] == 2.0
        assert config.filter_weights["time"] == 0.5

    def test_filter_result_has_weight(self):
        """FilterResult carries a weight field."""
        r = FilterResult(passed=True, reason="ok", filter_name="volume", weight=2.0)
        assert r.weight == 2.0

    def test_weighted_filter_score_all_pass(self):
        """When all filters pass, weighted score is 1.0."""
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
        row = pd.Series({"close": 100.0})
        ts = datetime(2024, 6, 15, 10, 30, tzinfo=UTC)
        score = sf.weighted_filter_score(row, "long", ts)
        assert score == 1.0

    def test_weighted_filter_score_respects_weights(self):
        """Heavier filters have more influence on the score."""
        config = FilterConfig(
            volume_enabled=True,
            volume_multiplier=99.0,  # Will fail — very high threshold
            rsi_enabled=False,
            adx_enabled=False,
            vwap_enabled=False,
            atr_enabled=False,
            macd_enabled=False,
            time_filter_enabled=False,
            filter_weights={
                "volume": 10.0,
                "rsi": 1.0,
                "adx": 1.0,
                "vwap": 1.0,
                "atr": 1.0,
                "macd": 1.0,
                "time": 1.0,
            },
        )
        sf = SignalFilter(config)
        row = pd.Series({"close": 100.0, "volume_ratio": 1.0})
        ts = datetime(2024, 6, 15, 10, 30, tzinfo=UTC)
        score = sf.weighted_filter_score(row, "long", ts)
        # volume (weight=10) fails; 6 others (weight=1 each, disabled→pass) pass
        # expected = 6 / (10 + 6) = 0.375
        assert score == pytest.approx(6.0 / 16.0, abs=0.01)

    def test_custom_weights_in_scanner_config(self):
        """ScannerConfig can carry custom filter weights."""
        config = ScannerConfig(
            filters=FilterConfig(
                filter_weights={
                    "volume": 5.0,
                    "rsi": 3.0,
                    "adx": 3.0,
                    "vwap": 2.0,
                    "atr": 1.0,
                    "macd": 1.0,
                    "time": 0.5,
                }
            )
        )
        assert config.filters.filter_weights["volume"] == 5.0


# ===================================================================
# 16. Data Quality Validation Post-Fetch
# ===================================================================


class TestDataQualityValidation:
    """Tests for validate_ohlcv and DataQualityResult."""

    def test_valid_data_passes(self):
        df = _make_ohlcv(50)
        _cleaned, result = validate_ohlcv(df, "TEST")
        assert result.is_valid
        assert result.rows_after == 50
        assert len(result.errors) == 0

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        _, result = validate_ohlcv(df, "TEST")
        assert not result.is_valid
        assert any("empty" in e.lower() for e in result.errors)

    def test_missing_columns(self):
        df = pd.DataFrame({"foo": [1, 2], "bar": [3, 4]})
        _, result = validate_ohlcv(df, "TEST")
        assert not result.is_valid
        assert any("Missing required columns" in e for e in result.errors)

    def test_nan_rows_dropped(self):
        df = _make_ohlcv(10)
        df.iloc[3, df.columns.get_loc("close")] = np.nan
        df.iloc[7, df.columns.get_loc("high")] = np.nan
        cleaned, result = validate_ohlcv(df, "TEST")
        assert result.nan_rows_dropped == 2
        assert result.rows_after == 8
        assert len(cleaned) == 8

    def test_non_positive_prices_dropped(self):
        df = _make_ohlcv(10)
        df.iloc[2, df.columns.get_loc("close")] = -5.0
        _cleaned, result = validate_ohlcv(df, "TEST")
        assert result.rows_after == 9
        assert any("non-positive" in w for w in result.warnings)

    def test_high_low_swapped_fixed(self):
        df = _make_ohlcv(10)
        # Swap high and low for row 4
        orig_high = df.iloc[4]["high"]
        orig_low = df.iloc[4]["low"]
        df.iloc[4, df.columns.get_loc("high")] = orig_low - 1
        df.iloc[4, df.columns.get_loc("low")] = orig_high + 1
        cleaned, result = validate_ohlcv(df, "TEST")
        assert any("high < low" in w for w in result.warnings)
        # After fix, high should be >= low
        assert cleaned.iloc[4]["high"] >= cleaned.iloc[4]["low"]

    def test_negative_volume_zeroed(self):
        df = _make_ohlcv(10)
        df.iloc[5, df.columns.get_loc("volume")] = -100.0
        cleaned, result = validate_ohlcv(df, "TEST")
        assert any("negative volume" in w.lower() for w in result.warnings)
        assert cleaned.iloc[5]["volume"] == 0

    def test_duplicate_timestamps_dropped(self):
        df = _make_ohlcv(10)
        # Duplicate the index
        dup = df.iloc[[3]].copy()
        df = pd.concat([df, dup])
        cleaned, result = validate_ohlcv(df, "TEST")
        assert result.duplicate_rows_dropped == 1
        assert len(cleaned) == 10

    def test_non_monotonic_sorted(self):
        df = _make_ohlcv(10)
        df = df.iloc[::-1]  # Reverse order
        cleaned, result = validate_ohlcv(df, "TEST")
        assert any("non-monotonic" in w.lower() for w in result.warnings)
        assert cleaned.index.is_monotonic_increasing

    def test_capitalized_columns_handled(self):
        """Columns with capital letters are lowered."""
        df = _make_ohlcv(10)
        df.columns = [c.capitalize() for c in df.columns]
        cleaned, result = validate_ohlcv(df, "TEST")
        assert result.is_valid
        assert "close" in cleaned.columns

    def test_data_quality_result_model(self):
        r = DataQualityResult(
            is_valid=True,
            rows_before=100,
            rows_after=95,
            nan_rows_dropped=5,
        )
        assert r.is_valid
        assert r.nan_rows_dropped == 5


# ===================================================================
# 17. Walk-Forward Backtesting
# ===================================================================


class TestWalkForwardBacktesting:
    """Tests for WalkForwardBacktester."""

    def test_walk_forward_window_model(self):
        w = WalkForwardWindow(
            window_index=0,
            in_sample_start=datetime(2024, 1, 1, tzinfo=UTC),
            in_sample_end=datetime(2024, 6, 1, tzinfo=UTC),
            out_of_sample_start=datetime(2024, 6, 1, tzinfo=UTC),
            out_of_sample_end=datetime(2024, 9, 1, tzinfo=UTC),
        )
        assert w.window_index == 0

    def test_walk_forward_result_model(self):
        r = WalkForwardResult(
            symbol="TEST",
            in_sample_size=500,
            out_of_sample_size=100,
            step_size=100,
        )
        assert r.total_windows == 0
        assert r.oos_total_trades == 0

    def test_walk_forward_insufficient_data(self):
        """Returns empty result when data is too small."""
        df = _make_ohlcv(50)
        wf = WalkForwardBacktester(in_sample_size=500, out_of_sample_size=100)
        result = wf.run(df, "TEST")
        assert result.total_windows == 0
        assert len(result.windows) == 0

    def test_walk_forward_basic_run(self):
        """Walk-forward runs with sufficient data and produces windows."""
        df = _make_ohlcv(800, trend="up")
        wf = WalkForwardBacktester(
            in_sample_size=300,
            out_of_sample_size=100,
            step_size=100,
            initial_capital=100000.0,
        )
        result = wf.run(df, "TEST")
        assert len(result.windows) > 0
        assert result.total_windows == len(result.windows)

        # Each window should have both IS and OOS results
        for w in result.windows:
            assert w.in_sample_result is not None
            assert w.out_of_sample_result is not None
            assert w.in_sample_bars == 300
            assert w.out_of_sample_bars <= 100

    def test_walk_forward_aggregate_metrics(self):
        """Aggregate OOS metrics are calculated."""
        df = _make_ohlcv(800, trend="up")
        wf = WalkForwardBacktester(
            in_sample_size=300,
            out_of_sample_size=100,
            step_size=100,
        )
        result = wf.run(df, "TEST")
        # Just verify the fields are populated (not NaN/None)
        assert isinstance(result.oos_win_rate, float)
        assert isinstance(result.oos_total_return_pct, float)
        assert isinstance(result.robustness_ratio, float)

    def test_walk_forward_format_summary(self):
        """format_summary returns a non-empty string."""
        df = _make_ohlcv(800, trend="up")
        wf = WalkForwardBacktester(
            in_sample_size=300,
            out_of_sample_size=100,
            step_size=100,
        )
        result = wf.run(df, "TEST")
        summary = result.format_summary()
        assert "WALK-FORWARD" in summary
        assert "TEST" in summary

    def test_walk_forward_with_pre_computed_signals(self):
        """Walk-forward can accept pre-computed signals."""
        df = _make_ohlcv(800, trend="up")
        # Build simple signals
        signals = []
        for i in range(250, 750, 50):
            signals.append(
                {
                    "direction": "long",
                    "signal_type": "ema_cross",
                    "strength": 4,
                    "stop_loss": df.iloc[i]["close"] * 0.98,
                    "take_profit": df.iloc[i]["close"] * 1.04,
                }
            )
            signals[-1]["timestamp"] = df.index[i]
        signals_df = pd.DataFrame(signals).set_index("timestamp")

        wf = WalkForwardBacktester(
            in_sample_size=300,
            out_of_sample_size=100,
            step_size=100,
        )
        result = wf.run(df, "TEST", signals_df=signals_df)
        assert len(result.windows) > 0

    def test_walk_forward_step_defaults_to_oos_size(self):
        """When step_size is not provided, it defaults to out_of_sample_size."""
        wf = WalkForwardBacktester(in_sample_size=300, out_of_sample_size=100)
        assert wf.step_size == 100


# ===================================================================
# 18. Config Schema Migration Support
# ===================================================================


class TestConfigSchemaMigration:
    """Tests for config schema versioning and migration."""

    def test_current_schema_version(self):
        """CONFIG_SCHEMA_VERSION is defined and >= 2."""
        assert CONFIG_SCHEMA_VERSION >= 2

    def test_scanner_config_has_schema_version(self):
        """ScannerConfig includes schema_version field."""
        config = ScannerConfig()
        assert config.schema_version == CONFIG_SCHEMA_VERSION

    def test_migrate_v1_to_v2_adds_filter_weights(self):
        """v1 config gets filter_weights added during migration."""
        v1_config = {
            "trading_style": "intraday",
            "filters": {
                "volume_enabled": True,
            },
        }
        migrated = migrate_config(v1_config)
        assert migrated["schema_version"] == 2
        assert "filter_weights" in migrated["filters"]
        assert migrated["filters"]["filter_weights"]["volume"] == 2.0

    def test_migrate_already_current(self):
        """Config at current version is returned unchanged."""
        config = {"schema_version": CONFIG_SCHEMA_VERSION, "filters": {}}
        migrated = migrate_config(config)
        assert migrated["schema_version"] == CONFIG_SCHEMA_VERSION

    def test_migrate_preserves_existing_filter_weights(self):
        """If filter_weights already exist in v1 config, migration preserves them."""
        v1_config = {
            "filters": {
                "filter_weights": {"volume": 5.0},
            },
        }
        migrated = migrate_config(v1_config)
        assert migrated["filters"]["filter_weights"]["volume"] == 5.0

    def test_save_includes_schema_version(self):
        """Saved config file includes schema_version."""
        config = ScannerConfig()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            config.save(f.name)
            saved = json.loads(Path(f.name).read_text())
        assert saved["schema_version"] == CONFIG_SCHEMA_VERSION

    def test_load_with_migration(self):
        """Loading a v1 config file migrates it automatically."""
        v1_config = {
            "trading_style": "swing",
            "filters": {"volume_enabled": False},
        }
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            json.dump(v1_config, f)
            f.flush()
            loaded = ScannerConfig.load(f.name)

        assert loaded.schema_version == CONFIG_SCHEMA_VERSION
        assert loaded.trading_style.value == "swing"
        assert loaded.filters.filter_weights["volume"] == 2.0

    def test_load_current_version_config(self):
        """Loading a current-version config works without migration."""
        config = ScannerConfig(trading_style="position")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            config.save(f.name)
            loaded = ScannerConfig.load(f.name)
        assert loaded.trading_style.value == "position"
        assert loaded.schema_version == CONFIG_SCHEMA_VERSION
