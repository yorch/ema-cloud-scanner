"""
Display data types for scanner output.

These Pydantic models define the structure for data displayed in dashboards
and other presentation layers.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class MTFDisplayData(BaseModel):
    """Multi-timeframe analysis display data"""

    enabled: bool = Field(default=False, description="Whether MTF analysis is enabled")
    alignment: str | None = Field(default=None, description="MTF alignment status")
    confidence: str | None = Field(default=None, description="Signal confidence level")
    bias: str | None = Field(default=None, description="Trading bias: long, short, or neutral")
    bullish_count: int = Field(default=0, description="Number of bullish timeframes")
    bearish_count: int = Field(default=0, description="Number of bearish timeframes")
    neutral_count: int = Field(default=0, description="Number of neutral timeframes")
    total_timeframes: int = Field(default=0, description="Total timeframes analyzed")
    alignment_pct: float = Field(default=0, description="Alignment percentage (0-100)")
    summary: str | None = Field(default=None, description="Human-readable summary")


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

    # Multi-timeframe analysis
    mtf: MTFDisplayData | None = Field(default=None, description="Multi-timeframe analysis data")

    # Cloud stacking
    stacking_score: float | None = Field(
        default=None, description="Cloud stacking score (-1.0 to 1.0)"
    )
    is_waterfall: bool = Field(default=False, description="True if all clouds perfectly stacked")


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

    # Tier 3 metrics
    weighted_filter_score: float | None = Field(
        default=None, description="Weighted filter score (0.0-1.0)"
    )
    stacking_score: float | None = Field(
        default=None, description="Cloud stacking score (-1.0 to 1.0)"
    )
    is_waterfall: bool = Field(default=False, description="True if all clouds perfectly stacked")


class HoldingDisplayData(BaseModel):
    """Data structure for holdings display"""

    symbol: str = Field(..., description="Stock symbol")
    company: str | None = Field(default=None, description="Company name")
    weight: float | None = Field(default=None, description="Holding weight percentage")
    price: float | None = Field(default=None, description="Price at signal generation")
    direction: str | None = Field(default=None, description="Signal direction: long or short")
    signal_type: str | None = Field(default=None, description="Type of signal detected")
    strength: str | None = Field(default=None, description="Signal strength rating")
    timestamp: datetime | None = Field(default=None, description="Signal timestamp")


class HoldingsETFDisplayData(BaseModel):
    """Holdings display data for a sector ETF"""

    etf_symbol: str = Field(..., description="ETF symbol")
    etf_name: str | None = Field(default=None, description="ETF name")
    sector: str | None = Field(default=None, description="Sector classification")
    sector_trend: str = Field(..., description="Sector trend: bullish, bearish, or neutral")
    total_holdings: int | None = Field(default=None, description="Total holdings count")
    holdings: list[HoldingDisplayData] = Field(
        default_factory=list, description="Holdings with signal details"
    )
