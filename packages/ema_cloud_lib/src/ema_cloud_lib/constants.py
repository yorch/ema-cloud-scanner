"""
Shared constants and enums for the EMA Cloud library.
"""

from datetime import UTC, datetime
from enum import StrEnum


class TrendDirection(StrEnum):
    """Trend direction classification."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


# Display constants
MAX_SIGNALS_DISPLAY = 50
MAX_LOG_LINES = 100


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime. Use this instead of datetime.now()."""
    return datetime.now(UTC)


# Scanner constants
MIN_BARS_FOR_ANALYSIS = 50  # Minimum bars needed for valid analysis
SIGNAL_COOLDOWN_CLEANUP_THRESHOLD = 1000  # Max cooldown entries before cleanup
SIGNAL_COOLDOWN_RETENTION_HOURS = 24  # Hours to retain cooldown history

# Signal strength thresholds
SIGNAL_STRENGTH_VERY_STRONG_THRESHOLD = 85
SIGNAL_STRENGTH_STRONG_THRESHOLD = 70
SIGNAL_STRENGTH_MODERATE_THRESHOLD = 55
SIGNAL_STRENGTH_WEAK_THRESHOLD = 40

# Holdings cache
HOLDINGS_CACHE_TTL_HOURS = 24  # Cache TTL for ETF holdings data
