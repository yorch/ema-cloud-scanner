"""
EMA Cloud Indicator Implementation

Based on Ripster's EMA Cloud Strategy:
- 5-12 EMA Cloud: Fluid trendline for day trades
- 8-9 EMA Cloud: Pullback levels
- 20-21 EMA Cloud: Short-term momentum
- 34-50 EMA Cloud: Bullish/bearish bias confirmation (KEY)
- 72-89 EMA Cloud: Long-term trend
- 200-233 EMA Cloud: Major trend/institutional levels

Additional indicators for signal filtering:
- RSI, ADX, ATR, VWAP, MACD, Volume analysis
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CloudState(Enum):
    """State of an EMA cloud"""

    BULLISH = "bullish"  # Fast EMA above slow EMA
    BEARISH = "bearish"  # Fast EMA below slow EMA
    CROSSING_UP = "crossing_up"  # Just crossed to bullish
    CROSSING_DOWN = "crossing_down"  # Just crossed to bearish


class PriceRelation(Enum):
    """Price relation to cloud"""

    ABOVE = "above"  # Price above cloud
    BELOW = "below"  # Price below cloud
    INSIDE = "inside"  # Price inside cloud
    TOUCHING_TOP = "touching_top"  # Price at top of cloud
    TOUCHING_BOTTOM = "touching_bottom"  # Price at bottom of cloud


@dataclass(frozen=True)
class RawSignal:
    """Structured signal emitted by detect_signals().

    Carries the signal_type, direction, originating cloud, and a
    human-readable message so downstream consumers never have to
    reverse-engineer semantics from display text.
    """

    signal_type: str  # e.g. "TREND_FLIP", "BREAKOUT", "BREAKDOWN", "SHORT_TERM", "PULLBACK_ENTRY", "STRONG_ALIGNMENT"
    direction: str  # "bullish" or "bearish"
    cloud_name: str  # e.g. "trend_confirmation", "trend_line", "pullback"
    message: str  # human-readable description (display only)


class CloudData(BaseModel):
    """Data structure for EMA cloud analysis"""

    name: str = Field(..., description="Cloud name")
    fast_ema: float = Field(..., description="Fast EMA value")
    slow_ema: float = Field(..., description="Slow EMA value")
    cloud_top: float = Field(..., description="Top of cloud (max of fast/slow)")
    cloud_bottom: float = Field(..., description="Bottom of cloud (min of fast/slow)")
    cloud_thickness: float = Field(..., description="Absolute cloud thickness")
    cloud_thickness_pct: float = Field(..., description="Cloud thickness as percentage")
    state: CloudState = Field(..., description="Current cloud state")
    price_relation: PriceRelation = Field(..., description="Price relation to cloud")
    is_expanding: bool = Field(..., description="Whether cloud is expanding")
    is_contracting: bool = Field(..., description="Whether cloud is contracting")
    slope: float = Field(..., description="Cloud slope (positive=upward, negative=downward)")


class StackingOrder(BaseModel):
    """Result of cloud stacking order analysis (waterfall detection)."""

    is_stacked_bullish: bool = Field(
        default=False,
        description="True when clouds are stacked in bullish waterfall order "
        "(shorter-term clouds above longer-term)",
    )
    is_stacked_bearish: bool = Field(
        default=False,
        description="True when clouds are stacked in bearish waterfall order "
        "(shorter-term clouds below longer-term)",
    )
    stacking_score: float = Field(
        default=0.0,
        description="Stacking quality score from -1.0 (perfect bearish) to 1.0 (perfect bullish)",
    )
    ordered_pairs: int = Field(
        default=0,
        description="Number of adjacent cloud pairs in correct stacking order",
    )
    total_pairs: int = Field(
        default=0,
        description="Total number of adjacent cloud pairs evaluated",
    )

    @property
    def is_waterfall(self) -> bool:
        """True when all cloud pairs are in perfect stacking order (bullish or bearish)."""
        return self.total_pairs > 0 and self.ordered_pairs == self.total_pairs


class TrendAnalysis(BaseModel):
    """Complete trend analysis result"""

    model_config = {"arbitrary_types_allowed": True}

    symbol: str = Field(..., description="Symbol being analyzed")
    timestamp: pd.Timestamp = Field(..., description="Analysis timestamp")
    price: float = Field(..., description="Current price")
    clouds: dict[str, CloudData] = Field(..., description="Cloud data by name")
    overall_trend: str = Field(..., description="Overall trend: bullish, bearish, or neutral")
    trend_strength: float = Field(..., description="Trend strength (0-100)")
    trend_alignment: int = Field(..., description="Number of aligned clouds")
    signals: list[str] = Field(default_factory=list, description="List of signal types detected")
    stacking: StackingOrder = Field(
        default_factory=StackingOrder,
        description="Cloud stacking order / waterfall analysis",
    )

    # Additional indicators
    rsi: float | None = Field(default=None, description="RSI value")
    adx: float | None = Field(default=None, description="ADX value")
    atr: float | None = Field(default=None, description="ATR value")
    atr_pct: float | None = Field(default=None, description="ATR as percentage of price")
    vwap: float | None = Field(default=None, description="VWAP value")
    volume_ratio: float | None = Field(default=None, description="Volume relative to average")
    macd: float | None = Field(default=None, description="MACD value")
    macd_signal: float | None = Field(default=None, description="MACD signal line")
    macd_histogram: float | None = Field(default=None, description="MACD histogram")

    @property
    def primary_cloud_state(self) -> CloudState | None:
        """Get the state of the primary trend confirmation cloud (34-50 EMA)"""
        if "trend_confirmation" in self.clouds:
            return self.clouds["trend_confirmation"].state
        return None


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate Exponential Moving Average"""
    return series.ewm(span=period, adjust=False).mean()


def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average"""
    return series.rolling(window=period).mean()


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.

    RSI = 100 - (100 / (1 + RS))
    RS = Average Gain / Average Loss
    """
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    # When avg_loss is 0 (no losses), RSI should be 100 (fully overbought).
    # When avg_gain is 0 (no gains), RSI should be 0 (fully oversold).
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    # Handle division by zero: avg_loss==0 → rs==inf → RSI=100
    # Handle 0/0 case: avg_gain==0 and avg_loss==0 → rs==NaN → RSI=NaN, fill with 50 (neutral)
    rsi = rsi.fillna(50.0)

    return rsi


def calculate_true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """Calculate True Range - maximum of (H-L), |H-PrevC|, |L-PrevC|"""
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def calculate_adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX).

    Returns DataFrame with columns: +DI, -DI, ADX
    """
    tr = calculate_true_range(high, low, close)

    # Directional Movement
    plus_dm = high.diff()
    minus_dm = -low.diff()

    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

    # Smoothed averages
    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

    # ADX
    # When plus_di + minus_di == 0, there is no directional movement; DX should be 0
    di_sum = plus_di + minus_di
    dx = 100 * abs(plus_di - minus_di) / di_sum.replace(0, np.nan)
    dx = dx.fillna(0.0)
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame({"plus_di": plus_di, "minus_di": minus_di, "adx": adx})


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    tr = calculate_true_range(high, low, close)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def calculate_vwap(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
) -> pd.Series:
    """
    Calculate Volume Weighted Average Price.
    Resets at the start of each trading day for intraday data.
    For daily or longer timeframes, uses a rolling cumulative calculation.
    """
    typical_price = (high + low + close) / 3
    tp_volume = typical_price * volume

    # Detect if data is intraday by checking if multiple bars share the same date
    if isinstance(high.index, pd.DatetimeIndex):
        dates = pd.Series(high.index.date, index=high.index)
        # Group by date and cumsum within each day
        cumulative_tp_volume = tp_volume.groupby(dates).cumsum()
        cumulative_volume = volume.groupby(dates).cumsum()
    else:
        # Fallback: no date info, use simple cumulative
        cumulative_tp_volume = tp_volume.cumsum()
        cumulative_volume = volume.cumsum()

    return cumulative_tp_volume / cumulative_volume.replace(0, np.nan)


def calculate_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Returns DataFrame with columns: macd, signal, histogram
    """
    fast_ema = calculate_ema(close, fast)
    slow_ema = calculate_ema(close, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line

    return pd.DataFrame({"macd": macd_line, "signal": signal_line, "histogram": histogram})


def calculate_bollinger_bands(
    close: pd.Series, period: int = 20, std_dev: float = 2.0
) -> pd.DataFrame:
    """Calculate Bollinger Bands"""
    sma = calculate_sma(close, period)
    std = close.rolling(window=period).std()

    return pd.DataFrame(
        {"middle": sma, "upper": sma + (std * std_dev), "lower": sma - (std * std_dev)}
    )


class EMACloudIndicator:
    """
    EMA Cloud indicator based on Ripster's strategy.

    Key clouds and their purposes:
    - 5-12/5-13: Fluid trendline for day trades
    - 8-9: Pullback levels
    - 20-21: Short-term momentum
    - 34-50: Bullish/bearish bias confirmation (MOST IMPORTANT)
    - 72-89: Long-term trend direction
    - 200-233: Major trend/institutional levels
    """

    def __init__(self, clouds_config: dict[str, tuple[int, int]] | None = None):
        """
        Initialize EMA Cloud indicator.

        Args:
            clouds_config: Dict of cloud names to (fast_period, slow_period) tuples
        """
        self.clouds_config = clouds_config or {
            "trend_line": (5, 12),
            "pullback": (8, 9),
            "momentum": (20, 21),
            "trend_confirmation": (34, 50),
            "long_term": (72, 89),
            "major_trend": (200, 233),
        }

    def add_cloud(self, name: str, fast_period: int, slow_period: int):
        """Add a new EMA cloud configuration"""
        self.clouds_config[name] = (fast_period, slow_period)

    def remove_cloud(self, name: str):
        """Remove an EMA cloud configuration"""
        if name in self.clouds_config:
            del self.clouds_config[name]

    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate all EMA clouds for the given data.

        Args:
            df: DataFrame with 'close' column (minimum)

        Returns:
            DataFrame with added EMA cloud columns
        """
        result = df.copy()

        for name, (fast, slow) in self.clouds_config.items():
            result[f"{name}_fast"] = calculate_ema(df["close"], fast)
            result[f"{name}_slow"] = calculate_ema(df["close"], slow)
            result[f"{name}_cloud_top"] = result[[f"{name}_fast", f"{name}_slow"]].max(axis=1)
            result[f"{name}_cloud_bottom"] = result[[f"{name}_fast", f"{name}_slow"]].min(axis=1)
            result[f"{name}_thickness"] = (
                result[f"{name}_cloud_top"] - result[f"{name}_cloud_bottom"]
            )
            result[f"{name}_thickness_pct"] = result[f"{name}_thickness"] / df["close"] * 100
            result[f"{name}_bullish"] = result[f"{name}_fast"] > result[f"{name}_slow"]

        return result

    def get_cloud_state(self, row: pd.Series, name: str) -> CloudState:
        """Get the state of a specific cloud at a point in time"""
        fast = row[f"{name}_fast"]
        slow = row[f"{name}_slow"]

        # Check for crossing (need previous row for this)
        is_bullish = fast > slow

        if is_bullish:
            return CloudState.BULLISH
        else:
            return CloudState.BEARISH

    def get_price_relation(
        self, price: float, cloud_top: float, cloud_bottom: float, tolerance_pct: float = 0.1
    ) -> PriceRelation:
        """Determine price relation to cloud"""
        cloud_height = cloud_top - cloud_bottom
        tolerance = cloud_height * tolerance_pct if cloud_height > 0 else price * 0.001

        if price > cloud_top + tolerance:
            return PriceRelation.ABOVE
        elif price < cloud_bottom - tolerance:
            return PriceRelation.BELOW
        elif abs(price - cloud_top) <= tolerance:
            return PriceRelation.TOUCHING_TOP
        elif abs(price - cloud_bottom) <= tolerance:
            return PriceRelation.TOUCHING_BOTTOM
        else:
            return PriceRelation.INSIDE

    def analyze_single(self, df: pd.DataFrame, idx: int = -1) -> dict[str, CloudData]:
        """
        Analyze cloud data at a specific index.

        Args:
            df: DataFrame with calculated cloud data
            idx: Index to analyze (-1 for latest)

        Returns:
            Dict of cloud names to CloudData objects
        """
        row = df.iloc[idx]
        price = row["close"]
        clouds = {}

        for name in self.clouds_config:
            fast = row[f"{name}_fast"]
            slow = row[f"{name}_slow"]
            top = row[f"{name}_cloud_top"]
            bottom = row[f"{name}_cloud_bottom"]
            thickness = row[f"{name}_thickness"]
            thickness_pct = row[f"{name}_thickness_pct"]

            # Get state
            state = CloudState.BULLISH if fast > slow else CloudState.BEARISH

            # Check for crossings
            if idx > 0:
                prev_row = df.iloc[idx - 1]
                prev_bullish = prev_row[f"{name}_fast"] > prev_row[f"{name}_slow"]
                curr_bullish = fast > slow

                if curr_bullish and not prev_bullish:
                    state = CloudState.CROSSING_UP
                elif not curr_bullish and prev_bullish:
                    state = CloudState.CROSSING_DOWN

            # Price relation
            price_relation = self.get_price_relation(price, top, bottom)

            # Expansion/contraction
            is_expanding = False
            is_contracting = False
            if idx >= 3:
                prev_thickness = df.iloc[idx - 3][f"{name}_thickness"]
                if thickness > prev_thickness * 1.1:
                    is_expanding = True
                elif thickness < prev_thickness * 0.9:
                    is_contracting = True

            # Slope (change in cloud midpoint)
            slope = 0.0
            if idx >= 3:
                curr_mid = (top + bottom) / 2
                prev_mid = (
                    df.iloc[idx - 3][f"{name}_cloud_top"] + df.iloc[idx - 3][f"{name}_cloud_bottom"]
                ) / 2
                slope = (curr_mid - prev_mid) / prev_mid * 100

            clouds[name] = CloudData(
                name=name,
                fast_ema=fast,
                slow_ema=slow,
                cloud_top=top,
                cloud_bottom=bottom,
                cloud_thickness=thickness,
                cloud_thickness_pct=thickness_pct,
                state=state,
                price_relation=price_relation,
                is_expanding=is_expanding,
                is_contracting=is_contracting,
                slope=slope,
            )

        return clouds

    # Canonical ordering from shortest-term to longest-term cloud
    CLOUD_ORDER: list[str] = [
        "trend_line",       # 5-12
        "pullback",         # 8-9
        "momentum",         # 20-21
        "trend_confirmation",  # 34-50
        "long_term",        # 72-89
        "major_trend",      # 200-233
    ]

    def analyze_stacking(self, clouds: dict[str, CloudData]) -> StackingOrder:
        """Analyse cloud stacking order (waterfall detection).

        In a perfect **bullish waterfall** the midpoint of each shorter-term
        cloud sits *above* the midpoint of the next longer-term cloud (e.g.
        5-12 > 8-9 > 20-21 > 34-50 > 72-89 > 200-233).  A perfect **bearish
        waterfall** is the reverse.

        Returns a ``StackingOrder`` with a score from -1.0 (perfect bearish)
        to +1.0 (perfect bullish) and counts of ordered pairs.
        """
        # Build ordered list of cloud midpoints present in the data
        ordered_mids: list[float] = []
        for name in self.CLOUD_ORDER:
            if name in clouds:
                c = clouds[name]
                ordered_mids.append((c.cloud_top + c.cloud_bottom) / 2)

        if len(ordered_mids) < 2:
            return StackingOrder()

        total_pairs = len(ordered_mids) - 1
        bullish_pairs = 0
        bearish_pairs = 0

        for i in range(total_pairs):
            if ordered_mids[i] > ordered_mids[i + 1]:
                bullish_pairs += 1
            elif ordered_mids[i] < ordered_mids[i + 1]:
                bearish_pairs += 1
            # equal → neither counted

        score = (bullish_pairs - bearish_pairs) / total_pairs
        is_bullish = bullish_pairs == total_pairs
        is_bearish = bearish_pairs == total_pairs

        return StackingOrder(
            is_stacked_bullish=is_bullish,
            is_stacked_bearish=is_bearish,
            stacking_score=score,
            ordered_pairs=max(bullish_pairs, bearish_pairs),
            total_pairs=total_pairs,
        )

    def detect_signals(self, df: pd.DataFrame, idx: int = -1) -> list[RawSignal]:
        """
        Detect trading signals based on cloud analysis.

        Returns structured RawSignal objects with signal_type, direction,
        cloud_name, and a human-readable message.

        Signals detected:
        - Cloud flip (color change)
        - Price crossing cloud
        - Cloud bounce
        - Multiple cloud alignment
        """
        signals: list[RawSignal] = []
        clouds = self.analyze_single(df, idx)

        # Key cloud for trend confirmation (34-50)
        if "trend_confirmation" in clouds:
            tc = clouds["trend_confirmation"]

            # Cloud flip signals
            if tc.state == CloudState.CROSSING_UP:
                signals.append(
                    RawSignal(
                        signal_type="TREND_FLIP",
                        direction="bullish",
                        cloud_name="trend_confirmation",
                        message="34-50 cloud turned green",
                    )
                )
            elif tc.state == CloudState.CROSSING_DOWN:
                signals.append(
                    RawSignal(
                        signal_type="TREND_FLIP",
                        direction="bearish",
                        cloud_name="trend_confirmation",
                        message="34-50 cloud turned red",
                    )
                )

            # Price crossing cloud
            if tc.price_relation == PriceRelation.ABOVE and tc.state == CloudState.BULLISH:
                if idx > 0:
                    prev_row = df.iloc[idx - 1]
                    prev_top = prev_row["trend_confirmation_cloud_top"]
                    if prev_row["close"] <= prev_top:
                        signals.append(
                            RawSignal(
                                signal_type="BREAKOUT",
                                direction="bullish",
                                cloud_name="trend_confirmation",
                                message="Price crossed above 34-50 cloud",
                            )
                        )
            elif tc.price_relation == PriceRelation.BELOW and tc.state == CloudState.BEARISH:
                if idx > 0:
                    prev_row = df.iloc[idx - 1]
                    prev_bottom = prev_row["trend_confirmation_cloud_bottom"]
                    if prev_row["close"] >= prev_bottom:
                        signals.append(
                            RawSignal(
                                signal_type="BREAKDOWN",
                                direction="bearish",
                                cloud_name="trend_confirmation",
                                message="Price crossed below 34-50 cloud",
                            )
                        )

        # Trend line cloud (5-12) signals
        if "trend_line" in clouds:
            tl = clouds["trend_line"]

            if tl.state == CloudState.CROSSING_UP:
                signals.append(
                    RawSignal(
                        signal_type="SHORT_TERM",
                        direction="bullish",
                        cloud_name="trend_line",
                        message="5-12 cloud turned green",
                    )
                )
            elif tl.state == CloudState.CROSSING_DOWN:
                signals.append(
                    RawSignal(
                        signal_type="SHORT_TERM",
                        direction="bearish",
                        cloud_name="trend_line",
                        message="5-12 cloud turned red",
                    )
                )

        # Pullback level (8-9) signals
        if "pullback" in clouds:
            pb = clouds["pullback"]

            if pb.price_relation == PriceRelation.TOUCHING_BOTTOM:
                if (
                    "trend_confirmation" in clouds
                    and clouds["trend_confirmation"].state == CloudState.BULLISH
                ):
                    signals.append(
                        RawSignal(
                            signal_type="PULLBACK_ENTRY",
                            direction="bullish",
                            cloud_name="pullback",
                            message="Price at 8-9 cloud support in uptrend",
                        )
                    )
            elif pb.price_relation == PriceRelation.TOUCHING_TOP:
                if (
                    "trend_confirmation" in clouds
                    and clouds["trend_confirmation"].state == CloudState.BEARISH
                ):
                    signals.append(
                        RawSignal(
                            signal_type="PULLBACK_ENTRY",
                            direction="bearish",
                            cloud_name="pullback",
                            message="Price at 8-9 cloud resistance in downtrend",
                        )
                    )

        # Multi-cloud alignment
        bullish_count = sum(
            1 for c in clouds.values() if c.state in [CloudState.BULLISH, CloudState.CROSSING_UP]
        )
        bearish_count = sum(
            1 for c in clouds.values() if c.state in [CloudState.BEARISH, CloudState.CROSSING_DOWN]
        )

        if bullish_count == len(clouds) and len(clouds) >= 3:
            signals.append(
                RawSignal(
                    signal_type="STRONG_ALIGNMENT",
                    direction="bullish",
                    cloud_name="all",
                    message="All clouds bullish",
                )
            )
        elif bearish_count == len(clouds) and len(clouds) >= 3:
            signals.append(
                RawSignal(
                    signal_type="STRONG_ALIGNMENT",
                    direction="bearish",
                    cloud_name="all",
                    message="All clouds bearish",
                )
            )

        # Waterfall detection — perfect stacking order
        stacking = self.analyze_stacking(clouds)
        if stacking.is_waterfall:
            if stacking.is_stacked_bullish:
                signals.append(
                    RawSignal(
                        signal_type="WATERFALL",
                        direction="bullish",
                        cloud_name="all",
                        message="Bullish waterfall — all clouds stacked in order",
                    )
                )
            elif stacking.is_stacked_bearish:
                signals.append(
                    RawSignal(
                        signal_type="WATERFALL",
                        direction="bearish",
                        cloud_name="all",
                        message="Bearish waterfall — all clouds stacked in order",
                    )
                )

        return signals


class TechnicalIndicators:
    """Comprehensive technical indicator calculations for filtering"""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all technical indicators"""
        result = df.copy()

        # RSI
        rsi_period = self.config.get("rsi_period", 14)
        result["rsi"] = calculate_rsi(df["close"], rsi_period)

        # ADX
        adx_period = self.config.get("adx_period", 14)
        adx_df = calculate_adx(df["high"], df["low"], df["close"], adx_period)
        result["adx"] = adx_df["adx"]
        result["plus_di"] = adx_df["plus_di"]
        result["minus_di"] = adx_df["minus_di"]

        # ATR
        atr_period = self.config.get("atr_period", 14)
        result["atr"] = calculate_atr(df["high"], df["low"], df["close"], atr_period)
        result["atr_pct"] = result["atr"] / df["close"] * 100

        # VWAP
        if "volume" in df.columns:
            result["vwap"] = calculate_vwap(df["high"], df["low"], df["close"], df["volume"])

        # MACD
        macd_fast = self.config.get("macd_fast", 12)
        macd_slow = self.config.get("macd_slow", 26)
        macd_signal = self.config.get("macd_signal", 9)
        macd_df = calculate_macd(df["close"], macd_fast, macd_slow, macd_signal)
        result["macd"] = macd_df["macd"]
        result["macd_signal"] = macd_df["signal"]
        result["macd_histogram"] = macd_df["histogram"]

        # Volume analysis
        if "volume" in df.columns:
            vol_period = self.config.get("volume_period", 20)
            result["volume_sma"] = calculate_sma(df["volume"], vol_period)
            result["volume_ratio"] = df["volume"] / result["volume_sma"]

        # Bollinger Bands
        bb_period = self.config.get("bb_period", 20)
        bb_std = self.config.get("bb_std", 2.0)
        bb_df = calculate_bollinger_bands(df["close"], bb_period, bb_std)
        result["bb_upper"] = bb_df["upper"]
        result["bb_middle"] = bb_df["middle"]
        result["bb_lower"] = bb_df["lower"]

        return result

    def get_analysis(self, df: pd.DataFrame, idx: int = -1) -> dict[str, Any]:
        """Get indicator analysis at a specific point"""
        row = df.iloc[idx]

        analysis = {
            "rsi": row.get("rsi"),
            "adx": row.get("adx"),
            "atr": row.get("atr"),
            "atr_pct": row.get("atr_pct"),
            "vwap": row.get("vwap"),
            "volume_ratio": row.get("volume_ratio"),
            "macd": row.get("macd"),
            "macd_signal": row.get("macd_signal"),
            "macd_histogram": row.get("macd_histogram"),
        }

        # Interpretations
        price = row["close"]

        if analysis["rsi"] is not None:
            if analysis["rsi"] > 70:
                analysis["rsi_signal"] = "overbought"
            elif analysis["rsi"] < 30:
                analysis["rsi_signal"] = "oversold"
            else:
                analysis["rsi_signal"] = "neutral"

        if analysis["adx"] is not None:
            if analysis["adx"] > 30:
                analysis["trend_strength"] = "strong"
            elif analysis["adx"] > 20:
                analysis["trend_strength"] = "moderate"
            else:
                analysis["trend_strength"] = "weak"

        if analysis["vwap"] is not None:
            analysis["price_vs_vwap"] = "above" if price > analysis["vwap"] else "below"

        if analysis["volume_ratio"] is not None:
            if analysis["volume_ratio"] > 2.0:
                analysis["volume_signal"] = "very_high"
            elif analysis["volume_ratio"] > 1.5:
                analysis["volume_signal"] = "high"
            elif analysis["volume_ratio"] < 0.5:
                analysis["volume_signal"] = "low"
            else:
                analysis["volume_signal"] = "normal"

        return analysis
