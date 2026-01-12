"""
Configuration settings for EMA Cloud Sector Scanner
Based on Ripster's EMA Cloud Strategy

All settings are configurable and support presets for different trading styles.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class TradingStyle(Enum):
    """Trading style presets based on Ripster's recommendations"""

    SCALPING = "scalping"  # 1-5 minute charts
    INTRADAY = "intraday"  # 10-minute charts (Ripster's primary)
    SWING = "swing"  # 1-hour/4-hour charts
    POSITION = "position"  # Daily charts
    LONG_TERM = "long_term"  # Weekly charts


class TrendState(Enum):
    """Possible trend states for the EMA cloud"""

    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    WEAK_BULLISH = "weak_bullish"
    NEUTRAL = "neutral"
    WEAK_BEARISH = "weak_bearish"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"


class SignalType(Enum):
    """Types of signals generated"""

    CLOUD_FLIP_BULLISH = "cloud_flip_bullish"  # EMA cloud turns green
    CLOUD_FLIP_BEARISH = "cloud_flip_bearish"  # EMA cloud turns red
    PRICE_CROSS_ABOVE = "price_cross_above"  # Price crosses above cloud
    PRICE_CROSS_BELOW = "price_cross_below"  # Price crosses below cloud
    CLOUD_BOUNCE_LONG = "cloud_bounce_long"  # Price bounces off cloud support
    CLOUD_BOUNCE_SHORT = "cloud_bounce_short"  # Price bounces off cloud resistance
    TREND_CONFIRMATION = "trend_confirmation"  # Multiple timeframe confirmation
    PULLBACK_ENTRY = "pullback_entry"  # Pullback to 8-9 EMA cloud


@dataclass
class EMACloudConfig:
    """Configuration for a single EMA cloud"""

    fast_period: int
    slow_period: int
    name: str
    description: str
    color_bullish: str = "#26a69a"  # Green
    color_bearish: str = "#ef5350"  # Red
    enabled: bool = True


@dataclass
class TimeframeConfig:
    """Configuration for a specific timeframe"""

    interval: str  # e.g., "1m", "5m", "10m", "1h", "1d"
    display_name: str
    bars_to_fetch: int = 500  # Number of historical bars to load


# Ripster's EMA Cloud Configurations
DEFAULT_EMA_CLOUDS = {
    "trend_line": EMACloudConfig(
        fast_period=5,
        slow_period=12,
        name="Trend Line Cloud",
        description="5-12 EMA: Fluid trendline for day trades",
    ),
    "pullback": EMACloudConfig(
        fast_period=8,
        slow_period=9,
        name="Pullback Cloud",
        description="8-9 EMA: Pullback levels (optional)",
    ),
    "momentum": EMACloudConfig(
        fast_period=20,
        slow_period=21,
        name="Momentum Cloud",
        description="20-21 EMA: Short-term momentum",
    ),
    "trend_confirmation": EMACloudConfig(
        fast_period=34,
        slow_period=50,
        name="Trend Confirmation Cloud",
        description="34-50 EMA: Bullish/bearish bias confirmation (KEY CLOUD)",
    ),
    "long_term": EMACloudConfig(
        fast_period=72,
        slow_period=89,
        name="Long Term Cloud",
        description="72-89 EMA: Long-term trend direction",
    ),
    "major_trend": EMACloudConfig(
        fast_period=200,
        slow_period=233,
        name="Major Trend Cloud",
        description="200-233 EMA: Major trend/institutional levels",
    ),
}


# Trading Style Presets
TRADING_PRESETS = {
    TradingStyle.SCALPING: {
        "primary_timeframe": TimeframeConfig("1m", "1 Minute", 500),
        "confirmation_timeframes": [
            TimeframeConfig("5m", "5 Minute", 200),
        ],
        "enabled_clouds": ["trend_line", "pullback", "momentum"],
        "signal_confirmation_bars": 1,
        "min_cloud_thickness_pct": 0.02,  # 0.02%
    },
    TradingStyle.INTRADAY: {
        "primary_timeframe": TimeframeConfig("10m", "10 Minute", 500),
        "confirmation_timeframes": [
            TimeframeConfig("1h", "1 Hour", 200),
            TimeframeConfig("1d", "Daily", 100),
        ],
        "enabled_clouds": ["trend_line", "pullback", "trend_confirmation"],
        "signal_confirmation_bars": 2,
        "min_cloud_thickness_pct": 0.05,  # 0.05%
    },
    TradingStyle.SWING: {
        "primary_timeframe": TimeframeConfig("1h", "1 Hour", 500),
        "confirmation_timeframes": [
            TimeframeConfig("4h", "4 Hour", 200),
            TimeframeConfig("1d", "Daily", 100),
        ],
        "enabled_clouds": ["trend_line", "trend_confirmation", "long_term"],
        "signal_confirmation_bars": 2,
        "min_cloud_thickness_pct": 0.1,  # 0.1%
    },
    TradingStyle.POSITION: {
        "primary_timeframe": TimeframeConfig("1d", "Daily", 500),
        "confirmation_timeframes": [
            TimeframeConfig("1wk", "Weekly", 104),
        ],
        "enabled_clouds": ["trend_confirmation", "long_term", "major_trend"],
        "signal_confirmation_bars": 3,
        "min_cloud_thickness_pct": 0.2,  # 0.2%
    },
    TradingStyle.LONG_TERM: {
        "primary_timeframe": TimeframeConfig("1wk", "Weekly", 260),
        "confirmation_timeframes": [
            TimeframeConfig("1mo", "Monthly", 60),
        ],
        "enabled_clouds": ["trend_confirmation", "long_term", "major_trend"],
        "signal_confirmation_bars": 2,
        "min_cloud_thickness_pct": 0.5,  # 0.5%
    },
}


# Sector ETF Definitions - Configurable
SECTOR_ETFS = {
    "technology": {
        "symbol": "XLK",
        "name": "Technology Select Sector SPDR",
        "description": "Technology sector - IT services, semiconductors, software",
    },
    "financials": {
        "symbol": "XLF",
        "name": "Financial Select Sector SPDR",
        "description": "Financial sector - Banks, insurance, capital markets",
    },
    "healthcare": {
        "symbol": "XLV",
        "name": "Health Care Select Sector SPDR",
        "description": "Healthcare sector - Pharma, biotech, medical devices",
    },
    "energy": {
        "symbol": "XLE",
        "name": "Energy Select Sector SPDR",
        "description": "Energy sector - Oil, gas, energy equipment",
    },
    "consumer_discretionary": {
        "symbol": "XLY",
        "name": "Consumer Discretionary Select Sector SPDR",
        "description": "Consumer discretionary - Retail, auto, hotels",
    },
    "consumer_staples": {
        "symbol": "XLP",
        "name": "Consumer Staples Select Sector SPDR",
        "description": "Consumer staples - Food, beverage, household products",
    },
    "industrials": {
        "symbol": "XLI",
        "name": "Industrial Select Sector SPDR",
        "description": "Industrials - Aerospace, machinery, transportation",
    },
    "materials": {
        "symbol": "XLB",
        "name": "Materials Select Sector SPDR",
        "description": "Materials - Chemicals, metals, mining",
    },
    "utilities": {
        "symbol": "XLU",
        "name": "Utilities Select Sector SPDR",
        "description": "Utilities - Electric, gas, water utilities",
    },
    "real_estate": {
        "symbol": "XLRE",
        "name": "Real Estate Select Sector SPDR",
        "description": "Real estate - REITs, real estate services",
    },
    "communication_services": {
        "symbol": "XLC",
        "name": "Communication Services Select Sector SPDR",
        "description": "Communication - Media, entertainment, telecom",
    },
}


# ETF Subsets for quick selection
ETF_SUBSETS = {
    "all_sectors": list(SECTOR_ETFS.keys()),
    "growth_sectors": ["technology", "consumer_discretionary", "communication_services"],
    "defensive_sectors": ["utilities", "consumer_staples", "healthcare"],
    "cyclical_sectors": ["financials", "industrials", "materials", "energy"],
    "rate_sensitive": ["financials", "real_estate", "utilities"],
    "commodity_linked": ["energy", "materials"],
}


@dataclass
class FilterConfig:
    """Configuration for signal filters"""

    # Volume filter
    volume_enabled: bool = True
    volume_multiplier: float = 1.5  # Volume must be 1.5x average
    volume_lookback: int = 20  # 20-bar average volume

    # RSI filter
    rsi_enabled: bool = True
    rsi_period: int = 14
    rsi_overbought: float = 70.0
    rsi_oversold: float = 30.0
    rsi_neutral_zone: tuple = (45.0, 55.0)

    # ADX filter (trend strength)
    adx_enabled: bool = True
    adx_period: int = 14
    adx_min_strength: float = 20.0  # Minimum ADX for valid trend
    adx_strong_trend: float = 30.0

    # VWAP filter
    vwap_enabled: bool = True
    vwap_confirmation: bool = True  # Require price on correct side of VWAP

    # ATR filter (volatility)
    atr_enabled: bool = True
    atr_period: int = 14
    atr_min_threshold: float = 0.5  # Minimum ATR as % of price
    atr_max_threshold: float = 5.0  # Maximum ATR (avoid extreme volatility)

    # MACD confirmation
    macd_enabled: bool = False
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9

    # Time of day filter
    time_filter_enabled: bool = True
    avoid_first_minutes: int = 15  # Avoid first 15 minutes
    avoid_last_minutes: int = 15  # Avoid last 15 minutes
    trading_start_time: str = "09:30"
    trading_end_time: str = "16:00"


@dataclass
class AlertConfig:
    """Configuration for alerts"""

    # Console alerts
    console_enabled: bool = True
    console_colors: bool = True

    # Desktop notifications
    desktop_enabled: bool = True
    desktop_sound: bool = True

    # Future extensions (placeholders)
    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    discord_enabled: bool = False
    discord_webhook_url: str | None = None

    email_enabled: bool = False
    email_smtp_server: str | None = None
    email_recipients: list[str] = field(default_factory=list)


@dataclass
class DataProviderConfig:
    """Configuration for data providers"""

    # Yahoo Finance (default, free)
    yahoo_enabled: bool = True

    # Alpaca
    alpaca_enabled: bool = False
    alpaca_api_key: str | None = None
    alpaca_secret_key: str | None = None
    alpaca_paper: bool = True  # Use paper trading endpoint

    # Polygon.io
    polygon_enabled: bool = False
    polygon_api_key: str | None = None

    # Rate limiting
    request_delay_ms: int = 100
    max_concurrent_requests: int = 5


@dataclass
class BacktestConfig:
    """Configuration for backtesting"""

    enabled: bool = True
    start_date: str | None = None  # YYYY-MM-DD
    end_date: str | None = None
    initial_capital: float = 100000.0
    position_size_pct: float = 10.0  # % of capital per trade
    commission_per_trade: float = 0.0
    slippage_pct: float = 0.05


@dataclass
class ScannerConfig:
    """Main scanner configuration"""

    # Trading style preset
    trading_style: TradingStyle = TradingStyle.INTRADAY

    # Sector configuration
    active_sectors: list[str] = field(default_factory=lambda: ETF_SUBSETS["all_sectors"])
    custom_symbols: list[str] = field(default_factory=list)  # Additional symbols to scan

    # EMA Cloud settings
    ema_clouds: dict[str, EMACloudConfig] = field(default_factory=lambda: DEFAULT_EMA_CLOUDS.copy())

    # Filter settings
    filters: FilterConfig = field(default_factory=FilterConfig)

    # Alert settings
    alerts: AlertConfig = field(default_factory=AlertConfig)

    # Data provider settings
    data_provider: DataProviderConfig = field(default_factory=DataProviderConfig)

    # Backtest settings
    backtest: BacktestConfig = field(default_factory=BacktestConfig)

    # Scan interval (seconds)
    scan_interval: int = 60

    # Holdings settings
    fetch_holdings: bool = True
    top_holdings_count: int = 10  # Number of top holdings to track per ETF

    # Dashboard settings
    dashboard_refresh_rate: int = 5  # Seconds
    show_all_etfs: bool = True

    def get_preset(self) -> dict[str, Any]:
        """Get the current trading style preset configuration"""
        return TRADING_PRESETS[self.trading_style]

    def get_active_etf_symbols(self) -> list[str]:
        """Get list of active ETF symbols"""
        symbols = [SECTOR_ETFS[sector]["symbol"] for sector in self.active_sectors]
        symbols.extend(self.custom_symbols)
        return symbols

    def get_enabled_clouds(self) -> dict[str, EMACloudConfig]:
        """Get enabled EMA clouds based on trading style"""
        preset = self.get_preset()
        enabled_names = preset.get("enabled_clouds", list(self.ema_clouds.keys()))
        return {
            name: cloud
            for name, cloud in self.ema_clouds.items()
            if name in enabled_names and cloud.enabled
        }

    def save(self, filepath: str):
        """Save configuration to JSON file"""
        config_dict = {
            "trading_style": self.trading_style.value,
            "active_sectors": self.active_sectors,
            "custom_symbols": self.custom_symbols,
            "scan_interval": self.scan_interval,
            "fetch_holdings": self.fetch_holdings,
            "top_holdings_count": self.top_holdings_count,
            "filters": {
                "volume_enabled": self.filters.volume_enabled,
                "volume_multiplier": self.filters.volume_multiplier,
                "rsi_enabled": self.filters.rsi_enabled,
                "adx_enabled": self.filters.adx_enabled,
                "vwap_enabled": self.filters.vwap_enabled,
                "atr_enabled": self.filters.atr_enabled,
                "time_filter_enabled": self.filters.time_filter_enabled,
            },
            "alerts": {
                "console_enabled": self.alerts.console_enabled,
                "desktop_enabled": self.alerts.desktop_enabled,
            },
            "data_provider": {
                "yahoo_enabled": self.data_provider.yahoo_enabled,
                "alpaca_enabled": self.data_provider.alpaca_enabled,
                "polygon_enabled": self.data_provider.polygon_enabled,
            },
        }
        Path(filepath).write_text(json.dumps(config_dict, indent=2))

    @classmethod
    def load(cls, filepath: str) -> "ScannerConfig":
        """Load configuration from JSON file"""
        config_dict = json.loads(Path(filepath).read_text())
        config = cls()

        if "trading_style" in config_dict:
            config.trading_style = TradingStyle(config_dict["trading_style"])
        if "active_sectors" in config_dict:
            config.active_sectors = config_dict["active_sectors"]
        if "custom_symbols" in config_dict:
            config.custom_symbols = config_dict["custom_symbols"]
        if "scan_interval" in config_dict:
            config.scan_interval = config_dict["scan_interval"]

        return config


# Default configuration instance
DEFAULT_CONFIG = ScannerConfig()
