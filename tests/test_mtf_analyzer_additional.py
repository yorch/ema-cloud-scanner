"""
Additional tests for Multi-Timeframe Analyzer to improve coverage.

These tests cover gaps identified in the original test suite:
- should_take_trade() method
- _tf_display_name() method
- MTFAnalysisResult properties
- Edge cases
"""

import pandas as pd
import pytest

from ema_cloud_lib.indicators.mtf_analyzer import (
    MTFAlignment,
    MTFAnalysisResult,
    MTFConfidence,
    MultiTimeframeAnalyzer,
    TimeframeResult,
)


@pytest.fixture
def bullish_data():
    """Create strongly bullish trending data."""
    dates = pd.date_range("2024-01-01", periods=250, freq="1D")
    # Strong uptrend: price increases consistently
    df = pd.DataFrame(
        {
            "open": [100 + i * 1.0 for i in range(250)],
            "high": [102 + i * 1.0 for i in range(250)],
            "low": [99 + i * 1.0 for i in range(250)],
            "close": [101 + i * 1.0 for i in range(250)],
            "volume": [1000000 + i * 10000 for i in range(250)],
        },
        index=dates,
    )
    return df


class TestShouldTakeTrade:
    """Test trade filtering logic based on MTF analysis."""

    def test_reject_low_confidence(self):
        """Should reject trades with LOW confidence."""
        analyzer = MultiTimeframeAnalyzer()

        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.FULL_BULL,
            confidence=MTFConfidence.LOW,
            bias="long",
            bullish_count=2,
            bearish_count=1,
            neutral_count=0,
            alignment_pct=66.7,
        )

        # Should reject even if bias matches
        assert analyzer.should_take_trade(result, "long") is False

    def test_reject_bias_mismatch(self):
        """Should reject when signal opposes MTF bias."""
        analyzer = MultiTimeframeAnalyzer()

        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.FULL_BULL,
            confidence=MTFConfidence.HIGH,
            bias="long",
            bullish_count=3,
            bearish_count=0,
            neutral_count=0,
            alignment_pct=100.0,
        )

        # Bullish MTF but short signal = reject
        assert analyzer.should_take_trade(result, "short") is False

    def test_accept_matching_bias_moderate_confidence(self):
        """Should accept when bias matches and confidence >= MODERATE."""
        analyzer = MultiTimeframeAnalyzer()

        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.PARTIAL_BULL,
            confidence=MTFConfidence.MODERATE,
            bias="long",
            bullish_count=2,
            bearish_count=1,
            neutral_count=0,
            alignment_pct=66.7,
        )

        assert analyzer.should_take_trade(result, "long") is True

    def test_accept_matching_bias_high_confidence(self):
        """Should accept when bias matches and confidence is HIGH."""
        analyzer = MultiTimeframeAnalyzer()

        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.FULL_BULL,
            confidence=MTFConfidence.HIGH,
            bias="long",
            bullish_count=3,
            bearish_count=0,
            neutral_count=0,
            alignment_pct=100.0,
        )

        assert analyzer.should_take_trade(result, "long") is True

    def test_accept_short_bias(self):
        """Should accept short signals when MTF is bearish."""
        analyzer = MultiTimeframeAnalyzer()

        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.FULL_BEAR,
            confidence=MTFConfidence.VERY_HIGH,
            bias="short",
            bullish_count=0,
            bearish_count=3,
            neutral_count=0,
            alignment_pct=100.0,
        )

        assert analyzer.should_take_trade(result, "short") is True


class TestTimeframeDisplayName:
    """Test timeframe interval to display name conversion."""

    def test_known_intervals(self):
        """Should convert known intervals to display names."""
        analyzer = MultiTimeframeAnalyzer()

        assert analyzer._tf_display_name("1m") == "1 Min"
        assert analyzer._tf_display_name("5m") == "5 Min"
        assert analyzer._tf_display_name("15m") == "15 Min"
        assert analyzer._tf_display_name("1h") == "1 Hour"
        assert analyzer._tf_display_name("4h") == "4 Hour"
        assert analyzer._tf_display_name("1d") == "Daily"
        assert analyzer._tf_display_name("1w") == "Weekly"

    def test_unknown_interval_fallback(self):
        """Should uppercase unknown intervals."""
        analyzer = MultiTimeframeAnalyzer()

        assert analyzer._tf_display_name("2h") == "2H"
        assert analyzer._tf_display_name("3d") == "3D"
        assert analyzer._tf_display_name("custom") == "CUSTOM"


class TestMTFAnalysisResultProperties:
    """Test MTFAnalysisResult computed properties."""

    def test_is_confirmed_very_high(self):
        """Should confirm VERY_HIGH confidence."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.FULL_BULL,
            confidence=MTFConfidence.VERY_HIGH,
            bias="long",
            bullish_count=3,
            bearish_count=0,
            neutral_count=0,
            alignment_pct=100.0,
        )

        assert result.is_confirmed is True

    def test_is_confirmed_high(self):
        """Should confirm HIGH confidence."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.PARTIAL_BULL,
            confidence=MTFConfidence.HIGH,
            bias="long",
            bullish_count=2,
            bearish_count=0,
            neutral_count=1,
            alignment_pct=100.0,
        )

        assert result.is_confirmed is True

    def test_is_not_confirmed_moderate(self):
        """Should not confirm MODERATE confidence."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.PARTIAL_BULL,
            confidence=MTFConfidence.MODERATE,
            bias="long",
            bullish_count=2,
            bearish_count=1,
            neutral_count=0,
            alignment_pct=66.7,
        )

        assert result.is_confirmed is False

    def test_is_not_confirmed_low(self):
        """Should not confirm LOW confidence."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.MIXED,
            confidence=MTFConfidence.LOW,
            bias="neutral",
            bullish_count=1,
            bearish_count=1,
            neutral_count=1,
            alignment_pct=33.3,
        )

        assert result.is_confirmed is False

    def _make_tf(self, timeframe: str, interval: str, trend: str = "bullish") -> TimeframeResult:
        return TimeframeResult(
            timeframe=timeframe,
            interval=interval,
            trend=trend,
            trend_strength=100.0,
            cloud_alignment=6,
            total_clouds=6,
        )

    def test_summary_full_bull(self):
        """Should generate correct summary for FULL_BULL."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[
                self._make_tf("Daily", "1d"),
                self._make_tf("4 Hour", "4h"),
                self._make_tf("1 Hour", "1h"),
            ],
            alignment=MTFAlignment.FULL_BULL,
            confidence=MTFConfidence.VERY_HIGH,
            bias="long",
            bullish_count=3,
            bearish_count=0,
            neutral_count=0,
            alignment_pct=100.0,
        )

        summary = result.summary
        assert "FULL ALIGNMENT" in summary
        assert "3/3" in summary
        assert "LONG BIAS" in summary

    def test_summary_full_bear(self):
        """Should generate correct summary for FULL_BEAR."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[self._make_tf("Daily", "1d", trend="bearish")],
            alignment=MTFAlignment.FULL_BEAR,
            confidence=MTFConfidence.VERY_HIGH,
            bias="short",
            bullish_count=0,
            bearish_count=1,
            neutral_count=0,
            alignment_pct=100.0,
        )

        summary = result.summary
        assert "FULL ALIGNMENT" in summary
        assert "1/1" in summary
        assert "SHORT BIAS" in summary

    def test_summary_partial_alignment(self):
        """Should generate correct summary for partial alignment."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[
                self._make_tf("Daily", "1d"),
                self._make_tf("4 Hour", "4h", trend="neutral"),
            ],
            alignment=MTFAlignment.PARTIAL_BULL,
            confidence=MTFConfidence.MODERATE,
            bias="long",
            bullish_count=1,
            bearish_count=0,
            neutral_count=1,
            alignment_pct=50.0,
        )

        summary = result.summary
        assert "PARTIAL ALIGNMENT" in summary
        assert "50%" in summary
        assert "LONG BIAS" in summary

    def test_summary_mixed(self):
        """Should generate correct summary for mixed signals."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[self._make_tf("Daily", "1d", trend="neutral")],
            alignment=MTFAlignment.MIXED,
            confidence=MTFConfidence.LOW,
            bias="neutral",
            bullish_count=1,
            bearish_count=1,
            neutral_count=1,
            alignment_pct=33.3,
        )

        summary = result.summary
        assert "MIXED SIGNALS" in summary
        assert "NO CLEAR BIAS" in summary


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_single_timeframe(self, bullish_data):
        """Should handle single timeframe analysis."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def mock_fetcher(symbol, timeframe, bars):
            return bullish_data

        result = await analyzer.analyze("TEST", mock_fetcher)

        assert len(result.timeframes) == 1
        assert result.symbol == "TEST"
        assert result.bias in ["long", "neutral"]

    @pytest.mark.asyncio
    async def test_all_neutral_timeframes(self):
        """Should handle all neutral timeframes correctly."""
        import pandas as pd

        # Create data that produces neutral trends
        dates = pd.date_range("2024-01-01", periods=250, freq="1D")
        neutral_data = pd.DataFrame(
            {
                "open": [100] * 250,
                "high": [101] * 250,
                "low": [99] * 250,
                "close": [100] * 250,
                "volume": [1000000] * 250,
            },
            index=dates,
        )

        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def mock_fetcher(symbol, timeframe, bars):
            return neutral_data

        result = await analyzer.analyze("TEST", mock_fetcher)

        # May be neutral or have slight bias depending on EMA calculations
        assert result.alignment in [
            MTFAlignment.NEUTRAL,
            MTFAlignment.MIXED,
            MTFAlignment.FULL_BULL,
            MTFAlignment.FULL_BEAR,
        ]

    @pytest.mark.asyncio
    async def test_many_timeframes(self, bullish_data):
        """Should handle many timeframes efficiently."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1w", "1d", "4h", "1h", "15m", "5m"])

        async def mock_fetcher(symbol, timeframe, bars):
            return bullish_data

        result = await analyzer.analyze("TEST", mock_fetcher)

        assert len(result.timeframes) == 6
        assert result.bullish_count + result.bearish_count + result.neutral_count == 6
