# Project Guidelines

This file provides guidance to AI Agents when working with code in this repository.

## Project Overview

**EMA Cloud Sector Scanner**: Real-time trading scanner monitoring sector ETFs using Ripster's EMA Cloud methodology. Detects cloud flips, price crosses, pullback entries, and multi-cloud alignment signals with configurable confirmation filters.

## Package Architecture

This is a **dual-package workspace** managed by `uv`:

```text
ema_cloud_sector_scanner/
├── packages/
│   ├── ema_cloud_lib/     # Core library (no CLI dependencies)
│   │   └── src/ema_cloud_lib/
│   │       ├── scanner.py           # EMACloudScanner, MarketHours
│   │       ├── config/              # Settings, presets, TradingStyle enums
│   │       ├── indicators/          # EMA cloud calculations (6 clouds)
│   │       ├── signals/             # Signal detection and strength rating
│   │       ├── alerts/              # Alert handlers (console, desktop, etc.)
│   │       ├── data_providers/      # Yahoo, Alpaca, Polygon integrations
│   │       ├── holdings/            # ETF holdings management
│   │       ├── backtesting/         # Backtest engine
│   │       └── types/               # Protocols, display data types
│   │
│   └── ema_cloud_cli/     # CLI application
│       └── src/ema_cloud_cli/
│           ├── cli.py               # Typer entry point
│           ├── config_store.py      # User preferences persistence
│           └── dashboard/           # Textual-based terminal UI
│
├── Dockerfile             # Production container (all providers + headless)
├── docker-compose.yml     # VPS deployment with env var config
├── .env.example           # Credentials template (copy to .env)
├── .dockerignore          # Build context exclusions
├── Justfile               # Developer task runner (run `just` to list)
├── pyproject.toml         # Workspace config
└── run.py                 # Development runner (no install needed)
```

**Key Principle**: `ema_cloud_lib` is **framework-agnostic** and has zero CLI dependencies. It uses **dependency injection** via `DashboardProtocol` to decouple from any specific UI framework.

## Common Development Commands

A `Justfile` is provided as a convenient wrapper. Run `just` (no args) to list all recipes.

### Using `just` (Recommended)

```bash
# Running the scanner
just once           # Single scan (market hours)
just dev            # Single scan, all-hours mode (for testing)
just run            # Continuous scan
just swing          # Swing style
just intraday       # Intraday style
just scalp          # Scalping style

# Testing
just test           # All tests
just test-v         # Verbose
just test-file tests/test_scanner.py  # Specific file
just test-alerts    # Alert handlers

# Code quality
just lint           # Ruff lint (packages + tests)
just fix            # Auto-fix (packages + tests)
just fmt            # Format (packages + tests)
just check          # Lint + format
just types          # mypy
just qa             # Format + lint + types

# Setup
just install        # Editable install of both packages
just install-all    # With optional providers
just install-dev    # With dev tools
just hooks          # Pre-commit hooks

# Docker
just docker-build   # Build image
just docker-up      # Start detached
just docker-down    # Stop
just docker-restart # Restart
just docker-logs    # Tail logs
just docker-once    # One-shot scan
just docker-shell   # Debug shell
just docker-clean   # Full reset

# Utilities
just help           # Scanner --help
just clear-cache    # Clear holdings cache
```

### Quick Development (No Installation)

```bash
# Run scanner directly (uv handles dependencies)
uv run python run.py --help
uv run python run.py --once
uv run python run.py --style swing --etfs XLK XLF
```

### Installation for Persistent Use

```bash
# Install both packages in editable mode
uv pip install -e packages/ema_cloud_lib
uv pip install -e packages/ema_cloud_cli

# Install with optional providers
uv pip install -e "packages/ema_cloud_lib[alpaca]"      # Alpaca data
uv pip install -e "packages/ema_cloud_lib[notifications]"  # Desktop alerts
uv pip install -e "packages/ema_cloud_lib[all]"         # All optionals

# Install dev tools
uv pip install -e "packages/ema_cloud_lib[dev]"
```

### Testing

```bash
# Run tests
uv run pytest tests/

# Run tests verbosely
uv run pytest tests/ -v

# Run specific test file
uv run pytest tests/test_scanner.py

# Run specific test
uv run pytest tests/test_scanner.py::test_signal_generation -v
```

### Code Quality

```bash
# Lint all packages and tests
uv run ruff check packages/ tests/

# Auto-fix issues
uv run ruff check --fix packages/ tests/

# Format code
uv run ruff format packages/ tests/

# Type check
uv run mypy packages/
```

### Pre-Commit Validation Checklist

**All of the following checks MUST pass before committing any changes:**

```bash
# 1. Format code (fixes in place)
just fmt

# 2. Lint check (fix first, then verify)
just fix
just lint

# 3. Type check
just types

# 4. Run tests
just test -q

# Or run all quality checks + tests in sequence:
just qa && just test -q
```

**Important notes:**
- `just fmt`, `just lint`, and `just fix` already cover both `packages/` and `tests/` directories
- Fix any issues before committing; do not commit with known failures

## Docker / VPS Deployment

The scanner ships with a full Docker setup for unattended server deployment.

### Files

| File                 | Purpose                                                                 |
| -------------------- | ----------------------------------------------------------------------- |
| `Dockerfile`         | Multi-stage build; installs all extras (alpaca, polygon, notifications) |
| `docker-compose.yml` | Orchestrates the container with env vars, restart policy, cache volume  |
| `.env.example`       | Annotated template — copy to `.env` and fill in credentials             |
| `.dockerignore`      | Excludes `.env`, tests, docs, cache from the build context              |

### Key design decisions

- **`--no-dashboard`** is always set in Docker — no TTY means no Textual TUI
- **Secrets come in via env vars only** — `ScannerConfig.save()` strips all secret fields, so credentials cannot be committed in config JSON files
- **Telegram and Discord auto-enable** when their env vars are set — no `--telegram-alerts` flag needed in `docker-compose.yml`
- **Named volume** `scanner-cache` persists the holdings cache across restarts

### Quick reference

```bash
just docker-build    # Build image
just docker-up       # Start detached
just docker-logs     # Tail logs
just docker-down     # Stop
just docker-once     # One-shot scan (smoke test)
just docker-shell    # Debug shell inside image
just docker-clean    # Full reset (removes volumes)
```

### Supported alert env vars

| Alert    | Env vars                                        |
| -------- | ----------------------------------------------- |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`        |
| Discord  | `DISCORD_WEBHOOK_URL`                           |
| Email    | `SMTP_SERVER`, `SMTP_USERNAME`, `SMTP_PASSWORD` |

### Supported data provider env vars

| Provider        | Env vars                              |
| --------------- | ------------------------------------- |
| Yahoo (default) | _(none needed)_                       |
| Alpaca          | `ALPACA_API_KEY`, `ALPACA_SECRET_KEY` |
| Polygon         | `POLYGON_API_KEY`                     |

## Architecture Patterns

### 1. Dependency Injection for Dashboard

The library uses **Protocol-based dependency injection** to avoid coupling to specific UI frameworks:

```python
# Library defines the protocol
class DashboardProtocol(Protocol):
    def update_etf_data(self, data: ETFDisplayData) -> None: ...
    def add_signal(self, signal: SignalDisplayData) -> None: ...
    def stop(self) -> None: ...

# Scanner accepts any dashboard implementation
scanner = EMACloudScanner(config)
scanner.set_dashboard(my_dashboard)  # Textual, Rich, Web, etc.
```

**When adding features**: Prefer extending protocols in `types/protocols.py` rather than importing UI frameworks into the library.

### 2. Data Provider Strategy Pattern

Data providers are **swappable implementations** of `DataProviderBase`:

```python
# All providers implement the same interface
class DataProviderBase:
    async def fetch_bars(
        self, symbol: str, timeframe: str, limit: int
    ) -> pd.DataFrame: ...
```

**Available providers**: Yahoo (default, free), Alpaca (real-time), Polygon (professional)

**When adding providers**: Subclass `DataProviderBase` in `data_providers/` directory and register in factory.

### 3. Signal Generation Pipeline

Signal detection follows a **multi-stage filtering pipeline**:

```text
Raw Data → EMA Clouds → Signal Detection → Confirmation Filters → Strength Rating → Alerts
```

- **Stage 1**: Calculate 6 EMA clouds (5-12, 8-9, 20-21, 34-50, 72-89, 200-233)
- **Stage 2**: Detect patterns (cloud flip, price cross, cloud bounce, pullback, alignment, waterfall)
- **Stage 3**: Apply confirmation filters (volume, RSI, ADX, VWAP, ATR, MACD)
- **Stage 4**: Rate signal strength (VERY_STRONG → VERY_WEAK)
- **Stage 5**: Route to alert handlers

**When modifying signals**: Update `signals/generator.py` for detection logic, `config/settings.py` for filter configuration.

### 4. Alert Handler Observer Pattern

Alert system uses **observer pattern** for extensibility:

```python
# Handlers subscribe to signals
scanner.alert_manager.add_handler(ConsoleAlertHandler())
scanner.alert_manager.add_handler(DesktopAlertHandler())
scanner.alert_manager.add_handler(TelegramAlertHandler(
    enabled=True,
    bot_token="your_token",
    chat_id="your_chat_id"
))
scanner.alert_manager.add_handler(DiscordAlertHandler(
    enabled=True,
    webhook_url="your_webhook_url"
))

# Alerts sent asynchronously to all enabled handlers
await scanner.alert_manager.send_alert(alert_message)
```

**Available handlers**:

- `ConsoleAlertHandler` - Terminal output with color coding
- `DesktopAlertHandler` - Native OS notifications (requires `plyer`)
- `TelegramAlertHandler` - Telegram bot messages (requires `aiohttp`)
- `DiscordAlertHandler` - Discord webhook messages (requires `aiohttp`)
- `EmailAlertHandler` - Email via SMTP (requires `aiosmtplib`)

**When adding alerts**: Create new handler subclassing `BaseAlertHandler` in `alerts/`.

**Alert configuration**: Use `AlertConfig` in `config/settings.py` to enable/disable handlers and provide credentials.

## Key Configuration Objects

### TradingStyle Presets

Predefined configurations for different trading approaches:

- `SCALPING`: 1m/5m charts, 5-12/8-9/20-21 clouds, 1 confirmation bar
- `INTRADAY`: 5m/10m charts, 8-9/20-21/34-50 clouds, 2 confirmation bars
- `SWING`: 1h/4h charts, 20-21/34-50/72-89 clouds, 2-3 confirmation bars
- `POSITION`: Daily, 34-50/72-89/200-233 clouds, 3 confirmation bars
- `LONG_TERM`: Daily/Weekly, 72-89/200-233 clouds, 3-5 confirmation bars

Located in: `packages/ema_cloud_lib/src/ema_cloud_lib/config/settings.py`

### ETF Symbols & Subsets

Default sectors: All 11 S&P sector SPDRs (XLK, XLF, XLV, XLE, XLY, XLP, XLI, XLB, XLU, XLRE, XLC)

Predefined subsets:

- `growth_sectors`: XLK, XLY, XLC
- `defensive_sectors`: XLP, XLV, XLU
- `cyclical_sectors`: XLI, XLB, XLE
- `rate_sensitive`: XLF, XLRE, XLU
- `commodity_linked`: XLE, XLB

Located in: `packages/ema_cloud_lib/src/ema_cloud_lib/config/settings.py`

## Ripster's EMA Cloud Strategy

**The Golden Rule**: Price above 34-50 cloud = BULLISH | Price below 34-50 cloud = BEARISH

### Six EMA Clouds

| Cloud                  | EMAs      | Purpose                  |
| ---------------------- | --------- | ------------------------ |
| Trendline              | 5-12      | Short-term trend         |
| Pullback               | 8-9       | Entry timing             |
| Momentum               | 20-21     | Momentum confirmation    |
| **Trend Confirmation** | **34-50** | **PRIMARY trend filter** |
| Long-term              | 72-89     | Intermediate trend       |
| Major Trend            | 200-233   | Long-term direction      |

### Signal Types

1. **Cloud Flip**: Fast EMA crosses slow EMA (cloud color change)
2. **Price Cross**: Price breaks above/below cloud boundary
3. **Cloud Bounce**: Price bounces off cloud acting as support/resistance
4. **Pullback Entry**: Price retraces to 8-9 EMA cloud for entry
5. **Multi-Cloud Alignment**: All clouds aligned same direction (trend confirmation)
6. **Waterfall**: All 6 clouds perfectly stacked in order (strongest trend signal)

### Cloud Stacking & Waterfall

Cloud stacking analysis (`EMACloudIndicator.analyze_stacking()`) compares midpoints of all 6 clouds in canonical order. A **waterfall** pattern occurs when all cloud midpoints are perfectly ordered from shortest-term to longest-term. Stacking score ranges from -1.0 (bearish) to 1.0 (bullish).

### Signal Strength Criteria

- **VERY_STRONG**: All 6 clouds aligned, all filters pass, ADX > 30, volume > 2x, waterfall bonus
- **STRONG**: 5+ clouds aligned, key filters pass, ADX > 25
- **MODERATE**: 4 clouds aligned, most filters pass, ADX > 20
- **WEAK**: 3 clouds aligned, some filters fail
- **VERY_WEAK**: < 3 clouds aligned, multiple filter failures

Signal strength is also influenced by **weighted filter scoring** (configurable per-filter weights in `FilterConfig.filter_weights`) and **cloud stacking bonus** (waterfall +5, partial stacking proportional).

## Market Hours & Timing

The scanner respects **US market hours** (9:30 AM - 4:00 PM ET) unless `--all-hours` flag is used:

```python
# MarketHours class handles timing
market_hours = MarketHours()
if market_hours.is_market_open():
    await scanner.run_scan_cycle()
```

**Time-of-day filter**: Default excludes first/last 15 minutes to avoid open/close volatility.

## Testing Strategy

**Unit tests**: Test individual components (indicators, signals, filters)
**Integration tests**: Test scanner with mock data providers
**Async tests**: Use `pytest-asyncio` with `@pytest.mark.asyncio`

```python
# Example async test structure
@pytest.mark.asyncio
async def test_scanner_run_cycle():
    config = ScannerConfig()
    scanner = EMACloudScanner(config)
    await scanner.run_scan_cycle()
```

## UI Framework Preference

**Current standard**: Use **Textual** (not Rich) for terminal UI development.

- Textual provides full TUI framework with interactive widgets
- Rich is used internally by Textual for rendering
- Better suited for CLI applications requiring user interaction

Stored in project memory: `cli_preferences`

## Common Pitfalls

1. **Don't import UI frameworks in `ema_cloud_lib`**: Use dependency injection via protocols
2. **Async context required**: Scanner methods are async; always use `asyncio.run()` or `await`
3. **Market hours awareness**: Respect market hours unless explicitly testing extended hours
4. **Data provider fallback**: Handle provider failures gracefully; test with mock providers
5. **Signal deduplication**: Avoid alerting same signal repeatedly; implement cooldown logic

## Performance Considerations

- **Async I/O**: All data fetching uses `aiohttp` for non-blocking operations
- **Batch processing**: Scan multiple ETFs concurrently using `asyncio.gather()`
- **Caching**: Holdings data cached 24 hours to reduce API calls
- **Efficient filtering**: Apply cheapest filters first (volume) before expensive ones (indicators)

## Configuration Files

User configurations can be saved as JSON:

```json
{
  "schema_version": 2,
  "trading_style": "swing",
  "active_sectors": ["technology", "financials"],
  "filters": {
    "volume_enabled": true,
    "rsi_enabled": true,
    "filter_weights": {
      "volume": 2.0,
      "rsi": 1.0,
      "adx": 2.0,
      "vwap": 1.5,
      "atr": 1.0,
      "macd": 1.0,
      "time": 0.5
    }
  }
}
```

Load with: `--config path/to/config.json`
Save with: `ema-scanner config-save path/to/config.json`

CLI preferences are stored in: `packages/ema_cloud_cli/src/ema_cloud_cli/config_store.py`

## Documentation References

- **Strategy details**: See `PRD_Detailed.md` for complete requirements and methodology
- **API examples**: See `README.md` for Python API usage patterns
- **Signal logic**: Review `packages/ema_cloud_lib/src/ema_cloud_lib/signals/generator.py`
- **Indicator calculations**: Review `packages/ema_cloud_lib/src/ema_cloud_lib/indicators/ema_cloud.py`
