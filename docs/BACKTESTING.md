# Backtesting Guide

Complete guide to backtesting the EMA Cloud strategy with historical data.

## Table of Contents

- [Overview](#overview)
- [Backtest Engine](#backtest-engine)
- [Running Backtests](#running-backtests)
- [Performance Metrics](#performance-metrics)
- [Trade Analysis](#trade-analysis)
- [Parameter Optimization](#parameter-optimization)
- [Walk-Forward Testing](#walk-forward-testing)

---

## Overview

The backtesting engine simulates trading signals on historical data to evaluate strategy performance before risking real capital.

### What Gets Backtested

```text
┌─────────────────────────────────────────────────────────────┐
│              Backtest Simulation Process                    │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │  Load Historical Data  │
            │     (OHLCV bars)       │
            └───────────┬────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │  Calculate Indicators  │
            │   (6 EMA clouds + RSI  │
            │    ADX, Volume, etc)   │
            └───────────┬────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │   Generate Signals     │
            │ (Cloud flips, crosses) │
            └───────────┬────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │   Simulate Trades      │
            │ (Entry, Exit, Stops)   │
            └───────────┬────────────┘
                        │
                        ▼
            ┌────────────────────────┐
            │  Calculate Metrics     │
            │ (Win rate, P&L, etc)   │
            └────────────────────────┘
```

### Backtest Components

| Component            | Description                              | Implementation          |
|---------------------|------------------------------------------|-------------------------|
| **Historical Data**  | OHLCV bars from data provider            | Yahoo Finance (default) |
| **Signal Generator** | Detects patterns in historical data      | Same as live scanner    |
| **Trade Simulator**  | Simulates entry/exit execution           | Backtester class        |
| **Exit Strategy**    | Stop loss, take profit, time-based       | Configurable rules      |
| **Performance**      | Win rate, Sharpe, drawdown, etc.         | BacktestResult metrics  |

---

## Backtest Engine

### Backtester Class

Located in: `packages/ema_cloud_lib/src/ema_cloud_lib/backtesting/engine.py`

```python
import asyncio
from datetime import datetime

from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

async def run_backtest():
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    df = await data_manager.get_historical_data(
        symbol="XLK",
        interval="1d",
        start=datetime(2025, 1, 1),
        end=datetime(2025, 12, 31),
    )

    backtester = Backtester(initial_capital=100000.0)
    result = backtester.run(df, "XLK")
    print(result.format_report())

asyncio.run(run_backtest())
```

**Note:** `Backtester.run()` uses a built-in EMA cross signal generator unless you pass a custom `signals_df`.

### Trade Class

Represents a single trade execution:

```python
@dataclass
class Trade:
    # Entry details
    entry_time: datetime
    entry_price: float
    direction: str  # "long" or "short"
    signal_type: str  # "CLOUD_FLIP", "PRICE_CROSS", etc.
    signal_strength: str  # "VERY_STRONG", "STRONG", etc.

    # Exit details
    exit_time: datetime | None
    exit_price: float | None
    exit_reason: str | None  # "stop_loss", "take_profit", "time", "signal"

    # Risk management
    stop_loss: float | None
    take_profit: float | None

    # Performance
    pnl: float  # Profit/loss amount
    pnl_pct: float  # Profit/loss percentage
    is_winner: bool  # True if profitable
    bars_held: int  # How long trade was held
```

### BacktestResult Class

Contains complete backtest performance metrics:

```python
@dataclass
class BacktestResult:
    symbol: str
    start_date: datetime
    end_date: datetime
    initial_capital: float
    final_capital: float
    trades: list[Trade]

    # Performance metrics
    total_return: float
    total_return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float  # Percentage

    avg_win: float
    avg_loss: float
    profit_factor: float  # Gross profit / Gross loss
    expectancy: float  # Average $ per trade

    max_drawdown: float
    max_drawdown_pct: float
    sharpe_ratio: float

    avg_bars_held: float
    avg_winner_bars: float
    avg_loser_bars: float
```

---

## Running Backtests

### Basic Backtest

```python
import asyncio
from datetime import datetime

from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

async def run_basic_backtest():
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    df = await data_manager.get_historical_data(
        symbol="XLK",
        interval="1d",
        start=datetime(2025, 1, 1),
        end=datetime(2025, 12, 31),
    )

    # Run backtest
    backtester = Backtester(initial_capital=100000.0)
    result = backtester.run(df, "XLK")

    # Display results
    print(result.format_report())

# Run
asyncio.run(run_basic_backtest())
```

### Multi-Symbol Backtest

```python
from datetime import datetime

from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

async def run_multi_symbol_backtest():
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    backtester = Backtester(initial_capital=100000.0)

    symbols = ["XLK", "XLF", "XLV", "XLE"]
    results = {}

    for symbol in symbols:
        df = await data_manager.get_historical_data(
            symbol=symbol,
            interval="1d",
            start=datetime(2025, 1, 1),
            end=datetime(2025, 12, 31),
        )
        results[symbol] = backtester.run(df, symbol)

    for symbol, result in results.items():
        print(f\"\\n{symbol}: {result.total_return_pct:.2f}% return, \"
              f\"{result.win_rate:.1f}% win rate\")

asyncio.run(run_multi_symbol_backtest())
```

### Custom Date Range

```python
from datetime import datetime, timedelta
from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

async def backtest_last_year():
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    backtester = Backtester(initial_capital=50000.0)

    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    df = await data_manager.get_historical_data(
        symbol="XLK",
        interval="1d",
        start=start_date,
        end=end_date,
    )

    return backtester.run(df, "XLK")

asyncio.run(backtest_last_year())
```

### CLI Backtest Command

```bash
# Basic usage
ema-scanner backtest XLK --start-date 2025-01-01 --end-date 2025-12-31 --capital 100000

# Multiple symbols
ema-scanner backtest XLK XLF XLV --start-date 2025-01-01 --end-date 2025-12-31

# With custom config
ema-scanner backtest XLK XLF --start-date 2025-01-01 --end-date 2025-12-31 --style swing

# Export results
ema-scanner backtest XLK --start-date 2025-01-01 --end-date 2025-12-31 --report backtest_results.json
```

---

## Performance Metrics

### Backtest Report Format

```text
BACKTEST RESULTS: XLK (Technology)
═══════════════════════════════════════════════════════════════════
Period: 2025-01-01 to 2025-12-31 (365 days)
Initial Capital: $100,000.00
Final Capital: $118,500.00
Total Return: $18,500.00 (+18.50%)

TRADE STATISTICS
───────────────────────────────────────────────────────────────────
Total Trades: 47
Winning Trades: 28 (59.6%)
Losing Trades: 19 (40.4%)

Average Win: $1,250.00 (+2.1%)
Average Loss: $780.00 (-1.3%)
Profit Factor: 2.12 (wins/losses ratio)
Expectancy: $394.68 (avg per trade)

Largest Win: $2,800.00 (+4.7%)
Largest Loss: $1,450.00 (-2.4%)

RISK METRICS
───────────────────────────────────────────────────────────────────
Max Drawdown: $8,200.00 (-7.2%)
Sharpe Ratio: 1.45 (risk-adjusted return)
Avg Bars Held: 12.3 bars

Winners Held: 10.5 bars (avg)
Losers Held: 15.2 bars (avg)

SIGNAL BREAKDOWN
───────────────────────────────────────────────────────────────────
CLOUD_FLIP: 18 trades (38.3%) - 61.1% win rate
PRICE_CROSS: 22 trades (46.8%) - 59.1% win rate
PULLBACK_ENTRY: 7 trades (14.9%) - 57.1% win rate

VERY_STRONG signals: 12 trades - 75.0% win rate
STRONG signals: 20 trades - 65.0% win rate
MODERATE signals: 15 trades - 40.0% win rate
═══════════════════════════════════════════════════════════════════
```

### Key Metrics Explained

#### Win Rate

```python
win_rate = (winning_trades / total_trades) * 100

# Example: 28 winners out of 47 trades
win_rate = (28 / 47) * 100 = 59.6%
```

**Interpretation**:
>
- > 60%: Excellent
- 50-60%: Good
- 40-50%: Acceptable (if profit factor > 1.5)
- < 40%: Poor (needs improvement)

#### Profit Factor

```python
gross_profit = sum(win.pnl for win in winning_trades)
gross_loss = abs(sum(loss.pnl for loss in losing_trades))
profit_factor = gross_profit / gross_loss

# Example:
# Gross profit: $35,000
# Gross loss: $16,500
profit_factor = 35000 / 16500 = 2.12
```

**Interpretation**:
>
- > 2.0: Excellent
- 1.5-2.0: Good
- 1.0-1.5: Acceptable
- < 1.0: Losing strategy (gross losses > gross profits)

#### Expectancy

```python
expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)

# Example:
# Win rate: 59.6%, avg win: $1,250
# Loss rate: 40.4%, avg loss: $780
expectancy = (0.596 * 1250) - (0.404 * 780) = $394.68
```

**Interpretation**:

- Positive expectancy: Strategy is profitable long-term
- Negative expectancy: Strategy loses money long-term
- Higher is better (measures average profit per trade)

#### Maximum Drawdown

```python
# Percentage peak-to-trough decline
drawdowns = []
peak = initial_capital

for i, equity in enumerate(equity_curve):
    if equity > peak:
        peak = equity
    drawdown = (peak - equity) / peak * 100
    drawdowns.append(drawdown)

max_drawdown_pct = max(drawdowns)
```

**Interpretation**:

- < 10%: Excellent risk management
- 10-20%: Acceptable
- 20-30%: High risk
- > 30%: Very high risk (consider reducing position size)

#### Sharpe Ratio

```python
# Risk-adjusted returns
returns = [trade.pnl_pct for trade in trades]
sharpe_ratio = mean(returns) / std(returns)
```

**Interpretation**:
>
- > 2.0: Excellent risk-adjusted returns
- 1.0-2.0: Good
- 0.5-1.0: Acceptable
- < 0.5: Poor (high risk relative to returns)

---

## Trade Analysis

### Analyzing Individual Trades

```python
# Get all trades
trades = result.trades

# Filter winning trades
winners = [t for t in trades if t.is_winner]

# Filter by signal type
cloud_flips = [t for t in trades if t.signal_type == "CLOUD_FLIP"]

# Filter by signal strength
strong_signals = [
    t for t in trades
    if t.signal_strength in ["VERY_STRONG", "STRONG"]
]

# Analyze exit reasons
exit_reasons = {}
for trade in trades:
    reason = trade.exit_reason
    exit_reasons[reason] = exit_reasons.get(reason, 0) + 1

print("Exit reasons:", exit_reasons)
# Example output: {'stop_loss': 12, 'take_profit': 18, 'time': 10, 'signal': 7}
```

### Trade Duration Analysis

```python
# Average hold time by outcome
winner_bars = [t.bars_held for t in trades if t.is_winner]
loser_bars = [t.bars_held for t in trades if not t.is_winner]

avg_winner_time = sum(winner_bars) / len(winner_bars)
avg_loser_time = sum(loser_bars) / len(loser_bars)

print(f"Winners held: {avg_winner_time:.1f} bars")
print(f"Losers held: {avg_loser_time:.1f} bars")

# Interpretation:
# - If losers held longer: Not cutting losses quickly enough
# - If winners held longer: Good - letting profits run
```

### Signal Strength Analysis

```python
# Win rate by signal strength
strength_stats = {}

for strength in ["VERY_STRONG", "STRONG", "MODERATE", "WEAK"]:
    strength_trades = [t for t in trades if t.signal_strength == strength]
    if strength_trades:
        winners = sum(1 for t in strength_trades if t.is_winner)
        win_rate = winners / len(strength_trades) * 100
        strength_stats[strength] = {
            "count": len(strength_trades),
            "win_rate": win_rate
        }

for strength, stats in strength_stats.items():
    print(f"{strength}: {stats['count']} trades, {stats['win_rate']:.1f}% win rate")

# Example output:
# VERY_STRONG: 12 trades, 75.0% win rate
# STRONG: 20 trades, 65.0% win rate
# MODERATE: 15 trades, 40.0% win rate
```

### Monthly Performance Breakdown

```python
from collections import defaultdict

# Group trades by month
monthly_pnl = defaultdict(list)

for trade in trades:
    month_key = trade.entry_time.strftime("%Y-%m")
    monthly_pnl[month_key].append(trade.pnl)

# Calculate monthly returns
for month, pnls in sorted(monthly_pnl.items()):
    total_pnl = sum(pnls)
    trade_count = len(pnls)
    print(f"{month}: ${total_pnl:,.2f} ({trade_count} trades)")
```

---

## Parameter Optimization

### Grid Search Optimization

Test multiple parameter combinations to find optimal settings:

```python
import pandas as pd
from datetime import datetime

from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

def generate_signals(df, adx_min: int, volume_multiplier: float):
    # Replace with your own signal generator to return a DataFrame indexed by timestamp.
    return pd.DataFrame()

async def optimize_parameters():
    from itertools import product

    # Parameter ranges to test
    adx_mins = [15, 20, 25, 30]
    volume_mults = [1.2, 1.5, 2.0, 2.5]

    best_result = None
    best_sharpe = -999
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    backtester = Backtester(initial_capital=100000.0)

    df = await data_manager.get_historical_data(
        symbol="XLK",
        interval="1d",
        start=datetime(2025, 1, 1),
        end=datetime(2025, 12, 31),
    )

    for adx_min, vol_mult in product(adx_mins, volume_mults):
        # Generate custom signals for this parameter set
        signals_df = generate_signals(df, adx_min=adx_min, volume_multiplier=vol_mult)

        result = backtester.run(df, "XLK", signals_df=signals_df)

        # Track best configuration
        if result.sharpe_ratio > best_sharpe:
            best_sharpe = result.sharpe_ratio
            best_result = result
            print(f"New best: ADX={adx_min}, Vol={vol_mult}, "
                  f"Sharpe={result.sharpe_ratio:.2f}")

    return best_result

# Run optimization
best = asyncio.run(optimize_parameters())
```

### Optimization Metrics

Choose optimization target based on goals:

| Metric            | When to Optimize For                     |
|-------------------|------------------------------------------|
| **Sharpe Ratio**  | Best risk-adjusted returns (recommended) |
| **Total Return**  | Maximum profit (may increase risk)       |
| **Win Rate**      | Consistency over absolute returns        |
| **Profit Factor** | Reliability of profitable trades         |
| **Max Drawdown**  | Minimize risk (conservative approach)    |

---

## Walk-Forward Testing

Validate strategy robustness with out-of-sample testing:

### Walk-Forward Process

```text
┌─────────────────────────────────────────────────────────────────┐
│               Walk-Forward Testing Timeline                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [In-Sample 1] [Out] [In-Sample 2] [Out] [In-Sample 3] [Out]  │
│   Optimize     Test   Optimize     Test   Optimize     Test    │
│   6 months   1 month   6 months  1 month  6 months   1 month   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Implementation

```python
import pandas as pd
from datetime import datetime, timedelta
from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.data_providers.base import DataProviderManager

def generate_signals(df, config):
    # Replace with your own signal generator for the chosen config.
    return pd.DataFrame()

async def walk_forward_test(
    symbol: str,
    start_date: datetime,
    end_date: datetime,
    in_sample_months: int = 6,
    out_sample_months: int = 1
):
    """
    Walk-forward testing with rolling optimization windows.

    Args:
        symbol: ETF symbol to test
        start_date: Start of testing period
        end_date: End of testing period
        in_sample_months: Months for optimization
        out_sample_months: Months for validation
    """
    results = []
    current_date = start_date
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})
    backtester = Backtester(initial_capital=100000.0)

    while current_date < end_date:
        # Define in-sample period
        in_sample_end = current_date + timedelta(days=30 * in_sample_months)

        # Optimize on in-sample data
        best_config = await optimize_on_period(
            symbol, current_date, in_sample_end
        )

        # Test on out-of-sample data
        out_sample_start = in_sample_end
        out_sample_end = out_sample_start + timedelta(days=30 * out_sample_months)

        df = await data_manager.get_historical_data(
            symbol=symbol,
            interval="1d",
            start=out_sample_start,
            end=out_sample_end,
        )
        signals_df = generate_signals(df, best_config)
        result = backtester.run(df, symbol, signals_df=signals_df)

        results.append({
            "period": f"{out_sample_start:%Y-%m} to {out_sample_end:%Y-%m}",
            "return": result.total_return_pct,
            "win_rate": result.win_rate,
            "config": best_config
        })

        # Move to next window
        current_date = out_sample_end

    # Aggregate results
    total_periods = len(results)
    positive_periods = sum(1 for r in results if r["return"] > 0)
    avg_return = sum(r["return"] for r in results) / total_periods

    print(f"Walk-Forward Results:")
    print(f"  Positive periods: {positive_periods}/{total_periods}")
    print(f"  Average return: {avg_return:.2f}%")

    return results
```

---

## Best Practices

### Sufficient Data

- **Minimum**: 1 year of historical data
- **Recommended**: 3-5 years for robust testing
- **Ideal**: Full market cycle (bull + bear markets)

### Sample Size

- **Minimum**: 30 trades for statistical significance
- **Recommended**: 50-100+ trades
- **Rule of thumb**: More trades = more reliable results

### Avoiding Overfitting

1. **Keep it simple**: Don't over-optimize parameters
2. **Use walk-forward**: Validate on out-of-sample data
3. **Test multiple symbols**: Strategy should work across sectors
4. **Check stability**: Small parameter changes shouldn't drastically affect results

### Realistic Assumptions

```python
# Include realistic trading costs
commission = 0.00  # Many brokers offer commission-free ETF trading
slippage = 0.02  # 0.02% for liquid ETFs

# Adjust entry/exit prices for slippage
adjusted_entry = entry_price * (1 + slippage/100)
adjusted_exit = exit_price * (1 - slippage/100)
```

---

## See Also

- [Main README](../README.md) - Strategy overview and quick start
- [Signal Management](SIGNAL_MANAGEMENT.md) - Signal generation and validation
- [PRD](../PRD_Detailed.md) - Complete strategy methodology
- [Project Guidelines](../AGENTS.md) - Development patterns
