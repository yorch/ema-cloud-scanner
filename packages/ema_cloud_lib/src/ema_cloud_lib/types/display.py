"""
Display data types for scanner output.

These dataclasses define the structure for data displayed in dashboards
and other presentation layers.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ETFDisplayData:
    """Data structure for ETF display"""

    symbol: str
    name: str
    sector: str
    price: float
    change_pct: float
    trend: str  # "bullish", "bearish", "neutral"
    trend_strength: float
    cloud_state: str
    signals_count: int
    last_signal: str | None = None
    last_signal_time: datetime | None = None
    rsi: float | None = None
    adx: float | None = None
    volume_ratio: float | None = None


@dataclass
class SignalDisplayData:
    """Data structure for signal display"""

    timestamp: datetime
    symbol: str
    direction: str
    signal_type: str
    price: float
    strength: str
    is_valid: bool
    notes: str
