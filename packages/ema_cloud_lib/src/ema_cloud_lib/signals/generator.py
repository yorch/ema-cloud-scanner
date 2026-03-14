"""
Signal Generator Module

Combines EMA Cloud analysis with filtering indicators to generate
high-quality trading signals. Based on Ripster's methodology with
additional confirmation filters.

Signal Generation Rules:
1. 34-50 EMA cloud determines primary trend bias
2. 5-12 EMA cloud for entries/exits
3. 8-9 EMA cloud for pullback entries
4. Volume, RSI, ADX for confirmation
5. Time-of-day filters for intraday
"""

import logging
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from ema_cloud_lib.config.settings import FilterConfig, SignalType, TradingStyle
from ema_cloud_lib.indicators.ema_cloud import (
    CloudData,
    CloudState,
    EMACloudIndicator,
    PriceRelation,
    TechnicalIndicators,
    TrendAnalysis,
)

logger = logging.getLogger(__name__)


class FilterResult(BaseModel):
    """Result of applying a single filter"""

    passed: bool = Field(..., description="Whether filter passed")
    reason: str = Field(..., description="Reason for pass/fail")
    filter_name: str = Field(default="", description="Name of the filter")

    def __bool__(self) -> bool:
        return self.passed


def count_bullish_clouds(clouds: dict[str, CloudData]) -> int:
    """Count clouds in bullish state (BULLISH or CROSSING_UP)"""
    return sum(
        1 for c in clouds.values() if c.state in [CloudState.BULLISH, CloudState.CROSSING_UP]
    )


class SignalDirection(Enum):
    """Signal direction classification"""

    LONG = "long"
    SHORT = "short"


class SignalStrength(Enum):
    """Signal strength classification"""

    VERY_STRONG = 5
    STRONG = 4
    MODERATE = 3
    WEAK = 2
    VERY_WEAK = 1


class Signal(BaseModel):
    """Trading signal with all relevant information"""

    symbol: str = Field(..., description="Symbol for the signal")
    signal_type: SignalType = Field(..., description="Type of signal")
    direction: str = Field(..., description="Signal direction: long or short")
    strength: SignalStrength = Field(..., description="Signal strength rating")
    timestamp: datetime = Field(..., description="Signal generation timestamp")
    price: float = Field(..., description="Price at signal generation")

    # Cloud data at signal time
    primary_cloud_state: CloudState = Field(..., description="Primary cloud state")
    price_relation: PriceRelation = Field(..., description="Price relation to cloud")

    # Confirmation indicators
    rsi: float | None = Field(default=None, description="RSI value")
    adx: float | None = Field(default=None, description="ADX value")
    volume_ratio: float | None = Field(default=None, description="Volume relative to average")
    vwap_confirmed: bool = Field(default=False, description="VWAP confirmation status")
    macd_confirmed: bool = Field(default=False, description="MACD confirmation status")

    # Risk management
    suggested_stop: float | None = Field(default=None, description="Suggested stop loss price")
    suggested_target: float | None = Field(default=None, description="Suggested target price")
    risk_reward_ratio: float | None = Field(default=None, description="Risk/reward ratio")

    # Filter results
    filters_passed: list[str] = Field(default_factory=list, description="List of passed filters")
    filters_failed: list[str] = Field(default_factory=list, description="List of failed filters")

    # Additional context
    sector: str | None = Field(default=None, description="Sector classification")
    etf_symbol: str | None = Field(default=None, description="Related ETF symbol")
    notes: list[str] = Field(default_factory=list, description="Additional notes")

    def is_valid(self) -> bool:
        """Check if signal passed all required filters"""
        return len(self.filters_failed) == 0

    def validate_signal(self) -> list[str]:
        """
        Comprehensive signal validation returning list of issues.
        Returns empty list if signal is fully valid.
        """
        issues = []

        # Price validation
        if self.price <= 0:
            issues.append(f"Invalid price: {self.price}")

        # Direction validation
        if self.direction not in ("long", "short"):
            issues.append(f"Invalid direction: {self.direction}")

        # Risk/reward validation
        if self.suggested_stop is not None and self.price > 0:
            if self.direction == "long" and self.suggested_stop >= self.price:
                issues.append(f"Stop loss {self.suggested_stop} above entry {self.price} for long")
            elif self.direction == "short" and self.suggested_stop <= self.price:
                issues.append(f"Stop loss {self.suggested_stop} below entry {self.price} for short")

        if self.risk_reward_ratio is not None and self.risk_reward_ratio < 1.0:
            issues.append(f"Poor risk/reward ratio: {self.risk_reward_ratio:.2f}")

        # RSI extreme values
        if self.rsi is not None:
            if self.direction == "long" and self.rsi > 80:
                issues.append(f"RSI extremely overbought ({self.rsi:.1f}) for long entry")
            elif self.direction == "short" and self.rsi < 20:
                issues.append(f"RSI extremely oversold ({self.rsi:.1f}) for short entry")

        # Add filter failures
        issues.extend(self.filters_failed)

        return issues

    def is_actionable(self) -> bool:
        """Check if signal is actionable (valid and strong enough)"""
        return (
            self.is_valid()
            and self.strength.value >= SignalStrength.MODERATE.value
            and (self.risk_reward_ratio is None or self.risk_reward_ratio >= 1.5)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "signal_type": self.signal_type.value,
            "direction": self.direction,
            "strength": self.strength.name,
            "timestamp": self.timestamp.isoformat(),
            "price": self.price,
            "cloud_state": self.primary_cloud_state.value,
            "price_relation": self.price_relation.value,
            "rsi": self.rsi,
            "adx": self.adx,
            "volume_ratio": self.volume_ratio,
            "vwap_confirmed": self.vwap_confirmed,
            "suggested_stop": self.suggested_stop,
            "suggested_target": self.suggested_target,
            "is_valid": self.is_valid(),
            "notes": self.notes,
        }


class SectorTrendState(BaseModel):
    """Current trend state for a sector ETF"""

    symbol: str = Field(..., description="ETF symbol")
    sector_name: str = Field(..., description="Sector name")
    timestamp: datetime = Field(..., description="Timestamp of trend state")

    # Trend info
    trend_direction: str = Field(..., description="Trend direction: bullish, bearish, or neutral")
    trend_strength: float = Field(..., description="Trend strength (0-100)")
    trend_duration: int = Field(..., description="Bars in current trend")

    # Cloud states
    cloud_states: dict[str, CloudState] = Field(
        default_factory=dict, description="Cloud states by name"
    )
    cloud_alignment: int = Field(default=0, description="Number of aligned clouds")

    # Key levels
    support_level: float | None = Field(default=None, description="Support price level")
    resistance_level: float | None = Field(default=None, description="Resistance price level")

    # Recent signals
    last_signal: Signal | None = Field(default=None, description="Most recent signal")

    def is_bullish(self) -> bool:
        return self.trend_direction == "bullish"

    def is_bearish(self) -> bool:
        return self.trend_direction == "bearish"


class SignalFilter:
    """
    Filter class for validating signals.
    Each filter returns a FilterResult with passed status and reason.
    """

    def __init__(self, config: FilterConfig):
        self.config = config

    def filter_volume(self, row: pd.Series) -> FilterResult:
        """Check if volume meets minimum threshold"""
        if not self.config.volume_enabled:
            return FilterResult(passed=True, reason="Volume filter disabled", filter_name="volume")

        volume_ratio = row.get("volume_ratio", 1.0)
        if pd.isna(volume_ratio):
            return FilterResult(
                passed=True, reason="Volume ratio not available", filter_name="volume"
            )
        if volume_ratio >= self.config.volume_multiplier:
            return FilterResult(
                passed=True,
                reason=f"Volume ratio {volume_ratio:.2f}x meets threshold",
                filter_name="volume",
            )
        return FilterResult(
            passed=False,
            reason=f"Volume ratio {volume_ratio:.2f}x below {self.config.volume_multiplier}x threshold",
            filter_name="volume",
        )

    def _evaluate_directional_filter(
        self,
        direction: str,
        long_condition: bool,
        short_condition: bool,
        long_message: str,
        short_message: str,
        filter_name: str,
    ) -> FilterResult:
        """
        Helper to evaluate directional filters (long vs short).

        Args:
            direction: "long" or "short"
            long_condition: Whether condition passes for long entry
            short_condition: Whether condition passes for short entry
            long_message: Success/failure message for long
            short_message: Success/failure message for short
            filter_name: Name of the filter (for logging)
        """
        if direction == "long":
            return FilterResult(long_condition, long_message, filter_name)
        else:  # short direction
            return FilterResult(short_condition, short_message, filter_name)

    def filter_rsi(self, row: pd.Series, direction: str) -> FilterResult:
        """Check RSI for overbought/oversold conditions"""
        if not self.config.rsi_enabled:
            return FilterResult(passed=True, reason="RSI filter disabled", filter_name="rsi")

        rsi = row.get("rsi")
        if rsi is None or pd.isna(rsi):
            return FilterResult(passed=True, reason="RSI not available", filter_name="rsi")

        # Long entry logic
        if direction == "long":
            if rsi > self.config.rsi_overbought:
                return FilterResult(
                    passed=False,
                    reason=f"RSI {rsi:.1f} overbought for long entry",
                    filter_name="rsi",
                )
            elif rsi < self.config.rsi_neutral_zone[0]:
                return FilterResult(
                    passed=True,
                    reason=f"RSI {rsi:.1f} showing potential upward momentum",
                    filter_name="rsi",
                )
            return FilterResult(
                passed=True, reason=f"RSI {rsi:.1f} in neutral zone", filter_name="rsi"
            )
        # Short entry logic
        if rsi < self.config.rsi_oversold:
            return FilterResult(
                passed=False, reason=f"RSI {rsi:.1f} oversold for short entry", filter_name="rsi"
            )
        elif rsi > self.config.rsi_neutral_zone[1]:
            return FilterResult(
                passed=True,
                reason=f"RSI {rsi:.1f} showing potential downward momentum",
                filter_name="rsi",
            )
        return FilterResult(passed=True, reason=f"RSI {rsi:.1f} in neutral zone", filter_name="rsi")

    def filter_adx(self, row: pd.Series) -> FilterResult:
        """Check ADX for trend strength"""
        if not self.config.adx_enabled:
            return FilterResult(passed=True, reason="ADX filter disabled", filter_name="adx")

        adx = row.get("adx")
        if adx is None or pd.isna(adx):
            return FilterResult(passed=True, reason="ADX not available", filter_name="adx")

        if adx >= self.config.adx_strong_trend:
            return FilterResult(
                passed=True, reason=f"ADX {adx:.1f} shows strong trend", filter_name="adx"
            )
        elif adx >= self.config.adx_min_strength:
            return FilterResult(
                passed=True, reason=f"ADX {adx:.1f} shows moderate trend", filter_name="adx"
            )
        return FilterResult(
            passed=False,
            reason=f"ADX {adx:.1f} too weak (min {self.config.adx_min_strength})",
            filter_name="adx",
        )

    def filter_vwap(self, row: pd.Series, direction: str) -> FilterResult:
        """Check price position relative to VWAP"""
        if not self.config.vwap_enabled:
            return FilterResult(passed=True, reason="VWAP filter disabled", filter_name="vwap")

        vwap = row.get("vwap")
        price = row.get("close")

        if vwap is None or price is None or pd.isna(vwap) or pd.isna(price):
            return FilterResult(passed=True, reason="VWAP not available", filter_name="vwap")

        if direction == "long":
            if price > vwap:
                return FilterResult(
                    passed=True,
                    reason=f"Price ${price:.2f} above VWAP ${vwap:.2f}",
                    filter_name="vwap",
                )
            return FilterResult(
                passed=False,
                reason=f"Price ${price:.2f} below VWAP ${vwap:.2f} for long",
                filter_name="vwap",
            )
        # Short direction
        if price < vwap:
            return FilterResult(
                passed=True, reason=f"Price ${price:.2f} below VWAP ${vwap:.2f}", filter_name="vwap"
            )
        return FilterResult(
            passed=False,
            reason=f"Price ${price:.2f} above VWAP ${vwap:.2f} for short",
            filter_name="vwap",
        )

    def filter_atr(self, row: pd.Series) -> FilterResult:
        """Check ATR for volatility conditions"""
        if not self.config.atr_enabled:
            return FilterResult(passed=True, reason="ATR filter disabled", filter_name="atr")

        atr_pct = row.get("atr_pct")
        if atr_pct is None or pd.isna(atr_pct):
            return FilterResult(passed=True, reason="ATR not available", filter_name="atr")

        if atr_pct < self.config.atr_min_threshold:
            return FilterResult(
                passed=False,
                reason=f"ATR {atr_pct:.2f}% too low (min {self.config.atr_min_threshold}%)",
                filter_name="atr",
            )
        elif atr_pct > self.config.atr_max_threshold:
            return FilterResult(
                passed=False,
                reason=f"ATR {atr_pct:.2f}% too high (max {self.config.atr_max_threshold}%)",
                filter_name="atr",
            )
        return FilterResult(
            passed=True, reason=f"ATR {atr_pct:.2f}% within acceptable range", filter_name="atr"
        )

    def filter_macd(self, row: pd.Series, direction: str) -> FilterResult:
        """Check MACD for momentum confirmation"""
        if not self.config.macd_enabled:
            return FilterResult(passed=True, reason="MACD filter disabled", filter_name="macd")

        macd_hist = row.get("macd_histogram")
        if macd_hist is None or pd.isna(macd_hist):
            return FilterResult(passed=True, reason="MACD not available", filter_name="macd")

        if direction == "long":
            if macd_hist > 0:
                return FilterResult(
                    passed=True,
                    reason=f"MACD histogram {macd_hist:.4f} positive",
                    filter_name="macd",
                )
            return FilterResult(
                passed=False,
                reason=f"MACD histogram {macd_hist:.4f} negative for long",
                filter_name="macd",
            )
        # Short direction
        if macd_hist < 0:
            return FilterResult(
                passed=True, reason=f"MACD histogram {macd_hist:.4f} negative", filter_name="macd"
            )
        return FilterResult(
            passed=False,
            reason=f"MACD histogram {macd_hist:.4f} positive for short",
            filter_name="macd",
        )

    def filter_time_of_day(self, timestamp: datetime) -> FilterResult:
        """Check if within valid trading hours"""
        if not self.config.time_filter_enabled:
            return FilterResult(passed=True, reason="Time filter disabled", filter_name="time")

        current_time = timestamp.time()

        # Parse trading hours
        start_parts = self.config.trading_start_time.split(":")
        end_parts = self.config.trading_end_time.split(":")

        trading_start = time(int(start_parts[0]), int(start_parts[1]))
        trading_end = time(int(end_parts[0]), int(end_parts[1]))

        # Add buffer for first/last minutes
        buffer_start = (
            datetime.combine(datetime.today(), trading_start)
            + timedelta(minutes=self.config.avoid_first_minutes)
        ).time()
        buffer_end = (
            datetime.combine(datetime.today(), trading_end)
            - timedelta(minutes=self.config.avoid_last_minutes)
        ).time()

        if current_time < buffer_start:
            return FilterResult(
                passed=False,
                reason=f"Too early - avoiding first {self.config.avoid_first_minutes} minutes",
                filter_name="time",
            )
        elif current_time > buffer_end:
            return FilterResult(
                passed=False,
                reason=f"Too late - avoiding last {self.config.avoid_last_minutes} minutes",
                filter_name="time",
            )
        return FilterResult(passed=True, reason="Within valid trading hours", filter_name="time")

    def apply_all_filters(
        self, row: pd.Series, direction: str, timestamp: datetime
    ) -> tuple[list[str], list[str]]:
        """
        Apply all filters and return (passed_filters, failed_filters)
        """
        passed = []
        failed = []

        results = [
            self.filter_volume(row),
            self.filter_rsi(row, direction),
            self.filter_adx(row),
            self.filter_vwap(row, direction),
            self.filter_atr(row),
            self.filter_macd(row, direction),
            self.filter_time_of_day(timestamp),
        ]

        for result in results:
            formatted = f"{result.filter_name}: {result.reason}"
            if result.passed:
                passed.append(formatted)
            else:
                failed.append(formatted)

        return passed, failed


class SignalGenerator:
    """
    Main signal generator combining EMA clouds with filters.

    Signal Generation Process:
    1. Calculate EMA clouds for all configured periods
    2. Detect cloud state changes and crossovers
    3. Calculate confirmation indicators
    4. Apply filters
    5. Calculate risk/reward levels
    6. Generate final signal with strength rating
    """

    def __init__(
        self,
        clouds_config: dict[str, tuple[int, int]] | None = None,
        filter_config: FilterConfig | None = None,
        trading_style: TradingStyle = TradingStyle.INTRADAY,
    ):
        self.cloud_indicator = EMACloudIndicator(clouds_config)
        self.tech_indicators = TechnicalIndicators()
        self.filter_config = filter_config or FilterConfig()
        self.signal_filter = SignalFilter(self.filter_config)
        self.trading_style = trading_style

        # Track recent signals to avoid duplicates
        self._recent_signals: dict[str, datetime] = {}
        self._signal_cooldown_bars = 5

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators on the data"""
        # Calculate EMA clouds
        result = self.cloud_indicator.calculate(df)

        # Calculate technical indicators
        result = self.tech_indicators.calculate_all(result)

        return result

    def analyze_trend(self, df: pd.DataFrame, symbol: str, idx: int = -1) -> TrendAnalysis:
        """
        Perform complete trend analysis at a specific point.

        Returns TrendAnalysis with all relevant information.
        """
        row = df.iloc[idx]
        timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp.now()
        price = row["close"]

        # Get cloud analysis
        clouds = self.cloud_indicator.analyze_single(df, idx)

        # Get technical indicator analysis
        indicators = self.tech_indicators.get_analysis(df, idx)

        # Detect signals
        signals = self.cloud_indicator.detect_signals(df, idx)

        # Determine overall trend
        bullish_clouds = count_bullish_clouds(clouds)
        total_clouds = len(clouds)

        if bullish_clouds >= total_clouds * 0.7:
            overall_trend = "bullish"
        elif bullish_clouds <= total_clouds * 0.3:
            overall_trend = "bearish"
        else:
            overall_trend = "neutral"

        # Calculate trend strength (0-100)
        trend_strength = 50.0

        # ADX contribution
        adx = indicators.get("adx")
        if adx is not None and not pd.isna(adx):
            trend_strength = min(100, adx * 2)

        # Cloud alignment contribution
        alignment_bonus = (bullish_clouds / total_clouds - 0.5) * 40 if total_clouds > 0 else 0
        if overall_trend == "bearish":
            alignment_bonus = (
                ((total_clouds - bullish_clouds) / total_clouds - 0.5) * 40
                if total_clouds > 0
                else 0
            )
        trend_strength += alignment_bonus

        trend_strength = max(0, min(100, trend_strength))

        return TrendAnalysis(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            clouds=clouds,
            overall_trend=overall_trend,
            trend_strength=trend_strength,
            trend_alignment=bullish_clouds
            if overall_trend == "bullish"
            else total_clouds - bullish_clouds,
            signals=signals,
            rsi=indicators.get("rsi"),
            adx=indicators.get("adx"),
            atr=indicators.get("atr"),
            atr_pct=indicators.get("atr_pct"),
            vwap=indicators.get("vwap"),
            volume_ratio=indicators.get("volume_ratio"),
            macd=indicators.get("macd"),
            macd_signal=indicators.get("macd_signal"),
            macd_histogram=indicators.get("macd_histogram"),
        )

    def generate_signals(
        self,
        df: pd.DataFrame,
        symbol: str,
        sector: str | None = None,
        etf_symbol: str | None = None,
        check_history: int = 3,
    ) -> list[Signal]:
        """
        Generate trading signals from the data.

        Args:
            df: DataFrame with OHLCV data
            symbol: Stock/ETF symbol
            sector: Sector name (optional)
            etf_symbol: Related ETF symbol for sector filtering
            check_history: Number of recent bars to check for signals

        Returns:
            List of Signal objects
        """
        signals = []

        # Prepare data with all indicators
        prepared_df = self.prepare_data(df)

        # Check recent bars for signals
        for i in range(-check_history, 0):
            if abs(i) >= len(prepared_df):
                continue

            row = prepared_df.iloc[i]
            timestamp = row.name if isinstance(row.name, pd.Timestamp) else pd.Timestamp.now()

            # Skip if we recently generated a signal for this symbol
            signal_key = f"{symbol}_{i}"
            if signal_key in self._recent_signals:
                continue

            # Analyze clouds at this point
            clouds = self.cloud_indicator.analyze_single(prepared_df, i)
            raw_signals = self.cloud_indicator.detect_signals(prepared_df, i)

            if not raw_signals:
                continue

            # Process each raw signal
            for raw_signal in raw_signals:
                signal = self._process_raw_signal(
                    raw_signal=raw_signal,
                    row=row,
                    clouds=clouds,
                    symbol=symbol,
                    timestamp=timestamp,
                    sector=sector,
                    etf_symbol=etf_symbol,
                )

                if signal:
                    signals.append(signal)
                    self._recent_signals[signal_key] = timestamp

        return signals

    def _process_raw_signal(
        self,
        raw_signal: str,
        row: pd.Series,
        clouds: dict[str, CloudData],
        symbol: str,
        timestamp: datetime,
        sector: str | None = None,
        etf_symbol: str | None = None,
    ) -> Signal | None:
        """Process a raw signal string into a Signal object"""

        # Determine direction from structured signal keywords
        raw_upper = raw_signal.upper()
        bullish_keywords = (
            "TREND_FLIP_BULLISH",
            "BREAKOUT",
            "SHORT_TERM_BULLISH",
            "PULLBACK_ENTRY: PRICE AT 8-9 CLOUD SUPPORT IN UPTREND",
            "STRONG_ALIGNMENT: ALL CLOUDS BULLISH",
        )
        is_bullish = any(kw in raw_upper for kw in bullish_keywords)
        direction = "long" if is_bullish else "short"

        # Map raw signal to SignalType
        if "TREND_FLIP" in raw_signal:
            signal_type = (
                SignalType.CLOUD_FLIP_BULLISH if is_bullish else SignalType.CLOUD_FLIP_BEARISH
            )
        elif "BREAKOUT" in raw_signal:
            signal_type = SignalType.PRICE_CROSS_ABOVE
        elif "BREAKDOWN" in raw_signal:
            signal_type = SignalType.PRICE_CROSS_BELOW
        elif "PULLBACK" in raw_signal:
            signal_type = SignalType.PULLBACK_ENTRY
        elif "ALIGNMENT" in raw_signal:
            signal_type = SignalType.TREND_CONFIRMATION
        else:
            signal_type = (
                SignalType.CLOUD_FLIP_BULLISH if is_bullish else SignalType.CLOUD_FLIP_BEARISH
            )

        # Get primary cloud state (34-50)
        primary_cloud = clouds.get(
            "trend_confirmation", next(iter(clouds.values())) if clouds else None
        )
        if not primary_cloud:
            return None

        # Apply filters
        passed_filters, failed_filters = self.signal_filter.apply_all_filters(
            row, direction, timestamp
        )

        # Calculate signal strength
        strength = self._calculate_signal_strength(
            clouds=clouds, row=row, passed_filters=passed_filters, failed_filters=failed_filters
        )

        # Calculate risk management levels
        atr = row.get("atr", row["close"] * 0.02)
        if pd.isna(atr):
            atr = row["close"] * 0.02
        price = row["close"]

        if direction == "long":
            stop_loss = primary_cloud.cloud_bottom - atr
            target = price + (price - stop_loss) * 2  # 2:1 R/R
        else:
            stop_loss = primary_cloud.cloud_top + atr
            target = price - (stop_loss - price) * 2

        risk = abs(price - stop_loss)
        reward = abs(target - price)
        rr_ratio = reward / risk if risk > 0 else 0

        return Signal(
            symbol=symbol,
            signal_type=signal_type,
            direction=direction,
            strength=strength,
            timestamp=timestamp,
            price=price,
            primary_cloud_state=primary_cloud.state,
            price_relation=primary_cloud.price_relation,
            rsi=row.get("rsi") if not pd.isna(row.get("rsi")) else None,
            adx=row.get("adx") if not pd.isna(row.get("adx")) else None,
            volume_ratio=row.get("volume_ratio") if not pd.isna(row.get("volume_ratio")) else None,
            vwap_confirmed=row.get("close", 0) > row.get("vwap", 0)
            if direction == "long"
            else row.get("close", 0) < row.get("vwap", 0),
            macd_confirmed=row.get("macd_histogram", 0) > 0
            if direction == "long"
            else row.get("macd_histogram", 0) < 0,
            suggested_stop=stop_loss,
            suggested_target=target,
            risk_reward_ratio=rr_ratio,
            filters_passed=passed_filters,
            filters_failed=failed_filters,
            sector=sector,
            etf_symbol=etf_symbol,
            notes=[raw_signal],
        )

    def _calculate_signal_strength(
        self,
        clouds: dict[str, CloudData],
        row: pd.Series,
        passed_filters: list[str],
        failed_filters: list[str],
    ) -> SignalStrength:
        """Calculate signal strength based on multiple factors"""

        score: float = 50

        # Cloud alignment bonus (up to +20)
        bullish_count = count_bullish_clouds(clouds)
        alignment_ratio = bullish_count / len(clouds) if clouds else 0.5
        # Adjust for bearish signals
        if alignment_ratio < 0.5:
            alignment_ratio = 1 - alignment_ratio
        score += (alignment_ratio - 0.5) * 40

        # Filter results (+/- 20)
        filter_ratio = (
            len(passed_filters) / (len(passed_filters) + len(failed_filters))
            if (passed_filters or failed_filters)
            else 0.5
        )
        score += (filter_ratio - 0.5) * 40

        # ADX bonus (up to +10)
        adx = row.get("adx")
        if adx is not None:
            if adx > 30:
                score += 10
            elif adx > 20:
                score += 5
            else:
                score -= 5

        # Volume bonus (up to +10)
        volume_ratio = row.get("volume_ratio")
        if volume_ratio is not None:
            if volume_ratio > 2.0:
                score += 10
            elif volume_ratio > 1.5:
                score += 5

        # Cloud expansion bonus (up to +5)
        primary_cloud = clouds.get("trend_confirmation")
        if primary_cloud and primary_cloud.is_expanding:
            score += 5

        # Map score to strength
        if score >= 85:
            return SignalStrength.VERY_STRONG
        elif score >= 70:
            return SignalStrength.STRONG
        elif score >= 55:
            return SignalStrength.MODERATE
        elif score >= 40:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK

    def _get_trend_from_clouds(self, df: pd.DataFrame, idx: int) -> str:
        """Get trend direction from cloud states at a specific index (efficient version)."""
        clouds = self.cloud_indicator.analyze_single(df, idx)
        bullish_clouds = count_bullish_clouds(clouds)
        total_clouds = len(clouds)

        if bullish_clouds >= total_clouds * 0.7:
            return "bullish"
        elif bullish_clouds <= total_clouds * 0.3:
            return "bearish"
        return "neutral"

    def get_sector_trend_state(
        self, df: pd.DataFrame, symbol: str, sector_name: str
    ) -> SectorTrendState:
        """
        Get current trend state for a sector ETF.
        Used to filter individual stock signals.

        Note: Expects df to be already prepared via prepare_data().
        """
        analysis = self.analyze_trend(df, symbol)
        current_trend = analysis.overall_trend

        # Count trend duration efficiently (without full analyze_trend)
        trend_duration = 0
        max_lookback = min(len(df) - 1, 100)  # Limit lookback for performance

        for i in range(len(df) - 2, len(df) - 2 - max_lookback, -1):
            if i < 0:
                break
            prev_trend = self._get_trend_from_clouds(df, i)
            if prev_trend == current_trend:
                trend_duration += 1
            else:
                break

        # Reuse cloud states from analysis (avoid duplicate calculation)
        cloud_states = {name: cloud.state for name, cloud in analysis.clouds.items()}

        # Calculate support/resistance from clouds
        primary_cloud = analysis.clouds.get("trend_confirmation")
        support = primary_cloud.cloud_bottom if primary_cloud else None
        resistance = primary_cloud.cloud_top if primary_cloud else None

        return SectorTrendState(
            symbol=symbol,
            sector_name=sector_name,
            timestamp=analysis.timestamp,
            trend_direction=analysis.overall_trend,
            trend_strength=analysis.trend_strength,
            trend_duration=trend_duration,
            cloud_states=cloud_states,
            cloud_alignment=analysis.trend_alignment,
            support_level=support,
            resistance_level=resistance,
        )

    def filter_by_sector_trend(self, stock_signal: Signal, sector_trend: SectorTrendState) -> bool:
        """
        Filter stock signal based on sector ETF trend.

        Rules:
        - Long signals only when sector is bullish
        - Short signals only when sector is bearish
        - Neutral sector = no filter (allow both)
        """
        if sector_trend.trend_direction == "neutral":
            return True

        if (stock_signal.direction == "long" and sector_trend.is_bullish()) or (
            stock_signal.direction == "short" and sector_trend.is_bearish()
        ):
            return True
        else:
            stock_signal.filters_failed.append(
                f"sector_trend: {sector_trend.sector_name} trend is {sector_trend.trend_direction}, "
                f"signal direction is {stock_signal.direction}"
            )
            return False

    def filter_signal_by_sector(
        self, signal: Signal, sector_state: SectorTrendState
    ) -> tuple[bool, str]:
        """
        Filter an individual stock signal based on sector ETF trend.

        Rules:
        - Long signals require bullish sector trend
        - Short signals require bearish sector trend
        - Sector trend strength affects signal validity
        """
        if signal.direction == "long":
            if sector_state.is_bullish():
                if sector_state.trend_strength >= 50:
                    return True, f"Sector {sector_state.sector_name} confirms bullish bias"
                else:
                    return (
                        True,
                        f"Sector {sector_state.sector_name} weak bullish - proceed with caution",
                    )
            elif sector_state.is_bearish():
                return False, f"Sector {sector_state.sector_name} bearish - avoid long entries"
            else:
                return True, f"Sector {sector_state.sector_name} neutral - use other confirmations"
        elif signal.direction == "short":
            if sector_state.is_bearish():
                if sector_state.trend_strength >= 50:
                    return True, f"Sector {sector_state.sector_name} confirms bearish bias"
                else:
                    return (
                        True,
                        f"Sector {sector_state.sector_name} weak bearish - proceed with caution",
                    )
            elif sector_state.is_bullish():
                return False, f"Sector {sector_state.sector_name} bullish - avoid short entries"
            else:
                return True, f"Sector {sector_state.sector_name} neutral - use other confirmations"
        else:
            return False, f"Unknown signal direction: {signal.direction}"
