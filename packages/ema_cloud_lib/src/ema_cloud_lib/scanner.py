"""
EMA Cloud Scanner Core

Core scanner functionality for real-time EMA Cloud monitoring.
Based on Ripster's EMA Cloud methodology.
"""

import asyncio
import logging
from datetime import datetime, time, timedelta

import pandas as pd

from ema_cloud_lib.alerts.handlers import AlertManager, create_alert_from_signal
from ema_cloud_lib.config.settings import (
    SYMBOL_TO_SECTOR,
    TRADING_PRESETS,
    ScannerConfig,
)
from ema_cloud_lib.data_providers.base import DataProviderManager
from ema_cloud_lib.holdings.manager import HoldingsManager
from ema_cloud_lib.indicators.ema_cloud import EMACloudIndicator
from ema_cloud_lib.signals.generator import SectorTrendState, Signal, SignalGenerator
from ema_cloud_lib.types.display import ETFDisplayData, SignalDisplayData
from ema_cloud_lib.types.protocols import DashboardProtocol

logger = logging.getLogger(__name__)


class MarketHours:
    """Market hours utilities"""

    # US Market hours (Eastern Time)
    MARKET_OPEN = time(9, 30)
    MARKET_CLOSE = time(16, 0)
    PRE_MARKET_OPEN = time(4, 0)
    AFTER_HOURS_CLOSE = time(20, 0)

    @classmethod
    def is_market_open(cls, check_time: datetime | None = None) -> bool:
        """Check if market is currently open"""
        if check_time is None:
            check_time = datetime.now()

        # Check if weekday (Mon=0, Sun=6)
        if check_time.weekday() >= 5:
            return False

        current_time = check_time.time()
        return cls.MARKET_OPEN <= current_time <= cls.MARKET_CLOSE

    @classmethod
    def is_extended_hours(cls, check_time: datetime | None = None) -> bool:
        """Check if in extended trading hours"""
        if check_time is None:
            check_time = datetime.now()

        if check_time.weekday() >= 5:
            return False

        current_time = check_time.time()

        # Pre-market or after-hours
        pre_market = cls.PRE_MARKET_OPEN <= current_time < cls.MARKET_OPEN
        after_hours = cls.MARKET_CLOSE < current_time <= cls.AFTER_HOURS_CLOSE

        return pre_market or after_hours

    @classmethod
    def time_to_open(cls, check_time: datetime | None = None) -> timedelta | None:
        """Get time until market opens"""
        if check_time is None:
            check_time = datetime.now()

        if cls.is_market_open(check_time):
            return timedelta(0)

        # Find next market open
        next_open = check_time.replace(
            hour=cls.MARKET_OPEN.hour, minute=cls.MARKET_OPEN.minute, second=0, microsecond=0
        )

        # If past close, move to next day
        if check_time.time() > cls.MARKET_CLOSE:
            next_open += timedelta(days=1)

        # Skip weekends
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)

        return next_open - check_time


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

        # Dashboard (optional, set via set_dashboard())
        self._dashboard: DashboardProtocol | None = None

        # State tracking
        self._running = False
        self._sector_states: dict[str, SectorTrendState] = {}
        self._recent_signals: dict[str, Signal] = {}
        self._signal_cooldown: dict[str, datetime] = {}

        # Cooldown period to avoid duplicate signals (minutes)
        self.signal_cooldown_minutes = 15

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
        return {
            "console": {
                "enabled": self.config.alerts.console_enabled,
                "colors": self.config.alerts.console_colors,
            },
            "desktop": {
                "enabled": self.config.alerts.desktop_enabled,
                "sound": self.config.alerts.desktop_sound,
            },
            "telegram": {
                "enabled": self.config.alerts.telegram_enabled,
                "bot_token": self.config.alerts.telegram_bot_token,
                "chat_id": self.config.alerts.telegram_chat_id,
            },
            "discord": {
                "enabled": self.config.alerts.discord_enabled,
                "webhook_url": self.config.alerts.discord_webhook_url,
            },
        }

    def _data_provider_config_dict(self) -> dict[str, dict]:
        return {
            "yahoo": {"enabled": self.config.data_provider.yahoo_enabled},
            "alpaca": {
                "enabled": self.config.data_provider.alpaca_enabled,
                "api_key": self.config.data_provider.alpaca_api_key,
                "secret_key": self.config.data_provider.alpaca_secret_key,
                "paper": self.config.data_provider.alpaca_paper,
            },
            "polygon": {
                "enabled": self.config.data_provider.polygon_enabled,
                "api_key": self.config.data_provider.polygon_api_key,
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
        """Apply a new configuration and rebuild dependent components."""
        self.config = config
        self.data_manager = DataProviderManager(self._data_provider_config_dict())
        self.cloud_indicator, self.signal_generator = self._build_indicators()
        self.alert_manager = AlertManager.create_default(self._alert_config_dict())

    def _get_etf_list(self) -> list[str]:
        """Get list of ETFs to scan based on config"""
        return self.config.get_active_etf_symbols()

    async def fetch_data(
        self, symbol: str, interval: str = "10m", lookback_days: int = 5
    ) -> pd.DataFrame | None:
        """Fetch historical data for a symbol"""
        try:
            start = datetime.now() - timedelta(days=lookback_days)
            df = await self.data_manager.get_historical_data(
                symbol=symbol, interval=interval, start=start
            )
            return df
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None

    async def analyze_etf(self, symbol: str) -> dict | None:
        """
        Analyze a single ETF and return analysis results.
        """
        # Fetch data
        preset = TRADING_PRESETS.get(self.config.trading_style, {})
        interval = preset.get("timeframe", "10m")

        df = await self.fetch_data(symbol, interval)
        if df is None or len(df) < 50:
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
        }

    async def scan_all_etfs(self) -> list[dict]:
        """Scan all configured ETFs"""
        etfs = self._get_etf_list()
        results = []

        # Fetch all data concurrently
        tasks = [self.analyze_etf(etf) for etf in etfs]
        analyses = await asyncio.gather(*tasks, return_exceptions=True)

        for etf, analysis in zip(etfs, analyses, strict=False):
            if isinstance(analysis, Exception):
                logger.error(f"Analysis failed for {etf}: {analysis}")
                continue
            if analysis:
                results.append(analysis)

        return results

    def _should_alert_signal(self, signal: Signal) -> bool:
        """Check if we should alert for this signal (cooldown check)"""
        key = f"{signal.symbol}|{signal.direction}|{signal.signal_type.value}"

        last_alert = self._signal_cooldown.get(key)
        if last_alert:
            elapsed = datetime.now() - last_alert
            if elapsed.total_seconds() < self.signal_cooldown_minutes * 60:
                return False

        # Update cooldown
        self._signal_cooldown[key] = datetime.now()
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

            self._dashboard.update_etf_data(
                ETFDisplayData(
                    symbol=analysis["symbol"],
                    name=analysis["symbol"],
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
                )
            )

    async def run_scan_cycle(self):
        """Run a single scan cycle"""
        logger.info("Starting scan cycle...")

        analyses = await self.scan_all_etfs()

        if analyses:
            await self.process_signals(analyses)
            self._update_dashboard(analyses)

        logger.info(f"Scan complete. Analyzed {len(analyses)} ETFs.")

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
