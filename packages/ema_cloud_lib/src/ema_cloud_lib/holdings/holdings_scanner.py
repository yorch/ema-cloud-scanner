"""Holdings Scanner for individual stock signals within sector ETFs."""

import asyncio
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ..config.settings import ScannerConfig
from ..data_providers.base import DataProviderManager
from ..indicators.ema_cloud import EMACloudIndicator
from ..signals.generator import Signal, SignalDirection, SignalGenerator, SignalStrength

logger = logging.getLogger(__name__)


class SectorTrend(StrEnum):
    """Sector ETF trend states."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class StockSignalContext:
    """Context for stock signal with sector information."""

    signal: Signal
    sector_etf: str
    sector_trend: SectorTrend
    filtered_by_sector: bool  # True if signal conflicts with sector trend
    sector_strength: int  # 0-100, sector trend strength


class HoldingsScanner:
    """
    Scanner for individual stock signals within sector ETF holdings.

    Filters stock signals based on sector ETF trend:
    - If sector ETF is BULLISH: Allow long signals, block shorts
    - If sector ETF is BEARISH: Allow short signals, block longs
    - If sector ETF is NEUTRAL: Allow both directions
    """

    def __init__(
        self,
        config: ScannerConfig,
        data_manager: DataProviderManager,
        cloud_indicator: EMACloudIndicator,
        signal_generator: SignalGenerator,
    ):
        self.config = config
        self.data_manager = data_manager
        self.cloud_indicator = cloud_indicator
        self.signal_generator = signal_generator

        # Track sector trends for filtering
        self._sector_trends: dict[str, SectorTrend] = {}
        self._sector_strengths: dict[str, int] = {}

        # Holdings cache
        self._etf_holdings: dict[str, list[str]] = {}

        logger.info("HoldingsScanner initialized")

    def update_sector_trend(self, etf_symbol: str, trend: SectorTrend, strength: int) -> None:
        """
        Update sector ETF trend state for filtering.

        Args:
            etf_symbol: Sector ETF symbol
            trend: Current trend direction
            strength: Trend strength (0-100)
        """
        self._sector_trends[etf_symbol] = trend
        self._sector_strengths[etf_symbol] = strength
        logger.debug(f"Updated {etf_symbol} trend: {trend} (strength: {strength}%)")

    def set_holdings(self, etf_holdings: dict[str, list[str]]) -> None:
        """
        Set holdings for scanning.

        Args:
            etf_holdings: Dict mapping ETF symbol to list of holding symbols
        """
        self._etf_holdings = etf_holdings
        total_stocks = sum(len(holdings) for holdings in etf_holdings.values())
        logger.info(f"Holdings set: {len(etf_holdings)} ETFs, {total_stocks} total stocks")

    async def scan_stock(self, symbol: str, sector_etf: str) -> StockSignalContext | None:
        """
        Scan individual stock for signals with sector context.

        Args:
            symbol: Stock symbol to scan
            sector_etf: Parent sector ETF symbol

        Returns:
            StockSignalContext if signal detected, None otherwise
        """
        try:
            # Fetch stock data
            preset = self.config.get_preset()
            primary_tf = preset.get("primary_timeframe")
            timeframe = primary_tf.interval if primary_tf else "10m"
            limit = primary_tf.bars_to_fetch if primary_tf else 500

            df = await self.data_manager.fetch_bars(symbol, timeframe, limit)
            if df is None or df.empty:
                logger.debug(f"No data for {symbol}")
                return None

            # Calculate EMA clouds
            df_with_clouds = self.cloud_indicator.calculate_all_clouds(df)

            # Generate signals
            signals = self.signal_generator.generate_signals(symbol, df_with_clouds)

            if not signals:
                return None

            # Get strongest signal
            signal = max(signals, key=lambda s: self._signal_strength_value(s.strength))

            # Get sector trend
            sector_trend = self._sector_trends.get(sector_etf, SectorTrend.NEUTRAL)
            sector_strength = self._sector_strengths.get(sector_etf, 50)

            # Check if signal conflicts with sector trend
            filtered = self._should_filter_signal(signal.direction, sector_trend)

            return StockSignalContext(
                signal=signal,
                sector_etf=sector_etf,
                sector_trend=sector_trend,
                filtered_by_sector=filtered,
                sector_strength=sector_strength,
            )

        except (ValueError, KeyError, IndexError) as e:
            logger.error(f"Data processing error scanning {symbol}: {e}")
            return None
        except OSError as e:
            logger.error(f"Network error scanning {symbol}: {e}")
            return None

    async def scan_holdings(
        self, etf_symbol: str, max_concurrent: int = 5
    ) -> list[StockSignalContext]:
        """
        Scan all holdings of a sector ETF for signals.

        Args:
            etf_symbol: Sector ETF symbol
            max_concurrent: Maximum concurrent scans

        Returns:
            List of stock signal contexts (filtered by sector trend)
        """
        holdings = self._etf_holdings.get(etf_symbol, [])
        if not holdings:
            logger.debug(f"No holdings for {etf_symbol}")
            return []

        logger.info(f"Scanning {len(holdings)} holdings for {etf_symbol}")

        # Scan stocks with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scan_with_limit(symbol: str) -> StockSignalContext | None:
            async with semaphore:
                return await self.scan_stock(symbol, etf_symbol)

        results = await asyncio.gather(
            *[scan_with_limit(symbol) for symbol in holdings],
            return_exceptions=True,
        )

        # Filter out None results and errors
        valid_signals = [
            r for r in results if isinstance(r, StockSignalContext) and not r.filtered_by_sector
        ]

        logger.info(f"Found {len(valid_signals)} valid stock signals in {etf_symbol} holdings")
        return valid_signals

    async def scan_all_holdings(
        self, etf_symbols: list[str] | None = None, max_concurrent: int = 5
    ) -> dict[str, list[StockSignalContext]]:
        """
        Scan holdings across multiple sector ETFs.

        Args:
            etf_symbols: List of ETF symbols to scan (None = all loaded holdings)
            max_concurrent: Maximum concurrent scans per ETF

        Returns:
            Dict mapping ETF symbol to list of stock signal contexts
        """
        if etf_symbols is None:
            etf_symbols = list(self._etf_holdings.keys())

        logger.info(f"Scanning holdings for {len(etf_symbols)} sector ETFs")

        results = {}
        for etf_symbol in etf_symbols:
            signals = await self.scan_holdings(etf_symbol, max_concurrent)
            if signals:
                results[etf_symbol] = signals

        total_signals = sum(len(signals) for signals in results.values())
        logger.info(f"Total stock signals found: {total_signals}")

        return results

    def _should_filter_signal(
        self, signal_direction: SignalDirection, sector_trend: SectorTrend
    ) -> bool:
        """
        Determine if signal should be filtered based on sector trend.

        Filtering Logic:
        - If sector is BULLISH: Block short signals
        - If sector is BEARISH: Block long signals
        - If sector is NEUTRAL: Allow all signals

        Args:
            signal_direction: Signal direction (LONG/SHORT)
            sector_trend: Sector ETF trend

        Returns:
            True if signal should be filtered (blocked), False otherwise
        """
        if sector_trend == SectorTrend.NEUTRAL:
            return False

        if sector_trend == SectorTrend.BULLISH and signal_direction == SignalDirection.SHORT:
            return True

        if sector_trend == SectorTrend.BEARISH and signal_direction == SignalDirection.LONG:
            return True

        return False

    def _signal_strength_value(self, strength: SignalStrength) -> int:
        """Convert signal strength to numeric value for comparison."""
        strength_map = {
            SignalStrength.VERY_STRONG: 5,
            SignalStrength.STRONG: 4,
            SignalStrength.MODERATE: 3,
            SignalStrength.WEAK: 2,
            SignalStrength.VERY_WEAK: 1,
        }
        return strength_map.get(strength, 0)

    def get_sector_filter_stats(self) -> dict[str, Any]:
        """
        Get statistics about sector filtering.

        Returns:
            Dict with filtering statistics
        """
        return {
            "sectors_tracked": len(self._sector_trends),
            "bullish_sectors": sum(
                1 for t in self._sector_trends.values() if t == SectorTrend.BULLISH
            ),
            "bearish_sectors": sum(
                1 for t in self._sector_trends.values() if t == SectorTrend.BEARISH
            ),
            "neutral_sectors": sum(
                1 for t in self._sector_trends.values() if t == SectorTrend.NEUTRAL
            ),
            "holdings_loaded": len(self._etf_holdings),
            "total_stocks": sum(len(h) for h in self._etf_holdings.values()),
        }
