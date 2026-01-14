"""Tests for holdings scanner functionality."""

from datetime import datetime

import pandas as pd
import pytest

from ema_cloud_lib.config.settings import ScannerConfig
from ema_cloud_lib.data_providers.base import DataProviderManager
from ema_cloud_lib.holdings import HoldingsScanner, SectorTrend, StockSignalContext
from ema_cloud_lib.indicators.ema_cloud import EMACloudIndicator
from ema_cloud_lib.signals.generator import (
    SignalDirection,
    SignalGenerator,
    SignalStrength,
)


@pytest.fixture
def scanner_config():
    """Create test scanner configuration."""
    return ScannerConfig(
        scan_holdings=True,
        top_holdings_count=5,
        holdings_max_concurrent=3,
    )


@pytest.fixture
def mock_data_manager(mocker):
    """Create mock data provider manager."""
    manager = mocker.Mock(spec=DataProviderManager)

    # Mock fetch_bars to return sample data
    async def mock_fetch_bars(symbol, timeframe, limit):
        dates = pd.date_range(end=datetime.now(), periods=limit, freq="1H")
        data = pd.DataFrame(
            {
                "open": [100 + i for i in range(limit)],
                "high": [102 + i for i in range(limit)],
                "low": [98 + i for i in range(limit)],
                "close": [101 + i for i in range(limit)],
                "volume": [1000000 + i * 1000 for i in range(limit)],
            },
            index=dates,
        )
        return data

    manager.fetch_bars = mock_fetch_bars
    return manager


@pytest.fixture
def holdings_scanner(scanner_config, mock_data_manager):
    """Create holdings scanner instance."""
    cloud_indicator = EMACloudIndicator(scanner_config.ema_clouds)
    signal_generator = SignalGenerator(
        config=scanner_config,
        ema_clouds=scanner_config.ema_clouds,
        filters=scanner_config.filters,
    )

    return HoldingsScanner(
        config=scanner_config,
        data_manager=mock_data_manager,
        cloud_indicator=cloud_indicator,
        signal_generator=signal_generator,
    )


def test_holdings_scanner_initialization(holdings_scanner):
    """Test holdings scanner initializes correctly."""
    assert holdings_scanner is not None
    assert holdings_scanner.config is not None
    assert holdings_scanner.data_manager is not None
    assert holdings_scanner.cloud_indicator is not None
    assert holdings_scanner.signal_generator is not None


def test_update_sector_trend(holdings_scanner):
    """Test updating sector trend state."""
    holdings_scanner.update_sector_trend("XLK", SectorTrend.BULLISH, 85)

    assert holdings_scanner._sector_trends["XLK"] == SectorTrend.BULLISH
    assert holdings_scanner._sector_strengths["XLK"] == 85


def test_set_holdings(holdings_scanner):
    """Test setting holdings data."""
    holdings_data = {
        "XLK": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
        "XLF": ["JPM", "BAC", "WFC", "C", "GS"],
    }

    holdings_scanner.set_holdings(holdings_data)

    assert holdings_scanner._etf_holdings == holdings_data
    assert len(holdings_scanner._etf_holdings) == 2


def test_sector_filter_bullish_blocks_shorts(holdings_scanner):
    """Test that bullish sector blocks short signals."""
    # Bullish sector should block SHORT signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.SHORT, SectorTrend.BULLISH
    )
    assert should_filter is True

    # Bullish sector should allow LONG signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.LONG, SectorTrend.BULLISH
    )
    assert should_filter is False


def test_sector_filter_bearish_blocks_longs(holdings_scanner):
    """Test that bearish sector blocks long signals."""
    # Bearish sector should block LONG signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.LONG, SectorTrend.BEARISH
    )
    assert should_filter is True

    # Bearish sector should allow SHORT signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.SHORT, SectorTrend.BEARISH
    )
    assert should_filter is False


def test_sector_filter_neutral_allows_both(holdings_scanner):
    """Test that neutral sector allows both directions."""
    # Neutral sector should allow LONG signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.LONG, SectorTrend.NEUTRAL
    )
    assert should_filter is False

    # Neutral sector should allow SHORT signals
    should_filter = holdings_scanner._should_filter_signal(
        SignalDirection.SHORT, SectorTrend.NEUTRAL
    )
    assert should_filter is False


def test_signal_strength_value_ordering(holdings_scanner):
    """Test signal strength value conversion."""
    assert holdings_scanner._signal_strength_value(SignalStrength.VERY_STRONG) == 5
    assert holdings_scanner._signal_strength_value(SignalStrength.STRONG) == 4
    assert holdings_scanner._signal_strength_value(SignalStrength.MODERATE) == 3
    assert holdings_scanner._signal_strength_value(SignalStrength.WEAK) == 2
    assert holdings_scanner._signal_strength_value(SignalStrength.VERY_WEAK) == 1


@pytest.mark.asyncio
async def test_scan_stock_returns_none_for_no_data(holdings_scanner, mock_data_manager):
    """Test scanning stock returns None when no data available."""

    # Mock fetch_bars to return None
    async def mock_fetch_bars_none(symbol, timeframe, limit):
        return None

    mock_data_manager.fetch_bars = mock_fetch_bars_none

    result = await holdings_scanner.scan_stock("INVALID", "XLK")
    assert result is None


@pytest.mark.asyncio
async def test_scan_holdings_with_no_holdings(holdings_scanner):
    """Test scanning holdings when no holdings set."""
    result = await holdings_scanner.scan_holdings("XLK")
    assert result == []


@pytest.mark.asyncio
async def test_scan_holdings_respects_sector_filter(holdings_scanner, mocker):
    """Test that holdings scanning respects sector trend filtering."""
    # Set up holdings
    holdings_scanner.set_holdings({"XLK": ["AAPL", "MSFT"]})

    # Set bullish sector trend (blocks shorts)
    holdings_scanner.update_sector_trend("XLK", SectorTrend.BULLISH, 80)

    # Mock scan_stock to return contexts
    mock_long_signal = StockSignalContext(
        signal=mocker.Mock(
            symbol="AAPL",
            direction=SignalDirection.LONG,
            strength=SignalStrength.STRONG,
        ),
        sector_etf="XLK",
        sector_trend=SectorTrend.BULLISH,
        filtered_by_sector=False,
        sector_strength=80,
    )

    mock_short_signal = StockSignalContext(
        signal=mocker.Mock(
            symbol="MSFT",
            direction=SignalDirection.SHORT,
            strength=SignalStrength.STRONG,
        ),
        sector_etf="XLK",
        sector_trend=SectorTrend.BULLISH,
        filtered_by_sector=True,  # Filtered because SHORT in BULLISH sector
        sector_strength=80,
    )

    # Mock scan_stock
    async def mock_scan_stock(symbol, sector_etf):
        if symbol == "AAPL":
            return mock_long_signal
        elif symbol == "MSFT":
            return mock_short_signal
        return None

    holdings_scanner.scan_stock = mock_scan_stock

    # Scan holdings
    results = await holdings_scanner.scan_holdings("XLK")

    # Should only return AAPL (LONG signal in BULLISH sector)
    # MSFT should be filtered (SHORT signal in BULLISH sector)
    assert len(results) == 1
    assert results[0].signal.symbol == "AAPL"


def test_get_sector_filter_stats(holdings_scanner):
    """Test getting sector filter statistics."""
    holdings_scanner.update_sector_trend("XLK", SectorTrend.BULLISH, 85)
    holdings_scanner.update_sector_trend("XLF", SectorTrend.BEARISH, 70)
    holdings_scanner.update_sector_trend("XLV", SectorTrend.NEUTRAL, 50)

    holdings_scanner.set_holdings(
        {
            "XLK": ["AAPL", "MSFT", "NVDA"],
            "XLF": ["JPM", "BAC"],
        }
    )

    stats = holdings_scanner.get_sector_filter_stats()

    assert stats["sectors_tracked"] == 3
    assert stats["bullish_sectors"] == 1
    assert stats["bearish_sectors"] == 1
    assert stats["neutral_sectors"] == 1
    assert stats["holdings_loaded"] == 2
    assert stats["total_stocks"] == 5
