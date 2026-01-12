# EMA Cloud Sector Scanner

Real-time sector ETF scanner based on **Ripster's EMA Cloud methodology**. Monitors sector ETFs for trend changes, cloud flips, and generates trading signals with strength ratings.

## Features

- **Multiple EMA Clouds**: All 6 Ripster cloud configurations (5-12, 8-9, 20-21, 34-50, 72-89, 200-233)
- **Real-time Signal Detection**: Cloud flips, price crosses, pullback entries, multi-cloud alignment
- **Signal Strength Ratings**: VERY_STRONG to VERY_WEAK with configurable filters
- **Multiple Trading Styles**: Scalping, Intraday, Swing, Position, Long-term presets
- **Confirmation Filters**: Volume, RSI, ADX, VWAP, ATR, MACD, time-of-day
- **Alert System**: Console, desktop notifications, Telegram, Discord (extensible)
- **Terminal Dashboard**: Rich-based real-time monitoring interface
- **ETF Holdings**: Fetch and analyze top holdings for each sector
- **Backtesting**: Test strategies against historical data

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ema_cloud_sector_scanner

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .

# Install with optional dependencies
uv sync --extra all          # All optional providers
uv sync --extra alpaca       # Alpaca data provider
uv sync --extra notifications # Desktop notifications
uv sync --extra dev          # Development tools
```

### Basic Usage

```bash
# Run scanner with default settings (intraday style, all sector ETFs)
uv run ema-scanner

# Run with specific trading style
uv run ema-scanner --style swing

# Scan specific ETFs
uv run ema-scanner --etfs XLK XLF XLV

# Scan a preset group
uv run ema-scanner --subset growth_sectors

# Single scan (no continuous monitoring)
uv run ema-scanner --once

# Verbose logging
uv run ema-scanner -v
```

### Python API

```python
import asyncio
from ema_cloud_sector_scanner import EMACloudScanner, ScannerConfig, TradingStyle

# Create configuration
config = ScannerConfig()
config.trading_style = TradingStyle.SWING
config.etf_symbols = ['XLK', 'XLF', 'XLV']

# Create and run scanner
scanner = EMACloudScanner(config)
asyncio.run(scanner.run())
```

## Ripster's EMA Cloud Strategy

The scanner is based on Ripster's EMA Cloud methodology, a popular trading approach that uses multiple EMAs to identify trends and trading opportunities.

### Key Clouds

| Cloud | EMA Pair | Purpose |
|-------|----------|---------|
| Trendline | 5-12 | Short-term trend identification |
| Pullback | 8-9 | Entry timing for pullbacks |
| Momentum | 20-21 | Momentum confirmation |
| **Trend Confirmation** | **34-50** | **Primary trend filter (most important)** |
| Long-term | 72-89 | Longer-term trend confirmation |
| Major Trend | 200-233 | Major market trend |

### Golden Rule

- **Price ABOVE 34-50 cloud** = Bullish environment (long bias)
- **Price BELOW 34-50 cloud** = Bearish environment (short bias)

### Signal Types

1. **Cloud Flip**: Cloud changes color (bullish ↔ bearish)
2. **Price Cross**: Price crosses above/below a cloud
3. **Pullback Entry**: Price pulls back to cloud acting as support/resistance
4. **Multi-Cloud Alignment**: Multiple clouds align in same direction

## Configuration

### Trading Style Presets

| Style | Timeframe | Primary Clouds | Use Case |
|-------|-----------|----------------|----------|
| Scalping | 1m | 5-12, 8-9, 20-21 | Quick trades, high frequency |
| Intraday | 10m | 8-9, 20-21, 34-50 | Day trading |
| Swing | 1h | 20-21, 34-50, 72-89 | Multi-day positions |
| Position | 4h | 34-50, 72-89, 200-233 | Multi-week positions |
| Long-term | 1d | 34-50, 72-89, 200-233 | Investment decisions |

### Sector ETFs

Default scans all 11 S&P sector ETFs:

- **XLK** - Technology
- **XLF** - Financials
- **XLV** - Health Care
- **XLE** - Energy
- **XLY** - Consumer Discretionary
- **XLP** - Consumer Staples
- **XLI** - Industrials
- **XLB** - Materials
- **XLU** - Utilities
- **XLRE** - Real Estate
- **XLC** - Communication Services

### ETF Subsets

```bash
# Scan growth sectors only
ema-scanner --subset growth_sectors  # XLK, XLY, XLC

# Scan defensive sectors
ema-scanner --subset defensive_sectors  # XLU, XLP, XLV

# Scan cyclical sectors
ema-scanner --subset cyclical_sectors  # XLI, XLB, XLE, XLF
```

### Filter Configuration

```python
from ema_cloud_sector_scanner.config import FilterConfig

filters = FilterConfig()
filters.volume_enabled = True
filters.volume_multiplier = 1.5  # Require 1.5x average volume
filters.rsi_enabled = True
filters.rsi_period = 14
filters.rsi_overbought = 70
filters.rsi_oversold = 30
filters.adx_enabled = True
filters.adx_min = 20  # Require trending market
```

## Alerts

### Console Output

Signals are printed to console with color coding:

- 🟢 Green: Long signals
- 🔴 Red: Short signals

### Desktop Notifications

Requires `plyer` package. Install with:

```bash
pip install plyer
```

### Telegram

Configure in settings:

```python
config.alerts.telegram_enabled = True
config.alerts.telegram_bot_token = "your_bot_token"
config.alerts.telegram_chat_id = "your_chat_id"
```

### Discord

Configure webhook URL:

```python
config.alerts.discord_enabled = True
config.alerts.discord_webhook = "your_webhook_url"
```

## Backtesting

```python
from ema_cloud_sector_scanner.backtesting import Backtester, run_quick_backtest
import yfinance as yf

# Fetch historical data
df = yf.download("XLK", period="1y", interval="1d")

# Run quick backtest
result = run_quick_backtest(df, "XLK", print_results=True)

# Or with custom parameters
backtester = Backtester(
    initial_capital=100000,
    position_size_pct=10,
    commission=1.0,
    slippage_pct=0.05
)
result = backtester.run(df, "XLK")
```

## Project Structure

```
ema_cloud_sector_scanner/
├── pyproject.toml          # Project configuration and dependencies
├── uv.lock                 # Locked dependencies
├── README.md
└── src/
    └── ema_cloud_sector_scanner/
        ├── __init__.py
        ├── scanner.py          # Main scanner with run loop
        ├── config/
        │   └── settings.py     # Configuration dataclasses
        ├── data_providers/
        │   └── base.py         # Data provider abstractions
        ├── indicators/
        │   └── ema_cloud.py    # EMA cloud calculations
        ├── signals/
        │   └── generator.py    # Signal generation logic
        ├── alerts/
        │   └── handlers.py     # Alert delivery system
        ├── holdings/
        │   └── manager.py      # ETF holdings management
        ├── visualization/
        │   └── dashboard.py    # Terminal dashboard
        └── backtesting/
            └── engine.py       # Backtesting engine
```

## CLI Options

```
usage: ema-scanner [-h] [--style {scalping,intraday,swing,position,long_term}]
                   [--etfs ETFS [ETFS ...]] [--subset SUBSET]
                   [--interval INTERVAL] [--no-dashboard] [--all-hours]
                   [--verbose] [--config CONFIG] [--once]

EMA Cloud Sector Scanner - Real-time trading signal scanner

optional arguments:
  -h, --help            show this help message and exit
  --style, -s           Trading style preset (default: intraday)
  --etfs, -e            Specific ETFs to scan
  --subset              ETF subset to scan
  --interval, -i        Scan interval in seconds (default: 60)
  --no-dashboard        Disable terminal dashboard
  --all-hours           Scan during extended hours
  --verbose, -v         Enable verbose logging
  --config, -c          Path to config JSON file
  --once                Run a single scan and exit
```

## Data Providers

### Yahoo Finance (Default)

Free, no API key required. Suitable for most use cases.

### Alpaca (Optional)

Real-time data with API key. Install extras:

```bash
pip install ema-cloud-sector-scanner[alpaca]
```

Configure:

```python
config.data_provider.provider = 'alpaca'
config.data_provider.api_key = 'your_key'
config.data_provider.api_secret = 'your_secret'
```

### Polygon.io (Optional)

Professional-grade data. Install extras:

```bash
pip install ema-cloud-sector-scanner[polygon]
```

## Development

```bash
# Install with dev dependencies
uv sync --extra dev

# Run tests
uv run pytest

# Format code
uv run black src/

# Lint
uv run ruff check src/

# Type check (if mypy is added)
uv run mypy src/
```

## License

MIT License

## Disclaimer

This software is for educational and informational purposes only. It does not constitute financial advice. Trading involves risk of loss. Always do your own research before making investment decisions.

## Credits

- Ripster47 for the EMA Cloud methodology
- The trading community for strategy refinements
