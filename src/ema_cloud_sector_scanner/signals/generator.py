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

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, time
from enum import Enum
import pandas as pd
import numpy as np
import logging

from ..indicators.ema_cloud import (
    EMACloudIndicator, TechnicalIndicators, CloudState, 
    PriceRelation, CloudData, TrendAnalysis
)
from ..config.settings import FilterConfig, TradingStyle, SignalType

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Signal strength classification"""
    VERY_STRONG = 5
    STRONG = 4
    MODERATE = 3
    WEAK = 2
    VERY_WEAK = 1


@dataclass
class Signal:
    """Trading signal with all relevant information"""
    symbol: str
    signal_type: SignalType
    direction: str  # "long" or "short"
    strength: SignalStrength
    timestamp: datetime
    price: float
    
    # Cloud data at signal time
    primary_cloud_state: CloudState
    price_relation: PriceRelation
    
    # Confirmation indicators
    rsi: Optional[float] = None
    adx: Optional[float] = None
    volume_ratio: Optional[float] = None
    vwap_confirmed: bool = False
    macd_confirmed: bool = False
    
    # Risk management
    suggested_stop: Optional[float] = None
    suggested_target: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    
    # Filter results
    filters_passed: List[str] = field(default_factory=list)
    filters_failed: List[str] = field(default_factory=list)
    
    # Additional context
    sector: Optional[str] = None
    etf_symbol: Optional[str] = None
    notes: List[str] = field(default_factory=list)
    
    def is_valid(self) -> bool:
        """Check if signal passed all required filters"""
        return len(self.filters_failed) == 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'signal_type': self.signal_type.value,
            'direction': self.direction,
            'strength': self.strength.name,
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'cloud_state': self.primary_cloud_state.value,
            'price_relation': self.price_relation.value,
            'rsi': self.rsi,
            'adx': self.adx,
            'volume_ratio': self.volume_ratio,
            'vwap_confirmed': self.vwap_confirmed,
            'suggested_stop': self.suggested_stop,
            'suggested_target': self.suggested_target,
            'is_valid': self.is_valid(),
            'notes': self.notes
        }


@dataclass
class SectorTrendState:
    """Current trend state for a sector ETF"""
    symbol: str
    sector_name: str
    timestamp: datetime
    
    # Trend info
    trend_direction: str  # "bullish", "bearish", "neutral"
    trend_strength: float  # 0-100
    trend_duration: int  # Bars in current trend
    
    # Cloud states
    cloud_states: Dict[str, CloudState] = field(default_factory=dict)
    cloud_alignment: int = 0  # Number of aligned clouds
    
    # Key levels
    support_level: Optional[float] = None
    resistance_level: Optional[float] = None
    
    # Recent signals
    last_signal: Optional[Signal] = None
    
    def is_bullish(self) -> bool:
        return self.trend_direction == "bullish"
    
    def is_bearish(self) -> bool:
        return self.trend_direction == "bearish"


class SignalFilter:
    """
    Filter class for validating signals.
    Each filter returns (passed: bool, reason: str)
    """
    
    def __init__(self, config: FilterConfig):
        self.config = config
    
    def filter_volume(self, row: pd.Series) -> Tuple[bool, str]:
        """Check if volume meets minimum threshold"""
        if not self.config.volume_enabled:
            return True, "Volume filter disabled"
        
        volume_ratio = row.get('volume_ratio', 1.0)
        if pd.isna(volume_ratio):
            return True, "Volume ratio not available"
        if volume_ratio >= self.config.volume_multiplier:
            return True, f"Volume ratio {volume_ratio:.2f}x meets threshold"
        else:
            return False, f"Volume ratio {volume_ratio:.2f}x below {self.config.volume_multiplier}x threshold"
    
    def filter_rsi(self, row: pd.Series, direction: str) -> Tuple[bool, str]:
        """Check RSI for overbought/oversold conditions"""
        if not self.config.rsi_enabled:
            return True, "RSI filter disabled"
        
        rsi = row.get('rsi')
        if rsi is None or pd.isna(rsi):
            return True, "RSI not available"
        
        if direction == "long":
            if rsi > self.config.rsi_overbought:
                return False, f"RSI {rsi:.1f} overbought for long entry"
            elif rsi < self.config.rsi_neutral_zone[0]:
                return True, f"RSI {rsi:.1f} showing potential upward momentum"
            else:
                return True, f"RSI {rsi:.1f} in neutral zone"
        else:  # short
            if rsi < self.config.rsi_oversold:
                return False, f"RSI {rsi:.1f} oversold for short entry"
            elif rsi > self.config.rsi_neutral_zone[1]:
                return True, f"RSI {rsi:.1f} showing potential downward momentum"
            else:
                return True, f"RSI {rsi:.1f} in neutral zone"
    
    def filter_adx(self, row: pd.Series) -> Tuple[bool, str]:
        """Check ADX for trend strength"""
        if not self.config.adx_enabled:
            return True, "ADX filter disabled"
        
        adx = row.get('adx')
        if adx is None or pd.isna(adx):
            return True, "ADX not available"
        
        if adx >= self.config.adx_strong_trend:
            return True, f"ADX {adx:.1f} shows strong trend"
        elif adx >= self.config.adx_min_strength:
            return True, f"ADX {adx:.1f} shows moderate trend"
        else:
            return False, f"ADX {adx:.1f} too weak (min {self.config.adx_min_strength})"
    
    def filter_vwap(self, row: pd.Series, direction: str) -> Tuple[bool, str]:
        """Check price position relative to VWAP"""
        if not self.config.vwap_enabled:
            return True, "VWAP filter disabled"
        
        vwap = row.get('vwap')
        price = row.get('close')
        
        if vwap is None or price is None or pd.isna(vwap) or pd.isna(price):
            return True, "VWAP not available"
        
        if direction == "long":
            if price > vwap:
                return True, f"Price ${price:.2f} above VWAP ${vwap:.2f}"
            else:
                return False, f"Price ${price:.2f} below VWAP ${vwap:.2f} for long"
        else:  # short
            if price < vwap:
                return True, f"Price ${price:.2f} below VWAP ${vwap:.2f}"
            else:
                return False, f"Price ${price:.2f} above VWAP ${vwap:.2f} for short"
    
    def filter_atr(self, row: pd.Series) -> Tuple[bool, str]:
        """Check ATR for volatility conditions"""
        if not self.config.atr_enabled:
            return True, "ATR filter disabled"
        
        atr_pct = row.get('atr_pct')
        if atr_pct is None or pd.isna(atr_pct):
            return True, "ATR not available"
        
        if atr_pct < self.config.atr_min_threshold:
            return False, f"ATR {atr_pct:.2f}% too low (min {self.config.atr_min_threshold}%)"
        elif atr_pct > self.config.atr_max_threshold:
            return False, f"ATR {atr_pct:.2f}% too high (max {self.config.atr_max_threshold}%)"
        else:
            return True, f"ATR {atr_pct:.2f}% within acceptable range"
    
    def filter_macd(self, row: pd.Series, direction: str) -> Tuple[bool, str]:
        """Check MACD for momentum confirmation"""
        if not self.config.macd_enabled:
            return True, "MACD filter disabled"
        
        macd_hist = row.get('macd_histogram')
        if macd_hist is None or pd.isna(macd_hist):
            return True, "MACD not available"
        
        if direction == "long":
            if macd_hist > 0:
                return True, f"MACD histogram {macd_hist:.4f} positive"
            else:
                return False, f"MACD histogram {macd_hist:.4f} negative for long"
        else:
            if macd_hist < 0:
                return True, f"MACD histogram {macd_hist:.4f} negative"
            else:
                return False, f"MACD histogram {macd_hist:.4f} positive for short"
    
    def filter_time_of_day(self, timestamp: datetime) -> Tuple[bool, str]:
        """Check if within valid trading hours"""
        if not self.config.time_filter_enabled:
            return True, "Time filter disabled"
        
        current_time = timestamp.time()
        
        # Parse trading hours
        start_parts = self.config.trading_start_time.split(':')
        end_parts = self.config.trading_end_time.split(':')
        
        trading_start = time(int(start_parts[0]), int(start_parts[1]))
        trading_end = time(int(end_parts[0]), int(end_parts[1]))
        
        # Add buffer for first/last minutes
        from datetime import timedelta
        
        buffer_start = (datetime.combine(datetime.today(), trading_start) + 
                       timedelta(minutes=self.config.avoid_first_minutes)).time()
        buffer_end = (datetime.combine(datetime.today(), trading_end) - 
                     timedelta(minutes=self.config.avoid_last_minutes)).time()
        
        if current_time < buffer_start:
            return False, f"Too early - avoiding first {self.config.avoid_first_minutes} minutes"
        elif current_time > buffer_end:
            return False, f"Too late - avoiding last {self.config.avoid_last_minutes} minutes"
        else:
            return True, f"Within valid trading hours"
    
    def apply_all_filters(
        self, 
        row: pd.Series, 
        direction: str,
        timestamp: datetime
    ) -> Tuple[List[str], List[str]]:
        """
        Apply all filters and return (passed_filters, failed_filters)
        """
        passed = []
        failed = []
        
        filters = [
            ('volume', self.filter_volume(row)),
            ('rsi', self.filter_rsi(row, direction)),
            ('adx', self.filter_adx(row)),
            ('vwap', self.filter_vwap(row, direction)),
            ('atr', self.filter_atr(row)),
            ('macd', self.filter_macd(row, direction)),
            ('time', self.filter_time_of_day(timestamp)),
        ]
        
        for name, (is_passed, reason) in filters:
            if is_passed:
                passed.append(f"{name}: {reason}")
            else:
                failed.append(f"{name}: {reason}")
        
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
        clouds_config: Optional[Dict[str, Tuple[int, int]]] = None,
        filter_config: Optional[FilterConfig] = None,
        trading_style: TradingStyle = TradingStyle.INTRADAY
    ):
        self.cloud_indicator = EMACloudIndicator(clouds_config)
        self.tech_indicators = TechnicalIndicators()
        self.filter_config = filter_config or FilterConfig()
        self.signal_filter = SignalFilter(self.filter_config)
        self.trading_style = trading_style
        
        # Track recent signals to avoid duplicates
        self._recent_signals: Dict[str, datetime] = {}
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
        price = row['close']
        
        # Get cloud analysis
        clouds = self.cloud_indicator.analyze_single(df, idx)
        
        # Get technical indicator analysis
        indicators = self.tech_indicators.get_analysis(df, idx)
        
        # Detect signals
        signals = self.cloud_indicator.detect_signals(df, idx)
        
        # Determine overall trend
        bullish_clouds = sum(1 for c in clouds.values() 
                           if c.state in [CloudState.BULLISH, CloudState.CROSSING_UP])
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
        adx = indicators.get('adx')
        if adx is not None and not pd.isna(adx):
            trend_strength = min(100, adx * 2)
        
        # Cloud alignment contribution
        alignment_bonus = (bullish_clouds / total_clouds - 0.5) * 40 if total_clouds > 0 else 0
        if overall_trend == "bearish":
            alignment_bonus = ((total_clouds - bullish_clouds) / total_clouds - 0.5) * 40 if total_clouds > 0 else 0
        trend_strength += alignment_bonus
        
        trend_strength = max(0, min(100, trend_strength))
        
        return TrendAnalysis(
            symbol=symbol,
            timestamp=timestamp,
            price=price,
            clouds=clouds,
            overall_trend=overall_trend,
            trend_strength=trend_strength,
            trend_alignment=bullish_clouds if overall_trend == "bullish" else total_clouds - bullish_clouds,
            signals=signals,
            rsi=indicators.get('rsi'),
            adx=indicators.get('adx'),
            atr=indicators.get('atr'),
            atr_pct=indicators.get('atr_pct'),
            vwap=indicators.get('vwap'),
            volume_ratio=indicators.get('volume_ratio'),
            macd=indicators.get('macd'),
            macd_signal=indicators.get('macd_signal'),
            macd_histogram=indicators.get('macd_histogram')
        )
    
    def generate_signals(
        self, 
        df: pd.DataFrame, 
        symbol: str,
        sector: Optional[str] = None,
        etf_symbol: Optional[str] = None,
        check_history: int = 3
    ) -> List[Signal]:
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
                    etf_symbol=etf_symbol
                )
                
                if signal:
                    signals.append(signal)
                    self._recent_signals[signal_key] = timestamp
        
        return signals
    
    def _process_raw_signal(
        self,
        raw_signal: str,
        row: pd.Series,
        clouds: Dict[str, CloudData],
        symbol: str,
        timestamp: datetime,
        sector: Optional[str] = None,
        etf_symbol: Optional[str] = None
    ) -> Optional[Signal]:
        """Process a raw signal string into a Signal object"""
        
        # Determine direction and signal type
        is_bullish = "🟢" in raw_signal or "BULLISH" in raw_signal.upper()
        direction = "long" if is_bullish else "short"
        
        # Map raw signal to SignalType
        if "TREND_FLIP" in raw_signal:
            signal_type = SignalType.CLOUD_FLIP_BULLISH if is_bullish else SignalType.CLOUD_FLIP_BEARISH
        elif "BREAKOUT" in raw_signal:
            signal_type = SignalType.PRICE_CROSS_ABOVE
        elif "BREAKDOWN" in raw_signal:
            signal_type = SignalType.PRICE_CROSS_BELOW
        elif "PULLBACK" in raw_signal:
            signal_type = SignalType.PULLBACK_ENTRY
        elif "ALIGNMENT" in raw_signal:
            signal_type = SignalType.TREND_CONFIRMATION
        else:
            signal_type = SignalType.CLOUD_FLIP_BULLISH if is_bullish else SignalType.CLOUD_FLIP_BEARISH
        
        # Get primary cloud state (34-50)
        primary_cloud = clouds.get('trend_confirmation', list(clouds.values())[0] if clouds else None)
        if not primary_cloud:
            return None
        
        # Apply filters
        passed_filters, failed_filters = self.signal_filter.apply_all_filters(
            row, direction, timestamp
        )
        
        # Calculate signal strength
        strength = self._calculate_signal_strength(
            clouds=clouds,
            row=row,
            passed_filters=passed_filters,
            failed_filters=failed_filters
        )
        
        # Calculate risk management levels
        atr = row.get('atr', row['close'] * 0.02)
        if pd.isna(atr):
            atr = row['close'] * 0.02
        price = row['close']
        
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
            rsi=row.get('rsi') if not pd.isna(row.get('rsi')) else None,
            adx=row.get('adx') if not pd.isna(row.get('adx')) else None,
            volume_ratio=row.get('volume_ratio') if not pd.isna(row.get('volume_ratio')) else None,
            vwap_confirmed=row.get('close', 0) > row.get('vwap', 0) if direction == "long" else row.get('close', 0) < row.get('vwap', 0),
            macd_confirmed=row.get('macd_histogram', 0) > 0 if direction == "long" else row.get('macd_histogram', 0) < 0,
            suggested_stop=stop_loss,
            suggested_target=target,
            risk_reward_ratio=rr_ratio,
            filters_passed=passed_filters,
            filters_failed=failed_filters,
            sector=sector,
            etf_symbol=etf_symbol,
            notes=[raw_signal]
        )
    
    def _calculate_signal_strength(
        self,
        clouds: Dict[str, CloudData],
        row: pd.Series,
        passed_filters: List[str],
        failed_filters: List[str]
    ) -> SignalStrength:
        """Calculate signal strength based on multiple factors"""
        
        score = 50
        
        # Cloud alignment bonus (up to +20)
        bullish_count = sum(1 for c in clouds.values() 
                          if c.state in [CloudState.BULLISH, CloudState.CROSSING_UP])
        alignment_ratio = bullish_count / len(clouds) if clouds else 0.5
        # Adjust for bearish signals
        if alignment_ratio < 0.5:
            alignment_ratio = 1 - alignment_ratio
        score += (alignment_ratio - 0.5) * 40
        
        # Filter results (+/- 20)
        filter_ratio = len(passed_filters) / (len(passed_filters) + len(failed_filters)) if (passed_filters or failed_filters) else 0.5
        score += (filter_ratio - 0.5) * 40
        
        # ADX bonus (up to +10)
        adx = row.get('adx')
        if adx is not None:
            if adx > 30:
                score += 10
            elif adx > 20:
                score += 5
            else:
                score -= 5
        
        # Volume bonus (up to +10)
        volume_ratio = row.get('volume_ratio')
        if volume_ratio is not None:
            if volume_ratio > 2.0:
                score += 10
            elif volume_ratio > 1.5:
                score += 5
        
        # Cloud expansion bonus (up to +5)
        primary_cloud = clouds.get('trend_confirmation')
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
    
    def get_sector_trend_state(
        self,
        df: pd.DataFrame,
        symbol: str,
        sector_name: str
    ) -> SectorTrendState:
        """
        Get current trend state for a sector ETF.
        Used to filter individual stock signals.
        """
        prepared_df = self.prepare_data(df)
        analysis = self.analyze_trend(prepared_df, symbol)
        
        # Count trend duration
        trend_duration = 0
        current_trend = analysis.overall_trend
        
        for i in range(len(prepared_df) - 1, 0, -1):
            prev_analysis = self.analyze_trend(prepared_df, symbol, i)
            if prev_analysis.overall_trend == current_trend:
                trend_duration += 1
            else:
                break
        
        # Get cloud states
        clouds = self.cloud_indicator.analyze_single(prepared_df, -1)
        cloud_states = {name: cloud.state for name, cloud in clouds.items()}
        
        # Calculate support/resistance from clouds
        primary_cloud = clouds.get('trend_confirmation')
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
            resistance_level=resistance
        )
    
    def filter_by_sector_trend(
        self,
        stock_signal: Signal,
        sector_trend: SectorTrendState
    ) -> bool:
        """
        Filter stock signal based on sector ETF trend.
        
        Rules:
        - Long signals only when sector is bullish
        - Short signals only when sector is bearish
        - Neutral sector = no filter (allow both)
        """
        if sector_trend.trend_direction == "neutral":
            return True
        
        if stock_signal.direction == "long" and sector_trend.is_bullish():
            return True
        elif stock_signal.direction == "short" and sector_trend.is_bearish():
            return True
        else:
            stock_signal.filters_failed.append(
                f"sector_trend: {sector_trend.sector_name} trend is {sector_trend.trend_direction}, "
                f"signal direction is {stock_signal.direction}"
            )
            return False
        
        # Cloud alignment bonus (up to +20)
        bullish_clouds = sum(1 for c in clouds.values() 
                           if c.state in [CloudState.BULLISH, CloudState.CROSSING_UP])
        alignment_ratio = bullish_clouds / len(clouds) if clouds else 0.5
        score += (alignment_ratio - 0.5) * 40
        
        # Filter results (+3 per passed, -10 per failed)
        score += len(passed_filters) * 3
        score -= len(failed_filters) * 10
        
        # ADX contribution (trend strength)
        adx = row.get('adx')
        if adx is not None and not pd.isna(adx):
            if adx > 30:
                score += 15
            elif adx > 20:
                score += 5
            else:
                score -= 10
        
        # Volume contribution
        volume_ratio = row.get('volume_ratio')
        if volume_ratio is not None and not pd.isna(volume_ratio):
            if volume_ratio > 2.0:
                score += 10
            elif volume_ratio > 1.5:
                score += 5
        
        # Cloud thickness (expanding cloud is stronger)
        primary_cloud = clouds.get('trend_confirmation')
        if primary_cloud and primary_cloud.is_expanding:
            score += 10
        
        # Normalize to SignalStrength
        if score >= 80:
            return SignalStrength.VERY_STRONG
        elif score >= 65:
            return SignalStrength.STRONG
        elif score >= 50:
            return SignalStrength.MODERATE
        elif score >= 35:
            return SignalStrength.WEAK
        else:
            return SignalStrength.VERY_WEAK
    
    def get_sector_trend_state(
        self,
        df: pd.DataFrame,
        symbol: str,
        sector_name: str
    ) -> SectorTrendState:
        """
        Get the current trend state for a sector ETF.
        Used to filter individual stock signals.
        """
        prepared_df = self.prepare_data(df)
        analysis = self.analyze_trend(prepared_df, symbol)
        
        # Calculate trend duration
        trend_duration = 1
        current_trend = analysis.overall_trend
        
        for i in range(2, min(100, len(prepared_df))):
            past_analysis = self.analyze_trend(prepared_df, symbol, -i)
            if past_analysis.overall_trend == current_trend:
                trend_duration += 1
            else:
                break
        
        # Get support/resistance from cloud levels
        clouds = analysis.clouds
        primary_cloud = clouds.get('trend_confirmation')
        
        support = None
        resistance = None
        if primary_cloud:
            if current_trend == "bullish":
                support = primary_cloud.cloud_bottom
                resistance = primary_cloud.cloud_top * 1.02  # 2% above
            else:
                resistance = primary_cloud.cloud_top
                support = primary_cloud.cloud_bottom * 0.98  # 2% below
        
        return SectorTrendState(
            symbol=symbol,
            sector_name=sector_name,
            timestamp=analysis.timestamp,
            trend_direction=current_trend,
            trend_strength=analysis.trend_strength,
            trend_duration=trend_duration,
            cloud_states={name: cloud.state for name, cloud in clouds.items()},
            cloud_alignment=analysis.trend_alignment,
            support_level=support,
            resistance_level=resistance
        )
    
    def filter_signal_by_sector(
        self,
        signal: Signal,
        sector_state: SectorTrendState
    ) -> Tuple[bool, str]:
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
                    return True, f"Sector {sector_state.sector_name} weak bullish - proceed with caution"
            elif sector_state.is_bearish():
                return False, f"Sector {sector_state.sector_name} bearish - avoid long entries"
            else:
                return True, f"Sector {sector_state.sector_name} neutral - use other confirmations"
        else:  # short
            if sector_state.is_bearish():
                if sector_state.trend_strength >= 50:
                    return True, f"Sector {sector_state.sector_name} confirms bearish bias"
                else:
                    return True, f"Sector {sector_state.sector_name} weak bearish - proceed with caution"
            elif sector_state.is_bullish():
                return False, f"Sector {sector_state.sector_name} bullish - avoid short entries"
            else:
                return True, f"Sector {sector_state.sector_name} neutral - use other confirmations"
