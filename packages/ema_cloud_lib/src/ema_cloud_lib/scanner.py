"""
EMA Cloud Scanner Core

Core scanner functionality for real-time EMA Cloud monitoring.
Based on Ripster's EMA Cloud methodology.
"""

import asyncio
import logging
from datetime import datetime, timedelta

import pandas as pd

from ema_cloud_lib.alerts import AlertManager, AlertMessage, create_alert_from_signal
from ema_cloud_lib.config.settings import (
    SYMBOL_TO_SECTOR,
    ScannerConfig,
)
from ema_cloud_lib.constants import (
    HOLDINGS_CACHE_TTL_HOURS,
    MIN_BARS_FOR_ANALYSIS,
    SIGNAL_COOLDOWN_CLEANUP_THRESHOLD,
    SIGNAL_COOLDOWN_RETENTION_HOURS,
    TrendDirection,
    utc_now,
)
from ema_cloud_lib.data_providers.base import DataProviderManager
from ema_cloud_lib.holdings.holdings_scanner import HoldingsScanner, SectorTrend
from ema_cloud_lib.holdings.manager import Holding, HoldingsManager
from ema_cloud_lib.indicators.ema_cloud import EMACloudIndicator
from ema_cloud_lib.indicators.mtf_analyzer import MTFAnalysisResult, MultiTimeframeAnalyzer
from ema_cloud_lib.market_hours import MarketHours
from ema_cloud_lib.signals.generator import SectorTrendState, Signal, SignalGenerator
from ema_cloud_lib.types.display import (
    ETFDisplayData,
    HoldingDisplayData,
    HoldingsETFDisplayData,
    MTFDisplayData,
    SignalDisplayData,
)
from ema_cloud_lib.types.protocols import DashboardProtocol

logger = logging.getLogger(__name__)


class EMACloudScanner:
    """
    Main scanner class for real-time EMA Cloud monitoring.

    This is the core library class. Dashboard integration is handled
    via dependency injection using set_dashboard().
    """

    def __init__(self, config: ScannerConfig | None = None):
        self.config = config or ScannerConfig()

        # Initialize components
        self.data_manager = DataProviderManager(self._data_provider_config_dict())

        self.cloud_indicator, self.signal_generator = self._build_indicators()

        self.holdings_manager = HoldingsManager()
        self.alert_manager = AlertManager.create_default(self._alert_config_dict())

        # Holdings scanner (initialized if enabled)
        self.holdings_scanner: HoldingsScanner | None = None
        if self.config.scan_holdings:
            self.holdings_scanner = HoldingsScanner(
                config=self.config,
                data_manager=self.data_manager,
                cloud_indicator=self.cloud_indicator,
                signal_generator=self.signal_generator,
            )
            logger.info("Holdings scanner enabled")

        # Multi-timeframe analyzer (initialized if enabled)
        self.mtf_analyzer: MultiTimeframeAnalyzer | None = None
        if self.config.mtf.enabled:
            self.mtf_analyzer = MultiTimeframeAnalyzer(
                timeframes=self.config.mtf.timeframes, cloud_configs=self.config.ema_clouds
            )
            logger.info(
                f"Multi-timeframe analyzer enabled for: {', '.join(self.config.mtf.timeframes)}"
            )

        # Dashboard (optional, set via set_dashboard())
        self._dashboard: DashboardProtocol | None = None

        # State tracking
        self._running = False
        self._sector_states: dict[str, SectorTrendState] = {}
        self._recent_signals: dict[str, Signal] = {}
        self._signal_cooldown: dict[str, datetime] = {}
        self._mtf_results: dict[str, MTFAnalysisResult] = {}  # symbol -> MTF result

        # Holdings cache (symbol -> (timestamp, holdings))
        self._holdings_cache: dict[str, tuple[datetime, list[Holding]]] = {}
        self._holdings_cache_ttl = timedelta(hours=HOLDINGS_CACHE_TTL_HOURS)

        # Cooldown period to avoid duplicate signals (minutes) - from config
        self.signal_cooldown_minutes = self.config.signal_cooldown_minutes

    @property
    def dashboard(self) -> DashboardProtocol | None:
        """Get the current dashboard instance"""
        return self._dashboard

    def set_dashboard(self, dashboard: DashboardProtocol | None) -> None:
        """
        Set the dashboard for displaying scan results.

        Args:
            dashboard: A dashboard implementing DashboardProtocol, or None to disable
        """
        self._dashboard = dashboard

    def _alert_config_dict(self) -> dict[str, dict]:
        return self.config.alerts.to_dict

    def _data_provider_config_dict(self) -> dict[str, dict]:
        dp = self.config.data_provider
        return {
            "yahoo": {"enabled": dp.yahoo_enabled},
            "alpaca": {
                "enabled": dp.alpaca_enabled,
                "api_key": dp.alpaca_api_key.get_secret_value() if dp.alpaca_api_key else None,
                "secret_key": dp.alpaca_secret_key.get_secret_value()
                if dp.alpaca_secret_key
                else None,
                "paper": dp.alpaca_paper,
            },
            "polygon": {
                "enabled": dp.polygon_enabled,
                "api_key": dp.polygon_api_key.get_secret_value() if dp.polygon_api_key else None,
            },
        }

    def _build_indicators(self) -> tuple[EMACloudIndicator, SignalGenerator]:
        clouds_config = {
            name: (cfg.fast_period, cfg.slow_period) for name, cfg in self.config.ema_clouds.items()
        }
        indicator = EMACloudIndicator(clouds_config=clouds_config)
        generator = SignalGenerator(
            clouds_config=clouds_config,
            filter_config=self.config.filters,
            trading_style=self.config.trading_style,
        )
        return indicator, generator

    def apply_config(self, config: ScannerConfig) -> None:
        """
        Apply a new configuration and rebuild dependent components.

        If configuration fails to apply, automatically rolls back to previous config.
        """
        # Save current configuration for rollback
        old_config = self.config
        old_data_manager = self.data_manager
        old_cloud_indicator = self.cloud_indicator
        old_signal_generator = self.signal_generator
        old_alert_manager = self.alert_manager

        try:
            # Apply new configuration
            self.config = config
            self.data_manager = DataProviderManager(self._data_provider_config_dict())
            self.cloud_indicator, self.signal_generator = self._build_indicators()
            self.alert_manager = AlertManager.create_default(self._alert_config_dict())
        except Exception as e:
            # Rollback to previous configuration on failure
            logger.error(f"Failed to apply configuration: {e}")
            logger.info("Rolling back to previous configuration")
            self.config = old_config
            self.data_manager = old_data_manager
            self.cloud_indicator = old_cloud_indicator
            self.signal_generator = old_signal_generator
            self.alert_manager = old_alert_manager
            raise RuntimeError(f"Configuration rollback performed due to: {e}") from e

        # Reinitialize holdings scanner if enabled
        if self.config.scan_holdings:
            self.holdings_scanner = HoldingsScanner(
                config=self.config,
                data_manager=self.data_manager,
                cloud_indicator=self.cloud_indicator,
                signal_generator=self.signal_generator,
            )
            logger.info("Holdings scanner reinitialized")
        else:
            self.holdings_scanner = None
            logger.info("Holdings scanner disabled")

        # Reinitialize MTF analyzer if enabled
        if self.config.mtf.enabled:
            self.mtf_analyzer = MultiTimeframeAnalyzer(
                timeframes=self.config.mtf.timeframes,
                cloud_configs=self.config.ema_clouds,
            )
            logger.info(
                f"MTF analyzer reinitialized for: {', '.join(self.config.mtf.timeframes)}"
            )
        else:
            self.mtf_analyzer = None
            logger.info("MTF analyzer disabled")

    def _get_etf_list(self) -> list[str]:
        """Get list of ETFs to scan based on config"""
        return self.config.get_active_etf_symbols()

    async def fetch_data(
        self, symbol: str, interval: str = "10m", lookback_days: int = 5
    ) -> pd.DataFrame | None:
        """Fetch historical data for a symbol"""
        from ema_cloud_lib.data_providers.base import DataProviderError

        try:
            start = utc_now() - timedelta(days=lookback_days)
            df = await self.data_manager.get_historical_data(
                symbol=symbol, interval=interval, start=start
            )
            return df
        except DataProviderError as e:
            logger.error(f"Data provider error for {symbol}: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"Data processing error for {symbol}: {e}")
            return None

    async def analyze_etf(self, symbol: str) -> dict | None:
        """
        Analyze a single ETF and return analysis results.
        """
        # Fetch data
        preset = self.config.get_preset()
        primary_tf = preset.get("primary_timeframe")
        interval = primary_tf.interval if primary_tf else "10m"

        df = await self.fetch_data(symbol, interval)
        if df is None or len(df) < MIN_BARS_FOR_ANALYSIS:
            return None

        # Prepare data with indicators
        prepared_df = self.signal_generator.prepare_data(df)

        # Get trend analysis
        trend = self.signal_generator.analyze_trend(prepared_df, symbol)

        # Get cloud states
        clouds = self.cloud_indicator.analyze_single(prepared_df, -1)

        # Generate signals
        signals = self.signal_generator.generate_signals(prepared_df, symbol)

        # Update sector state
        sector_name = SYMBOL_TO_SECTOR.get(symbol, symbol)
        self._sector_states[symbol] = self.signal_generator.get_sector_trend_state(
            prepared_df, symbol, sector_name
        )

        # Multi-timeframe analysis (if enabled)
        mtf_result = None
        if self.mtf_analyzer:
            try:
                mtf_result = await self.mtf_analyzer.analyze(
                    symbol=symbol,
                    data_fetcher=self._fetch_mtf_data,
                    bars_per_tf=self.config.mtf.bars_per_timeframe,
                )
                self._mtf_results[symbol] = mtf_result
                logger.debug(f"MTF analysis for {symbol}: {mtf_result.summary}")
            except Exception as e:
                logger.error(f"MTF analysis failed for {symbol}: {e}")

        # Get latest row for display
        latest = prepared_df.iloc[-1]
        prev_close = prepared_df.iloc[-2]["close"] if len(prepared_df) > 1 else latest["close"]
        change_pct = ((latest["close"] - prev_close) / prev_close) * 100

        return {
            "symbol": symbol,
            "sector": sector_name,
            "price": latest["close"],
            "change_pct": change_pct,
            "trend": trend,
            "clouds": clouds,
            "signals": signals,
            "rsi": latest.get("rsi"),
            "adx": latest.get("adx"),
            "volume_ratio": latest.get("volume_ratio"),
            "mtf_result": mtf_result,
        }

    async def _fetch_mtf_data(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame | None:
        """
        Fetch data for multi-timeframe analysis.

        Args:
            symbol: Symbol to fetch
            timeframe: Timeframe interval (e.g., '1d', '4h', '1h')
            limit: Number of bars to fetch

        Returns:
            DataFrame with OHLCV data
        """
        try:
            # Calculate lookback period based on timeframe
            lookback_days = self._calculate_lookback(timeframe, limit)
            start = datetime.now() - timedelta(days=lookback_days)

            df = await self.data_manager.get_historical_data(
                symbol=symbol, interval=timeframe, start=start
            )
            return df
        except Exception as e:
            logger.error(f"Error fetching MTF data for {symbol} ({timeframe}): {e}")
            return None

    def _calculate_lookback(self, timeframe: str, bars: int) -> int:
        """Calculate lookback days needed for a timeframe"""
        # Estimate days needed based on timeframe
        tf_to_days = {
            "1m": max(2, bars // (24 * 60)),
            "5m": max(3, bars // (24 * 12)),
            "15m": max(5, bars // (24 * 4)),
            "1h": max(10, bars // 24),
            "4h": max(30, bars // 6),
            "1d": max(round(bars * 1.5), 300),  # ~1.5x buffer for weekends/holidays
            "1w": max(bars * 10, 730),  # Allow for weekly bars
        }
        return tf_to_days.get(timeframe, 30)

    async def scan_etf_holdings(self, etf_symbol: str) -> list[dict] | None:
        """
        Scan holdings of a sector ETF for individual stock signals.

        Args:
            etf_symbol: Sector ETF symbol

        Returns:
            List of stock signal dictionaries, or None if holdings scanning disabled
        """
        if not self.holdings_scanner:
            return None

        # Get sector trend for filtering
        sector_state = self._sector_states.get(etf_symbol)
        if sector_state:
            # Convert SectorTrendState to SectorTrend for filtering
            sector_trend = self._sector_trend_from_state(sector_state)
            trend_strength = int(sector_state.trend_strength * 100)
            self.holdings_scanner.update_sector_trend(etf_symbol, sector_trend, trend_strength)

        # Scan holdings
        max_concurrent = self.config.holdings_max_concurrent
        stock_signals = await self.holdings_scanner.scan_holdings(etf_symbol, max_concurrent)

        if not stock_signals:
            return None

        # Convert to display format
        results = []
        for context in stock_signals:
            signal = context.signal
            results.append(
                {
                    "symbol": signal.symbol,
                    "sector_etf": context.sector_etf,
                    "sector_trend": context.sector_trend.value,
                    "signal_type": signal.signal_type.value,
                    "direction": signal.direction,
                    "strength": signal.strength.value,
                    "price": signal.price,
                    "timestamp": signal.timestamp,
                    "filters_passed": signal.filters_passed,
                }
            )

        return results

    def _sector_trend_from_state(self, state: SectorTrendState) -> SectorTrend:
        """
        Convert SectorTrendState to SectorTrend enum.

        Args:
            state: Sector trend state from signal generator

        Returns:
            SectorTrend enum value
        """
        trend_str = state.trend_direction.lower()
        if TrendDirection.BULLISH.value in trend_str:
            return SectorTrend.BULLISH
        elif TrendDirection.BEARISH.value in trend_str:
            return SectorTrend.BEARISH
        else:
            return SectorTrend.NEUTRAL

    def _create_signal_display_data(
        self, signal_data: dict, signal_type_suffix: str = "", notes: str = ""
    ) -> SignalDisplayData:
        """
        Create SignalDisplayData from signal dictionary.

        Args:
            signal_data: Signal data dictionary
            signal_type_suffix: Optional suffix to append to signal type
            notes: Optional notes for the signal

        Returns:
            SignalDisplayData instance
        """
        signal_type = signal_data["signal_type"]
        if signal_type_suffix:
            signal_type = f"{signal_type} {signal_type_suffix}"

        return SignalDisplayData(
            symbol=signal_data["symbol"],
            timestamp=signal_data["timestamp"],
            signal_type=signal_type,
            direction=signal_data["direction"],
            strength=signal_data["strength"],
            price=signal_data["price"],
            is_valid=signal_data.get("filters_passed", True),
            notes=notes,
        )

    async def scan_all_etfs(self) -> list[dict]:  # type: ignore[type-arg]
        """Scan all configured ETFs"""
        etfs = self._get_etf_list()
        results: list[dict] = []  # type: ignore[type-arg]

        # Fetch all data concurrently
        tasks = [self.analyze_etf(etf) for etf in etfs]
        analyses = await asyncio.gather(*tasks, return_exceptions=True)

        for etf, analysis in zip(etfs, analyses, strict=False):
            if isinstance(analysis, BaseException):
                logger.error(f"Analysis failed for {etf}: {analysis}")
                continue
            if analysis:
                results.append(analysis)

        return results

    def _should_alert_signal(self, signal: Signal) -> bool:
        """Check if we should alert for this signal (cooldown check)"""
        # Cleanup expired entries periodically to prevent memory leak
        if len(self._signal_cooldown) > SIGNAL_COOLDOWN_CLEANUP_THRESHOLD:
            cutoff = datetime.now() - timedelta(hours=SIGNAL_COOLDOWN_RETENTION_HOURS)
            self._signal_cooldown = {k: v for k, v in self._signal_cooldown.items() if v > cutoff}

        key = f"{signal.symbol}|{signal.direction}|{signal.signal_type.value}"

        last_alert = self._signal_cooldown.get(key)
        if last_alert:
            elapsed = utc_now() - last_alert
            if elapsed.total_seconds() < self.signal_cooldown_minutes * 60:
                return False

        # Update cooldown
        self._signal_cooldown[key] = utc_now()
        return True

    async def process_signals(self, analyses: list[dict]):
        """Process and alert on valid signals"""
        for analysis in analyses:
            for sig in analysis.get("signals", []):
                if sig.is_valid() and self._should_alert_signal(sig):
                    # Create alert
                    alert = create_alert_from_signal(sig)
                    await self.alert_manager.send_alert(alert)

                    # Update dashboard
                    if self._dashboard:
                        self._dashboard.add_signal(
                            SignalDisplayData(
                                timestamp=sig.timestamp,
                                symbol=sig.symbol,
                                direction=sig.direction,
                                signal_type=sig.signal_type.value,
                                price=sig.price,
                                strength=sig.strength.name,
                                is_valid=sig.is_valid(),
                                notes="",
                            )
                        )

    def _update_dashboard(self, analyses: list[dict]):
        """Update dashboard with latest data"""
        if not self._dashboard:
            return

        for analysis in analyses:
            trend = analysis["trend"]
            symbol = analysis["symbol"]

            # Prepare MTF display data if available
            mtf_data = None
            if symbol in self._mtf_results:
                mtf_result = self._mtf_results[symbol]
                mtf_data = MTFDisplayData(
                    enabled=True,
                    alignment=mtf_result.alignment.value,
                    confidence=mtf_result.confidence.value,
                    bias=mtf_result.bias,
                    bullish_count=mtf_result.bullish_count,
                    bearish_count=mtf_result.bearish_count,
                    neutral_count=mtf_result.neutral_count,
                    total_timeframes=len(mtf_result.timeframes),
                    alignment_pct=mtf_result.alignment_pct,
                    summary=mtf_result.summary,
                )

            self._dashboard.update_etf_data(
                ETFDisplayData(
                    symbol=symbol,
                    name=symbol,
                    sector=analysis["sector"],
                    price=analysis["price"],
                    change_pct=analysis["change_pct"],
                    trend=trend.overall_trend,
                    trend_strength=trend.trend_strength,
                    cloud_state=trend.primary_cloud_state.name
                    if trend.primary_cloud_state
                    else "UNKNOWN",
                    signals_count=len([s for s in analysis["signals"] if s.is_valid()]),
                    rsi=analysis.get("rsi"),
                    adx=analysis.get("adx"),
                    volume_ratio=analysis.get("volume_ratio"),
                    mtf=mtf_data,
                )
            )

    async def run_scan_cycle(self):
        """Run a single scan cycle"""
        logger.info("Starting scan cycle...")

        # Scan sector ETFs
        analyses = await self.scan_all_etfs()

        if analyses:
            await self.process_signals(analyses)
            self._update_dashboard(analyses)

        # Scan holdings if enabled
        if self.holdings_scanner and self.config.scan_holdings:
            await self._scan_all_holdings(analyses)

        logger.info(f"Scan complete. Analyzed {len(analyses)} ETFs.")

    async def _scan_all_holdings(self, etf_analyses: list[dict]) -> None:
        """
        Scan holdings for all analyzed ETFs.

        Args:
            etf_analyses: List of ETF analysis results
        """
        if not self.holdings_scanner:
            return

        # Fetch holdings with metadata (using cache)
        etf_symbols = [analysis["symbol"] for analysis in etf_analyses]
        holdings_by_etf: dict[str, list[Holding]] = {}
        total_holdings_by_etf: dict[str, int] = {}
        etf_names: dict[str, str] = {}

        # Check cache first and build list of symbols needing fetch
        symbols_to_fetch = []
        now = datetime.now()

        for symbol in etf_symbols:
            if symbol in self._holdings_cache:
                cache_time, cached_holdings = self._holdings_cache[symbol]
                if now - cache_time < self._holdings_cache_ttl:
                    # Use cached data
                    holdings_by_etf[symbol] = cached_holdings
                    total_holdings_by_etf[symbol] = len(cached_holdings)
                    etf_names[symbol] = symbol
                    continue
            symbols_to_fetch.append(symbol)

        # Fetch only uncached symbols
        if symbols_to_fetch:
            holdings_results = await asyncio.gather(
                *[self.holdings_manager.get_holdings(symbol) for symbol in symbols_to_fetch],
                return_exceptions=True,
            )
        else:
            holdings_results = []

        for etf_symbol, holdings in zip(symbols_to_fetch, holdings_results, strict=False):
            if isinstance(holdings, Exception):
                logger.warning(f"Holdings lookup failed for {etf_symbol}: {holdings}")
                # Set empty defaults to prevent KeyError later
                holdings_by_etf[etf_symbol] = []
                total_holdings_by_etf[etf_symbol] = 0
                etf_names[etf_symbol] = etf_symbol
                continue
            if holdings:
                top_holdings = holdings.get_top_holdings(self.config.top_holdings_count)
                holdings_by_etf[etf_symbol] = top_holdings
                total_holdings_by_etf[etf_symbol] = len(top_holdings)
                etf_names[etf_symbol] = holdings.etf_name
                # Cache the holdings
                self._holdings_cache[etf_symbol] = (now, top_holdings)
            else:
                custom_holdings = self.holdings_manager.get_custom_holdings(etf_symbol)
                if custom_holdings:
                    holdings_by_etf[etf_symbol] = [
                        Holding(symbol=symbol, name=symbol, weight=0.0)
                        for symbol in custom_holdings[: self.config.top_holdings_count]
                    ]
                    total_holdings_by_etf[etf_symbol] = len(custom_holdings)
                    etf_names[etf_symbol] = etf_symbol
                else:
                    # No holdings available for this ETF
                    holdings_by_etf[etf_symbol] = []
                    total_holdings_by_etf[etf_symbol] = 0
                    etf_names[etf_symbol] = etf_symbol

        # Set holdings in scanner
        holdings_symbols = {
            etf_symbol: [holding.symbol for holding in holdings]
            for etf_symbol, holdings in holdings_by_etf.items()
        }
        self.holdings_scanner.set_holdings(holdings_symbols)

        logger.info(f"Scanning holdings for {len(etf_symbols)} sector ETFs")

        # Scan each ETF's holdings
        all_stock_signals = []
        for etf_symbol in etf_symbols:
            stock_signals = await self.scan_etf_holdings(etf_symbol)
            if stock_signals:
                all_stock_signals.extend(stock_signals)
            self._update_holdings_dashboard(
                etf_symbol,
                holdings_by_etf.get(etf_symbol, []),
                stock_signals or [],
                total_holdings_by_etf.get(etf_symbol),
                etf_names.get(etf_symbol),
            )

        if all_stock_signals:
            logger.info(f"Found {len(all_stock_signals)} stock signals across all holdings")
            await self._process_holdings_signals(all_stock_signals)
        else:
            logger.debug("No stock signals found in holdings")

    async def _process_holdings_signals(self, stock_signals: list[dict]) -> None:
        """
        Process and alert on stock signals from holdings.

        Args:
            stock_signals: List of stock signal dictionaries
        """
        for signal_data in stock_signals:
            # Create alert message
            alert_msg = self._format_stock_signal_alert(signal_data)

            # Send alert
            await self.alert_manager.send_alert(alert_msg)

            # Update dashboard if available
            if self._dashboard:
                # Convert to SignalDisplayData format using helper
                signal_display = self._create_signal_display_data(
                    signal_data,
                    signal_type_suffix=f"(Holdings: {signal_data['sector_etf']})",
                    notes="Holdings signal",
                )
                self._dashboard.add_signal(signal_display)

    def _update_holdings_dashboard(
        self,
        etf_symbol: str,
        holdings: list[Holding],
        stock_signals: list[dict],
        total_holdings: int | None,
        etf_name: str | None,
    ) -> None:
        """Update dashboard holdings view with latest data."""
        if not self._dashboard:
            return

        sector_state = self._sector_states.get(etf_symbol)
        sector_trend = (
            self._sector_trend_from_state(sector_state).value
            if sector_state
            else SectorTrend.NEUTRAL.value
        )

        holdings_by_symbol = {holding.symbol: holding for holding in holdings}
        signals_by_symbol = {signal["symbol"]: signal for signal in stock_signals}

        display_holdings: list[HoldingDisplayData] = []
        for holding in holdings:
            signal = signals_by_symbol.get(holding.symbol)
            display_holdings.append(
                HoldingDisplayData(
                    symbol=holding.symbol,
                    company=holding.name,
                    weight=holding.weight,
                    price=signal["price"] if signal else None,
                    direction=signal["direction"] if signal else None,
                    signal_type=signal["signal_type"] if signal else None,
                    strength=signal["strength"] if signal else None,
                    timestamp=signal["timestamp"] if signal else None,
                )
            )

        for symbol, signal in signals_by_symbol.items():
            if symbol in holdings_by_symbol:
                continue
            display_holdings.append(
                HoldingDisplayData(
                    symbol=symbol,
                    company=None,
                    weight=None,
                    price=signal["price"],
                    direction=signal["direction"],
                    signal_type=signal["signal_type"],
                    strength=signal["strength"],
                    timestamp=signal["timestamp"],
                )
            )

        self._dashboard.update_holdings_data(
            HoldingsETFDisplayData(
                etf_symbol=etf_symbol,
                etf_name=etf_name,
                sector=SYMBOL_TO_SECTOR.get(etf_symbol, etf_symbol),
                sector_trend=sector_trend,
                total_holdings=total_holdings,
                holdings=display_holdings,
            )
        )

    def _format_stock_signal_alert(self, signal_data: dict) -> AlertMessage:  # type: ignore[type-arg]
        """
        Format stock signal as AlertMessage.

        Args:
            signal_data: Stock signal dictionary

        Returns:
            AlertMessage for the alert system
        """
        symbol = signal_data["symbol"]
        sector_etf = signal_data["sector_etf"]
        sector_trend = signal_data["sector_trend"]
        signal_type = signal_data["signal_type"]
        direction = signal_data["direction"]
        strength = signal_data["strength"]
        price = signal_data["price"]

        direction_arrow = "↑" if direction == "long" else "↓"

        return AlertMessage(
            title=f"🎯 HOLDINGS SIGNAL: {symbol} ({sector_etf})",
            body=(
                f"Signal: {signal_type} {direction_arrow}\n"
                f"Strength: {strength.upper()}\n"
                f"Price: ${price:.2f}\n"
                f"Sector Trend: {sector_trend.upper()}\n"
                f"Filters: {signal_data['filters_passed']}"
            ),
            symbol=symbol,
            signal_type=signal_type,
            direction=direction,
            strength=strength,
            price=price,
            timestamp=signal_data.get("timestamp", utc_now()),
        )

    async def run(
        self,
        scan_interval_seconds: int | None = None,
        market_hours_only: bool = True,
    ):
        """
        Main run loop for continuous scanning.

        Note: Dashboard must be set via set_dashboard() before calling run()
        if you want dashboard output. The dashboard task management is handled
        by the caller (typically CLI).
        """
        self._running = True

        try:
            while self._running:
                # Check market hours
                if market_hours_only and not MarketHours.is_market_open():
                    time_to_open = MarketHours.time_to_open()
                    if time_to_open and time_to_open.total_seconds() > 0:
                        logger.info(f"Market closed. Opens in {time_to_open}")

                        # Wait until closer to market open (check every 5 minutes)
                        wait_time = min(time_to_open.total_seconds(), 300)
                        await asyncio.sleep(wait_time)
                        continue

                # Run scan
                await self.run_scan_cycle()

                # Wait for next interval
                interval = (
                    self.config.scan_interval
                    if scan_interval_seconds is None
                    else scan_interval_seconds
                )
                await asyncio.sleep(interval)

        except asyncio.CancelledError:
            logger.info("Scanner cancelled")
        finally:
            self._running = False

    def stop(self):
        """Stop the scanner"""
        self._running = False

    @property
    def is_running(self) -> bool:
        """Check if scanner is currently running"""
        return self._running
