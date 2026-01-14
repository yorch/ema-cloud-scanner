"""
Data Provider Interface and Implementations

Supports multiple data sources with easy extensibility:
- Yahoo Finance (default, free)
- Alpaca (real-time with API key)
- Polygon.io (real-time with API key)

Each provider must implement the BaseDataProvider interface.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class APICallTracker:
    """Track API calls and calculate comprehensive statistics."""

    def __init__(self):
        self._total_calls: int = 0
        self._failed_calls: int = 0
        self._call_timestamps: list[float] = []
        self._window_seconds: int = 60  # Track calls within last minute
        self._last_call_time: float | None = None
        self._start_time: float = self._get_time()
        self._cache_hits: int = 0
        self._cache_attempts: int = 0

    def _get_time(self) -> float:
        """Get current time (mockable for testing)."""
        import time

        return time.time()

    def record_call(self, failed: bool = False) -> None:
        """Record an API call."""
        current_time = self._get_time()
        self._total_calls += 1
        if failed:
            self._failed_calls += 1
        self._call_timestamps.append(current_time)
        self._last_call_time = current_time
        # Clean old timestamps outside the window
        cutoff = current_time - self._window_seconds
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]

    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self._cache_attempts += 1
        self._cache_hits += 1

    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self._cache_attempts += 1

    @property
    def total_calls(self) -> int:
        """Total number of API calls made."""
        return self._total_calls

    @property
    def failed_calls(self) -> int:
        """Total number of failed API calls."""
        return self._failed_calls

    @property
    def success_rate(self) -> float:
        """Success rate as percentage (0-100)."""
        if self._total_calls == 0:
            return 100.0
        return ((self._total_calls - self._failed_calls) / self._total_calls) * 100

    @property
    def calls_per_minute(self) -> float:
        """Calculate calls per minute based on recent activity."""
        if not self._call_timestamps:
            return 0.0
        current_time = self._get_time()
        cutoff = current_time - self._window_seconds
        recent_calls = [t for t in self._call_timestamps if t > cutoff]
        return len(recent_calls)

    @property
    def last_call_seconds_ago(self) -> float | None:
        """Seconds since last API call."""
        if self._last_call_time is None:
            return None
        return self._get_time() - self._last_call_time

    @property
    def uptime_seconds(self) -> float:
        """Total uptime in seconds since tracker creation."""
        return self._get_time() - self._start_time

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate as percentage (0-100)."""
        if self._cache_attempts == 0:
            return 0.0
        return (self._cache_hits / self._cache_attempts) * 100

    @property
    def cache_hits(self) -> int:
        """Total cache hits."""
        return self._cache_hits

    @property
    def cache_misses(self) -> int:
        """Total cache misses."""
        return self._cache_attempts - self._cache_hits

    def get_stats(self) -> dict:
        """
        Get comprehensive statistics.

        Returns:
            dict with keys:
                - total_calls: int
                - failed_calls: int
                - success_rate: float (percentage)
                - calls_per_minute: float
                - last_call_seconds_ago: float | None
                - uptime_seconds: float
                - cache_hits: int
                - cache_misses: int
                - cache_hit_rate: float (percentage)
        """
        return {
            "total_calls": self.total_calls,
            "failed_calls": self.failed_calls,
            "success_rate": self.success_rate,
            "calls_per_minute": self.calls_per_minute,
            "last_call_seconds_ago": self.last_call_seconds_ago,
            "uptime_seconds": self.uptime_seconds,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate,
        }

    def reset(self) -> None:
        """Reset the tracker."""
        self._total_calls = 0
        self._failed_calls = 0
        self._call_timestamps = []
        self._last_call_time = None
        self._start_time = self._get_time()
        self._cache_hits = 0
        self._cache_attempts = 0


# Global API call tracker instance
api_call_tracker = APICallTracker()


# Interval to minutes mapping for time range calculations
INTERVAL_MINUTES = {
    "1m": 1,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1wk": 10080,
    "1mo": 43200,
}


class OHLCV(BaseModel):
    """Standard OHLCV data structure"""

    timestamp: datetime = Field(..., description="Bar timestamp")
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="Highest price")
    low: float = Field(..., description="Lowest price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Trading volume")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for compatibility"""
        return self.model_dump()


class Quote(BaseModel):
    """Real-time quote data"""

    symbol: str = Field(..., description="Stock/ETF symbol")
    bid: float = Field(..., description="Bid price")
    ask: float = Field(..., description="Ask price")
    last: float = Field(..., description="Last trade price")
    volume: float = Field(..., description="Trade volume")
    timestamp: datetime = Field(..., description="Quote timestamp")


class DataProviderError(Exception):
    """Base exception for data provider errors"""

    pass


class RateLimitError(DataProviderError):
    """Rate limit exceeded"""

    pass


class InvalidSymbolError(DataProviderError):
    """Invalid or unknown symbol"""

    pass


class BaseDataProvider(ABC):
    """
    Abstract base class for data providers.
    All data providers must implement these methods.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._rate_limit_delay = self.config.get("rate_limit_delay", 0.1)
        self._last_request_time = 0

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name"""
        pass

    @property
    @abstractmethod
    def supports_realtime(self) -> bool:
        """Whether provider supports real-time data"""
        pass

    @abstractmethod
    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        bars: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data.

        Args:
            symbol: Stock/ETF symbol
            interval: Time interval (1m, 5m, 10m, 15m, 30m, 1h, 4h, 1d, 1wk, 1mo)
            start: Start datetime
            end: End datetime
            bars: Number of bars to fetch

        Returns:
            DataFrame with columns: open, high, low, close, volume, indexed by datetime
        """
        pass

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote for a symbol"""
        pass

    @abstractmethod
    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get real-time quotes for multiple symbols"""
        pass

    async def _rate_limit(self):
        """Apply rate limiting between requests and track API calls."""
        current_time = asyncio.get_event_loop().time()
        elapsed = current_time - self._last_request_time
        if elapsed < self._rate_limit_delay:
            await asyncio.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()
        # Track the API call
        api_call_tracker.record_call()

    def _validate_interval(self, interval: str) -> str:
        """Validate and normalize interval string"""
        valid_intervals = {
            "1m": "1m",
            "1min": "1m",
            "5m": "5m",
            "5min": "5m",
            "10m": "10m",
            "10min": "10m",
            "15m": "15m",
            "15min": "15m",
            "30m": "30m",
            "30min": "30m",
            "1h": "1h",
            "60m": "1h",
            "1hour": "1h",
            "4h": "4h",
            "240m": "4h",
            "1d": "1d",
            "daily": "1d",
            "d": "1d",
            "1wk": "1wk",
            "weekly": "1wk",
            "w": "1wk",
            "1mo": "1mo",
            "monthly": "1mo",
            "m": "1mo",
        }
        normalized = valid_intervals.get(interval.lower())
        if not normalized:
            raise ValueError(f"Invalid interval: {interval}")
        return normalized


class YahooFinanceProvider(BaseDataProvider):
    """
    Yahoo Finance data provider using yfinance library.
    Free, no API key required, but rate limited.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self._yf = None

    @property
    def name(self) -> str:
        return "Yahoo Finance"

    @property
    def supports_realtime(self) -> bool:
        return False  # Yahoo provides delayed quotes

    def _get_yf(self):
        """Lazy load yfinance"""
        if self._yf is None:
            import yfinance as yf

            self._yf = yf
        return self._yf

    def _convert_interval(self, interval: str) -> str:
        """Convert normalized interval to yfinance format"""
        mapping = {
            "1m": "1m",
            "5m": "5m",
            "10m": "15m",  # yfinance doesn't support 10m, use 15m
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "4h": "1h",  # Will resample
            "1d": "1d",
            "1wk": "1wk",
            "1mo": "1mo",
        }
        return mapping.get(interval, "1d")

    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        bars: int = 500,
    ) -> pd.DataFrame:
        """Fetch historical data from Yahoo Finance"""
        await self._rate_limit()

        interval = self._validate_interval(interval)
        yf_interval = self._convert_interval(interval)

        yf = self._get_yf()
        ticker = yf.Ticker(symbol)

        # Calculate period based on interval and bars
        period_map = {
            "1m": "7d",  # Max 7 days for 1m data
            "5m": "60d",
            "15m": "60d",
            "30m": "60d",
            "1h": "730d",
            "1d": "max",
            "1wk": "max",
            "1mo": "max",
        }

        try:
            if start and end:
                df = ticker.history(start=start, end=end, interval=yf_interval)
            else:
                period = period_map.get(yf_interval, "1y")
                df = ticker.history(period=period, interval=yf_interval)

            if df.empty:
                raise InvalidSymbolError(f"No data found for {symbol}")

            # Standardize column names
            df.columns = [c.lower() for c in df.columns]
            df = df[["open", "high", "low", "close", "volume"]].copy()

            # Resample if needed (for 10m and 4h)
            if interval == "10m" and yf_interval == "15m":
                # Keep 15m data as is (closest available)
                pass
            elif interval == "4h" and yf_interval == "1h":
                df = (
                    df.resample("4h")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                )

            # Limit to requested number of bars
            if len(df) > bars:
                df = df.tail(bars)

            return df

        except Exception as e:
            logger.error(f"Error fetching {symbol} from Yahoo Finance: {e}")
            raise DataProviderError(f"Failed to fetch data for {symbol}: {e}")

    async def get_quote(self, symbol: str) -> Quote:
        """Get current quote from Yahoo Finance"""
        await self._rate_limit()

        yf = self._get_yf()
        ticker = yf.Ticker(symbol)

        try:
            info = ticker.info
            fast_info = ticker.fast_info

            return Quote(
                symbol=symbol,
                bid=info.get("bid", fast_info.get("lastPrice", 0)),
                ask=info.get("ask", fast_info.get("lastPrice", 0)),
                last=fast_info.get("lastPrice", info.get("regularMarketPrice", 0)),
                volume=fast_info.get("lastVolume", info.get("volume", 0)),
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            raise DataProviderError(f"Failed to get quote for {symbol}: {e}")

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols (parallel fetching)"""

        async def fetch_quote(symbol: str) -> tuple[str, Quote | None]:
            try:
                return symbol, await self.get_quote(symbol)
            except Exception as e:
                logger.warning(f"Failed to get quote for {symbol}: {e}")
                return symbol, None

        results = await asyncio.gather(*[fetch_quote(s) for s in symbols])
        return {symbol: quote for symbol, quote in results if quote is not None}


class AlpacaProvider(BaseDataProvider):
    """
    Alpaca data provider for real-time market data.
    Requires API key and secret.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = config.get("api_key") if config else None
        self.secret_key = config.get("secret_key") if config else None
        self.paper = config.get("paper", True) if config else True
        self._client = None

    @property
    def name(self) -> str:
        return "Alpaca"

    @property
    def supports_realtime(self) -> bool:
        return True

    def _get_client(self):
        """Lazy load Alpaca client"""
        if self._client is None:
            if not self.api_key or not self.secret_key:
                raise DataProviderError("Alpaca API key and secret required")

            from alpaca.data.historical import StockHistoricalDataClient

            self._client = StockHistoricalDataClient(self.api_key, self.secret_key)
        return self._client

    def _convert_interval(self, interval: str) -> str:
        """Convert to Alpaca timeframe"""
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

        mapping = {
            "1m": TimeFrame.Minute,
            "5m": TimeFrame(5, TimeFrameUnit.Minute),
            "10m": TimeFrame(10, TimeFrameUnit.Minute),
            "15m": TimeFrame(15, TimeFrameUnit.Minute),
            "30m": TimeFrame(30, TimeFrameUnit.Minute),
            "1h": TimeFrame.Hour,
            "4h": TimeFrame(4, TimeFrameUnit.Hour),
            "1d": TimeFrame.Day,
            "1wk": TimeFrame.Week,
            "1mo": TimeFrame.Month,
        }
        return mapping.get(interval, TimeFrame.Day)

    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        bars: int = 500,
    ) -> pd.DataFrame:
        """Fetch historical data from Alpaca"""
        await self._rate_limit()

        interval = self._validate_interval(interval)

        try:
            from alpaca.data.requests import StockBarsRequest

            client = self._get_client()
            timeframe = self._convert_interval(interval)

            # Default time range if not specified
            if end is None:
                end = datetime.now()
            if start is None:
                # Estimate start based on bars and interval
                minutes = INTERVAL_MINUTES.get(interval, 1440)
                start = end - timedelta(minutes=minutes * bars * 1.5)

            request = StockBarsRequest(
                symbol_or_symbols=symbol, timeframe=timeframe, start=start, end=end, limit=bars
            )

            bars_data = client.get_stock_bars(request)
            df = bars_data.df

            if df.empty:
                raise InvalidSymbolError(f"No data found for {symbol}")

            # Reset multi-index if present
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index(level=0, drop=True)

            df.columns = [c.lower() for c in df.columns]
            return df[["open", "high", "low", "close", "volume"]]

        except ImportError:
            raise DataProviderError("alpaca-py package not installed. Run: pip install alpaca-py")
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Alpaca: {e}")
            raise DataProviderError(f"Failed to fetch data for {symbol}: {e}")

    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote from Alpaca"""
        await self._rate_limit()

        try:
            from alpaca.data.requests import StockLatestQuoteRequest

            client = self._get_client()
            request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            quotes = client.get_stock_latest_quote(request)

            quote_data = quotes[symbol]
            return Quote(
                symbol=symbol,
                bid=quote_data.bid_price,
                ask=quote_data.ask_price,
                last=(quote_data.bid_price + quote_data.ask_price) / 2,
                volume=0,  # Alpaca quote doesn't include volume
                timestamp=quote_data.timestamp,
            )
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            raise DataProviderError(f"Failed to get quote for {symbol}: {e}")

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols from Alpaca"""
        await self._rate_limit()

        try:
            from alpaca.data.requests import StockLatestQuoteRequest

            client = self._get_client()
            request = StockLatestQuoteRequest(symbol_or_symbols=symbols)
            quotes_data = client.get_stock_latest_quote(request)

            quotes = {}
            for symbol, quote_data in quotes_data.items():
                quotes[symbol] = Quote(
                    symbol=symbol,
                    bid=quote_data.bid_price,
                    ask=quote_data.ask_price,
                    last=(quote_data.bid_price + quote_data.ask_price) / 2,
                    volume=0,
                    timestamp=quote_data.timestamp,
                )
            return quotes
        except Exception as e:
            logger.error(f"Error getting quotes: {e}")
            raise DataProviderError(f"Failed to get quotes: {e}")


class PolygonProvider(BaseDataProvider):
    """
    Polygon.io data provider for real-time market data.
    Requires API key.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        self.api_key = config.get("api_key") if config else None
        self._client = None

    @property
    def name(self) -> str:
        return "Polygon.io"

    @property
    def supports_realtime(self) -> bool:
        return True

    def _get_client(self):
        """Lazy load Polygon client"""
        if self._client is None:
            if not self.api_key:
                raise DataProviderError("Polygon API key required")

            from polygon import RESTClient

            self._client = RESTClient(self.api_key)
        return self._client

    def _convert_interval(self, interval: str) -> tuple:
        """Convert to Polygon multiplier and timespan"""
        mapping = {
            "1m": (1, "minute"),
            "5m": (5, "minute"),
            "10m": (10, "minute"),
            "15m": (15, "minute"),
            "30m": (30, "minute"),
            "1h": (1, "hour"),
            "4h": (4, "hour"),
            "1d": (1, "day"),
            "1wk": (1, "week"),
            "1mo": (1, "month"),
        }
        return mapping.get(interval, (1, "day"))

    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        bars: int = 500,
    ) -> pd.DataFrame:
        """Fetch historical data from Polygon"""
        await self._rate_limit()

        interval = self._validate_interval(interval)
        multiplier, timespan = self._convert_interval(interval)

        try:
            client = self._get_client()

            if end is None:
                end = datetime.now()
            if start is None:
                # Estimate start based on bars and interval
                minutes = INTERVAL_MINUTES.get(interval, 1440)
                start = end - timedelta(minutes=minutes * bars * 1.5)

            aggs = client.get_aggs(
                ticker=symbol,
                multiplier=multiplier,
                timespan=timespan,
                from_=start.strftime("%Y-%m-%d"),
                to=end.strftime("%Y-%m-%d"),
                limit=bars,
            )

            if not aggs:
                raise InvalidSymbolError(f"No data found for {symbol}")

            data = []
            for bar in aggs:
                data.append(
                    {
                        "timestamp": pd.to_datetime(bar.timestamp, unit="ms"),
                        "open": bar.open,
                        "high": bar.high,
                        "low": bar.low,
                        "close": bar.close,
                        "volume": bar.volume,
                    }
                )

            df = pd.DataFrame(data)
            df.set_index("timestamp", inplace=True)
            return df

        except ImportError:
            raise DataProviderError(
                "polygon-api-client package not installed. Run: pip install polygon-api-client"
            )
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Polygon: {e}")
            raise DataProviderError(f"Failed to fetch data for {symbol}: {e}")

    async def get_quote(self, symbol: str) -> Quote:
        """Get real-time quote from Polygon"""
        await self._rate_limit()

        try:
            client = self._get_client()
            quote = client.get_last_quote(symbol)

            return Quote(
                symbol=symbol,
                bid=quote.bid_price if hasattr(quote, "bid_price") else 0,
                ask=quote.ask_price if hasattr(quote, "ask_price") else 0,
                last=quote.last_price if hasattr(quote, "last_price") else 0,
                volume=0,
                timestamp=datetime.now(),
            )
        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            raise DataProviderError(f"Failed to get quote for {symbol}: {e}")

    async def get_quotes(self, symbols: list[str]) -> dict[str, Quote]:
        """Get quotes for multiple symbols (parallel fetching)"""

        async def fetch_quote(symbol: str) -> tuple[str, Quote | None]:
            try:
                return symbol, await self.get_quote(symbol)
            except Exception as e:
                logger.warning(f"Failed to get quote for {symbol}: {e}")
                return symbol, None

        results = await asyncio.gather(*[fetch_quote(s) for s in symbols])
        return {symbol: quote for symbol, quote in results if quote is not None}


class DataProviderManager:
    """
    Manager class for handling multiple data providers.
    Provides fallback and load balancing capabilities.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.providers: dict[str, BaseDataProvider] = {}
        self.primary_provider: BaseDataProvider | None = None
        self._initialize_providers()

    def _initialize_providers(self):
        """Initialize configured data providers"""
        # Always add Yahoo Finance as fallback
        self.providers["yahoo"] = YahooFinanceProvider(self.config.get("yahoo", {}))

        # Add Alpaca if configured
        alpaca_config = self.config.get("alpaca", {})
        if alpaca_config.get("enabled") and alpaca_config.get("api_key"):
            self.providers["alpaca"] = AlpacaProvider(alpaca_config)

        # Add Polygon if configured
        polygon_config = self.config.get("polygon", {})
        if polygon_config.get("enabled") and polygon_config.get("api_key"):
            self.providers["polygon"] = PolygonProvider(polygon_config)

        # Set primary provider (prefer real-time capable)
        for name in ["alpaca", "polygon", "yahoo"]:
            if name in self.providers:
                self.primary_provider = self.providers[name]
                break

    def add_provider(self, name: str, provider: BaseDataProvider):
        """Add a custom data provider"""
        self.providers[name] = provider

    def get_provider(self, name: str) -> BaseDataProvider | None:
        """Get a specific provider by name"""
        return self.providers.get(name)

    async def get_historical_data(
        self,
        symbol: str,
        interval: str,
        start: datetime | None = None,
        end: datetime | None = None,
        bars: int = 500,
        provider: str | None = None,
    ) -> pd.DataFrame:
        """
        Get historical data with automatic fallback.

        Args:
            symbol: Stock symbol
            interval: Time interval
            start: Start datetime
            end: End datetime
            bars: Number of bars
            provider: Specific provider to use (optional)
        """
        providers_to_try = []

        if provider and provider in self.providers:
            providers_to_try = [self.providers[provider]]
        else:
            providers_to_try = list(self.providers.values())

        last_error = None
        for prov in providers_to_try:
            try:
                return await prov.get_historical_data(symbol, interval, start, end, bars)
            except Exception as e:
                last_error = e
                logger.warning(f"Provider {prov.name} failed for {symbol}: {e}")
                continue

        raise DataProviderError(f"All providers failed for {symbol}: {last_error}")

    async def get_quotes(self, symbols: list[str], provider: str | None = None) -> dict[str, Quote]:
        """Get quotes with automatic fallback"""
        providers_to_try = []

        if provider and provider in self.providers:
            providers_to_try = [self.providers[provider]]
        else:
            # Prefer real-time providers
            for name in ["alpaca", "polygon", "yahoo"]:
                if name in self.providers:
                    providers_to_try.append(self.providers[name])

        for prov in providers_to_try:
            try:
                return await prov.get_quotes(symbols)
            except Exception as e:
                logger.warning(f"Provider {prov.name} failed for quotes: {e}")
                continue

        raise DataProviderError("All providers failed for quotes")
