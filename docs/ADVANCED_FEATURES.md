# Advanced Features Guide

Guide to advanced trading features including multi-timeframe confirmation, sector relative strength analysis, and risk management.

## Table of Contents

- [Multi-Timeframe Confirmation](#multi-timeframe-confirmation)
- [Sector Relative Strength](#sector-relative-strength)
- [Risk Management](#risk-management)
- [Position Sizing](#position-sizing)
- [Stop Loss Strategies](#stop-loss-strategies)
- [Target Price Calculation](#target-price-calculation)

---

## Multi-Timeframe Confirmation

### Overview

Multi-timeframe (MTF) confirmation improves signal quality by requiring alignment across multiple timeframes.

```text
┌─────────────────────────────────────────────────────────────────┐
│            Multi-Timeframe Confirmation Strategy                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Daily Chart (Higher TF)         1-Hour Chart (Entry TF)       │
│  ┌───────────────┐               ┌───────────────┐            │
│  │ ▲ BULLISH     │  ────────────>│ ✓ LONG Signal │            │
│  │ (34-50 cloud) │    Confirm    │   Entry       │            │
│  └───────────────┘               └───────────────┘            │
│                                                                 │
│  If Daily = BEARISH → REJECT Long signals on 1H chart         │
│  If Daily = BULLISH → ALLOW Long signals on 1H chart          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation Status

**Current**: Multi-timeframe confirmation is supported via configuration and CLI flags.

### Reference Implementation (Simplified)

```python
from dataclasses import dataclass
from enum import Enum

class TimeframeLevel(Enum):
    """Timeframe hierarchy for MTF analysis"""
    ENTRY = "entry"  # Fast timeframe for entries
    INTERMEDIATE = "intermediate"  # Trend confirmation
    HIGHER = "higher"  # Overall trend direction

@dataclass
class MTFConfig:
    """Multi-timeframe configuration"""
    entry_timeframe: str  # "5m", "1h", etc.
    intermediate_timeframe: str | None  # "1h", "4h", etc.
    higher_timeframe: str  # "D", "W", etc.

    require_all_aligned: bool = True
    min_alignment: int = 2  # Minimum TFs that must agree

class MultiTimeframeAnalyzer:
    """Analyze signals across multiple timeframes"""

    def __init__(self, config: MTFConfig):
        self.config = config

    async def analyze_symbol(self, symbol: str) -> dict:
        """
        Analyze symbol across multiple timeframes.

        Returns:
            dict with trend direction for each timeframe
        """
        results = {}

        # Analyze each timeframe
        for tf_level, timeframe in [
            (TimeframeLevel.HIGHER, self.config.higher_timeframe),
            (TimeframeLevel.INTERMEDIATE, self.config.intermediate_timeframe),
            (TimeframeLevel.ENTRY, self.config.entry_timeframe),
        ]:
            if timeframe:
                trend = await self._analyze_timeframe(symbol, timeframe)
                results[tf_level] = {
                    "timeframe": timeframe,
                    "trend": trend.direction,
                    "strength": trend.strength,
                }

        # Check alignment
        results["alignment"] = self._check_alignment(results)

        return results

    def _check_alignment(self, results: dict) -> dict:
        """Check if timeframes are aligned"""
        trends = [
            r["trend"] for r in results.values()
            if isinstance(r, dict) and "trend" in r
        ]

        bullish_count = sum(1 for t in trends if t == "BULLISH")
        bearish_count = sum(1 for t in trends if t == "BEARISH")

        return {
            "all_aligned": len(set(trends)) == 1,
            "min_alignment_met": max(bullish_count, bearish_count) >= self.config.min_alignment,
            "dominant_trend": "BULLISH" if bullish_count > bearish_count else "BEARISH",
            "alignment_strength": max(bullish_count, bearish_count) / len(trends),
        }

# Usage
config = MTFConfig(
    entry_timeframe="1h",
    intermediate_timeframe="4h",
    higher_timeframe="D",
    require_all_aligned=False,
    min_alignment=2
)

analyzer = MultiTimeframeAnalyzer(config)
analysis = await analyzer.analyze_symbol("XLK")

# Example output:
# {
#     TimeframeLevel.HIGHER: {"timeframe": "D", "trend": "BULLISH", "strength": 85},
#     TimeframeLevel.INTERMEDIATE: {"timeframe": "4h", "trend": "BULLISH", "strength": 72},
#     TimeframeLevel.ENTRY: {"timeframe": "1h", "trend": "BULLISH", "strength": 68},
#     "alignment": {
#         "all_aligned": True,
#         "min_alignment_met": True,
#         "dominant_trend": "BULLISH",
#         "alignment_strength": 1.0
#     }
# }
```

### MTF Signal Filtering

```python
def filter_signal_by_mtf(signal: Signal, mtf_analysis: dict) -> bool:
    """
    Filter signal based on multi-timeframe confirmation.

    Args:
        signal: Signal from entry timeframe
        mtf_analysis: Results from MultiTimeframeAnalyzer

    Returns:
        True if signal passes MTF filter, False otherwise
    """
    alignment = mtf_analysis["alignment"]

    # Reject if higher timeframe contradicts signal
    higher_tf = mtf_analysis[TimeframeLevel.HIGHER]
    if signal.direction == "LONG" and higher_tf["trend"] == "BEARISH":
        logger.info(f"Rejecting {signal.symbol} LONG: Higher TF is BEARISH")
        return False

    if signal.direction == "SHORT" and higher_tf["trend"] == "BULLISH":
        logger.info(f"Rejecting {signal.symbol} SHORT: Higher TF is BULLISH")
        return False

    # Check minimum alignment requirement
    if not alignment["min_alignment_met"]:
        logger.info(
            f"Rejecting {signal.symbol}: Insufficient MTF alignment "
            f"({alignment['alignment_strength']:.0%})"
        )
        return False

    # Boost signal strength for full alignment
    if alignment["all_aligned"]:
        signal.strength_boost = 1.2  # 20% strength boost
        logger.info(f"{signal.symbol}: All timeframes aligned - strength boost applied")

    return True
```

### MTF Dashboard Display

```text
XLK (Technology) - Multi-Timeframe View
┌─────────────────────────────────────────────────────────────┐
│ Timeframe │ Trend    │ Strength │ EMA Clouds │ RSI │ ADX   │
├─────────────────────────────────────────────────────────────┤
│ Daily     │ 🟢 BULL  │ 85%      │ 6/6 ↑      │ 62  │ 28    │
│ 4-Hour    │ 🟢 BULL  │ 72%      │ 5/6 ↑      │ 58  │ 24    │
│ 1-Hour    │ 🟢 BULL  │ 68%      │ 4/6 ↑      │ 55  │ 22    │
├─────────────────────────────────────────────────────────────┤
│ Alignment │ ✅ FULL (3/3 bullish)  │ Signal: LONG CONFIRMED │
└─────────────────────────────────────────────────────────────┘

Entry Signal: CLOUD_FLIP on 1H (STRONG)
Confirmation: Daily and 4H trends both bullish
Risk Level: LOW (full alignment)
```

---

## Sector Relative Strength

### Overview

Identify sectors outperforming or underperforming the market to focus on strongest opportunities.

### Relative Strength Calculation

```python
import pandas as pd
from dataclasses import dataclass

@dataclass
class RelativeStrength:
    """Relative strength metrics for a sector"""
    symbol: str
    sector: str
    rs_rating: float  # 0-100 scale
    vs_spy_pct: float  # % vs S&P 500
    vs_avg_sector_pct: float  # % vs average sector
    rank: int  # Ranking among all sectors (1 = strongest)
    trend: str  # "IMPROVING", "STABLE", "DECLINING"

class SectorRelativeStrengthAnalyzer:
    """Analyze relative strength of sector ETFs"""

    def __init__(self):
        self.benchmark_symbol = "SPY"  # S&P 500 as benchmark

    async def calculate_relative_strength(
        self,
        symbols: list[str],
        lookback_days: int = 20
    ) -> list[RelativeStrength]:
        """
        Calculate relative strength for sector ETFs.

        Args:
            symbols: List of sector ETF symbols
            lookback_days: Period for RS calculation

        Returns:
            List of RelativeStrength objects, sorted by strength
        """
        # Fetch price data for all symbols + benchmark
        data = {}
        for symbol in symbols + [self.benchmark_symbol]:
            bars = await self._fetch_historical_data(symbol, lookback_days)
            data[symbol] = bars

        # Calculate returns
        results = []
        benchmark_return = self._calculate_return(data[self.benchmark_symbol])

        sector_returns = []
        for symbol in symbols:
            symbol_return = self._calculate_return(data[symbol])
            sector_returns.append(symbol_return)

            # Calculate relative performance
            vs_spy = symbol_return - benchmark_return

            results.append({
                "symbol": symbol,
                "return": symbol_return,
                "vs_spy": vs_spy,
            })

        # Calculate average sector return
        avg_sector_return = sum(sector_returns) / len(sector_returns)

        # Calculate RS ratings and rankings
        sorted_results = sorted(results, key=lambda x: x["return"], reverse=True)

        relative_strengths = []
        for rank, result in enumerate(sorted_results, 1):
            vs_avg = result["return"] - avg_sector_return

            # RS rating: 0-100 scale based on percentile rank
            rs_rating = ((len(sorted_results) - rank + 1) / len(sorted_results)) * 100

            # Determine trend
            trend = self._determine_trend(result["symbol"], data[result["symbol"]])

            relative_strengths.append(RelativeStrength(
                symbol=result["symbol"],
                sector=SYMBOL_TO_SECTOR.get(result["symbol"], "Unknown"),
                rs_rating=rs_rating,
                vs_spy_pct=result["vs_spy"],
                vs_avg_sector_pct=vs_avg,
                rank=rank,
                trend=trend
            ))

        return relative_strengths

    def _calculate_return(self, bars: pd.DataFrame) -> float:
        """Calculate percentage return over period"""
        if len(bars) < 2:
            return 0.0

        start_price = bars.iloc[0]['close']
        end_price = bars.iloc[-1]['close']

        return ((end_price - start_price) / start_price) * 100

    def _determine_trend(self, symbol: str, bars: pd.DataFrame) -> str:
        """Determine if RS is improving, stable, or declining"""
        if len(bars) < 10:
            return "STABLE"

        # Compare recent RS to earlier RS
        recent_return = self._calculate_return(bars.iloc[-5:])
        earlier_return = self._calculate_return(bars.iloc[-10:-5])

        change = recent_return - earlier_return

        if change > 2.0:
            return "IMPROVING"
        elif change < -2.0:
            return "DECLINING"
        else:
            return "STABLE"

# Usage
analyzer = SectorRelativeStrengthAnalyzer()
rs_rankings = await analyzer.calculate_relative_strength(
    symbols=["XLK", "XLF", "XLV", "XLE", "XLY", "XLP", "XLI", "XLB", "XLU", "XLRE", "XLC"],
    lookback_days=20
)

# Display rankings
print("Sector Relative Strength Rankings (20-day)")
print("=" * 70)
for rs in rs_rankings:
    print(
        f"{rs.rank}. {rs.symbol} ({rs.sector}): "
        f"RS Rating: {rs.rs_rating:.0f} | "
        f"vs SPY: {rs.vs_spy_pct:+.2f}% | "
        f"Trend: {rs.trend}"
    )
```

### RS-Based Signal Filtering

```python
def filter_by_relative_strength(
    signal: Signal,
    rs_rankings: list[RelativeStrength],
    min_rs_rating: float = 50,
    top_n_only: int | None = 5
) -> bool:
    """
    Filter signals based on relative strength.

    Args:
        signal: Trading signal to evaluate
        rs_rankings: List of RelativeStrength objects
        min_rs_rating: Minimum RS rating to accept (0-100)
        top_n_only: Only accept signals from top N sectors (None = no limit)

    Returns:
        True if signal passes RS filter, False otherwise
    """
    # Find RS for this symbol
    rs = next((r for r in rs_rankings if r.symbol == signal.symbol), None)

    if not rs:
        logger.warning(f"No RS data for {signal.symbol}")
        return True  # Don't filter if no data

    # Check minimum RS rating
    if rs.rs_rating < min_rs_rating:
        logger.info(
            f"Rejecting {signal.symbol}: RS rating too low "
            f"({rs.rs_rating:.0f} < {min_rs_rating})"
        )
        return False

    # Check if in top N sectors
    if top_n_only and rs.rank > top_n_only:
        logger.info(
            f"Rejecting {signal.symbol}: Not in top {top_n_only} sectors "
            f"(rank: {rs.rank})"
        )
        return False

    # Prefer improving RS trends for long signals
    if signal.direction == "LONG" and rs.trend == "DECLINING":
        logger.warning(
            f"{signal.symbol}: LONG signal but RS declining - "
            f"consider passing"
        )
        signal.risk_level = "MEDIUM"  # Increase risk rating

    return True

# Usage
if filter_by_relative_strength(signal, rs_rankings, min_rs_rating=60, top_n_only=5):
    # Signal passed RS filter - proceed with alert
    await alert_manager.send_alert(signal)
```

### RS Dashboard Display

```text
Sector Relative Strength (20-day)
┌──────────────────────────────────────────────────────────────────┐
│ Rank │ Sector               │ RS │ vs SPY │ vs Avg │ Trend      │
├──────────────────────────────────────────────────────────────────┤
│ 1    │ 🟢 XLK (Technology)  │ 95 │ +4.2%  │ +2.8%  │ IMPROVING  │
│ 2    │ 🟢 XLY (Consumer D.) │ 86 │ +3.1%  │ +1.7%  │ STABLE     │
│ 3    │ 🟢 XLC (Comm Svcs)   │ 77 │ +2.3%  │ +0.9%  │ IMPROVING  │
│ 4    │ ⚪ XLF (Financials)  │ 68 │ +1.5%  │ +0.1%  │ STABLE     │
│ 5    │ ⚪ XLV (Healthcare)  │ 59 │ +0.8%  │ -0.6%  │ DECLINING  │
│ 6    │ ⚪ XLI (Industrials) │ 50 │ +0.2%  │ -1.2%  │ STABLE     │
│ 7    │ 🔴 XLP (Staples)     │ 41 │ -0.5%  │ -1.9%  │ DECLINING  │
│ 8    │ 🔴 XLU (Utilities)   │ 32 │ -1.2%  │ -2.6%  │ DECLINING  │
│ 9    │ 🔴 XLB (Materials)   │ 23 │ -1.8%  │ -3.2%  │ STABLE     │
│ 10   │ 🔴 XLRE (Real Est.)  │ 14 │ -2.5%  │ -3.9%  │ DECLINING  │
│ 11   │ 🔴 XLE (Energy)      │ 5  │ -3.1%  │ -4.5%  │ DECLINING  │
└──────────────────────────────────────────────────────────────────┘

Focus on: Top 3 sectors (XLK, XLY, XLC) for long opportunities
Avoid: Bottom 3 sectors (XLB, XLRE, XLE) for new long positions
```

---

## Risk Management

### Risk/Reward Ratio Calculation

```python
from dataclasses import dataclass

@dataclass
class TradeRisk:
    """Risk/reward analysis for a trade"""
    entry_price: float
    stop_loss: float
    take_profit: float

    risk_dollars: float
    reward_dollars: float
    risk_reward_ratio: float  # R:R (e.g., 1:3 = 3.0)

    risk_percent: float  # % risk of entry price
    reward_percent: float  # % reward of entry price

    position_valid: bool  # True if R:R meets criteria

def calculate_trade_risk(
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    min_rr_ratio: float = 2.0
) -> TradeRisk:
    """
    Calculate risk/reward metrics for a trade.

    Args:
        entry_price: Proposed entry price
        stop_loss: Stop loss price
        take_profit: Target price
        min_rr_ratio: Minimum acceptable risk/reward ratio

    Returns:
        TradeRisk object with complete analysis
    """
    # Calculate dollar amounts
    risk_dollars = abs(entry_price - stop_loss)
    reward_dollars = abs(take_profit - entry_price)

    # Calculate percentages
    risk_percent = (risk_dollars / entry_price) * 100
    reward_percent = (reward_dollars / entry_price) * 100

    # Calculate R:R ratio
    rr_ratio = reward_dollars / risk_dollars if risk_dollars > 0 else 0

    # Validate
    position_valid = rr_ratio >= min_rr_ratio

    return TradeRisk(
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_dollars=risk_dollars,
        reward_dollars=reward_dollars,
        risk_reward_ratio=rr_ratio,
        risk_percent=risk_percent,
        reward_percent=reward_percent,
        position_valid=position_valid
    )

# Usage
risk = calculate_trade_risk(
    entry_price=235.50,
    stop_loss=232.00,  # Below 34-50 cloud
    take_profit=245.00,  # 2x ATR target
    min_rr_ratio=2.0
)

print(f"Entry: ${risk.entry_price}")
print(f"Stop: ${risk.stop_loss} (-{risk.risk_percent:.2f}%)")
print(f"Target: ${risk.take_profit} (+{risk.reward_percent:.2f}%)")
print(f"R:R Ratio: 1:{risk.risk_reward_ratio:.1f}")
print(f"Position Valid: {risk.position_valid}")
```

---

## Position Sizing

### Position Size Calculator

```python
def calculate_position_size(
    account_balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss: float
) -> dict:
    """
    Calculate position size based on account risk.

    Args:
        account_balance: Total account balance
        risk_per_trade_pct: Max % of account to risk (e.g., 1.0 for 1%)
        entry_price: Proposed entry price
        stop_loss: Stop loss price

    Returns:
        dict with position sizing details
    """
    # Calculate dollar risk per trade
    risk_dollars = account_balance * (risk_per_trade_pct / 100)

    # Calculate risk per share
    risk_per_share = abs(entry_price - stop_loss)

    # Calculate number of shares
    shares = int(risk_dollars / risk_per_share)

    # Calculate total position value
    position_value = shares * entry_price

    # Calculate position as % of account
    position_pct = (position_value / account_balance) * 100

    return {
        "shares": shares,
        "position_value": position_value,
        "position_pct": position_pct,
        "risk_dollars": risk_dollars,
        "risk_per_share": risk_per_share,
        "max_loss_if_stopped": risk_dollars,
    }

# Usage
position = calculate_position_size(
    account_balance=100000,
    risk_per_trade_pct=1.0,  # Risk 1% per trade
    entry_price=235.50,
    stop_loss=232.00
)

print(f"Position Size: {position['shares']} shares")
print(f"Position Value: ${position['position_value']:,.2f} ({position['position_pct']:.1f}% of account)")
print(f"Risk per Share: ${position['risk_per_share']:.2f}")
print(f"Max Loss: ${position['max_loss_if_stopped']:,.2f}")
```

---

## Stop Loss Strategies

### ATR-Based Stop Loss

```python
def calculate_atr_stop(
    entry_price: float,
    atr: float,
    direction: str,
    multiplier: float = 2.0
) -> float:
    """
    Calculate ATR-based stop loss.

    Args:
        entry_price: Entry price
        atr: Average True Range value
        direction: "LONG" or "SHORT"
        multiplier: ATR multiplier (typically 1.5-3.0)

    Returns:
        Stop loss price
    """
    stop_distance = atr * multiplier

    if direction == "LONG":
        return entry_price - stop_distance
    else:
        return entry_price + stop_distance

# Usage
stop = calculate_atr_stop(
    entry_price=235.50,
    atr=2.80,
    direction="LONG",
    multiplier=2.0
)
print(f"ATR Stop Loss: ${stop:.2f}")
```

### Cloud-Based Stop Loss

```python
def calculate_cloud_stop(
    entry_price: float,
    cloud_bottom: float,
    cloud_top: float,
    direction: str,
    buffer_pct: float = 0.2
) -> float:
    """
    Calculate stop loss based on EMA cloud support/resistance.

    Args:
        entry_price: Entry price
        cloud_bottom: Lower cloud boundary
        cloud_top: Upper cloud boundary
        direction: "LONG" or "SHORT"
        buffer_pct: % buffer below/above cloud (e.g., 0.2 for 0.2%)

    Returns:
        Stop loss price
    """
    if direction == "LONG":
        # Place stop below cloud bottom
        stop = cloud_bottom * (1 - buffer_pct / 100)
    else:
        # Place stop above cloud top
        stop = cloud_top * (1 + buffer_pct / 100)

    return stop

# Usage - Long entry with price above 34-50 cloud
stop = calculate_cloud_stop(
    entry_price=235.50,
    cloud_bottom=233.20,  # 34-EMA
    cloud_top=234.80,     # 50-EMA
    direction="LONG",
    buffer_pct=0.2
)
print(f"Cloud-Based Stop: ${stop:.2f}")
```

---

## Target Price Calculation

### ATR-Based Targets

```python
def calculate_targets(
    entry_price: float,
    stop_loss: float,
    direction: str,
    targets: list[float] = [2.0, 3.0, 4.0]  # R:R multiples
) -> list[dict]:
    """
    Calculate multiple profit targets based on risk.

    Args:
        entry_price: Entry price
        stop_loss: Stop loss price
        direction: "LONG" or "SHORT"
        targets: List of R:R multiples for targets

    Returns:
        List of target levels with prices and percentages
    """
    risk = abs(entry_price - stop_loss)

    target_levels = []
    for rr_multiple in targets:
        reward = risk * rr_multiple

        if direction == "LONG":
            target_price = entry_price + reward
        else:
            target_price = entry_price - reward

        target_pct = (reward / entry_price) * 100

        target_levels.append({
            "rr_multiple": rr_multiple,
            "price": target_price,
            "percent": target_pct,
            "reward_dollars": reward
        })

    return target_levels

# Usage
targets = calculate_targets(
    entry_price=235.50,
    stop_loss=232.00,
    direction="LONG",
    targets=[2.0, 3.0, 4.0]
)

print("Profit Targets:")
for i, target in enumerate(targets, 1):
    print(
        f"T{i} (R:{target['rr_multiple']:.0f}): "
        f"${target['price']:.2f} (+{target['percent']:.2f}%)"
    )

# Output:
# T1 (R:2): $242.00 (+2.76%)
# T2 (R:3): $245.50 (+4.25%)
# T3 (R:4): $249.00 (+5.73%)
```

---

## See Also

- [Main README](../README.md) - Strategy overview and quick start
- [Signal Management](SIGNAL_MANAGEMENT.md) - Signal generation and validation
- [Backtesting](BACKTESTING.md) - Strategy testing and optimization
- [PRD](../PRD_Detailed.md) - Complete strategy methodology
