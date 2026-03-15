"""
Unit tests for data providers module.

Covers APICallTracker, BaseDataProvider interval validation,
YahooFinanceProvider, DataProviderManager fallback/retry logic,
and provider initialization.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from ema_cloud_lib.data_providers.base import (
    AlpacaProvider,
    APICallTracker,
    BaseDataProvider,
    DataProviderError,
    DataProviderManager,
    InvalidSymbolError,
    PolygonProvider,
    Quote,
    RateLimitError,
    YahooFinanceProvider,
)


def _make_ohlcv_df(n: int = 50) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame for testing."""
    import numpy as np

    rng = np.random.default_rng(42)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    close = 100.0 + rng.normal(0, 0.5, n).cumsum()
    return pd.DataFrame(
        {
            "Open": close + 0.1,
            "High": close + 0.5,
            "Low": close - 0.5,
            "Close": close,
            "Volume": rng.integers(100000, 1000000, n).astype(float),
        },
        index=dates,
    )


class ConcreteProvider(BaseDataProvider):
    """Concrete implementation of BaseDataProvider for testing base class logic."""

    @property
    def name(self) -> str:
        return "Test"

    @property
    def supports_realtime(self) -> bool:
        return False

    async def get_historical_data(self, symbol, interval, start=None, end=None, bars=500):
        return pd.DataFrame()

    async def get_quote(self, symbol):
        return Quote(
            symbol=symbol,
            bid=100.0,
            ask=100.1,
            last=100.05,
            volume=1000.0,
            timestamp=datetime.now(UTC),
        )

    async def get_quotes(self, symbols):
        return {}


class TestAPICallTracker:
    def test_initial_state(self):
        tracker = APICallTracker()
        assert tracker.total_calls == 0
        assert tracker.failed_calls == 0
        assert tracker.success_rate == 100.0
        assert tracker.calls_per_minute == 0.0
        assert tracker.last_call_seconds_ago is None
        assert tracker.cache_hits == 0
        assert tracker.cache_misses == 0
        assert tracker.cache_hit_rate == 0.0

    def test_record_successful_call(self):
        tracker = APICallTracker()
        tracker.record_call(failed=False)
        assert tracker.total_calls == 1
        assert tracker.failed_calls == 0
        assert tracker.success_rate == 100.0

    def test_record_failed_call(self):
        tracker = APICallTracker()
        tracker.record_call(failed=True)
        assert tracker.total_calls == 1
        assert tracker.failed_calls == 1
        assert tracker.success_rate == 0.0

    def test_success_rate_mixed(self):
        tracker = APICallTracker()
        tracker.record_call(failed=False)
        tracker.record_call(failed=False)
        tracker.record_call(failed=True)
        assert tracker.success_rate == pytest.approx(66.67, abs=0.01)

    def test_record_cache_hit(self):
        tracker = APICallTracker()
        tracker.record_cache_hit()
        assert tracker.cache_hits == 1
        assert tracker.cache_misses == 0
        assert tracker.cache_hit_rate == 100.0

    def test_record_cache_miss(self):
        tracker = APICallTracker()
        tracker.record_cache_miss()
        assert tracker.cache_hits == 0
        assert tracker.cache_misses == 1
        assert tracker.cache_hit_rate == 0.0

    def test_cache_hit_rate_mixed(self):
        tracker = APICallTracker()
        tracker.record_cache_hit()
        tracker.record_cache_miss()
        assert tracker.cache_hit_rate == 50.0

    def test_calls_per_minute(self):
        tracker = APICallTracker()
        tracker.record_call()
        tracker.record_call()
        # Both calls within the last 60 seconds
        assert tracker.calls_per_minute == 2

    def test_last_call_seconds_ago(self):
        tracker = APICallTracker()
        tracker.record_call()
        assert tracker.last_call_seconds_ago is not None
        assert tracker.last_call_seconds_ago < 1.0

    def test_uptime_seconds(self):
        tracker = APICallTracker()
        assert tracker.uptime_seconds >= 0

    def test_get_stats_returns_all_fields(self):
        tracker = APICallTracker()
        tracker.record_call()
        tracker.record_cache_hit()
        stats = tracker.get_stats()
        expected_keys = {
            "total_calls",
            "failed_calls",
            "success_rate",
            "calls_per_minute",
            "last_call_seconds_ago",
            "uptime_seconds",
            "cache_hits",
            "cache_misses",
            "cache_hit_rate",
        }
        assert set(stats.keys()) == expected_keys

    def test_reset(self):
        tracker = APICallTracker()
        tracker.record_call()
        tracker.record_call(failed=True)
        tracker.record_cache_hit()
        tracker.reset()
        assert tracker.total_calls == 0
        assert tracker.failed_calls == 0
        assert tracker.cache_hits == 0
        assert tracker.last_call_seconds_ago is None


class TestValidateInterval:
    def test_standard_intervals(self):
        provider = ConcreteProvider()
        assert provider._validate_interval("1m") == "1m"
        assert provider._validate_interval("5m") == "5m"
        assert provider._validate_interval("10m") == "10m"
        assert provider._validate_interval("15m") == "15m"
        assert provider._validate_interval("30m") == "30m"
        assert provider._validate_interval("1h") == "1h"
        assert provider._validate_interval("4h") == "4h"
        assert provider._validate_interval("1d") == "1d"
        assert provider._validate_interval("1wk") == "1wk"
        assert provider._validate_interval("1mo") == "1mo"

    def test_aliases(self):
        provider = ConcreteProvider()
        assert provider._validate_interval("1min") == "1m"
        assert provider._validate_interval("5min") == "5m"
        assert provider._validate_interval("60m") == "1h"
        assert provider._validate_interval("1hour") == "1h"
        assert provider._validate_interval("240m") == "4h"
        assert provider._validate_interval("daily") == "1d"
        assert provider._validate_interval("d") == "1d"
        assert provider._validate_interval("weekly") == "1wk"
        assert provider._validate_interval("w") == "1wk"
        assert provider._validate_interval("monthly") == "1mo"
        assert provider._validate_interval("m") == "1mo"

    def test_case_insensitive(self):
        provider = ConcreteProvider()
        assert provider._validate_interval("1D") == "1d"
        assert provider._validate_interval("DAILY") == "1d"

    def test_invalid_interval_raises(self):
        provider = ConcreteProvider()
        with pytest.raises(ValueError, match="Invalid interval"):
            provider._validate_interval("invalid")
        with pytest.raises(ValueError, match="Invalid interval"):
            provider._validate_interval("")


class TestYahooFinanceProvider:
    def test_name_and_realtime(self):
        provider = YahooFinanceProvider()
        assert provider.name == "Yahoo Finance"
        assert provider.supports_realtime is False

    def test_convert_interval(self):
        provider = YahooFinanceProvider()
        assert provider._convert_interval("1d") == "1d"
        assert provider._convert_interval("10m") == "15m"  # No 10m in yfinance
        assert provider._convert_interval("4h") == "1h"  # Will resample

    def test_convert_interval_unknown_defaults_to_1d(self):
        provider = YahooFinanceProvider()
        assert provider._convert_interval("unknown") == "1d"

    @pytest.mark.asyncio
    async def test_get_historical_data_success(self):
        """Test successful data fetch with mocked yfinance."""
        provider = YahooFinanceProvider()
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_ohlcv_df(50)
        mock_yf.Ticker.return_value = mock_ticker
        provider._yf = mock_yf

        # Mock rate limiting
        with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
            df = await provider.get_historical_data("XLK", "1d")

        assert not df.empty
        assert list(df.columns) == ["open", "high", "low", "close", "volume"]

    @pytest.mark.asyncio
    async def test_get_historical_data_empty_raises_invalid_symbol(self):
        """Empty result raises InvalidSymbolError."""
        provider = YahooFinanceProvider()
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = pd.DataFrame()
        mock_yf.Ticker.return_value = mock_ticker
        provider._yf = mock_yf

        with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
            with pytest.raises(InvalidSymbolError, match="No data found"):
                await provider.get_historical_data("INVALID", "1d")

    @pytest.mark.asyncio
    async def test_get_historical_data_limits_bars(self):
        """Result is limited to requested number of bars."""
        provider = YahooFinanceProvider()
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.history.return_value = _make_ohlcv_df(100)
        mock_yf.Ticker.return_value = mock_ticker
        provider._yf = mock_yf

        with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
            df = await provider.get_historical_data("XLK", "1d", bars=20)

        assert len(df) == 20

    @pytest.mark.asyncio
    async def test_get_quote_success(self):
        """Test successful quote fetch."""
        provider = YahooFinanceProvider()
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.info = {"bid": 150.0, "ask": 150.1}
        mock_ticker.fast_info = {"lastPrice": 150.05, "lastVolume": 50000}
        mock_yf.Ticker.return_value = mock_ticker
        provider._yf = mock_yf

        with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
            quote = await provider.get_quote("XLK")

        assert quote.symbol == "XLK"
        assert quote.bid == 150.0
        assert quote.ask == 150.1

    @pytest.mark.asyncio
    async def test_get_quotes_parallel(self):
        """get_quotes fetches multiple symbols."""
        provider = YahooFinanceProvider()
        mock_yf = MagicMock()
        mock_ticker = MagicMock()
        mock_ticker.info = {"bid": 100.0, "ask": 100.1}
        mock_ticker.fast_info = {"lastPrice": 100.0, "lastVolume": 10000}
        mock_yf.Ticker.return_value = mock_ticker
        provider._yf = mock_yf

        with patch.object(provider, "_rate_limit", new_callable=AsyncMock):
            quotes = await provider.get_quotes(["XLK", "XLF"])

        assert "XLK" in quotes
        assert "XLF" in quotes

    @pytest.mark.asyncio
    async def test_get_quotes_partial_failure(self):
        """get_quotes skips failed symbols."""
        provider = YahooFinanceProvider()

        call_count = 0

        async def mock_get_quote(symbol):
            nonlocal call_count
            call_count += 1
            if symbol == "BAD":
                raise DataProviderError("bad symbol")
            return Quote(
                symbol=symbol,
                bid=100.0,
                ask=100.1,
                last=100.05,
                volume=1000.0,
                timestamp=datetime.now(UTC),
            )

        with patch.object(provider, "get_quote", side_effect=mock_get_quote):
            quotes = await provider.get_quotes(["XLK", "BAD", "XLF"])

        assert "XLK" in quotes
        assert "XLF" in quotes
        assert "BAD" not in quotes


class TestAlpacaProvider:
    def test_name_and_realtime(self):
        provider = AlpacaProvider({"api_key": "test", "secret_key": "test"})
        assert provider.name == "Alpaca"
        assert provider.supports_realtime is True

    def test_missing_credentials(self):
        provider = AlpacaProvider()
        with pytest.raises(DataProviderError, match="API key"):
            provider._get_client()


class TestPolygonProvider:
    def test_name_and_realtime(self):
        provider = PolygonProvider({"api_key": "test"})
        assert provider.name == "Polygon.io"
        assert provider.supports_realtime is True

    def test_missing_api_key(self):
        provider = PolygonProvider()
        with pytest.raises(DataProviderError, match="API key"):
            provider._get_client()

    def test_convert_interval(self):
        provider = PolygonProvider({"api_key": "test"})
        assert provider._convert_interval("1m") == (1, "minute")
        assert provider._convert_interval("1d") == (1, "day")
        assert provider._convert_interval("4h") == (4, "hour")
        assert provider._convert_interval("1wk") == (1, "week")
        assert provider._convert_interval("unknown") == (1, "day")


class TestDataProviderManager:
    def test_default_initialization_yahoo_only(self):
        """Manager initializes with Yahoo when no API keys provided."""
        manager = DataProviderManager({"yahoo": {"enabled": True}})
        assert "yahoo" in manager.providers
        assert manager.primary_provider is not None
        assert manager.primary_provider.name == "Yahoo Finance"

    def test_yahoo_always_added(self):
        """Yahoo is always available as fallback."""
        manager = DataProviderManager({})
        assert "yahoo" in manager.providers

    def test_alpaca_added_with_credentials(self):
        """Alpaca added when enabled with API key."""
        manager = DataProviderManager(
            {
                "alpaca": {"enabled": True, "api_key": "key", "secret_key": "secret"},
            }
        )
        assert "alpaca" in manager.providers
        # Alpaca preferred as primary (real-time)
        assert manager.primary_provider.name == "Alpaca"

    def test_polygon_added_with_credentials(self):
        """Polygon added when enabled with API key."""
        manager = DataProviderManager(
            {
                "polygon": {"enabled": True, "api_key": "key"},
            }
        )
        assert "polygon" in manager.providers

    def test_alpaca_not_added_without_key(self):
        """Alpaca not added when enabled but no API key."""
        manager = DataProviderManager(
            {
                "alpaca": {"enabled": True},
            }
        )
        assert "alpaca" not in manager.providers

    def test_provider_priority_order(self):
        """Primary provider follows priority: Alpaca > Polygon > Yahoo."""
        manager = DataProviderManager(
            {
                "alpaca": {"enabled": True, "api_key": "k", "secret_key": "s"},
                "polygon": {"enabled": True, "api_key": "k"},
                "yahoo": {"enabled": True},
            }
        )
        assert manager.primary_provider.name == "Alpaca"

    def test_add_custom_provider(self):
        """add_provider registers custom provider."""
        manager = DataProviderManager({})
        custom = ConcreteProvider()
        manager.add_provider("custom", custom)
        assert manager.get_provider("custom") is custom

    def test_get_provider_returns_none_for_unknown(self):
        manager = DataProviderManager({})
        assert manager.get_provider("nonexistent") is None

    @pytest.mark.asyncio
    async def test_get_historical_data_success(self):
        """Manager returns data from first successful provider."""
        manager = DataProviderManager({})
        mock_provider = MagicMock()
        df = _make_ohlcv_df(50)
        mock_provider.get_historical_data = AsyncMock(return_value=df)
        mock_provider.name = "Mock"
        manager.providers = {"mock": mock_provider}

        result = await manager.get_historical_data("XLK", "1d")
        assert len(result) == 50

    @pytest.mark.asyncio
    async def test_get_historical_data_fallback(self):
        """Manager falls back to next provider on failure."""
        manager = DataProviderManager({}, max_retries=1)

        failing_provider = MagicMock()
        failing_provider.get_historical_data = AsyncMock(side_effect=DataProviderError("fail"))
        failing_provider.name = "Failing"

        success_provider = MagicMock()
        df = _make_ohlcv_df(50)
        success_provider.get_historical_data = AsyncMock(return_value=df)
        success_provider.name = "Success"

        manager.providers = {"failing": failing_provider, "success": success_provider}

        result = await manager.get_historical_data("XLK", "1d")
        assert len(result) == 50
        # Failing provider was tried first
        failing_provider.get_historical_data.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_historical_data_retry_with_backoff(self):
        """Manager retries with exponential backoff before falling back."""
        manager = DataProviderManager({}, max_retries=3, base_delay=0.01)

        failing_provider = MagicMock()
        failing_provider.get_historical_data = AsyncMock(side_effect=DataProviderError("fail"))
        failing_provider.name = "Failing"

        manager.providers = {"failing": failing_provider}

        with pytest.raises(DataProviderError, match="All providers failed"):
            await manager.get_historical_data("XLK", "1d")

        # Should have retried 3 times
        assert failing_provider.get_historical_data.call_count == 3

    @pytest.mark.asyncio
    async def test_get_historical_data_specific_provider(self):
        """Manager uses specific provider when requested."""
        manager = DataProviderManager({})

        yahoo = MagicMock()
        yahoo.get_historical_data = AsyncMock(return_value=_make_ohlcv_df(10))
        yahoo.name = "Yahoo"

        custom = MagicMock()
        custom.get_historical_data = AsyncMock(return_value=_make_ohlcv_df(20))
        custom.name = "Custom"

        manager.providers = {"yahoo": yahoo, "custom": custom}

        result = await manager.get_historical_data("XLK", "1d", provider="custom")
        assert len(result) == 20
        yahoo.get_historical_data.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_historical_data_all_fail(self):
        """Manager raises when all providers fail."""
        manager = DataProviderManager({}, max_retries=1, base_delay=0.01)

        for name in list(manager.providers):
            mock = MagicMock()
            mock.get_historical_data = AsyncMock(side_effect=DataProviderError("fail"))
            mock.name = name
            manager.providers[name] = mock

        with pytest.raises(DataProviderError, match="All providers failed"):
            await manager.get_historical_data("XLK", "1d")

    @pytest.mark.asyncio
    async def test_get_quotes_success(self):
        """Manager returns quotes from first successful provider."""
        manager = DataProviderManager({}, max_retries=1)

        mock_provider = MagicMock()
        mock_provider.get_quotes = AsyncMock(
            return_value={
                "XLK": Quote(
                    symbol="XLK",
                    bid=150.0,
                    ask=150.1,
                    last=150.05,
                    volume=50000.0,
                    timestamp=datetime.now(UTC),
                )
            }
        )
        mock_provider.name = "Mock"
        mock_provider.supports_realtime = True
        # Override providers entirely so fallback order matches
        manager.providers = {"yahoo": mock_provider}

        quotes = await manager.get_quotes(["XLK"])
        assert "XLK" in quotes

    @pytest.mark.asyncio
    async def test_get_quotes_all_fail(self):
        """Manager raises when all providers fail for quotes."""
        manager = DataProviderManager({}, max_retries=1, base_delay=0.01)

        for name in list(manager.providers):
            mock = MagicMock()
            mock.get_quotes = AsyncMock(side_effect=DataProviderError("fail"))
            mock.name = name
            manager.providers[name] = mock

        with pytest.raises(DataProviderError, match="All providers failed"):
            await manager.get_quotes(["XLK"])


class TestExceptions:
    def test_data_provider_error_is_exception(self):
        assert issubclass(DataProviderError, Exception)

    def test_rate_limit_error_is_data_provider_error(self):
        assert issubclass(RateLimitError, DataProviderError)

    def test_invalid_symbol_error_is_data_provider_error(self):
        assert issubclass(InvalidSymbolError, DataProviderError)


class TestIsRateLimit:
    """Unit tests for the _is_rate_limit() heuristic."""

    def setup_method(self):
        from ema_cloud_lib.data_providers.base import _is_rate_limit

        self.fn = _is_rate_limit

    def test_message_contains_429(self):
        assert self.fn(Exception("HTTP 429 Too Many Requests")) is True

    def test_message_contains_too_many_requests_lowercase(self):
        assert self.fn(Exception("too many requests")) is True

    def test_message_contains_rate_limit(self):
        assert self.fn(Exception("rate limit exceeded")) is True

    def test_status_code_attribute_429(self):
        exc = Exception("API error")
        exc.status_code = 429  # type: ignore[attr-defined]
        assert self.fn(exc) is True

    def test_code_attribute_429(self):
        exc = Exception("API error")
        exc.code = 429  # type: ignore[attr-defined]
        assert self.fn(exc) is True

    def test_http_status_attribute_429(self):
        exc = Exception("API error")
        exc.http_status = 429  # type: ignore[attr-defined]
        assert self.fn(exc) is True

    def test_non_rate_limit_500(self):
        assert self.fn(Exception("Internal Server Error 500")) is False

    def test_non_rate_limit_plain(self):
        assert self.fn(ValueError("bad value")) is False

    def test_non_rate_limit_status_code_400(self):
        exc = Exception("Bad Request")
        exc.status_code = 400  # type: ignore[attr-defined]
        assert self.fn(exc) is False


class TestRateLimitHandlingInManager:
    """DataProviderManager should apply a longer backoff for RateLimitError."""

    @pytest.mark.asyncio
    async def test_rate_limit_uses_long_backoff(self):
        """When a provider raises RateLimitError, manager waits >=60 s before retry."""
        manager = DataProviderManager()
        mock_prov = MagicMock()
        mock_prov.name = "mock"
        mock_prov.get_historical_data = AsyncMock(
            side_effect=RateLimitError("rate limit hit")
        )
        manager.providers = {"mock": mock_prov}
        manager.max_retries = 2
        manager.base_delay = 1.0

        sleep_calls = []

        async def fake_sleep(secs):
            sleep_calls.append(secs)

        with patch("ema_cloud_lib.data_providers.base.asyncio.sleep", new=fake_sleep):
            with pytest.raises(DataProviderError):
                await manager.get_historical_data("XLK", "1d")

        # At least one sleep call should be >= 60 s
        assert sleep_calls, "Expected at least one sleep call for rate-limit backoff"
        assert max(sleep_calls) >= 60.0

    @pytest.mark.asyncio
    async def test_transient_error_uses_short_backoff(self):
        """Non-rate-limit errors should use the normal short exponential backoff."""
        manager = DataProviderManager()
        mock_prov = MagicMock()
        mock_prov.name = "mock"
        mock_prov.get_historical_data = AsyncMock(
            side_effect=DataProviderError("transient error")
        )
        manager.providers = {"mock": mock_prov}
        manager.max_retries = 2
        manager.base_delay = 1.0

        sleep_calls = []

        async def fake_sleep(secs):
            sleep_calls.append(secs)

        with patch("ema_cloud_lib.data_providers.base.asyncio.sleep", new=fake_sleep):
            with pytest.raises(DataProviderError):
                await manager.get_historical_data("XLK", "1d")

        # Backoff should be base_delay * 2^0 = 1 s — well below 60 s
        assert sleep_calls
        assert max(sleep_calls) < 60.0
