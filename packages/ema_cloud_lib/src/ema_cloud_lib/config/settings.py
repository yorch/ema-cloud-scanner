"""
Configuration settings for EMA Cloud Sector Scanner
Based on Ripster's EMA Cloud Strategy

All settings are configurable and support presets for different trading styles.
"""

from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, SecretStr, ValidationInfo, field_validator


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


class EMACloudConfig(BaseModel):
    """Configuration for a single EMA cloud"""

    fast_period: int = Field(..., description="Fast EMA period")
    slow_period: int = Field(..., description="Slow EMA period")
    name: str = Field(..., description="Cloud name")
    description: str = Field(..., description="Cloud description")
    color_bullish: str = Field(default="#26a69a", description="Bullish color (green)")
    color_bearish: str = Field(default="#ef5350", description="Bearish color (red)")
    enabled: bool = Field(default=True, description="Whether cloud is enabled")

    @field_validator("fast_period", "slow_period")
    @classmethod
    def validate_period(cls, v: int) -> int:
        """Validate EMA period is positive."""
        if v < 1:
            raise ValueError("EMA period must be >= 1")
        return v

    @field_validator("slow_period")
    @classmethod
    def validate_slow_greater_than_fast(cls, v: int, info: ValidationInfo) -> int:
        """Validate slow period is greater than fast period."""
        if "fast_period" in info.data and v <= info.data["fast_period"]:
            raise ValueError("slow_period must be greater than fast_period")
        return v


class TimeframeConfig(BaseModel):
    """Configuration for a specific timeframe"""

    interval: str = Field(..., description="Timeframe interval (e.g., '1m', '5m', '1h', '1d')")
    display_name: str = Field(..., description="Human-readable name")
    bars_to_fetch: int = Field(default=500, description="Number of historical bars to load")

    @field_validator("bars_to_fetch")
    @classmethod
    def validate_bars(cls, v: int) -> int:
        """Validate bars to fetch is positive."""
        if v < 1:
            raise ValueError("bars_to_fetch must be >= 1")
        return v


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
        "primary_timeframe": TimeframeConfig(
            interval="1m", display_name="1 Minute", bars_to_fetch=500
        ),
        "confirmation_timeframes": [
            TimeframeConfig(interval="5m", display_name="5 Minute", bars_to_fetch=200),
        ],
        "enabled_clouds": ["trend_line", "pullback", "momentum"],
        "signal_confirmation_bars": 1,
        "min_cloud_thickness_pct": 0.02,  # 0.02%
    },
    TradingStyle.INTRADAY: {
        "primary_timeframe": TimeframeConfig(
            interval="10m", display_name="10 Minute", bars_to_fetch=500
        ),
        "confirmation_timeframes": [
            TimeframeConfig(interval="1h", display_name="1 Hour", bars_to_fetch=200),
            TimeframeConfig(interval="1d", display_name="Daily", bars_to_fetch=100),
        ],
        "enabled_clouds": ["trend_line", "pullback", "trend_confirmation"],
        "signal_confirmation_bars": 2,
        "min_cloud_thickness_pct": 0.05,  # 0.05%
    },
    TradingStyle.SWING: {
        "primary_timeframe": TimeframeConfig(
            interval="1h", display_name="1 Hour", bars_to_fetch=500
        ),
        "confirmation_timeframes": [
            TimeframeConfig(interval="4h", display_name="4 Hour", bars_to_fetch=200),
            TimeframeConfig(interval="1d", display_name="Daily", bars_to_fetch=100),
        ],
        "enabled_clouds": ["trend_line", "trend_confirmation", "long_term"],
        "signal_confirmation_bars": 2,
        "min_cloud_thickness_pct": 0.1,  # 0.1%
    },
    TradingStyle.POSITION: {
        "primary_timeframe": TimeframeConfig(
            interval="1d", display_name="Daily", bars_to_fetch=500
        ),
        "confirmation_timeframes": [
            TimeframeConfig(interval="1wk", display_name="Weekly", bars_to_fetch=104),
        ],
        "enabled_clouds": ["trend_confirmation", "long_term", "major_trend"],
        "signal_confirmation_bars": 3,
        "min_cloud_thickness_pct": 0.2,  # 0.2%
    },
    TradingStyle.LONG_TERM: {
        "primary_timeframe": TimeframeConfig(
            interval="1wk", display_name="Weekly", bars_to_fetch=260
        ),
        "confirmation_timeframes": [
            TimeframeConfig(interval="1mo", display_name="Monthly", bars_to_fetch=60),
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


# Reverse lookup: symbol -> sector name
SYMBOL_TO_SECTOR = {info["symbol"]: sector for sector, info in SECTOR_ETFS.items()}


# ETF Subsets for quick selection
ETF_SUBSETS = {
    "all_sectors": list(SECTOR_ETFS.keys()),
    "growth_sectors": ["technology", "consumer_discretionary", "communication_services"],
    "defensive_sectors": ["utilities", "consumer_staples", "healthcare"],
    "cyclical_sectors": ["financials", "industrials", "materials", "energy"],
    "rate_sensitive": ["financials", "real_estate", "utilities"],
    "commodity_linked": ["energy", "materials"],
}


class FilterConfig(BaseModel):
    """Configuration for signal filters"""

    # Volume filter
    volume_enabled: bool = Field(default=True, description="Enable volume filter")
    volume_multiplier: float = Field(
        default=1.5, description="Volume multiplier threshold (e.g., 1.5x average)"
    )
    volume_lookback: int = Field(default=20, description="Lookback period for average volume")

    # RSI filter
    rsi_enabled: bool = Field(default=True, description="Enable RSI filter")
    rsi_period: int = Field(default=14, description="RSI calculation period")
    rsi_overbought: float = Field(default=70.0, description="RSI overbought threshold")
    rsi_oversold: float = Field(default=30.0, description="RSI oversold threshold")
    rsi_neutral_zone: tuple[float, float] = Field(
        default=(45.0, 55.0), description="RSI neutral zone range"
    )

    # ADX filter (trend strength)
    adx_enabled: bool = Field(default=True, description="Enable ADX filter")
    adx_period: int = Field(default=14, description="ADX calculation period")
    adx_min_strength: float = Field(default=20.0, description="Minimum ADX for valid trend")
    adx_strong_trend: float = Field(default=30.0, description="ADX threshold for strong trend")

    # VWAP filter
    vwap_enabled: bool = Field(default=True, description="Enable VWAP filter")
    vwap_confirmation: bool = Field(
        default=True, description="Require price on correct side of VWAP"
    )

    # ATR filter (volatility)
    atr_enabled: bool = Field(default=True, description="Enable ATR filter")
    atr_period: int = Field(default=14, description="ATR calculation period")
    atr_min_threshold: float = Field(default=0.5, description="Minimum ATR as % of price")
    atr_max_threshold: float = Field(
        default=5.0, description="Maximum ATR (avoid extreme volatility)"
    )

    # MACD confirmation
    macd_enabled: bool = Field(default=False, description="Enable MACD filter")
    macd_fast: int = Field(default=12, description="MACD fast period")
    macd_slow: int = Field(default=26, description="MACD slow period")
    macd_signal: int = Field(default=9, description="MACD signal period")

    # Time of day filter
    time_filter_enabled: bool = Field(default=True, description="Enable time of day filter")
    avoid_first_minutes: int = Field(default=15, description="Minutes to avoid after market open")
    avoid_last_minutes: int = Field(default=15, description="Minutes to avoid before market close")
    trading_start_time: str = Field(default="09:30", description="Trading start time (HH:MM)")
    trading_end_time: str = Field(default="16:00", description="Trading end time (HH:MM)")

    @field_validator("rsi_overbought", "rsi_oversold")
    @classmethod
    def validate_rsi_range(cls, v: float) -> float:
        """Validate RSI values are between 0 and 100."""
        if not (0 <= v <= 100):
            raise ValueError("RSI values must be between 0 and 100")
        return v

    @field_validator("rsi_overbought")
    @classmethod
    def validate_rsi_overbought_greater(cls, v: float, info: ValidationInfo) -> float:
        """Validate overbought is greater than oversold."""
        if "rsi_oversold" in info.data and v <= info.data["rsi_oversold"]:
            raise ValueError("rsi_overbought must be greater than rsi_oversold")
        return v

    @field_validator(
        "volume_multiplier",
        "adx_min_strength",
        "adx_strong_trend",
        "atr_min_threshold",
        "atr_max_threshold",
    )
    @classmethod
    def validate_positive(cls, v: float) -> float:
        """Validate numeric thresholds are positive."""
        if v <= 0:
            raise ValueError("Threshold must be positive")
        return v


class AlertConfig(BaseModel):
    """Configuration for alerts"""

    # Console alerts
    console_enabled: bool = Field(default=True, description="Enable console alerts")
    console_colors: bool = Field(default=True, description="Use colors in console alerts")

    # Desktop notifications
    desktop_enabled: bool = Field(default=True, description="Enable desktop notifications")
    desktop_sound: bool = Field(default=True, description="Play sound with desktop notifications")

    # Telegram notifications
    telegram_enabled: bool = Field(default=False, description="Enable Telegram notifications")
    telegram_bot_token: SecretStr | None = Field(
        default=None, description="Telegram bot token (from @BotFather)"
    )
    telegram_chat_id: str | None = Field(
        default=None, description="Telegram chat ID (user or group)"
    )

    # Discord notifications
    discord_enabled: bool = Field(default=False, description="Enable Discord notifications")
    discord_webhook_url: SecretStr | None = Field(default=None, description="Discord webhook URL")

    # Email notifications
    email_enabled: bool = Field(default=False, description="Enable email notifications")
    email_smtp_server: str | None = Field(
        default=None, description="SMTP server address (e.g., smtp.gmail.com)"
    )
    email_smtp_port: int = Field(
        default=587, description="SMTP server port (587 for TLS, 465 for SSL)"
    )
    email_use_tls: bool = Field(default=True, description="Use TLS encryption")
    email_use_ssl: bool = Field(
        default=False, description="Use SSL encryption (alternative to TLS)"
    )
    email_username: str | None = Field(
        default=None, description="SMTP username (usually email address)"
    )
    email_password: SecretStr | None = Field(
        default=None, description="SMTP password or app-specific password"
    )
    email_from_address: str | None = Field(default=None, description="From email address")
    email_from_name: str = Field(default="EMA Cloud Scanner", description="From name")
    email_recipients: list[str] = Field(default_factory=list, description="Email recipients list")
    email_subject_prefix: str = Field(default="[EMA Signal]", description="Email subject prefix")

    @property
    def to_dict(self) -> dict:
        """Convert to dictionary for AlertManager (extracts secret values for runtime use)"""
        return {
            "console": {
                "enabled": self.console_enabled,
                "colors": self.console_colors,
            },
            "desktop": {
                "enabled": self.desktop_enabled,
                "sound": self.desktop_sound,
            },
            "telegram": {
                "enabled": self.telegram_enabled,
                "bot_token": self.telegram_bot_token.get_secret_value()
                if self.telegram_bot_token
                else None,
                "chat_id": self.telegram_chat_id,
            },
            "discord": {
                "enabled": self.discord_enabled,
                "webhook_url": self.discord_webhook_url.get_secret_value()
                if self.discord_webhook_url
                else None,
            },
            "email": {
                "enabled": self.email_enabled,
                "smtp_server": self.email_smtp_server,
                "smtp_port": self.email_smtp_port,
                "use_tls": self.email_use_tls,
                "use_ssl": self.email_use_ssl,
                "username": self.email_username,
                "password": self.email_password.get_secret_value() if self.email_password else None,
                "from_address": self.email_from_address,
                "from_name": self.email_from_name,
                "recipients": self.email_recipients,
                "subject_prefix": self.email_subject_prefix,
            },
        }


class DataProviderConfig(BaseModel):
    """Configuration for data providers"""

    # Yahoo Finance (default, free)
    yahoo_enabled: bool = Field(default=True, description="Enable Yahoo Finance data provider")

    # Alpaca
    alpaca_enabled: bool = Field(default=False, description="Enable Alpaca data provider")
    alpaca_api_key: SecretStr | None = Field(default=None, description="Alpaca API key")
    alpaca_secret_key: SecretStr | None = Field(default=None, description="Alpaca secret key")
    alpaca_paper: bool = Field(default=True, description="Use Alpaca paper trading endpoint")

    # Polygon.io
    polygon_enabled: bool = Field(default=False, description="Enable Polygon.io data provider")
    polygon_api_key: SecretStr | None = Field(default=None, description="Polygon.io API key")

    # Rate limiting
    request_delay_ms: int = Field(default=100, description="Delay between requests (ms)")
    max_concurrent_requests: int = Field(default=5, description="Maximum concurrent requests")

    @field_validator("request_delay_ms", "max_concurrent_requests")
    @classmethod
    def validate_positive_int(cls, v: int) -> int:
        """Validate rate limiting parameters are positive."""
        if v < 1:
            raise ValueError("Rate limiting parameters must be >= 1")
        return v


class BacktestConfig(BaseModel):
    """Configuration for backtesting"""

    enabled: bool = Field(default=True, description="Enable backtesting")
    start_date: str | None = Field(default=None, description="Backtest start date (YYYY-MM-DD)")
    end_date: str | None = Field(default=None, description="Backtest end date (YYYY-MM-DD)")
    initial_capital: float = Field(default=100000.0, description="Initial capital for backtest")
    position_size_pct: float = Field(
        default=10.0, description="Position size as % of capital per trade"
    )
    commission_per_trade: float = Field(default=0.0, description="Commission per trade")
    slippage_pct: float = Field(default=0.05, description="Slippage as % of price")

    @field_validator("initial_capital")
    @classmethod
    def validate_initial_capital(cls, v: float) -> float:
        """Validate initial capital is positive."""
        if v <= 0:
            raise ValueError("initial_capital must be positive")
        return v

    @field_validator("position_size_pct")
    @classmethod
    def validate_position_size(cls, v: float) -> float:
        """Validate position size is between 0 and 100."""
        if not (0 < v <= 100):
            raise ValueError("position_size_pct must be between 0 and 100")
        return v


class MTFConfig(BaseModel):
    """Multi-Timeframe Analysis Configuration"""

    enabled: bool = Field(default=False, description="Enable multi-timeframe analysis")
    timeframes: list[str] = Field(
        default_factory=lambda: ["1d", "4h", "1h"],
        description="Timeframes to analyze (higher to lower)",
    )
    min_confidence: Literal["very_high", "high", "moderate", "low"] = Field(
        default="moderate",
        description="Minimum confidence level: very_high, high, moderate, low",
    )
    require_alignment: bool = Field(
        default=True, description="Only take trades aligned with MTF bias"
    )
    bars_per_timeframe: int = Field(
        default=200, description="Historical bars to fetch per timeframe"
    )

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, v: list[str]) -> list[str]:
        """Validate timeframes list"""
        if len(v) < 1:
            raise ValueError("At least one timeframe required")
        valid_tfs = {"1m", "5m", "15m", "1h", "4h", "1d", "1w"}
        for tf in v:
            if tf not in valid_tfs:
                raise ValueError(f"Invalid timeframe: {tf}. Must be one of {valid_tfs}")
        return v

    @field_validator("bars_per_timeframe")
    @classmethod
    def validate_bars(cls, v: int) -> int:
        """Validate bars per timeframe"""
        if v < 50:
            raise ValueError("bars_per_timeframe must be >= 50")
        return v


class ScannerConfig(BaseModel):
    """Main scanner configuration"""

    # Trading style preset
    trading_style: TradingStyle = Field(
        default=TradingStyle.INTRADAY, description="Trading style preset"
    )

    # Sector configuration
    active_sectors: list[str] = Field(
        default_factory=lambda: ETF_SUBSETS["all_sectors"].copy(),
        description="Active sector ETFs to scan",
    )
    custom_symbols: list[str] = Field(
        default_factory=list, description="Additional symbols to scan"
    )

    # EMA Cloud settings
    ema_clouds: dict[str, EMACloudConfig] = Field(
        default_factory=lambda: DEFAULT_EMA_CLOUDS.copy(), description="EMA cloud configurations"
    )

    # Filter settings
    filters: FilterConfig = Field(
        default_factory=FilterConfig, description="Signal filter configuration"
    )

    # Alert settings
    alerts: AlertConfig = Field(default_factory=AlertConfig, description="Alert configuration")

    # Data provider settings
    data_provider: DataProviderConfig = Field(
        default_factory=DataProviderConfig, description="Data provider configuration"
    )

    # Multi-timeframe analysis settings
    mtf: MTFConfig = Field(default_factory=MTFConfig, description="Multi-timeframe configuration")

    # Backtest settings
    backtest: BacktestConfig = Field(
        default_factory=BacktestConfig, description="Backtest configuration"
    )

    # Scan interval (seconds)
    scan_interval: int = Field(default=60, description="Scan interval in seconds")

    # Holdings settings
    fetch_holdings: bool = Field(default=True, description="Fetch ETF holdings data")
    top_holdings_count: int = Field(
        default=10, description="Number of top holdings to track per ETF"
    )
    scan_holdings: bool = Field(
        default=False, description="Enable scanning individual stocks within sector holdings"
    )
    holdings_max_concurrent: int = Field(
        default=5, description="Maximum concurrent stock scans per ETF"
    )

    # Dashboard settings
    dashboard_refresh_rate: int = Field(default=5, description="Dashboard refresh rate in seconds")
    show_all_etfs: bool = Field(default=True, description="Show all ETFs in dashboard")

    # Signal cooldown (minutes)
    signal_cooldown_minutes: int = Field(
        default=15, description="Signal cooldown period in minutes to avoid duplicate alerts"
    )

    @field_validator("scan_interval")
    @classmethod
    def validate_scan_interval(cls, v: int) -> int:
        """Validate scan interval is reasonable."""
        if v < 1:
            raise ValueError("scan_interval must be >= 1 second")
        return v

    @field_validator("top_holdings_count")
    @classmethod
    def validate_holdings_count(cls, v: int) -> int:
        """Validate holdings count is positive."""
        if v < 1:
            raise ValueError("top_holdings_count must be >= 1")
        return v

    @field_validator("holdings_max_concurrent")
    @classmethod
    def validate_holdings_concurrent(cls, v: int) -> int:
        """Validate concurrent scan limit is reasonable."""
        if v < 1:
            raise ValueError("holdings_max_concurrent must be >= 1")
        if v > 20:
            raise ValueError("holdings_max_concurrent must be <= 20 to avoid rate limits")
        return v

    @field_validator("dashboard_refresh_rate")
    @classmethod
    def validate_refresh_rate(cls, v: int) -> int:
        """Validate refresh rate is positive."""
        if v < 1:
            raise ValueError("dashboard_refresh_rate must be >= 1 second")
        return v

    @field_validator("active_sectors")
    @classmethod
    def validate_active_sectors(cls, v: list[str]) -> list[str]:
        """Validate all sectors exist."""
        for sector in v:
            if sector not in SECTOR_ETFS:
                raise ValueError(f"Unknown sector: {sector}")
        return v

    def get_preset(self) -> dict[str, Any]:
        """Get the current trading style preset configuration"""
        return TRADING_PRESETS[self.trading_style]

    def get_active_etf_symbols(self) -> list[str]:
        """Get list of active ETF symbols"""
        symbols = [SECTOR_ETFS[sector]["symbol"] for sector in self.active_sectors]
        symbols.extend(self.custom_symbols)
        return symbols

    def validate_config(self) -> list[str]:
        """
        Validate configuration and return list of warnings (not errors).
        Pydantic handles hard validation errors automatically.
        This method provides soft warnings for suboptimal settings.
        """
        warnings = []

        # Warn about scan interval extremes
        if self.scan_interval < 10:
            warnings.append(f"Scan interval {self.scan_interval}s is very low, may hit rate limits")
        if self.scan_interval > 3600:
            warnings.append(f"Scan interval {self.scan_interval}s is very high, may miss signals")

        return warnings

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
        """Save configuration to JSON file using Pydantic serialization"""
        config_json = self.model_dump_json(indent=2, exclude_none=False)
        Path(filepath).write_text(config_json)

    @classmethod
    def load(cls, filepath: str) -> "ScannerConfig":
        """Load configuration from JSON file using Pydantic deserialization"""
        config_json = Path(filepath).read_text()
        return cls.model_validate_json(config_json)


# Default configuration instance
DEFAULT_CONFIG = ScannerConfig()
