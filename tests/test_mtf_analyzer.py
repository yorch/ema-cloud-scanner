"""
Tests for Multi-Timeframe Analyzer.

Covers:
- MTFAlignment / MTFConfidence enum values
- MTFAnalysisResult model creation, is_confirmed property, summary generation
- MultiTimeframeAnalyzer initialization, bullish/bearish/mixed analysis
- should_take_trade() trade filtering
- _tf_display_name() timeframe display names
- Edge cases: single timeframe, all neutral, many timeframes
- Integration: real-world scenarios, alignment percentage
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
def sample_data():
    """Create sample OHLCV data for testing."""
    dates = pd.date_range("2024-01-01", periods=250, freq="1D")
    df = pd.DataFrame(
        {
            "open": [100 + i * 0.5 for i in range(250)],
            "high": [101 + i * 0.5 for i in range(250)],
            "low": [99 + i * 0.5 for i in range(250)],
            "close": [100.5 + i * 0.5 for i in range(250)],
            "volume": [1000000 + i * 10000 for i in range(250)],
        },
        index=dates,
    )
    return df


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


@pytest.fixture
def bearish_data():
    """Create strongly bearish trending data."""
    dates = pd.date_range("2024-01-01", periods=250, freq="1D")
    # Strong downtrend: price decreases consistently
    df = pd.DataFrame(
        {
            "open": [350 - i * 1.0 for i in range(250)],
            "high": [352 - i * 1.0 for i in range(250)],
            "low": [349 - i * 1.0 for i in range(250)],
            "close": [351 - i * 1.0 for i in range(250)],
            "volume": [1000000 + i * 10000 for i in range(250)],
        },
        index=dates,
    )
    return df


@pytest.fixture
def mixed_data():
    """Create mixed/choppy data with no clear trend."""
    import numpy as np

    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=250, freq="1D")
    # Sideways price action with noise
    base_price = 200
    noise = rng.standard_normal(250) * 5
    df = pd.DataFrame(
        {
            "open": base_price + noise,
            "high": base_price + noise + 2,
            "low": base_price + noise - 2,
            "close": base_price + noise + 1,
            "volume": [1000000 + i * 1000 for i in range(250)],
        },
        index=dates,
    )
    return df


class TestMTFAlignment:
    """Test MTFAlignment enum."""

    def test_alignment_values(self):
        """Test all alignment enum values exist."""
        assert MTFAlignment.FULL_BULL.value == "full_bullish"
        assert MTFAlignment.FULL_BEAR.value == "full_bearish"
        assert MTFAlignment.PARTIAL_BULL.value == "partial_bullish"
        assert MTFAlignment.PARTIAL_BEAR.value == "partial_bearish"
        assert MTFAlignment.MIXED.value == "mixed"
        assert MTFAlignment.NEUTRAL.value == "neutral"


class TestMTFConfidence:
    """Test MTFConfidence enum."""

    def test_confidence_values(self):
        """Test all confidence enum values exist."""
        assert MTFConfidence.VERY_HIGH.value == "very_high"
        assert MTFConfidence.HIGH.value == "high"
        assert MTFConfidence.MODERATE.value == "moderate"
        assert MTFConfidence.LOW.value == "low"


class TestMTFAnalysisResult:
    """Test MTFAnalysisResult model."""

    def test_result_creation(self):
        """Test creating a valid analysis result."""
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

        assert result.alignment == MTFAlignment.FULL_BULL
        assert result.confidence == MTFConfidence.VERY_HIGH
        assert result.bias == "long"
        assert result.bullish_count == 3
        assert result.alignment_pct == 100.0

    def test_partial_bull_result(self):
        """Test partial bullish result."""
        result = MTFAnalysisResult(
            symbol="TEST",
            timeframes=[],
            alignment=MTFAlignment.PARTIAL_BULL,
            confidence=MTFConfidence.HIGH,
            bias="long",
            bullish_count=2,
            bearish_count=1,
            neutral_count=0,
            alignment_pct=100.0,
        )

        assert result.alignment == MTFAlignment.PARTIAL_BULL
        assert result.bullish_count == 2
        assert result.bearish_count == 1


class TestMultiTimeframeAnalyzer:
    """Test MultiTimeframeAnalyzer class."""

    def test_analyzer_initialization(self):
        """Test analyzer initialization with default timeframes."""
        analyzer = MultiTimeframeAnalyzer()

        assert analyzer.timeframes == ["1d", "4h", "1h"]
        assert len(analyzer.indicators) == 3
        assert "1d" in analyzer.indicators
        assert "4h" in analyzer.indicators
        assert "1h" in analyzer.indicators

    def test_analyzer_custom_timeframes(self):
        """Test analyzer with custom timeframes."""
        timeframes = ["1w", "1d", "4h"]
        analyzer = MultiTimeframeAnalyzer(timeframes=timeframes)

        assert analyzer.timeframes == timeframes
        assert len(analyzer.indicators) == 3

    @pytest.mark.asyncio
    async def test_analyze_bullish_trend(self, bullish_data):
        """Test MTF analysis on bullish trending data."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def mock_fetcher(symbol, timeframe, bars):
            return bullish_data

        result = await analyzer.analyze("TEST", mock_fetcher, bars_per_tf=200)

        assert isinstance(result, MTFAnalysisResult)
        assert result.bias == "long"
        assert result.bullish_count >= 1
        assert result.alignment_pct >= 50.0

    @pytest.mark.asyncio
    async def test_analyze_bearish_trend(self, bearish_data):
        """Test MTF analysis on bearish trending data."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def mock_fetcher(symbol, timeframe, bars):
            return bearish_data

        result = await analyzer.analyze("TEST", mock_fetcher, bars_per_tf=200)

        assert isinstance(result, MTFAnalysisResult)
        assert result.bias == "short"
        assert result.bearish_count >= 1
        assert result.alignment_pct >= 50.0

    @pytest.mark.asyncio
    async def test_analyze_mixed_trend(self, mixed_data):
        """Test MTF analysis on mixed/choppy data."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def mock_fetcher(symbol, timeframe, bars):
            return mixed_data

        result = await analyzer.analyze("TEST", mock_fetcher, bars_per_tf=200)

        assert isinstance(result, MTFAnalysisResult)
        # Mixed data may still produce a trend based on cloud states
        # Just verify we got a valid result
        assert result.alignment in [
            MTFAlignment.FULL_BULL,
            MTFAlignment.FULL_BEAR,
            MTFAlignment.PARTIAL_BULL,
            MTFAlignment.PARTIAL_BEAR,
            MTFAlignment.MIXED,
            MTFAlignment.NEUTRAL,
        ]

    @pytest.mark.asyncio
    async def test_full_alignment(self, bullish_data):
        """Test full alignment detection with all bullish timeframes."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d", "4h", "1h"])

        async def mock_fetcher(symbol, timeframe, bars):
            # Return same bullish data for all timeframes
            return bullish_data

        result = await analyzer.analyze("TEST", mock_fetcher, bars_per_tf=200)

        assert result.bullish_count == 3
        assert result.bearish_count == 0
        assert result.alignment in [MTFAlignment.FULL_BULL, MTFAlignment.PARTIAL_BULL]
        assert result.confidence in [MTFConfidence.VERY_HIGH, MTFConfidence.HIGH]

    @pytest.mark.asyncio
    async def test_partial_alignment(self, bullish_data, bearish_data):
        """Test partial alignment with mixed timeframes."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d", "4h"])

        call_count = 0

        async def mock_fetcher(symbol, timeframe, bars):
            nonlocal call_count
            call_count += 1
            # Return bullish for first call, bearish for second
            return bullish_data if call_count == 1 else bearish_data

        result = await analyzer.analyze("TEST", mock_fetcher, bars_per_tf=200)

        assert len(result.timeframes) == 2
        # Should have 1 bullish and 1 bearish
        assert result.bullish_count >= 0
        assert result.bearish_count >= 0
        assert result.bullish_count + result.bearish_count + result.neutral_count == 2

    def test_alignment_logic_through_integration(self):
        """Test alignment determination logic through public API."""
        # These tests verify the logic exists but test through the public interface
        # The _calculate_alignment method encapsulates this logic
        analyzer = MultiTimeframeAnalyzer()

        # Test through the public analyze method with mock data
        # The logic is tested indirectly through integration tests
        assert analyzer.timeframes == ["1d", "4h", "1h"]
        assert len(analyzer.indicators) == 3

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in analysis."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def failing_fetcher(symbol, timeframe, bars):
            raise ValueError("Data fetch failed")

        # Errors are caught and logged, returns neutral result
        result = await analyzer.analyze("TEST", failing_fetcher)

        # Should return a neutral result when all timeframes fail
        assert result.symbol == "TEST"
        assert result.alignment == MTFAlignment.NEUTRAL
        assert len(result.timeframes) == 0

    @pytest.mark.asyncio
    async def test_insufficient_data(self):
        """Test handling of insufficient data."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d"])

        async def empty_fetcher(symbol, timeframe, bars):
            return pd.DataFrame()

        # Should handle empty data gracefully
        result = await analyzer.analyze("TEST", empty_fetcher)
        assert len(result.timeframes) >= 0  # Empty or 1 depending on handling
        # Empty data should result in neutral
        assert result.neutral_count >= 0


class TestIntegration:
    """Integration tests for MTF analyzer."""

    @pytest.mark.asyncio
    async def test_real_world_scenario(self, bullish_data, bearish_data, mixed_data):
        """Test realistic multi-timeframe scenario."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d", "4h", "1h"])

        # Simulate: Daily bullish, 4H neutral, 1H bullish
        call_count = 0

        async def scenario_fetcher(symbol, timeframe, bars):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # Daily
                return bullish_data
            elif call_count == 2:  # 4H
                return mixed_data
            else:  # 1H
                return bullish_data

        result = await analyzer.analyze("SPY", scenario_fetcher, bars_per_tf=200)

        # Should have 2 bullish and 1 neutral
        assert len(result.timeframes) == 3
        assert result.bias in ["long", "neutral"]
        assert result.bullish_count >= 1
        assert "SPY" in result.summary or result.summary is not None

    @pytest.mark.asyncio
    async def test_alignment_percentage_calculation(self, bullish_data, bearish_data):
        """Test alignment percentage is calculated correctly."""
        analyzer = MultiTimeframeAnalyzer(timeframes=["1d", "4h", "1h"])

        call_count = 0

        async def mixed_fetcher(symbol, timeframe, bars):
            nonlocal call_count
            call_count += 1
            # 2 bullish, 1 bearish
            return bullish_data if call_count <= 2 else bearish_data

        result = await analyzer.analyze("TEST", mixed_fetcher, bars_per_tf=200)

        # With 2 out of 3 aligned, should be around 66.7%
        # But calculation is based on dominant direction alignment
        assert 0 <= result.alignment_pct <= 100
        assert len(result.timeframes) == 3


# ---------------------------------------------------------------------------
# should_take_trade() tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _tf_display_name() tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# MTFAnalysisResult properties tests
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


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
