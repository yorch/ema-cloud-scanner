"""
Multi-Timeframe Analyzer

Analyzes trends across multiple timeframes to confirm signal quality.
Professional traders use higher timeframe trend confirmation to filter
lower timeframe entries, significantly improving win rates.

Typical Setup:
- Daily: Overall trend bias
- 4H: Intermediate trend
- 1H: Entry timeframe

Signal Quality:
- All aligned = VERY HIGH confidence
- 2/3 aligned = MODERATE confidence
- Divergent = LOW confidence (avoid trade)
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from enum import Enum

import pandas as pd
from pydantic import BaseModel, Field

from ema_cloud_lib.indicators.ema_cloud import EMACloudIndicator

logger = logging.getLogger(__name__)

# Type alias for the data fetcher callable
DataFetcherT = Callable[[str, str, int], Awaitable[pd.DataFrame | None]]


class MTFAlignment(Enum):
    """Multi-timeframe alignment status"""

    FULL_BULL = "full_bullish"  # All timeframes bullish
    FULL_BEAR = "full_bearish"  # All timeframes bearish
    PARTIAL_BULL = "partial_bullish"  # Majority bullish
    PARTIAL_BEAR = "partial_bearish"  # Majority bearish
    MIXED = "mixed"  # No clear consensus
    NEUTRAL = "neutral"  # All timeframes neutral


class MTFConfidence(Enum):
    """Signal confidence based on MTF alignment"""

    VERY_HIGH = "very_high"  # 100% alignment
    HIGH = "high"  # 80%+ alignment
    MODERATE = "moderate"  # 60%+ alignment
    LOW = "low"  # < 60% alignment


class TimeframeResult(BaseModel):
    """Analysis result for a single timeframe"""

    timeframe: str
    interval: str
    trend: str  # bullish, bearish, neutral
    trend_strength: float  # 0-100
    cloud_alignment: int  # Number of aligned clouds
    total_clouds: int  # Total clouds analyzed
    rsi: float | None = None
    adx: float | None = None
    timestamp: datetime | None = None


class MTFAnalysisResult(BaseModel):
    """Complete multi-timeframe analysis result"""

    symbol: str = Field(..., description="Symbol analyzed")
    timeframes: list[TimeframeResult] = Field(..., description="Results per timeframe")
    alignment: MTFAlignment = Field(..., description="Overall alignment status")
    confidence: MTFConfidence = Field(..., description="Signal confidence level")
    bias: str = Field(..., description="Trading bias: long, short, or neutral")
    bullish_count: int = Field(..., description="Number of bullish timeframes")
    bearish_count: int = Field(..., description="Number of bearish timeframes")
    neutral_count: int = Field(..., description="Number of neutral timeframes")
    alignment_pct: float = Field(..., description="Percentage alignment (0-100)")

    @property
    def is_confirmed(self) -> bool:
        """Whether signal is confirmed by higher timeframes"""
        return self.confidence in (MTFConfidence.VERY_HIGH, MTFConfidence.HIGH)

    @property
    def summary(self) -> str:
        """Human-readable summary"""
        if self.alignment == MTFAlignment.FULL_BULL:
            return f"✅ FULL ALIGNMENT ({self.bullish_count}/{len(self.timeframes)} bullish) → LONG BIAS"
        elif self.alignment == MTFAlignment.FULL_BEAR:
            return f"✅ FULL ALIGNMENT ({self.bearish_count}/{len(self.timeframes)} bearish) → SHORT BIAS"
        elif self.alignment in (MTFAlignment.PARTIAL_BULL, MTFAlignment.PARTIAL_BEAR):
            return f"⚠️ PARTIAL ALIGNMENT ({self.alignment_pct:.0f}%) → {self.bias.upper()} BIAS"
        else:
            return "❌ MIXED SIGNALS → NO CLEAR BIAS"


class MultiTimeframeAnalyzer:
    """
    Analyzes EMA cloud trends across multiple timeframes.

    Professional Trading Approach:
    1. Higher timeframe defines bias (Daily/4H)
    2. Lower timeframe provides entries (1H/15m)
    3. Only trade WITH higher timeframe trend
    """

    def __init__(
        self,
        timeframes: list[str] | None = None,
        cloud_configs: dict | None = None,
    ):
        """
        Initialize MTF analyzer.

        Args:
            timeframes: List of timeframe intervals to analyze (e.g., ['1d', '4h', '1h'])
                       Defaults to ['1d', '4h', '1h'] for swing trading
            cloud_configs: EMA cloud configurations to use
        """
        self.timeframes = timeframes or ["1d", "4h", "1h"]
        self.cloud_configs = cloud_configs

        # Create indicator instances per timeframe
        self.indicators: dict[str, EMACloudIndicator] = {}
        for tf in self.timeframes:
            self.indicators[tf] = EMACloudIndicator(clouds_config=cloud_configs)

        logger.info(f"MTF Analyzer initialized for timeframes: {self.timeframes}")

    async def analyze(
        self,
        symbol: str,
        data_fetcher: DataFetcherT,
        bars_per_tf: int = 200,
    ) -> MTFAnalysisResult:
        """
        Perform multi-timeframe analysis concurrently across all timeframes.

        Args:
            symbol: Symbol to analyze
            data_fetcher: Async callable (symbol, timeframe, limit) -> DataFrame | None
            bars_per_tf: Number of bars to fetch per timeframe

        Returns:
            MTFAnalysisResult with complete analysis
        """
        tasks = [
            self._analyze_single_tf(symbol, tf, data_fetcher, bars_per_tf) for tf in self.timeframes
        ]
        tf_results = await asyncio.gather(*tasks)
        results = [r for r in tf_results if r is not None]

        if not results:
            return self._create_neutral_result(symbol)

        return self._calculate_alignment(symbol, results)

    async def _analyze_single_tf(
        self,
        symbol: str,
        tf: str,
        data_fetcher: DataFetcherT,
        bars_per_tf: int,
    ) -> TimeframeResult | None:
        """Analyze a single timeframe, returning None on failure or missing data."""
        try:
            df = await data_fetcher(symbol, tf, bars_per_tf)

            if df is None or df.empty:
                logger.warning(f"No data for {symbol} on {tf} timeframe")
                return None

            indicator = self.indicators[tf]
            df_with_emas = indicator.calculate(df)
            clouds = indicator.analyze_single(df_with_emas, -1)

            bullish_clouds = sum(
                1 for c in clouds.values() if c.state.name in ["BULLISH", "CROSSING_UP"]
            )
            bearish_clouds = sum(
                1 for c in clouds.values() if c.state.name in ["BEARISH", "CROSSING_DOWN"]
            )
            total_clouds = len(clouds)

            if bullish_clouds > bearish_clouds:
                trend = "bullish"
                trend_strength = (bullish_clouds / total_clouds) * 100
            elif bearish_clouds > bullish_clouds:
                trend = "bearish"
                trend_strength = (bearish_clouds / total_clouds) * 100
            else:
                trend = "neutral"
                trend_strength = 0.0

            timestamp = df_with_emas.index[-1].to_pydatetime() if not df_with_emas.empty else None
            rsi = df_with_emas.iloc[-1].get("rsi") if "rsi" in df_with_emas.columns else None
            adx = df_with_emas.iloc[-1].get("adx") if "adx" in df_with_emas.columns else None

            return TimeframeResult(
                timeframe=self._tf_display_name(tf),
                interval=tf,
                trend=trend,
                trend_strength=trend_strength,
                cloud_alignment=max(bullish_clouds, bearish_clouds),
                total_clouds=total_clouds,
                rsi=rsi,
                adx=adx,
                timestamp=timestamp,
            )

        except Exception as e:
            logger.error(f"Error analyzing {symbol} on {tf}: {e}")
            return None

    def _calculate_alignment(
        self, symbol: str, results: list[TimeframeResult]
    ) -> MTFAnalysisResult:
        """Calculate alignment status from timeframe results"""
        bullish_count = sum(1 for r in results if r.trend == "bullish")
        bearish_count = sum(1 for r in results if r.trend == "bearish")
        neutral_count = sum(1 for r in results if r.trend == "neutral")
        total = len(results)

        # Calculate alignment percentage (ignoring neutrals)
        directional = bullish_count + bearish_count
        if directional > 0:
            alignment_pct = (max(bullish_count, bearish_count) / directional) * 100
        else:
            alignment_pct = 0

        # Determine overall alignment
        if bullish_count == total:
            alignment = MTFAlignment.FULL_BULL
            bias = "long"
        elif bearish_count == total:
            alignment = MTFAlignment.FULL_BEAR
            bias = "short"
        elif bullish_count > bearish_count and bullish_count >= total * 0.6:
            alignment = MTFAlignment.PARTIAL_BULL
            bias = "long"
        elif bearish_count > bullish_count and bearish_count >= total * 0.6:
            alignment = MTFAlignment.PARTIAL_BEAR
            bias = "short"
        elif neutral_count == total:
            alignment = MTFAlignment.NEUTRAL
            bias = "neutral"
        else:
            alignment = MTFAlignment.MIXED
            bias = "neutral"

        # Determine confidence level
        if alignment_pct == 100:
            confidence = MTFConfidence.VERY_HIGH
        elif alignment_pct >= 80:
            confidence = MTFConfidence.HIGH
        elif alignment_pct >= 60:
            confidence = MTFConfidence.MODERATE
        else:
            confidence = MTFConfidence.LOW

        return MTFAnalysisResult(
            symbol=symbol,
            timeframes=results,
            alignment=alignment,
            confidence=confidence,
            bias=bias,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            neutral_count=neutral_count,
            alignment_pct=alignment_pct,
        )

    def _create_neutral_result(self, symbol: str) -> MTFAnalysisResult:
        """Create a neutral result when no data is available"""
        return MTFAnalysisResult(
            symbol=symbol,
            timeframes=[],
            alignment=MTFAlignment.NEUTRAL,
            confidence=MTFConfidence.LOW,
            bias="neutral",
            bullish_count=0,
            bearish_count=0,
            neutral_count=0,
            alignment_pct=0,
        )

    def _tf_display_name(self, interval: str) -> str:
        """Convert interval to display name"""
        mapping = {
            "1m": "1 Min",
            "5m": "5 Min",
            "15m": "15 Min",
            "1h": "1 Hour",
            "4h": "4 Hour",
            "1d": "Daily",
            "1w": "Weekly",
        }
        return mapping.get(interval, interval.upper())

    def should_take_trade(self, mtf_result: MTFAnalysisResult, signal_direction: str) -> bool:
        """
        Determine if a signal should be taken based on MTF analysis.

        Args:
            mtf_result: Multi-timeframe analysis result
            signal_direction: 'long' or 'short'

        Returns:
            True if signal aligns with MTF bias and confidence is acceptable
        """
        # Require at least moderate confidence
        if mtf_result.confidence == MTFConfidence.LOW:
            logger.info(f"{mtf_result.symbol}: LOW MTF confidence - SKIP trade")
            return False

        # Check if signal aligns with MTF bias
        if signal_direction != mtf_result.bias:
            logger.info(
                f"{mtf_result.symbol}: Signal ({signal_direction}) against "
                f"MTF bias ({mtf_result.bias}) - SKIP trade"
            )
            return False

        logger.info(
            f"{mtf_result.symbol}: MTF confirmed ({mtf_result.confidence.value}) - "
            f"OK to take {signal_direction} trade"
        )
        return True
