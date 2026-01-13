"""
ETF Holdings Module

Fetches and manages top holdings for sector ETFs.
Supports multiple data sources and caching.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Holding(BaseModel):
    """Single ETF holding"""

    symbol: str = Field(..., description="Stock symbol")
    name: str = Field(..., description="Company name")
    weight: float = Field(..., description="Percentage weight in ETF")
    shares: int | None = Field(default=None, description="Number of shares held")
    market_value: float | None = Field(default=None, description="Market value of holding")
    sector: str | None = Field(default=None, description="Sector classification")


class ETFHoldings(BaseModel):
    """Holdings data for an ETF"""

    etf_symbol: str = Field(..., description="ETF symbol")
    etf_name: str = Field(..., description="ETF name")
    as_of_date: datetime = Field(..., description="Data as of date")
    total_holdings: int = Field(..., description="Total number of holdings")
    holdings: list[Holding] = Field(..., description="List of holdings")

    def get_top_holdings(self, n: int = 10) -> list[Holding]:
        """Get top N holdings by weight"""
        sorted_holdings = sorted(self.holdings, key=lambda h: h.weight, reverse=True)
        return sorted_holdings[:n]

    def get_symbols(self) -> list[str]:
        """Get list of all holding symbols"""
        return [h.symbol for h in self.holdings]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for compatibility"""
        return self.model_dump()


class HoldingsProvider:
    """Base class for holdings data providers"""

    async def get_holdings(self, etf_symbol: str) -> ETFHoldings | None:
        """Fetch holdings for an ETF"""
        raise NotImplementedError


class YahooHoldingsProvider(HoldingsProvider):
    """Fetch holdings from Yahoo Finance"""

    async def get_holdings(self, etf_symbol: str) -> ETFHoldings | None:
        """Fetch holdings using yfinance"""
        try:
            import yfinance as yf

            ticker = yf.Ticker(etf_symbol)

            # Try to get holdings from the fund's holdings property
            try:
                holdings_df = ticker.get_holdings()
                if holdings_df is not None and not holdings_df.empty:
                    holdings = []
                    for _, row in holdings_df.iterrows():
                        symbol = row.get("Symbol", row.name if isinstance(row.name, str) else "")
                        holdings.append(
                            Holding(
                                symbol=str(symbol),
                                name=str(row.get("Name", row.get("holdingName", ""))),
                                weight=float(
                                    row.get("% Assets", row.get("holdingPercent", 0)) or 0
                                ),
                                shares=int(row.get("Shares", 0) or 0)
                                if row.get("Shares")
                                else None,
                            )
                        )

                    return ETFHoldings(
                        etf_symbol=etf_symbol,
                        etf_name=ticker.info.get("shortName", etf_symbol),
                        as_of_date=datetime.now(),
                        total_holdings=len(holdings),
                        holdings=holdings,
                    )
            except Exception as e:
                logger.debug(f"Could not get holdings via get_holdings(): {e}")

            # Fallback: try institutional holders
            try:
                info = ticker.info
                # Some ETFs have top holdings in info
                if "holdings" in info:
                    holdings = []
                    for h in info["holdings"]:
                        holdings.append(
                            Holding(
                                symbol=h.get("symbol", ""),
                                name=h.get("holdingName", ""),
                                weight=h.get("holdingPercent", 0) * 100,
                            )
                        )

                    return ETFHoldings(
                        etf_symbol=etf_symbol,
                        etf_name=info.get("shortName", etf_symbol),
                        as_of_date=datetime.now(),
                        total_holdings=len(holdings),
                        holdings=holdings,
                    )
            except Exception as e:
                logger.debug(f"Could not get holdings from info: {e}")

            logger.warning(f"No holdings data available for {etf_symbol}")
            return None

        except Exception as e:
            logger.error(f"Error fetching holdings for {etf_symbol}: {e}")
            return None


class StaticHoldingsProvider(HoldingsProvider):
    """
    Provide static holdings data for common sector ETFs.
    Updated periodically - useful as fallback.
    """

    # Static holdings data for sector ETFs (top 10 as of knowledge cutoff)
    STATIC_HOLDINGS = {
        "XLK": [
            Holding(symbol="NVDA", name="NVIDIA Corporation", weight=14.79),
            Holding(symbol="AAPL", name="Apple Inc.", weight=12.59),
            Holding(symbol="MSFT", name="Microsoft Corporation", weight=11.69),
            Holding(symbol="AVGO", name="Broadcom Inc.", weight=5.16),
            Holding(symbol="PLTR", name="Palantir Technologies Inc.", weight=3.47),
            Holding(symbol="AMD", name="Advanced Micro Devices", weight=3.25),
            Holding(symbol="CRM", name="Salesforce Inc.", weight=3.10),
            Holding(symbol="ORCL", name="Oracle Corporation", weight=2.95),
            Holding(symbol="CSCO", name="Cisco Systems Inc.", weight=2.45),
            Holding(symbol="ADBE", name="Adobe Inc.", weight=2.35),
        ],
        "XLF": [
            Holding(symbol="BRK.B", name="Berkshire Hathaway Inc.", weight=11.46),
            Holding(symbol="JPM", name="JPMorgan Chase & Co.", weight=11.22),
            Holding(symbol="V", name="Visa Inc.", weight=7.43),
            Holding(symbol="MA", name="Mastercard Inc.", weight=5.94),
            Holding(symbol="BAC", name="Bank of America Corporation", weight=4.72),
            Holding(symbol="WFC", name="Wells Fargo & Company", weight=3.25),
            Holding(symbol="GS", name="Goldman Sachs Group Inc.", weight=2.85),
            Holding(symbol="SPGI", name="S&P Global Inc.", weight=2.65),
            Holding(symbol="MS", name="Morgan Stanley", weight=2.55),
            Holding(symbol="AXP", name="American Express Company", weight=2.45),
        ],
        "XLV": [
            Holding(symbol="LLY", name="Eli Lilly and Company", weight=11.85),
            Holding(symbol="UNH", name="UnitedHealth Group Inc.", weight=9.25),
            Holding(symbol="JNJ", name="Johnson & Johnson", weight=6.45),
            Holding(symbol="ABBV", name="AbbVie Inc.", weight=5.85),
            Holding(symbol="MRK", name="Merck & Co. Inc.", weight=5.15),
            Holding(symbol="TMO", name="Thermo Fisher Scientific", weight=4.25),
            Holding(symbol="ABT", name="Abbott Laboratories", weight=3.95),
            Holding(symbol="PFE", name="Pfizer Inc.", weight=3.15),
            Holding(symbol="DHR", name="Danaher Corporation", weight=2.85),
            Holding(symbol="AMGN", name="Amgen Inc.", weight=2.75),
        ],
        "XLE": [
            Holding(symbol="XOM", name="Exxon Mobil Corporation", weight=23.15),
            Holding(symbol="CVX", name="Chevron Corporation", weight=16.85),
            Holding(symbol="COP", name="ConocoPhillips", weight=7.25),
            Holding(symbol="EOG", name="EOG Resources Inc.", weight=4.95),
            Holding(symbol="SLB", name="Schlumberger Limited", weight=4.65),
            Holding(symbol="MPC", name="Marathon Petroleum Corp.", weight=4.35),
            Holding(symbol="PSX", name="Phillips 66", weight=3.85),
            Holding(symbol="VLO", name="Valero Energy Corporation", weight=3.55),
            Holding(symbol="WMB", name="Williams Companies Inc.", weight=3.25),
            Holding(symbol="OKE", name="ONEOK Inc.", weight=2.95),
        ],
        "XLY": [
            Holding(symbol="AMZN", name="Amazon.com Inc.", weight=22.45),
            Holding(symbol="TSLA", name="Tesla Inc.", weight=12.85),
            Holding(symbol="HD", name="The Home Depot Inc.", weight=8.45),
            Holding(symbol="MCD", name="McDonald's Corporation", weight=4.25),
            Holding(symbol="LOW", name="Lowe's Companies Inc.", weight=3.85),
            Holding(symbol="BKNG", name="Booking Holdings Inc.", weight=3.55),
            Holding(symbol="SBUX", name="Starbucks Corporation", weight=3.25),
            Holding(symbol="TJX", name="TJX Companies Inc.", weight=2.95),
            Holding(symbol="NKE", name="Nike Inc.", weight=2.65),
            Holding(symbol="CMG", name="Chipotle Mexican Grill", weight=2.35),
        ],
        "XLP": [
            Holding(symbol="PG", name="Procter & Gamble Company", weight=14.85),
            Holding(symbol="COST", name="Costco Wholesale Corp.", weight=12.45),
            Holding(symbol="WMT", name="Walmart Inc.", weight=10.25),
            Holding(symbol="KO", name="Coca-Cola Company", weight=9.15),
            Holding(symbol="PEP", name="PepsiCo Inc.", weight=8.45),
            Holding(symbol="PM", name="Philip Morris Int'l", weight=5.25),
            Holding(symbol="MDLZ", name="Mondelez International", weight=3.95),
            Holding(symbol="MO", name="Altria Group Inc.", weight=3.55),
            Holding(symbol="CL", name="Colgate-Palmolive Company", weight=3.15),
            Holding(symbol="KMB", name="Kimberly-Clark Corp.", weight=2.45),
        ],
        "XLI": [
            Holding(symbol="GE", name="General Electric Company", weight=5.25),
            Holding(symbol="CAT", name="Caterpillar Inc.", weight=4.85),
            Holding(symbol="RTX", name="RTX Corporation", weight=4.55),
            Holding(symbol="HON", name="Honeywell International", weight=4.25),
            Holding(symbol="UNP", name="Union Pacific Corporation", weight=4.05),
            Holding(symbol="BA", name="Boeing Company", weight=3.75),
            Holding(symbol="DE", name="Deere & Company", weight=3.45),
            Holding(symbol="LMT", name="Lockheed Martin Corp.", weight=3.15),
            Holding(symbol="UPS", name="United Parcel Service", weight=2.95),
            Holding(symbol="ADP", name="Automatic Data Processing", weight=2.75),
        ],
        "XLB": [
            Holding(symbol="LIN", name="Linde plc", weight=17.85),
            Holding(symbol="SHW", name="Sherwin-Williams Company", weight=9.45),
            Holding(symbol="FCX", name="Freeport-McMoRan Inc.", weight=7.25),
            Holding(symbol="APD", name="Air Products & Chemicals", weight=6.85),
            Holding(symbol="ECL", name="Ecolab Inc.", weight=5.45),
            Holding(symbol="NEM", name="Newmont Corporation", weight=4.85),
            Holding(symbol="CTVA", name="Corteva Inc.", weight=4.25),
            Holding(symbol="DOW", name="Dow Inc.", weight=3.95),
            Holding(symbol="DD", name="DuPont de Nemours Inc.", weight=3.55),
            Holding(symbol="NUE", name="Nucor Corporation", weight=3.15),
        ],
        "XLU": [
            Holding(symbol="NEE", name="NextEra Energy Inc.", weight=14.25),
            Holding(symbol="SO", name="Southern Company", weight=8.45),
            Holding(symbol="DUK", name="Duke Energy Corporation", weight=7.85),
            Holding(symbol="CEG", name="Constellation Energy", weight=6.55),
            Holding(symbol="SRE", name="Sempra Energy", weight=5.25),
            Holding(symbol="AEP", name="American Electric Power", weight=4.85),
            Holding(symbol="D", name="Dominion Energy Inc.", weight=4.25),
            Holding(symbol="PCG", name="PG&E Corporation", weight=3.95),
            Holding(symbol="EXC", name="Exelon Corporation", weight=3.55),
            Holding(symbol="XEL", name="Xcel Energy Inc.", weight=3.15),
        ],
        "XLRE": [
            Holding(symbol="PLD", name="Prologis Inc.", weight=10.85),
            Holding(symbol="AMT", name="American Tower Corp.", weight=9.45),
            Holding(symbol="EQIX", name="Equinix Inc.", weight=7.85),
            Holding(symbol="WELL", name="Welltower Inc.", weight=5.95),
            Holding(symbol="SPG", name="Simon Property Group", weight=5.25),
            Holding(symbol="PSA", name="Public Storage", weight=4.85),
            Holding(symbol="DLR", name="Digital Realty Trust", weight=4.25),
            Holding(symbol="O", name="Realty Income Corp.", weight=3.95),
            Holding(symbol="CCI", name="Crown Castle Inc.", weight=3.55),
            Holding(symbol="VICI", name="VICI Properties Inc.", weight=3.25),
        ],
        "XLC": [
            Holding(symbol="META", name="Meta Platforms Inc.", weight=22.45),
            Holding(symbol="GOOGL", name="Alphabet Inc. Class A", weight=12.85),
            Holding(symbol="GOOG", name="Alphabet Inc. Class C", weight=10.75),
            Holding(symbol="NFLX", name="Netflix Inc.", weight=5.45),
            Holding(symbol="T", name="AT&T Inc.", weight=4.95),
            Holding(symbol="VZ", name="Verizon Communications", weight=4.55),
            Holding(symbol="DIS", name="Walt Disney Company", weight=4.15),
            Holding(symbol="CMCSA", name="Comcast Corporation", weight=3.85),
            Holding(symbol="CHTR", name="Charter Communications", weight=2.95),
            Holding(symbol="EA", name="Electronic Arts Inc.", weight=2.45),
        ],
    }

    async def get_holdings(self, etf_symbol: str) -> ETFHoldings | None:
        """Return static holdings data"""
        if etf_symbol.upper() in self.STATIC_HOLDINGS:
            holdings = self.STATIC_HOLDINGS[etf_symbol.upper()]
            return ETFHoldings(
                etf_symbol=etf_symbol,
                etf_name=f"{etf_symbol} (Static Data)",
                as_of_date=datetime.now(),
                total_holdings=len(holdings),
                holdings=holdings,
            )
        return None


class HoldingsManager:
    """
    Manages ETF holdings with caching and multiple providers.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        cache_duration_hours: int = 24,
        custom_holdings: dict[str, list[str]] | None = None,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else Path("./holdings_cache")
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self.custom_holdings = custom_holdings or {}

        # Providers in order of preference
        self.providers: list[HoldingsProvider] = [
            YahooHoldingsProvider(),
            StaticHoldingsProvider(),
        ]

        # In-memory cache
        self._cache: dict[str, ETFHoldings] = {}
        self._cache_times: dict[str, datetime] = {}

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def add_custom_holdings(self, etf_symbol: str, symbols: list[str]):
        """Add custom holdings for an ETF (user-defined)"""
        self.custom_holdings[etf_symbol] = symbols

    async def get_holdings(
        self, etf_symbol: str, force_refresh: bool = False
    ) -> ETFHoldings | None:
        """
        Get holdings for an ETF with caching.

        Args:
            etf_symbol: ETF symbol
            force_refresh: Force refresh from provider

        Returns:
            ETFHoldings or None if not available
        """
        etf_symbol = etf_symbol.upper()

        # Check memory cache
        if not force_refresh and etf_symbol in self._cache:
            cache_time = self._cache_times.get(etf_symbol)
            if cache_time and datetime.now() - cache_time < self.cache_duration:
                return self._cache[etf_symbol]

        # Check file cache
        cache_file = self.cache_dir / f"{etf_symbol}_holdings.json"
        if not force_refresh and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                cache_date = datetime.fromisoformat(data["as_of_date"])
                if datetime.now() - cache_date < self.cache_duration:
                    holdings = self._parse_cached_holdings(data)
                    self._cache[etf_symbol] = holdings
                    self._cache_times[etf_symbol] = cache_date
                    return holdings
            except Exception as e:
                logger.warning(f"Error reading cache for {etf_symbol}: {e}")

        # Fetch from providers
        for provider in self.providers:
            try:
                holdings = await provider.get_holdings(etf_symbol)
                if holdings and holdings.holdings:
                    # Update caches
                    self._cache[etf_symbol] = holdings
                    self._cache_times[etf_symbol] = datetime.now()

                    # Save to file cache
                    try:
                        cache_file.write_text(json.dumps(holdings.to_dict(), indent=2))
                    except Exception as e:
                        logger.warning(f"Error writing cache for {etf_symbol}: {e}")

                    return holdings
            except Exception as e:
                logger.warning(f"Provider {type(provider).__name__} failed for {etf_symbol}: {e}")
                continue

        logger.warning(f"No holdings data available for {etf_symbol}")
        return None

    def _parse_cached_holdings(self, data: dict) -> ETFHoldings:
        """Parse holdings from cached JSON data"""
        holdings = [
            Holding(
                symbol=h["symbol"],
                name=h["name"],
                weight=h["weight"],
                shares=h.get("shares"),
                market_value=h.get("market_value"),
            )
            for h in data["holdings"]
        ]

        return ETFHoldings(
            etf_symbol=data["etf_symbol"],
            etf_name=data["etf_name"],
            as_of_date=datetime.fromisoformat(data["as_of_date"]),
            total_holdings=data["total_holdings"],
            holdings=holdings,
        )

    async def get_all_sector_holdings(
        self, sector_symbols: list[str], top_n: int = 10
    ) -> dict[str, list[str]]:
        """
        Get top holdings for multiple sector ETFs.

        Returns:
            Dict mapping ETF symbol to list of holding symbols
        """
        result = {}

        for etf_symbol in sector_symbols:
            holdings = await self.get_holdings(etf_symbol)
            if holdings:
                top_holdings = holdings.get_top_holdings(top_n)
                result[etf_symbol] = [h.symbol for h in top_holdings]
            elif etf_symbol in self.custom_holdings:
                result[etf_symbol] = self.custom_holdings[etf_symbol][:top_n]

        return result

    def get_custom_holdings(self, etf_symbol: str) -> list[str]:
        """Get user-defined custom holdings"""
        return self.custom_holdings.get(etf_symbol.upper(), [])
