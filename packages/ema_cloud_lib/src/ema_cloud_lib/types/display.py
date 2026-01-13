"""
Display data types for scanner output.

These Pydantic models define the structure for data displayed in dashboards
and other presentation layers.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ETFDisplayData(BaseModel):
    """Data structure for ETF display"""

    symbol: str = Field(..., description="ETF symbol")
    name: str = Field(..., description="ETF name")
    sector: str = Field(..., description="Sector classification")
    price: float = Field(..., description="Current price")
    change_pct: float = Field(..., description="Percentage change")
    trend: str = Field(..., description="Trend direction: bullish, bearish, or neutral")
    trend_strength: float = Field(..., description="Strength of the trend (0-1)")
    cloud_state: str = Field(..., description="EMA cloud state description")
    signals_count: int = Field(..., description="Number of active signals")
    last_signal: str | None = Field(default=None, description="Most recent signal type")
    last_signal_time: datetime | None = Field(default=None, description="Time of last signal")
    rsi: float | None = Field(default=None, description="Current RSI value")
    adx: float | None = Field(default=None, description="Current ADX value")
    volume_ratio: float | None = Field(default=None, description="Volume relative to average")


class SignalDisplayData(BaseModel):
    """Data structure for signal display"""

    timestamp: datetime = Field(..., description="Signal timestamp")
    symbol: str = Field(..., description="ETF symbol")
    direction: str = Field(..., description="Signal direction: long or short")
    signal_type: str = Field(..., description="Type of signal detected")
    price: float = Field(..., description="Price at signal generation")
    strength: str = Field(..., description="Signal strength rating")
    is_valid: bool = Field(..., description="Whether signal passes all validations")
    notes: str = Field(..., description="Additional signal notes")
