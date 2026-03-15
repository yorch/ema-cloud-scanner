"""
Unit tests for the EMACloudScanner core module.

Covers initialization, configuration management, data fetching,
signal cooldown, ETF scanning, and the main run loop.
"""

import asyncio
import contextlib
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from ema_cloud_lib.config.settings import ScannerConfig, SignalType, TradingStyle
from ema_cloud_lib.constants import (
    SIGNAL_COOLDOWN_CLEANUP_THRESHOLD,
    utc_now,
)
from ema_cloud_lib.indicators.ema_cloud import CloudState, PriceRelation
from ema_cloud_lib.scanner import EMACloudScanner
from ema_cloud_lib.signals.generator import Signal, SignalStrength


def _make_signal(
    symbol: str = "XLK",
    direction: str = "long",
    signal_type: SignalType = SignalType.CLOUD_FLIP_BULLISH,
    strength: SignalStrength = SignalStrength.STRONG,
    price: float = 150.0,
    filters_passed: list[str] | None = None,
    filters_failed: list[str] | None = None,
) -> Signal:
    """Create a Signal for testing."""
    return Signal(
        symbol=symbol,
        signal_type=signal_type,
        direction=direction,
        strength=strength,
        price=price,
        timestamp=utc_now(),
        cloud_name="trend_confirmation",
        description="Test signal",
        primary_cloud_state=CloudState.BULLISH,
        price_relation=PriceRelation.ABOVE,
        filters_passed=filters_passed if filters_passed is not None else ["volume", "rsi"],
        filters_failed=filters_failed if filters_failed is not None else [],
    )


def _make_ohlcv_df(n: int = 100) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame for testing."""
    import numpy as np

    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100.0 + rng.normal(0, 0.5, n).cumsum()
    return pd.DataFrame(
        {
            "open": close + rng.normal(0, 0.1, n),
            "high": close + abs(rng.normal(0, 0.5, n)),
            "low": close - abs(rng.normal(0, 0.5, n)),
            "close": close,
            "volume": rng.integers(100_000, 1_000_000, n).astype(float),
        },
        index=dates,
    )


@pytest.fixture
def config():
    """Create a minimal ScannerConfig."""
    return ScannerConfig(
        trading_style=TradingStyle.SWING,
        scan_holdings=False,
    )


@pytest.fixture
def scanner(config):
    """Create an EMACloudScanner with mocked heavy dependencies."""
    with (
        patch("ema_cloud_lib.scanner.DataProviderManager") as MockDPM,
        patch("ema_cloud_lib.scanner.AlertManager") as MockAM,
    ):
        MockDPM.return_value = MagicMock()
        mock_manager = MagicMock()
        mock_manager.send_alert = AsyncMock(return_value={"Console": True})
        MockAM.create_default.return_value = mock_manager

        s = EMACloudScanner(config)
        # Replace data_manager with async mock
        s.data_manager = MagicMock()
        s.data_manager.get_historical_data = AsyncMock(return_value=_make_ohlcv_df(100))
        return s


class TestEMACloudScannerInit:
    def test_default_config(self):
        """Scanner initializes with default config when none provided."""
        with (
            patch("ema_cloud_lib.scanner.DataProviderManager"),
            patch("ema_cloud_lib.scanner.AlertManager"),
        ):
            s = EMACloudScanner()
            assert s.config is not None
            assert isinstance(s.config, ScannerConfig)

    def test_custom_config(self, config):
        """Scanner uses provided config."""
        with (
            patch("ema_cloud_lib.scanner.DataProviderManager"),
            patch("ema_cloud_lib.scanner.AlertManager"),
        ):
            s = EMACloudScanner(config)
            assert s.config.trading_style == TradingStyle.SWING

    def test_initial_state(self, scanner):
        """Scanner starts in non-running state with empty caches."""
        assert scanner.is_running is False
        assert scanner.dashboard is None
        assert scanner._signal_cooldown == {}
        assert scanner._sector_states == {}

    def test_holdings_scanner_disabled(self, scanner):
        """Holdings scanner is None when scan_holdings=False."""
        assert scanner.holdings_scanner is None

    def test_holdings_scanner_enabled(self):
        """Holdings scanner is created when scan_holdings=True."""
        config = ScannerConfig(scan_holdings=True)
        with (
            patch("ema_cloud_lib.scanner.DataProviderManager"),
            patch("ema_cloud_lib.scanner.AlertManager"),
        ):
            s = EMACloudScanner(config)
            assert s.holdings_scanner is not None

    def test_mtf_disabled_by_default(self, scanner):
        """MTF analyzer is None when mtf not enabled."""
        assert scanner.mtf_analyzer is None


class TestDashboard:
    def test_set_dashboard(self, scanner):
        mock_dashboard = MagicMock()
        scanner.set_dashboard(mock_dashboard)
        assert scanner.dashboard is mock_dashboard

    def test_set_dashboard_none(self, scanner):
        scanner.set_dashboard(MagicMock())
        scanner.set_dashboard(None)
        assert scanner.dashboard is None


class TestApplyConfig:
    def test_apply_valid_config(self, scanner):
        """apply_config updates scanner components."""
        new_config = ScannerConfig(trading_style=TradingStyle.SCALPING)

        with (
            patch("ema_cloud_lib.scanner.DataProviderManager"),
            patch("ema_cloud_lib.scanner.AlertManager"),
        ):
            scanner.apply_config(new_config)

        assert scanner.config.trading_style == TradingStyle.SCALPING

    def test_apply_config_rollback_on_failure(self, scanner):
        """apply_config rolls back on failure."""
        old_config = scanner.config

        with (
            patch(
                "ema_cloud_lib.scanner.DataProviderManager",
                side_effect=ValueError("bad config"),
            ),
        ):
            with pytest.raises(RuntimeError, match="rollback"):
                scanner.apply_config(ScannerConfig(trading_style=TradingStyle.SCALPING))

        # Config should be rolled back
        assert scanner.config is old_config


class TestFetchData:
    @pytest.mark.asyncio
    async def test_fetch_data_success(self, scanner):
        """fetch_data returns DataFrame on success."""
        df = await scanner.fetch_data("XLK", "1d", 5)
        assert df is not None
        assert len(df) == 100

    @pytest.mark.asyncio
    async def test_fetch_data_provider_error(self, scanner):
        """fetch_data returns None on DataProviderError."""
        from ema_cloud_lib.data_providers.base import DataProviderError

        scanner.data_manager.get_historical_data = AsyncMock(
            side_effect=DataProviderError("network error")
        )
        result = await scanner.fetch_data("XLK", "1d", 5)
        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_data_value_error(self, scanner):
        """fetch_data returns None on ValueError."""
        scanner.data_manager.get_historical_data = AsyncMock(side_effect=ValueError("bad data"))
        result = await scanner.fetch_data("XLK", "1d", 5)
        assert result is None


class TestCalculateLookback:
    def test_known_timeframes(self, scanner):
        assert scanner._calculate_lookback("1d", 200) >= 200
        assert scanner._calculate_lookback("1h", 100) >= 4
        assert scanner._calculate_lookback("5m", 100) >= 3

    def test_unknown_timeframe_defaults(self, scanner):
        assert scanner._calculate_lookback("unknown", 100) == 30

    def test_weekly(self, scanner):
        assert scanner._calculate_lookback("1w", 52) >= 520


class TestSignalCooldown:
    def test_first_signal_always_alerts(self, scanner):
        """First occurrence of a signal should alert."""
        signal = _make_signal()
        assert scanner._should_alert_signal(signal) is True

    def test_duplicate_signal_within_cooldown(self, scanner):
        """Same signal within cooldown period should NOT alert."""
        signal = _make_signal()
        scanner._should_alert_signal(signal)  # First: registers cooldown
        assert scanner._should_alert_signal(signal) is False

    def test_signal_after_cooldown_expires(self, scanner):
        """Same signal after cooldown expires should alert again."""
        signal = _make_signal()
        scanner._should_alert_signal(signal)

        # Manually expire the cooldown
        key = f"{signal.symbol}|{signal.direction}|{signal.signal_type.value}"
        scanner._signal_cooldown[key] = utc_now() - timedelta(
            minutes=scanner.signal_cooldown_minutes + 1
        )
        assert scanner._should_alert_signal(signal) is True

    def test_different_signals_independent(self, scanner):
        """Different signal types don't affect each other's cooldown."""
        sig_flip = _make_signal(signal_type=SignalType.CLOUD_FLIP_BULLISH)
        sig_cross = _make_signal(signal_type=SignalType.PRICE_CROSS_ABOVE)

        scanner._should_alert_signal(sig_flip)
        assert scanner._should_alert_signal(sig_cross) is True

    def test_cooldown_cleanup_on_threshold(self, scanner):
        """Expired entries are cleaned up when threshold exceeded."""
        expired_time = utc_now() - timedelta(hours=25)
        # Fill cooldown past threshold
        for i in range(SIGNAL_COOLDOWN_CLEANUP_THRESHOLD + 1):
            scanner._signal_cooldown[f"key_{i}"] = expired_time

        signal = _make_signal()
        scanner._should_alert_signal(signal)

        # All expired entries should be cleaned up
        assert len(scanner._signal_cooldown) < SIGNAL_COOLDOWN_CLEANUP_THRESHOLD


class TestAnalyzeETF:
    @pytest.mark.asyncio
    async def test_returns_none_for_no_data(self, scanner):
        """analyze_etf returns None when no data is available."""
        scanner.data_manager.get_historical_data = AsyncMock(side_effect=Exception("no data"))
        # fetch_data will catch and return None, then analyze_etf returns None
        with patch.object(scanner, "fetch_data", new_callable=AsyncMock, return_value=None):
            result = await scanner.analyze_etf("XLK")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_insufficient_data(self, scanner):
        """analyze_etf returns None when insufficient bars."""
        short_df = _make_ohlcv_df(n=10)
        with patch.object(scanner, "fetch_data", new_callable=AsyncMock, return_value=short_df):
            result = await scanner.analyze_etf("XLK")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_analysis_dict(self, scanner):
        """analyze_etf returns analysis dict on success."""
        df = _make_ohlcv_df(n=100)
        with patch.object(scanner, "fetch_data", new_callable=AsyncMock, return_value=df):
            result = await scanner.analyze_etf("XLK")
        assert result is not None
        assert result["symbol"] == "XLK"
        assert "price" in result
        assert "change_pct" in result
        assert "signals" in result
        assert "trend" in result


class TestScanAllETFs:
    @pytest.mark.asyncio
    async def test_scan_all_returns_results(self, scanner):
        """scan_all_etfs returns list of analysis dicts."""
        mock_analysis = {
            "symbol": "XLK",
            "sector": "Technology",
            "price": 150.0,
            "change_pct": 1.5,
            "trend": MagicMock(),
            "signals": [],
            "clouds": {},
            "rsi": 55.0,
            "adx": 25.0,
            "volume_ratio": 1.2,
            "mtf_result": None,
        }
        with patch.object(
            scanner, "analyze_etf", new_callable=AsyncMock, return_value=mock_analysis
        ):
            results = await scanner.scan_all_etfs()
        assert len(results) > 0
        assert results[0]["symbol"] == "XLK"

    @pytest.mark.asyncio
    async def test_scan_all_handles_failures(self, scanner):
        """scan_all_etfs skips failed analyses."""
        call_count = 0

        async def mock_analyze(symbol):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise ValueError("analysis failed")
            return {"symbol": symbol, "signals": []}

        with patch.object(scanner, "analyze_etf", side_effect=mock_analyze):
            results = await scanner.scan_all_etfs()
        # Some should succeed, some fail - results should only contain successes
        assert all(isinstance(r, dict) for r in results)

    @pytest.mark.asyncio
    async def test_scan_all_skips_none_results(self, scanner):
        """scan_all_etfs skips None analyses."""
        with patch.object(scanner, "analyze_etf", new_callable=AsyncMock, return_value=None):
            results = await scanner.scan_all_etfs()
        assert results == []


class TestProcessSignals:
    @pytest.mark.asyncio
    async def test_sends_alert_for_valid_signal(self, scanner):
        """process_signals sends alerts for valid signals."""
        signal = _make_signal()  # no failed filters = valid
        analyses = [{"signals": [signal]}]

        await scanner.process_signals(analyses)
        scanner.alert_manager.send_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_invalid_signals(self, scanner):
        """process_signals skips signals that didn't pass filters."""
        signal = _make_signal(filters_failed=["volume"])  # has failed filter = invalid
        analyses = [{"signals": [signal]}]

        await scanner.process_signals(analyses)
        scanner.alert_manager.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_respects_cooldown(self, scanner):
        """process_signals doesn't re-alert within cooldown."""
        signal = _make_signal()
        analyses = [{"signals": [signal]}]

        await scanner.process_signals(analyses)
        scanner.alert_manager.send_alert.reset_mock()

        await scanner.process_signals(analyses)
        scanner.alert_manager.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_updates_dashboard(self, scanner):
        """process_signals updates dashboard when set."""
        mock_dashboard = MagicMock()
        scanner.set_dashboard(mock_dashboard)

        signal = _make_signal()
        analyses = [{"signals": [signal]}]

        await scanner.process_signals(analyses)
        mock_dashboard.add_signal.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_dashboard_no_error(self, scanner):
        """process_signals works without dashboard."""
        signal = _make_signal()
        analyses = [{"signals": [signal]}]
        await scanner.process_signals(analyses)  # Should not raise


class TestRunScanCycle:
    @pytest.mark.asyncio
    async def test_run_scan_cycle(self, scanner):
        """run_scan_cycle calls scan_all_etfs and process_signals."""
        analysis = {
            "symbol": "XLK",
            "sector": "Technology",
            "price": 150.0,
            "change_pct": 1.0,
            "trend": MagicMock(
                overall_trend="bullish",
                trend_strength=0.75,
                primary_cloud_state=MagicMock(name="BULLISH"),
            ),
            "signals": [],
            "clouds": {},
            "rsi": 55.0,
            "adx": 25.0,
            "volume_ratio": 1.2,
            "mtf_result": None,
        }
        with patch.object(
            scanner, "scan_all_etfs", new_callable=AsyncMock, return_value=[analysis]
        ):
            await scanner.run_scan_cycle()

    @pytest.mark.asyncio
    async def test_run_scan_cycle_empty_results(self, scanner):
        """run_scan_cycle handles empty scan results gracefully."""
        with patch.object(scanner, "scan_all_etfs", new_callable=AsyncMock, return_value=[]):
            await scanner.run_scan_cycle()  # Should not raise


class TestRunLoop:
    @pytest.mark.asyncio
    async def test_stop_sets_running_false(self, scanner):
        """stop() sets is_running to False."""
        scanner._running = True
        scanner.stop()
        assert scanner.is_running is False

    @pytest.mark.asyncio
    async def test_run_can_be_cancelled(self, scanner):
        """run() exits cleanly on CancelledError."""
        with patch.object(scanner, "run_scan_cycle", new_callable=AsyncMock):
            task = asyncio.create_task(
                scanner.run(scan_interval_seconds=1, market_hours_only=False)
            )
            await asyncio.sleep(0.05)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        assert scanner.is_running is False

    @pytest.mark.asyncio
    async def test_run_stops_on_stop_call(self, scanner):
        """run() exits when stop() is called."""

        async def stop_after_delay():
            await asyncio.sleep(0.05)
            scanner.stop()

        with patch.object(scanner, "run_scan_cycle", new_callable=AsyncMock):
            await asyncio.gather(
                scanner.run(scan_interval_seconds=0.01, market_hours_only=False),
                stop_after_delay(),
            )
        assert scanner.is_running is False


class TestUpdateDashboard:
    def test_no_dashboard_no_error(self, scanner):
        """_update_dashboard does nothing when no dashboard is set."""
        scanner._update_dashboard([{"symbol": "XLK"}])  # Should not raise

    def test_updates_etf_data(self, scanner):
        """_update_dashboard calls update_etf_data for each analysis."""
        mock_dashboard = MagicMock()
        scanner.set_dashboard(mock_dashboard)

        trend = MagicMock(
            overall_trend="bullish",
            trend_strength=0.8,
        )
        trend.primary_cloud_state = CloudState.BULLISH
        analyses = [
            {
                "symbol": "XLK",
                "sector": "Technology",
                "price": 150.0,
                "change_pct": 1.5,
                "trend": trend,
                "signals": [],
                "rsi": 55.0,
                "adx": 25.0,
                "volume_ratio": 1.2,
                "mtf_result": None,
            }
        ]

        scanner._update_dashboard(analyses)
        mock_dashboard.update_etf_data.assert_called_once()


class TestSectorTrendConversion:
    def _make_sector_state(
        self, scanner, trend_direction, trend_strength=0.8, clouds_bullish=3, clouds_bearish=3
    ):
        from ema_cloud_lib.signals.generator import SectorTrendState

        return SectorTrendState(
            symbol="XLK",
            sector_name="Technology",
            timestamp=utc_now(),
            trend_direction=trend_direction,
            trend_strength=trend_strength,
            trend_duration=10,
            clouds_bullish=clouds_bullish,
            clouds_bearish=clouds_bearish,
        )

    def test_bullish_trend(self, scanner):
        from ema_cloud_lib.holdings.holdings_scanner import SectorTrend

        state = self._make_sector_state(scanner, "bullish", clouds_bullish=5, clouds_bearish=1)
        assert scanner._sector_trend_from_state(state) == SectorTrend.BULLISH

    def test_bearish_trend(self, scanner):
        from ema_cloud_lib.holdings.holdings_scanner import SectorTrend

        state = self._make_sector_state(scanner, "bearish", clouds_bullish=1, clouds_bearish=5)
        assert scanner._sector_trend_from_state(state) == SectorTrend.BEARISH

    def test_neutral_trend(self, scanner):
        from ema_cloud_lib.holdings.holdings_scanner import SectorTrend

        state = self._make_sector_state(scanner, "mixed", trend_strength=0.3)
        assert scanner._sector_trend_from_state(state) == SectorTrend.NEUTRAL
