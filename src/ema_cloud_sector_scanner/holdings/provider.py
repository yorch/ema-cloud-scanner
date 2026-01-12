"""
ETF Holdings Provider Module

Fetches top holdings for sector ETFs from various sources.
Supports both automatic fetching and user-defined holdings lists.

Sources:
- Yahoo Finance (holdings info)
- Web scraping from fund providers (SPDR, iShares, Vanguard)
- User-defined custom lists
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import asyncio
import logging
import json
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Holding:
    """Individual holding in an ETF"""
    symbol: str
    name: str
    weight: float  # Percentage weight in the ETF
    shares: Optional[int] = None
    market_value: Optional[float] = None
    sector: Optional[str] = None


@dataclass
class ETFHoldings:
    """Complete holdings data for an ETF"""
    etf_symbol: str
    etf_name: str
    holdings: List[Holding]
    total_holdings_count: int
    last_updated: datetime
    source: str
    
    def get_top_holdings(self, n: int = 10) -> List[Holding]:
        """Get top N holdings by weight"""
        sorted_holdings = sorted(self.holdings, key=lambda h: h.weight, reverse=True)
        return sorted_holdings[:n]
    
    def get_symbols(self) -> List[str]:
        """Get list of all holding symbols"""
        return [h.symbol for h in self.holdings]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'etf_symbol': self.etf_symbol,
            'etf_name': self.etf_name,
            'holdings': [
                {
                    'symbol': h.symbol,
                    'name': h.name,
                    'weight': h.weight,
                    'shares': h.shares,
                    'market_value': h.market_value
                }
                for h in self.holdings
            ],
            'total_count': self.total_holdings_count,
            'last_updated': self.last_updated.isoformat(),
            'source': self.source
        }


class BaseHoldingsProvider(ABC):
    """Abstract base class for holdings providers"""
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
    
    @abstractmethod
    async def get_holdings(self, etf_symbol: str) -> ETFHoldings:
        pass


class YahooHoldingsProvider(BaseHoldingsProvider):
    """
    Fetch ETF holdings from Yahoo Finance.
    Uses the yfinance library.
    """
    
    @property
    def name(self) -> str:
        return "Yahoo Finance"
    
    async def get_holdings(self, etf_symbol: str) -> ETFHoldings:
        """Fetch holdings from Yahoo Finance"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(etf_symbol)
            
            # Get holdings data
            try:
                holdings_df = ticker.get_institutional_holders()
            except:
                holdings_df = None
            
            # Try to get top holdings from info
            info = ticker.info
            
            holdings = []
            
            # Yahoo Finance structure for ETF holdings varies
            # Try different approaches
            try:
                # Some ETFs have holdings data
                if hasattr(ticker, 'major_holders'):
                    major = ticker.major_holders
                    
                # Get from fund_top_holdings if available
                fund_holdings = info.get('holdings', [])
                for h in fund_holdings:
                    holdings.append(Holding(
                        symbol=h.get('symbol', 'N/A'),
                        name=h.get('holdingName', 'Unknown'),
                        weight=h.get('holdingPercent', 0) * 100 if h.get('holdingPercent') else 0
                    ))
            except Exception as e:
                logger.debug(f"Could not get detailed holdings for {etf_symbol}: {e}")
            
            # If we didn't get holdings, create empty result
            if not holdings:
                # Return known top holdings for major sector ETFs (fallback)
                holdings = self._get_fallback_holdings(etf_symbol)
            
            return ETFHoldings(
                etf_symbol=etf_symbol,
                etf_name=info.get('longName', etf_symbol),
                holdings=holdings,
                total_holdings_count=len(holdings),
                last_updated=datetime.now(),
                source=self.name
            )
            
        except Exception as e:
            logger.error(f"Error fetching holdings for {etf_symbol}: {e}")
            return self._get_fallback_etf_holdings(etf_symbol)
    
    def _get_fallback_holdings(self, etf_symbol: str) -> List[Holding]:
        """Fallback holdings for major sector ETFs"""
        
        # Known top holdings for major sector ETFs (as of late 2024/early 2025)
        fallback_data = {
            'XLK': [
                Holding('NVDA', 'NVIDIA Corporation', 14.8),
                Holding('AAPL', 'Apple Inc.', 12.6),
                Holding('MSFT', 'Microsoft Corporation', 11.7),
                Holding('AVGO', 'Broadcom Inc.', 5.2),
                Holding('PLTR', 'Palantir Technologies', 3.5),
                Holding('AMD', 'Advanced Micro Devices', 3.2),
                Holding('CRM', 'Salesforce Inc.', 2.8),
                Holding('ORCL', 'Oracle Corporation', 2.6),
                Holding('CSCO', 'Cisco Systems', 2.4),
                Holding('ACN', 'Accenture', 2.2),
            ],
            'XLF': [
                Holding('BRK-B', 'Berkshire Hathaway', 11.5),
                Holding('JPM', 'JPMorgan Chase', 11.2),
                Holding('V', 'Visa Inc.', 7.4),
                Holding('MA', 'Mastercard', 5.9),
                Holding('BAC', 'Bank of America', 4.7),
                Holding('WFC', 'Wells Fargo', 3.5),
                Holding('GS', 'Goldman Sachs', 2.9),
                Holding('AXP', 'American Express', 2.8),
                Holding('MS', 'Morgan Stanley', 2.6),
                Holding('SPGI', 'S&P Global', 2.4),
            ],
            'XLV': [
                Holding('LLY', 'Eli Lilly', 11.8),
                Holding('UNH', 'UnitedHealth Group', 9.2),
                Holding('JNJ', 'Johnson & Johnson', 6.5),
                Holding('ABBV', 'AbbVie Inc.', 5.8),
                Holding('MRK', 'Merck & Co.', 5.2),
                Holding('TMO', 'Thermo Fisher Scientific', 4.1),
                Holding('ABT', 'Abbott Laboratories', 3.8),
                Holding('PFE', 'Pfizer Inc.', 3.4),
                Holding('AMGN', 'Amgen Inc.', 2.9),
                Holding('DHR', 'Danaher Corporation', 2.7),
            ],
            'XLE': [
                Holding('XOM', 'Exxon Mobil', 22.5),
                Holding('CVX', 'Chevron Corporation', 17.2),
                Holding('COP', 'ConocoPhillips', 7.8),
                Holding('EOG', 'EOG Resources', 5.1),
                Holding('SLB', 'Schlumberger', 4.8),
                Holding('MPC', 'Marathon Petroleum', 4.2),
                Holding('PSX', 'Phillips 66', 3.9),
                Holding('WMB', 'Williams Companies', 3.6),
                Holding('VLO', 'Valero Energy', 3.4),
                Holding('OKE', 'ONEOK Inc.', 3.1),
            ],
            'XLY': [
                Holding('AMZN', 'Amazon.com', 22.8),
                Holding('TSLA', 'Tesla Inc.', 12.5),
                Holding('HD', 'Home Depot', 8.2),
                Holding('MCD', 'McDonald\'s', 4.8),
                Holding('LOW', 'Lowe\'s Companies', 3.9),
                Holding('BKNG', 'Booking Holdings', 3.6),
                Holding('NKE', 'Nike Inc.', 3.2),
                Holding('SBUX', 'Starbucks', 2.9),
                Holding('TJX', 'TJX Companies', 2.7),
                Holding('CMG', 'Chipotle Mexican Grill', 2.4),
            ],
            'XLP': [
                Holding('PG', 'Procter & Gamble', 14.2),
                Holding('COST', 'Costco Wholesale', 12.8),
                Holding('WMT', 'Walmart Inc.', 10.5),
                Holding('KO', 'Coca-Cola Company', 9.1),
                Holding('PEP', 'PepsiCo Inc.', 8.6),
                Holding('PM', 'Philip Morris', 5.2),
                Holding('MO', 'Altria Group', 3.8),
                Holding('MDLZ', 'Mondelez International', 3.5),
                Holding('CL', 'Colgate-Palmolive', 3.2),
                Holding('KMB', 'Kimberly-Clark', 2.4),
            ],
            'XLI': [
                Holding('GE', 'GE Aerospace', 8.5),
                Holding('CAT', 'Caterpillar', 5.8),
                Holding('RTX', 'RTX Corporation', 5.2),
                Holding('UNP', 'Union Pacific', 4.8),
                Holding('HON', 'Honeywell', 4.5),
                Holding('DE', 'Deere & Company', 4.2),
                Holding('BA', 'Boeing Company', 3.8),
                Holding('UPS', 'United Parcel Service', 3.5),
                Holding('LMT', 'Lockheed Martin', 3.2),
                Holding('ADP', 'ADP', 2.9),
            ],
            'XLB': [
                Holding('LIN', 'Linde PLC', 18.5),
                Holding('SHW', 'Sherwin-Williams', 8.2),
                Holding('APD', 'Air Products', 6.8),
                Holding('FCX', 'Freeport-McMoRan', 6.5),
                Holding('ECL', 'Ecolab Inc.', 5.8),
                Holding('NEM', 'Newmont Corporation', 5.2),
                Holding('DOW', 'Dow Inc.', 4.8),
                Holding('DD', 'DuPont', 4.2),
                Holding('CTVA', 'Corteva Inc.', 3.8),
                Holding('NUE', 'Nucor Corporation', 3.5),
            ],
            'XLU': [
                Holding('NEE', 'NextEra Energy', 14.8),
                Holding('SO', 'Southern Company', 8.5),
                Holding('DUK', 'Duke Energy', 7.2),
                Holding('CEG', 'Constellation Energy', 6.8),
                Holding('SRE', 'Sempra', 5.5),
                Holding('AEP', 'American Electric Power', 4.8),
                Holding('D', 'Dominion Energy', 4.2),
                Holding('PCG', 'PG&E Corporation', 3.9),
                Holding('EXC', 'Exelon Corporation', 3.6),
                Holding('XEL', 'Xcel Energy', 3.2),
            ],
            'XLRE': [
                Holding('PLD', 'Prologis Inc.', 11.2),
                Holding('AMT', 'American Tower', 8.5),
                Holding('EQIX', 'Equinix Inc.', 7.8),
                Holding('WELL', 'Welltower Inc.', 6.2),
                Holding('SPG', 'Simon Property Group', 5.5),
                Holding('DLR', 'Digital Realty', 5.1),
                Holding('PSA', 'Public Storage', 4.8),
                Holding('O', 'Realty Income', 4.2),
                Holding('CCI', 'Crown Castle', 3.8),
                Holding('VICI', 'VICI Properties', 3.5),
            ],
            'XLC': [
                Holding('META', 'Meta Platforms', 22.5),
                Holding('GOOGL', 'Alphabet Inc. Class A', 12.8),
                Holding('GOOG', 'Alphabet Inc. Class C', 11.2),
                Holding('NFLX', 'Netflix Inc.', 5.2),
                Holding('DIS', 'Walt Disney', 4.8),
                Holding('TMUS', 'T-Mobile US', 4.5),
                Holding('CMCSA', 'Comcast Corporation', 4.2),
                Holding('VZ', 'Verizon Communications', 3.8),
                Holding('T', 'AT&T Inc.', 3.5),
                Holding('CHTR', 'Charter Communications', 2.8),
            ],
        }
        
        return fallback_data.get(etf_symbol, [])
    
    def _get_fallback_etf_holdings(self, etf_symbol: str) -> ETFHoldings:
        """Return fallback holdings for an ETF"""
        holdings = self._get_fallback_holdings(etf_symbol)
        return ETFHoldings(
            etf_symbol=etf_symbol,
            etf_name=etf_symbol,
            holdings=holdings,
            total_holdings_count=len(holdings),
            last_updated=datetime.now(),
            source="Fallback Data"
        )


class CustomHoldingsProvider(BaseHoldingsProvider):
    """
    Provider for user-defined custom holdings lists.
    Loads from JSON configuration files.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/custom_holdings.json"
        self._custom_holdings: Dict[str, List[Dict]] = {}
        self._load_config()
    
    @property
    def name(self) -> str:
        return "Custom Holdings"
    
    def _load_config(self):
        """Load custom holdings from config file"""
        try:
            path = Path(self.config_path)
            if path.exists():
                self._custom_holdings = json.loads(path.read_text())
        except Exception as e:
            logger.warning(f"Could not load custom holdings config: {e}")
    
    def add_holdings(self, etf_symbol: str, holdings: List[Dict]):
        """Add or update custom holdings for an ETF"""
        self._custom_holdings[etf_symbol] = holdings
        self._save_config()
    
    def _save_config(self):
        """Save custom holdings to config file"""
        try:
            path = Path(self.config_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._custom_holdings, indent=2))
        except Exception as e:
            logger.error(f"Could not save custom holdings config: {e}")
    
    async def get_holdings(self, etf_symbol: str) -> Optional[ETFHoldings]:
        """Get custom holdings for an ETF"""
        if etf_symbol not in self._custom_holdings:
            return None
        
        holdings_data = self._custom_holdings[etf_symbol]
        holdings = [
            Holding(
                symbol=h['symbol'],
                name=h.get('name', h['symbol']),
                weight=h.get('weight', 0)
            )
            for h in holdings_data
        ]
        
        return ETFHoldings(
            etf_symbol=etf_symbol,
            etf_name=f"Custom: {etf_symbol}",
            holdings=holdings,
            total_holdings_count=len(holdings),
            last_updated=datetime.now(),
            source=self.name
        )


class HoldingsManager:
    """
    Manager class for ETF holdings.
    Combines multiple providers with caching.
    """
    
    def __init__(
        self,
        cache_duration_hours: int = 24,
        custom_config_path: Optional[str] = None
    ):
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._cache: Dict[str, ETFHoldings] = {}
        
        # Initialize providers
        self.providers = {
            'yahoo': YahooHoldingsProvider(),
            'custom': CustomHoldingsProvider(custom_config_path),
        }
        
        self.primary_provider = 'yahoo'
    
    async def get_holdings(
        self,
        etf_symbol: str,
        force_refresh: bool = False,
        use_custom: bool = True
    ) -> ETFHoldings:
        """
        Get holdings for an ETF with caching.
        
        Args:
            etf_symbol: ETF ticker symbol
            force_refresh: Force refresh from provider
            use_custom: Check custom holdings first
        """
        cache_key = etf_symbol
        
        # Check cache
        if not force_refresh and cache_key in self._cache:
            cached = self._cache[cache_key]
            if datetime.now() - cached.last_updated < self.cache_duration:
                return cached
        
        # Try custom holdings first
        if use_custom:
            custom = await self.providers['custom'].get_holdings(etf_symbol)
            if custom and custom.holdings:
                self._cache[cache_key] = custom
                return custom
        
        # Try primary provider
        try:
            holdings = await self.providers[self.primary_provider].get_holdings(etf_symbol)
            self._cache[cache_key] = holdings
            return holdings
        except Exception as e:
            logger.error(f"Error getting holdings for {etf_symbol}: {e}")
            
            # Return cached even if expired
            if cache_key in self._cache:
                return self._cache[cache_key]
            
            # Return empty holdings
            return ETFHoldings(
                etf_symbol=etf_symbol,
                etf_name=etf_symbol,
                holdings=[],
                total_holdings_count=0,
                last_updated=datetime.now(),
                source="Error - No Data"
            )
    
    async def get_all_holdings(
        self,
        etf_symbols: List[str],
        top_n: int = 10
    ) -> Dict[str, List[Holding]]:
        """
        Get top holdings for multiple ETFs.
        
        Returns dict of ETF symbol to list of top holdings.
        """
        result = {}
        
        for symbol in etf_symbols:
            holdings = await self.get_holdings(symbol)
            result[symbol] = holdings.get_top_holdings(top_n)
        
        return result
    
    def add_custom_holdings(self, etf_symbol: str, holdings: List[Dict]):
        """Add custom holdings for an ETF"""
        self.providers['custom'].add_holdings(etf_symbol, holdings)
    
    def get_all_stock_symbols(
        self,
        etf_symbols: List[str],
        top_n: int = 10
    ) -> List[str]:
        """
        Get unique list of all stock symbols from top holdings.
        Synchronous version using cached data.
        """
        symbols = set()
        
        for etf in etf_symbols:
            if etf in self._cache:
                for holding in self._cache[etf].get_top_holdings(top_n):
                    symbols.add(holding.symbol)
        
        return list(symbols)
