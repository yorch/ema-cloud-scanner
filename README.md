# EMA Cloud Sector Scanner

Real-time sector ETF scanner based on **Ripster's EMA Cloud methodology**. Monitors sector ETFs for trend changes, cloud flips, and generates trading signals with strength ratings.

## Features

- **Multiple EMA Clouds**: All 6 Ripster cloud configurations (5-12, 8-9, 20-21, 34-50, 72-89, 200-233)
- **Real-time Signal Detection**: Cloud flips, price crosses, pullback entries, multi-cloud alignment, waterfall patterns
- **Signal Strength Ratings**: VERY_STRONG to VERY_WEAK with configurable filters
- **Multiple Trading Styles**: Scalping, Intraday, Swing, Position, Long-term presets
- **Confirmation Filters**: Volume, RSI, ADX, VWAP, ATR, MACD, time-of-day with configurable weighted scoring
- **Market Hours Detection**: Automatic NYSE/NASDAQ holiday and early close detection using official trading calendar
- **Alert System**: Console, desktop notifications, Telegram, Discord, Email
- **Terminal Dashboard**: Textual-based real-time monitoring interface
- **ETF Holdings**: Fetch and analyze top holdings for each sector
- **Holdings Scanning**: Scan individual stocks within sector ETF holdings with sector trend filtering
- **Backtesting**: Test strategies against historical data with walk-forward validation
- **Data Quality Validation**: Automatic OHLCV data validation post-fetch (NaN, duplicates, anomalies)
- **Config Schema Migration**: Versioned config files with automatic migration on load

## Package Structure

This is a **dual-package workspace** managed by `uv`:

```text
ema_cloud_sector_scanner/
├── packages/
│   ├── ema_cloud_lib/     # Core library (no CLI dependencies)
│   └── ema_cloud_cli/     # Command-line interface with Textual dashboard
├── .github/
│   └── workflows/
│       └── ci.yml         # CI pipeline: lint → test → typecheck → build → docker
├── Dockerfile             # Two-stage build (builder + runtime, ~426MB final image)
├── docker-compose.yml     # VPS deployment with env var config
├── run.py                 # Development runner (no install needed)
└── pyproject.toml         # Root project configuration
```

**Key Principle**: `ema-cloud-lib` is framework-agnostic and uses dependency injection for UI integration.

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
```

### Basic Usage

```bash
# Run scanner with default settings (intraday style, all sector ETFs)
ema-scanner

# Run with specific trading style
ema-scanner --style swing

# Scan specific ETFs
ema-scanner --etfs XLK XLF XLV

# Single scan (no continuous monitoring)
ema-scanner --once

# Enable holdings scanning (scan individual stocks within sector ETFs)
ema-scanner --scan-holdings

# Verbose logging
ema-scanner -v
```

### Python API

```python
import asyncio
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle

# Create configuration
config = ScannerConfig(
    trading_style=TradingStyle.SWING,
    active_sectors=["technology", "financials", "healthcare"],
)

# Create and run scanner
scanner = EMACloudScanner(config)

# Run a single scan cycle
asyncio.run(scanner.run_scan_cycle())

# Or run continuous monitoring
asyncio.run(scanner.run())
```

## Ripster's EMA Cloud Strategy

The scanner is based on Ripster's EMA Cloud methodology, using multiple EMAs to identify trends and trading opportunities.

### Six EMA Clouds

| Cloud                  | EMA Pair  | Purpose                                   |
| ---------------------- | --------- | ----------------------------------------- |
| Trendline              | 5-12      | Short-term trend identification           |
| Pullback               | 8-9       | Entry timing for pullbacks                |
| Momentum               | 20-21     | Momentum confirmation                     |
| **Trend Confirmation** | **34-50** | **Primary trend filter (most important)** |
| Long-term              | 72-89     | Longer-term trend confirmation            |
| Major Trend            | 200-233   | Major market trend                        |

### The Golden Rule

- **Price ABOVE 34-50 cloud** = Bullish environment (long bias)
- **Price BELOW 34-50 cloud** = Bearish environment (short bias)

### Signal Types

1. **Cloud Flip**: Cloud changes color (bullish ↔ bearish)
2. **Price Cross**: Price crosses above/below a cloud
3. **Cloud Bounce**: Price bounces off cloud acting as support/resistance
4. **Pullback Entry**: Price pulls back to 8-9 EMA cloud for entry
5. **Multi-Cloud Alignment**: Multiple clouds align in same direction
6. **Waterfall**: All 6 clouds perfectly stacked in order (strongest trend signal)

## Running on a VPS / Docker

The scanner can run unattended in a Docker container with Telegram, Discord, or Email alerts.

### Quick Start

```bash
# 1. Copy and fill in your credentials
cp .env.example .env
# edit .env — set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID, or DISCORD_WEBHOOK_URL

# 2. Build and start (detached)
just docker-build
just docker-up

# 3. Watch logs
just docker-logs
```

### Environment Variables

| Variable                                          | Description                    | Default    |
| ------------------------------------------------- | ------------------------------ | ---------- |
| `EMA_SCANNER_TRADING_STYLE`                       | Trading style preset           | `intraday` |
| `EMA_SCANNER_SCAN_INTERVAL`                       | Scan interval (seconds)        | `60`       |
| `EMA_SCANNER_MARKET_HOURS_ONLY`                   | Respect market hours           | `true`     |
| `EMA_DATA_PROVIDER`                               | `yahoo` / `alpaca` / `polygon` | `yahoo`    |
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY`            | Alpaca credentials             | —          |
| `POLYGON_API_KEY`                                 | Polygon.io API key             | —          |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`         | Telegram alert bot             | —          |
| `DISCORD_WEBHOOK_URL`                             | Discord webhook                | —          |
| `SMTP_SERVER` / `SMTP_USERNAME` / `SMTP_PASSWORD` | Email (SMTP)                   | —          |

Telegram and Discord alerts are **auto-enabled** when their credentials are set — no extra flags needed.

See `.env.example` for a fully annotated template.

## CI / Docker Images

Every push to `main` and `v*` tag runs the full CI pipeline and publishes a Docker image to GHCR:

```bash
# Pull the latest image directly (no local build needed)
docker pull ghcr.io/<your-org>/ema_cloud_sector_scanner:latest
```

**CI pipeline**: lint → typecheck → test (Python 3.11–3.13) → build → docker publish

**Tags published**:

- `latest` — tip of `main`
- `main` — branch name
- `YYYYMMDDHHMM_<sha>` — exact build (e.g. `202603151430_455431c`)
- `v1.2.3` — on git tags

Pull requests always build the Docker image as a validation check. Images are only pushed when the `publish-docker` label is added to the PR.

For VPS deployments where you don't want to build locally, update `docker-compose.yml`:

```yaml
services:
  scanner:
    image: ghcr.io/<your-org>/ema_cloud_sector_scanner:latest
    # remove the `build: .` line
```

## Advanced Features

### Multi-Timeframe Analysis

Analyze signals across multiple timeframes for confirmation. Supports custom primary timeframes and multiple confirmation timeframes to reduce false positives.

**See**: [CLI_ADVANCED_FEATURES.md](docs/CLI_ADVANCED_FEATURES.md)

### EMA Cloud Customization

Control which of the 6 EMA clouds are active, adjust cloud thickness thresholds, and create custom combinations for different trading styles.

**See**: [CLI_ADVANCED_FEATURES.md](docs/CLI_ADVANCED_FEATURES.md)

### Holdings Scanning

Scan individual stocks within sector ETF holdings. The sector's trend direction filters signals: bullish sectors allow only LONG signals for stocks, bearish sectors allow only SHORT signals.

**See**: [HOLDINGS_SCANNING.md](docs/HOLDINGS_SCANNING.md)

### Alert System

Multiple alert channels for real-time notifications:

- **Console** - Terminal output with color coding (enabled by default)
- **Desktop** - Native OS notifications
- **Telegram** - Bot messages to your phone
- **Discord** - Webhook messages to Discord channels
- **Email** - SMTP notifications via Gmail, Outlook, or custom servers

**See**: [ALERTS.md](docs/ALERTS.md)

### Backtesting

Run historical backtests to evaluate strategy performance with complete trade statistics, risk metrics, and parameter optimization tools.

**See**: [BACKTESTING.md](docs/BACKTESTING.md)

### Data Providers

Choose from multiple data sources:

- **Yahoo Finance** (default, free)
- **Alpaca** (real-time, requires API keys)
- **Polygon.io** (professional)

**See**: [CONFIGURATION_MANAGEMENT.md](docs/CONFIGURATION_MANAGEMENT.md) and [CLI_REFERENCE.md](docs/CLI_REFERENCE.md)

## Configuration

### Trading Styles

Five preset configurations optimized for different timeframes:

| Style     | Timeframe    | Clouds Used           | Confirmation |
| --------- | ------------ | --------------------- | ------------ |
| Scalping  | 1m-5m        | 5-12, 8-9, 20-21      | 1 bar        |
| Intraday  | 5m-10m       | 8-9, 20-21, 34-50     | 2 bars       |
| Swing     | 1h-4h        | 20-21, 34-50, 72-89   | 2-3 bars     |
| Position  | Daily        | 34-50, 72-89, 200-233 | 3 bars       |
| Long-term | Daily/Weekly | 72-89, 200-233        | 3-5 bars     |

### Monitored ETFs

Scans all 11 S&P sector ETFs by default:

- **Technology** (XLK), **Financials** (XLF), **Healthcare** (XLV)
- **Energy** (XLE), **Consumer Discretionary** (XLY), **Consumer Staples** (XLP)
- **Industrials** (XLI), **Materials** (XLB), **Utilities** (XLU)
- **Real Estate** (XLRE), **Communication Services** (XLC)

**Preset groups**: `growth_sectors`, `defensive_sectors`, `cyclical_sectors`, `rate_sensitive`, `commodity_linked`

**See**: [CONFIGURATION_MANAGEMENT.md](docs/CONFIGURATION_MANAGEMENT.md) for complete configuration options.

## Development

### Quick Start (No Installation Required)

A `Justfile` is provided for convenience. Run `just` to list all available recipes.

```bash
# Using just (recommended)
just dev            # Run once, all market hours (for local testing)
just once           # Run once during market hours
just swing          # Run with swing style
just test           # Run all tests
just qa             # Lint + format + type check

# Or directly with uv
uv run python run.py --help
uv run python run.py --once
uv run python run.py --style swing --etfs XLK XLF
```

### Code Quality

```bash
# Using just (recommended)
just lint           # Lint all packages and tests
just fix            # Auto-fix lint issues
just fmt            # Format code
just types          # Type check
just qa             # Format + lint + type check

# Or directly with uv
uv run ruff check packages/ tests/
uv run ruff format packages/ tests/
uv run mypy packages/
uv run pytest tests/
```

**See**: [AGENTS.md](AGENTS.md) for comprehensive development guidelines and architecture patterns.

## Documentation

Comprehensive guides organized by topic:

| Topic                 | Key Documents                                                                                                                      |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| **Getting Started**   | [CLI Reference](docs/CLI_REFERENCE.md), [CLI Settings](docs/CLI_SETTINGS.md)                                                       |
| **Advanced Features** | [Multi-Timeframe & Cloud Config](docs/CLI_ADVANCED_FEATURES.md), [Holdings Scanning](docs/HOLDINGS_SCANNING.md)                    |
| **Configuration**     | [Configuration Management](docs/CONFIGURATION_MANAGEMENT.md), [Alerts](docs/ALERTS.md), [Security](docs/SECURITY.md)               |
| **Trading & Testing** | [Signal Management](docs/SIGNAL_MANAGEMENT.md), [Backtesting](docs/BACKTESTING.md), [Advanced Features](docs/ADVANCED_FEATURES.md) |
| **Operations**        | [Monitoring](docs/MONITORING.md), [Logging](docs/LOGGING.md), [Interactive Features](docs/INTERACTIVE_FEATURES.md)                 |
| **Development**       | [AGENTS.md](AGENTS.md) - Architecture patterns and development guide                                                               |

## License

MIT License

## Disclaimer

This software is for educational and informational purposes only. It does not constitute financial advice. Trading involves risk of loss. Always do your own research before making investment decisions.

## Credits

- Ripster47 for the EMA Cloud methodology
