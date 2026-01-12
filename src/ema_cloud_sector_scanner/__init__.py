"""
EMA Cloud Sector Scanner

Real-time sector ETF scanner based on Ripster's EMA Cloud methodology.
Monitors sector ETFs for trend changes, cloud flips, and trading signals.

Features:
- Multiple EMA cloud configurations (5-12, 8-9, 20-21, 34-50, 72-89, 200-233)
- Real-time signal detection with strength ratings
- Configurable filters (volume, RSI, ADX, VWAP, ATR)
- Multiple trading style presets (scalping to long-term)
- Console and desktop notifications
- Terminal-based dashboard
- ETF holdings analysis
- Backtesting capabilities

Usage:
    from ema_cloud_sector_scanner import EMACloudScanner, ScannerConfig

    config = ScannerConfig()
    scanner = EMACloudScanner(config)
    await scanner.run()
"""

__version__ = "0.1.0"
__author__ = "EMA Cloud Scanner"

from .config.settings import (
    DEFAULT_EMA_CLOUDS,
    ETF_SUBSETS,
    SECTOR_ETFS,
    TRADING_PRESETS,
    FilterConfig,
    ScannerConfig,
    TradingStyle,
)
from .scanner import EMACloudScanner, MarketHours


__all__ = [
    "DEFAULT_EMA_CLOUDS",
    "ETF_SUBSETS",
    "SECTOR_ETFS",
    "TRADING_PRESETS",
    "EMACloudScanner",
    "FilterConfig",
    "MarketHours",
    "ScannerConfig",
    "TradingStyle",
]
