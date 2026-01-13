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

## Package Structure

This project is split into two packages:

- **`ema-cloud-lib`**: Core library with all business logic (no CLI dependencies)
- **`ema-cloud-cli`**: Command-line interface with Rich terminal dashboard

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd ema_cloud_sector_scanner

# Quick start - run directly without installing (recommended for development)
uv run python run.py --once

# Or install packages for persistent use
uv pip install -e packages/ema_cloud_lib
uv pip install -e packages/ema_cloud_cli

# Install with optional dependencies
uv pip install -e "packages/ema_cloud_lib[all]"      # All optional providers
uv pip install -e "packages/ema_cloud_lib[alpaca]"   # Alpaca data provider
uv pip install -e "packages/ema_cloud_lib[notifications]" # Desktop notifications
```

### Basic Usage (CLI)

```bash
# Run scanner with default settings (intraday style, all sector ETFs)
ema-scanner

# Run with specific trading style
ema-scanner --style swing

# Scan specific ETFs
ema-scanner --etfs XLK XLF XLV

# Scan a preset group
ema-scanner --subset growth_sectors

# Single scan (no continuous monitoring)
ema-scanner --once

# Verbose logging
ema-scanner -v
```

### Python API (Library)

```python
import asyncio
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle

# Create configuration
config = ScannerConfig()
config.trading_style = TradingStyle.SWING
config.etf_symbols = ['XLK', 'XLF', 'XLV']

# Create and run scanner
scanner = EMACloudScanner(config)

# Run a single scan cycle
asyncio.run(scanner.run_scan_cycle())

# Or run continuous monitoring
asyncio.run(scanner.run())
```

### Custom Dashboard Integration

The library uses dependency injection for dashboard integration:

```python
from ema_cloud_lib import EMACloudScanner, ScannerConfig, DashboardProtocol
from ema_cloud_lib import ETFDisplayData, SignalDisplayData

class MyCustomDashboard(DashboardProtocol):
    def update_etf_data(self, data: ETFDisplayData) -> None:
        # Handle ETF data updates
        print(f"{data.symbol}: {data.trend} @ ${data.price:.2f}")

    def add_signal(self, signal: SignalDisplayData) -> None:
        # Handle new signals
        print(f"Signal: {signal.symbol} {signal.direction}")

    def stop(self) -> None:
        pass

# Use custom dashboard
scanner = EMACloudScanner(ScannerConfig())
scanner.set_dashboard(MyCustomDashboard())
asyncio.run(scanner.run())
```

## Ripster's EMA Cloud Strategy

The scanner is based on Ripster's EMA Cloud methodology, a popular trading approach that uses multiple EMAs to identify trends and trading opportunities.

### Key Clouds

| Cloud                  | EMA Pair  | Purpose                                   |
| ---------------------- | --------- | ----------------------------------------- |
| Trendline              | 5-12      | Short-term trend identification           |
| Pullback               | 8-9       | Entry timing for pullbacks                |
| Momentum               | 20-21     | Momentum confirmation                     |
| **Trend Confirmation** | **34-50** | **Primary trend filter (most important)** |
| Long-term              | 72-89     | Longer-term trend confirmation            |
| Major Trend            | 200-233   | Major market trend                        |

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

| Style     | Timeframe | Primary Clouds        | Use Case                     |
| --------- | --------- | --------------------- | ---------------------------- |
| Scalping  | 1m        | 5-12, 8-9, 20-21      | Quick trades, high frequency |
| Intraday  | 10m       | 8-9, 20-21, 34-50     | Day trading                  |
| Swing     | 1h        | 20-21, 34-50, 72-89   | Multi-day positions          |
| Position  | 4h        | 34-50, 72-89, 200-233 | Multi-week positions         |
| Long-term | 1d        | 34-50, 72-89, 200-233 | Investment decisions         |

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
from ema_cloud_lib import FilterConfig

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

Requires `plyer` package:

```bash
uv pip install -e "packages/ema_cloud_lib[notifications]"
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
from ema_cloud_lib import Backtester, run_quick_backtest
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

```text
ema_cloud_sector_scanner/
├── pyproject.toml              # Workspace configuration
├── README.md
└── packages/
    ├── ema_cloud_lib/          # Core library (no CLI deps)
    │   ├── pyproject.toml
    │   └── src/ema_cloud_lib/
    │       ├── __init__.py     # Public API exports
    │       ├── scanner.py      # EMACloudScanner, MarketHours
    │       ├── config/         # Settings, presets, constants
    │       ├── indicators/     # EMA cloud calculations
    │       ├── signals/        # Signal generation logic
    │       ├── alerts/         # Alert delivery system
    │       ├── holdings/       # ETF holdings management
    │       ├── data_providers/ # Yahoo, Alpaca, Polygon
    │       ├── backtesting/    # Backtesting engine
    │       └── types/          # Display types, protocols
    │
    └── ema_cloud_cli/          # CLI application
        ├── pyproject.toml
        └── src/ema_cloud_cli/
            ├── __init__.py
            ├── cli.py          # Entry point, argparse
            └── dashboard/      # Rich terminal UI
```

## CLI Options

```text
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

## Logging

The scanner uses intelligent logging that adapts based on the display mode:

- **With dashboard** (default): Logs written to file, clean TUI interface
  - Log file: `~/Library/Logs/ema-cloud-scanner/scanner.log` (macOS)
  - Third-party logs suppressed for cleaner output
  - Location displayed at startup

- **Without dashboard** (`--no-dashboard`): Logs to console with formatted output

For detailed logging information, see [packages/ema_cloud_cli/LOGGING.md](packages/ema_cloud_cli/LOGGING.md).

## Data Providers

### Yahoo Finance (Default)

Free, no API key required. Suitable for most use cases.

### Alpaca (Optional)

Real-time data with API key:

```bash
uv pip install -e "packages/ema_cloud_lib[alpaca]"
```

Configure:

```python
config.data_provider.provider = 'alpaca'
config.data_provider.api_key = 'your_key'
config.data_provider.api_secret = 'your_secret'
```

### Polygon.io (Optional)

Professional-grade data:

```bash
uv pip install -e "packages/ema_cloud_lib[polygon]"
```

## Development

### Quick Start (No Installation Required)

Use `run.py` to run directly from source:

```bash
# Run scanner (uv handles dependencies automatically)
uv run python run.py --help
uv run python run.py --once
uv run python run.py --style swing --etfs XLK XLF
```

### Installing Packages

For a full installation:

```bash
# Install packages in editable mode
uv pip install -e packages/ema_cloud_lib
uv pip install -e packages/ema_cloud_cli

# Or with dev dependencies
uv pip install -e "packages/ema_cloud_lib[dev]"
uv pip install -e "packages/ema_cloud_cli[dev]"
```

### Code Quality

```bash
# Lint
ruff check packages/

# Format
ruff format packages/

# Type check
mypy packages/

# Run tests
pytest
```

## License

MIT License

## Disclaimer

This software is for educational and informational purposes only. It does not constitute financial advice. Trading involves risk of loss. Always do your own research before making investment decisions.

## Credits

- Ripster47 for the EMA Cloud methodology
