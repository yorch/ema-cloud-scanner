"""
EMA Cloud Library

Core library for EMA Cloud trading analysis based on Ripster's methodology.
Provides signal generation, backtesting, and market analysis capabilities.

Example usage:
    from ema_cloud_lib import EMACloudScanner, ScannerConfig

    config = ScannerConfig()
    scanner = EMACloudScanner(config)
    await scanner.run_scan_cycle()
"""

# Core scanner
# Alerts
from ema_cloud_lib.alerts import (
    AlertManager,
    AlertMessage,
    BaseAlertHandler,
    ConsoleAlertHandler,
    DesktopAlertHandler,
    create_alert_from_signal,
)

# Backtesting
from ema_cloud_lib.backtesting.engine import (
    Backtester,
    BacktestResult,
    Trade,
    run_quick_backtest,
)

# Configuration and constants
from ema_cloud_lib.config.settings import (
    ETF_SUBSETS,
    SECTOR_ETFS,
    SYMBOL_TO_SECTOR,
    TRADING_PRESETS,
    EMACloudConfig,
    FilterConfig,
    ScannerConfig,
    SignalType,
    TradingStyle,
)
from ema_cloud_lib.constants import MAX_LOG_LINES, MAX_SIGNALS_DISPLAY, TrendDirection

# Data providers
from ema_cloud_lib.data_providers.base import (
    APICallTracker,
    BaseDataProvider,
    DataProviderManager,
    YahooFinanceProvider,
    api_call_tracker,
)

# Holdings
from ema_cloud_lib.holdings.manager import (
    ETFHoldings,
    Holding,
    HoldingsManager,
)

# Indicators
from ema_cloud_lib.indicators.ema_cloud import (
    CloudData,
    CloudState,
    EMACloudIndicator,
    PriceRelation,
    TechnicalIndicators,
    TrendAnalysis,
)
from ema_cloud_lib.scanner import EMACloudScanner, MarketHours

# Signals
from ema_cloud_lib.signals.generator import (
    FilterResult,
    SectorTrendState,
    Signal,
    SignalFilter,
    SignalGenerator,
    SignalStrength,
)

# Types for display/dashboard integration
from ema_cloud_lib.types.display import (
    ETFDisplayData,
    HoldingDisplayData,
    HoldingsETFDisplayData,
    SignalDisplayData,
)
from ema_cloud_lib.types.protocols import DashboardProtocol

__version__ = "0.1.0"

__all__ = [
    # Version
    "__version__",
    # Core scanner
    "EMACloudScanner",
    "MarketHours",
    # Configuration
    "ScannerConfig",
    "FilterConfig",
    "EMACloudConfig",
    "TradingStyle",
    "SignalType",
    "SignalStrength",
    "SECTOR_ETFS",
    "ETF_SUBSETS",
    "SYMBOL_TO_SECTOR",
    "TRADING_PRESETS",
    # Constants
    "TrendDirection",
    "MAX_SIGNALS_DISPLAY",
    "MAX_LOG_LINES",
    # Types
    "ETFDisplayData",
    "HoldingDisplayData",
    "HoldingsETFDisplayData",
    "SignalDisplayData",
    "DashboardProtocol",
    # Indicators
    "EMACloudIndicator",
    "TechnicalIndicators",
    "CloudData",
    "CloudState",
    "PriceRelation",
    "TrendAnalysis",
    # Signals
    "SignalGenerator",
    "SignalFilter",
    "Signal",
    "SectorTrendState",
    "FilterResult",
    # Alerts
    "AlertManager",
    "AlertMessage",
    "BaseAlertHandler",
    "ConsoleAlertHandler",
    "DesktopAlertHandler",
    "create_alert_from_signal",
    # Data providers
    "DataProviderManager",
    "BaseDataProvider",
    "YahooFinanceProvider",
    "APICallTracker",
    "api_call_tracker",
    # Holdings
    "HoldingsManager",
    "ETFHoldings",
    "Holding",
    # Backtesting
    "Backtester",
    "BacktestResult",
    "Trade",
    "run_quick_backtest",
]
