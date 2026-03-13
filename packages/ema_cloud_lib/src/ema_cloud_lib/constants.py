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
