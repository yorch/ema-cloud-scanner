"""
ETF Holdings Module

Fetches and manages top holdings for sector ETFs.
Supports multiple data sources and caching.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    """Single ETF holding"""

    symbol: str
    name: str
    weight: float  # Percentage weight in ETF
    shares: int | None = None
    market_value: float | None = None
    sector: str | None = None


@dataclass
class ETFHoldings:
    """Holdings data for an ETF"""

    etf_symbol: str
    etf_name: str
    as_of_date: datetime
    total_holdings: int
    holdings: list[Holding]

    def get_top_holdings(self, n: int = 10) -> list[Holding]:
        """Get top N holdings by weight"""
        sorted_holdings = sorted(self.holdings, key=lambda h: h.weight, reverse=True)
        return sorted_holdings[:n]

    def get_symbols(self) -> list[str]:
        """Get list of all holding symbols"""
        return [h.symbol for h in self.holdings]

    def to_dict(self) -> dict[str, Any]:
        return {
            "etf_symbol": self.etf_symbol,
            "etf_name": self.etf_name,
            "as_of_date": self.as_of_date.isoformat(),
            "total_holdings": self.total_holdings,
            "holdings": [
                {
                    "symbol": h.symbol,
                    "name": h.name,
                    "weight": h.weight,
                    "shares": h.shares,
                    "market_value": h.market_value,
                }
                for h in self.holdings
            ],
        }


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
            Holding("NVDA", "NVIDIA Corporation", 14.79),
            Holding("AAPL", "Apple Inc.", 12.59),
            Holding("MSFT", "Microsoft Corporation", 11.69),
            Holding("AVGO", "Broadcom Inc.", 5.16),
            Holding("PLTR", "Palantir Technologies Inc.", 3.47),
            Holding("AMD", "Advanced Micro Devices", 3.25),
            Holding("CRM", "Salesforce Inc.", 3.10),
            Holding("ORCL", "Oracle Corporation", 2.95),
            Holding("CSCO", "Cisco Systems Inc.", 2.45),
            Holding("ADBE", "Adobe Inc.", 2.35),
        ],
        "XLF": [
            Holding("BRK.B", "Berkshire Hathaway Inc.", 11.46),
            Holding("JPM", "JPMorgan Chase & Co.", 11.22),
            Holding("V", "Visa Inc.", 7.43),
            Holding("MA", "Mastercard Inc.", 5.94),
            Holding("BAC", "Bank of America Corporation", 4.72),
            Holding("WFC", "Wells Fargo & Company", 3.25),
            Holding("GS", "Goldman Sachs Group Inc.", 2.85),
            Holding("SPGI", "S&P Global Inc.", 2.65),
            Holding("MS", "Morgan Stanley", 2.55),
            Holding("AXP", "American Express Company", 2.45),
        ],
        "XLV": [
            Holding("LLY", "Eli Lilly and Company", 11.85),
            Holding("UNH", "UnitedHealth Group Inc.", 9.25),
            Holding("JNJ", "Johnson & Johnson", 6.45),
            Holding("ABBV", "AbbVie Inc.", 5.85),
            Holding("MRK", "Merck & Co. Inc.", 5.15),
            Holding("TMO", "Thermo Fisher Scientific", 4.25),
            Holding("ABT", "Abbott Laboratories", 3.95),
            Holding("PFE", "Pfizer Inc.", 3.15),
            Holding("DHR", "Danaher Corporation", 2.85),
            Holding("AMGN", "Amgen Inc.", 2.75),
        ],
        "XLE": [
            Holding("XOM", "Exxon Mobil Corporation", 23.15),
            Holding("CVX", "Chevron Corporation", 16.85),
            Holding("COP", "ConocoPhillips", 7.25),
            Holding("EOG", "EOG Resources Inc.", 4.95),
            Holding("SLB", "Schlumberger Limited", 4.65),
            Holding("MPC", "Marathon Petroleum Corp.", 4.35),
            Holding("PSX", "Phillips 66", 3.85),
            Holding("VLO", "Valero Energy Corporation", 3.55),
            Holding("WMB", "Williams Companies Inc.", 3.25),
            Holding("OKE", "ONEOK Inc.", 2.95),
        ],
        "XLY": [
            Holding("AMZN", "Amazon.com Inc.", 22.45),
            Holding("TSLA", "Tesla Inc.", 12.85),
            Holding("HD", "The Home Depot Inc.", 8.45),
            Holding("MCD", "McDonald's Corporation", 4.25),
            Holding("LOW", "Lowe's Companies Inc.", 3.85),
            Holding("BKNG", "Booking Holdings Inc.", 3.55),
            Holding("SBUX", "Starbucks Corporation", 3.25),
            Holding("TJX", "TJX Companies Inc.", 2.95),
            Holding("NKE", "Nike Inc.", 2.65),
            Holding("CMG", "Chipotle Mexican Grill", 2.35),
        ],
        "XLP": [
            Holding("PG", "Procter & Gamble Company", 14.85),
            Holding("COST", "Costco Wholesale Corp.", 12.45),
            Holding("WMT", "Walmart Inc.", 10.25),
            Holding("KO", "Coca-Cola Company", 9.15),
            Holding("PEP", "PepsiCo Inc.", 8.45),
            Holding("PM", "Philip Morris Int'l", 5.25),
            Holding("MDLZ", "Mondelez International", 3.95),
            Holding("MO", "Altria Group Inc.", 3.55),
            Holding("CL", "Colgate-Palmolive Company", 3.15),
            Holding("KMB", "Kimberly-Clark Corp.", 2.45),
        ],
        "XLI": [
            Holding("GE", "General Electric Company", 5.25),
            Holding("CAT", "Caterpillar Inc.", 4.85),
            Holding("RTX", "RTX Corporation", 4.55),
            Holding("HON", "Honeywell International", 4.25),
            Holding("UNP", "Union Pacific Corporation", 4.05),
            Holding("BA", "Boeing Company", 3.75),
            Holding("DE", "Deere & Company", 3.45),
            Holding("LMT", "Lockheed Martin Corp.", 3.15),
            Holding("UPS", "United Parcel Service", 2.95),
            Holding("ADP", "Automatic Data Processing", 2.75),
        ],
        "XLB": [
            Holding("LIN", "Linde plc", 17.85),
            Holding("SHW", "Sherwin-Williams Company", 9.45),
            Holding("FCX", "Freeport-McMoRan Inc.", 7.25),
            Holding("APD", "Air Products & Chemicals", 6.85),
            Holding("ECL", "Ecolab Inc.", 5.45),
            Holding("NEM", "Newmont Corporation", 4.85),
            Holding("CTVA", "Corteva Inc.", 4.25),
            Holding("DOW", "Dow Inc.", 3.95),
            Holding("DD", "DuPont de Nemours Inc.", 3.55),
            Holding("NUE", "Nucor Corporation", 3.15),
        ],
        "XLU": [
            Holding("NEE", "NextEra Energy Inc.", 14.25),
            Holding("SO", "Southern Company", 8.45),
            Holding("DUK", "Duke Energy Corporation", 7.85),
            Holding("CEG", "Constellation Energy", 6.55),
            Holding("SRE", "Sempra Energy", 5.25),
            Holding("AEP", "American Electric Power", 4.85),
            Holding("D", "Dominion Energy Inc.", 4.25),
            Holding("PCG", "PG&E Corporation", 3.95),
            Holding("EXC", "Exelon Corporation", 3.55),
            Holding("XEL", "Xcel Energy Inc.", 3.15),
        ],
        "XLRE": [
            Holding("PLD", "Prologis Inc.", 10.85),
            Holding("AMT", "American Tower Corp.", 9.45),
            Holding("EQIX", "Equinix Inc.", 7.85),
            Holding("WELL", "Welltower Inc.", 5.95),
            Holding("SPG", "Simon Property Group", 5.25),
            Holding("PSA", "Public Storage", 4.85),
            Holding("DLR", "Digital Realty Trust", 4.25),
            Holding("O", "Realty Income Corp.", 3.95),
            Holding("CCI", "Crown Castle Inc.", 3.55),
            Holding("VICI", "VICI Properties Inc.", 3.25),
        ],
        "XLC": [
            Holding("META", "Meta Platforms Inc.", 22.45),
            Holding("GOOGL", "Alphabet Inc. Class A", 12.85),
            Holding("GOOG", "Alphabet Inc. Class C", 10.75),
            Holding("NFLX", "Netflix Inc.", 5.45),
            Holding("T", "AT&T Inc.", 4.95),
            Holding("VZ", "Verizon Communications", 4.55),
            Holding("DIS", "Walt Disney Company", 4.15),
            Holding("CMCSA", "Comcast Corporation", 3.85),
            Holding("CHTR", "Charter Communications", 2.95),
            Holding("EA", "Electronic Arts Inc.", 2.45),
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
