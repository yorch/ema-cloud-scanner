# CLI Reference Guide

Complete command-line reference for the EMA Cloud Sector Scanner.

## Installation

```bash
# Quick start (no installation)
uv run python run.py --once

# Install for persistent use
uv pip install -e packages/ema_cloud_cli
```

## Commands

### `scan` (Default Command)

Run real-time EMA Cloud scanner with signal detection and alerts.

```bash
ema-scanner [OPTIONS]
# or
uv run python run.py [OPTIONS]
```

#### Core Options

| Option           | Type    | Default  | Description              |
| ---------------- | ------- | -------- | ------------------------ |
| `--style`, `-s`  | Choice  | intraday | Trading style preset     |
| `--once`         | Flag    | false    | Run single scan and exit |
| `--interval`     | Integer | 60       | Scan interval (seconds)  |
| `--verbose`,`-v` | Flag    | false    | Enable verbose logging   |
| `-vv`            | Flag    | false    | Extra verbose logging    |

**Trading styles**: `scalping`, `intraday`, `swing`, `position`, `long_term`

#### Symbol Selection

| Option             | Type     | Description                           |
| ------------------ | -------- | ------------------------------------- |
| `--etfs`, `-e`     | Multiple | Specific ETFs (e.g., `XLK XLF XLV`)   |
| `--subset`         | Choice   | Preset ETF group                      |
| `--custom-symbols` | Multiple | Additional symbols beyond sector ETFs |

**Available subsets**:

- `all_sectors` - All 11 S&P sector ETFs (default)
- `growth_sectors` - XLK, XLY, XLC
- `defensive_sectors` - XLP, XLV, XLU
- `cyclical_sectors` - XLI, XLB, XLE, XLF
- `rate_sensitive` - XLF, XLRE, XLU
- `commodity_linked` - XLE, XLB

#### Multi-Timeframe & Cloud Options

| Option                 | Type     | Description                          |
| ---------------------- | -------- | ------------------------------------ |
| `--timeframe`          | String   | Primary timeframe (e.g., `1h`, `5m`) |
| `--confirm-timeframes` | Multiple | Confirmation timeframes              |
| `--disable-mtf`        | Flag     | Disable multi-timeframe confirmation |
| `--enable-clouds`      | Multiple | Enable specific clouds only          |
| `--disable-clouds`     | Multiple | Disable specific clouds              |
| `--cloud-thickness`    | Float    | Cloud thickness threshold (%)        |

**Available clouds**: `trend_line`, `pullback`, `momentum`, `trend_confirmation`, `long_term`, `major_trend`

**See**: [CLI_ADVANCED_FEATURES.md](CLI_ADVANCED_FEATURES.md) for detailed examples and best practices.

#### Holdings Scanning

| Option                  | Type    | Default | Description                |
| ----------------------- | ------- | ------- | -------------------------- |
| `--scan-holdings`       | Flag    | false   | Enable holdings scanning   |
| `--holdings-count`      | Integer | 10      | Top holdings per ETF       |
| `--holdings-concurrent` | Integer | 5       | Max concurrent stock scans |

**See**: [HOLDINGS_SCANNING.md](HOLDINGS_SCANNING.md) for complete guide.

#### Dashboard & Display

| Option           | Type    | Default | Description                      |
| ---------------- | ------- | ------- | -------------------------------- |
| `--no-dashboard` | Flag    | false   | Disable terminal dashboard       |
| `--refresh-rate` | Integer | 5       | Dashboard refresh rate (seconds) |
| `--all-hours`    | Flag    | false   | Scan during extended hours       |

#### Data Providers

| Option            | Type   | Default | Description                |
| ----------------- | ------ | ------- | -------------------------- |
| `--provider`      | Choice | yahoo   | Data source                |
| `--alpaca-key`    | String | -       | Alpaca API key             |
| `--alpaca-secret` | String | -       | Alpaca secret key          |
| `--alpaca-paper`  | Flag   | true    | Use paper trading endpoint |
| `--alpaca-live`   | Flag   | false   | Use live trading endpoint  |
| `--polygon-key`   | String | -       | Polygon.io API key         |

**Providers**: `yahoo` (free), `alpaca` (real-time), `polygon` (professional)

**See**: [SECURITY.md](SECURITY.md) for API key management.

#### Confirmation Filters

Enable/disable filters:

| Filter | Default  | Enable            | Disable            |
| ------ | -------- | ----------------- | ------------------ |
| Volume | Enabled  | `--enable-volume` | `--disable-volume` |
| RSI    | Enabled  | `--enable-rsi`    | `--disable-rsi`    |
| ADX    | Enabled  | `--enable-adx`    | `--disable-adx`    |
| VWAP   | Enabled  | `--enable-vwap`   | `--disable-vwap`   |
| ATR    | Enabled  | `--enable-atr`    | `--disable-atr`    |
| MACD   | Disabled | `--enable-macd`   | `--disable-macd`   |

Filter parameters:

| Option                | Type    | Default | Description                                    |
| --------------------- | ------- | ------- | ---------------------------------------------- |
| `--rsi-period`        | Integer | 14      | RSI calculation period                         |
| `--adx-period`        | Integer | 14      | ADX calculation period                         |
| `--volume-multiplier` | Float   | 1.5     | Volume threshold multiplier                    |
| `--filter-weights`    | String  | -       | Filter weights as JSON (e.g., `'{"volume":2.0}'`) |

#### Alert Configuration

| Option            | Type     | Description                |
| ----------------- | -------- | -------------------------- |
| `--email-alerts`  | Flag     | Enable email notifications |
| `--smtp-server`   | String   | SMTP server address        |
| `--smtp-port`     | Integer  | SMTP port (587 or 465)     |
| `--smtp-username` | String   | SMTP username              |
| `--smtp-password` | String   | SMTP password              |
| `--email-from`    | String   | From email address         |
| `--email-to`      | Multiple | Recipient addresses        |

**See**: [ALERTS.md](ALERTS.md) for complete alert setup including Telegram, Discord, and email configuration.

#### Signal Management

| Option              | Type    | Default | Description               |
| ------------------- | ------- | ------- | ------------------------- |
| `--signal-cooldown` | Integer | 15      | Signal cooldown (minutes) |

#### Configuration Management

| Option           | Type | Description                   |
| ---------------- | ---- | ----------------------------- |
| `--config`, `-c` | Path | Load config from JSON file    |
| `--print-config` | Flag | Print effective configuration |

---

### `backtest` Command

Run historical backtests to evaluate strategy performance.

```bash
ema-scanner backtest SYMBOLS... --start-date YYYY-MM-DD --end-date YYYY-MM-DD [OPTIONS]
```

#### Required Arguments

| Argument       | Type     | Description                     |
| -------------- | -------- | ------------------------------- |
| `SYMBOLS`      | Multiple | One or more symbols to backtest |
| `--start-date` | Date     | Backtest start (YYYY-MM-DD)     |
| `--end-date`   | Date     | Backtest end (YYYY-MM-DD)       |

#### Backtest Options

| Option              | Type    | Default  | Description                             |
| ------------------- | ------- | -------- | --------------------------------------- |
| `--style`           | Choice  | intraday | Trading style preset                    |
| `--capital`         | Float   | 100000.0 | Initial capital                         |
| `--position-size`   | Float   | 10.0     | Position size (% of capital)            |
| `--commission`      | Float   | 0.0      | Commission per trade                    |
| `--slippage`        | Float   | 0.05     | Slippage (% of price)                   |
| `--report`          | Path    | -        | Save detailed JSON report               |
| `--walk-forward`    | Flag    | false    | Enable walk-forward validation          |
| `--wf-in-sample`    | Integer | 500      | Walk-forward in-sample window (bars)    |
| `--wf-out-sample`   | Integer | 100      | Walk-forward out-of-sample window (bars)|
| `--verbose`, `-v`   | Flag    | false    | Verbose logging                         |

**Example**:

```bash
ema-scanner backtest XLK XLF --start-date 2023-01-01 --end-date 2023-12-31 --style swing
```

**See**: [BACKTESTING.md](BACKTESTING.md) for complete guide with performance metrics and optimization.

---

### `stats` Command

Display API usage statistics and cache status.

```bash
ema-scanner stats
```

**Output includes**:

- Total API calls made
- Current calls per minute rate
- Cache directory location
- Number of cached files
- Total cache size

---

### `clear-cache` Command

Clear all cached data (holdings, historical bars).

```bash
ema-scanner clear-cache [OPTIONS]
```

| Option        | Description              |
| ------------- | ------------------------ |
| `--yes`, `-y` | Skip confirmation prompt |

---

### `config-show` Command

Display configuration settings as formatted JSON.

```bash
ema-scanner config-show [CONFIG_PATH]
```

| Argument      | Required | Description                 |
| ------------- | -------- | --------------------------- |
| `CONFIG_PATH` | No       | Path to config file to show |

---

### `config-save` Command

Save configuration settings to a JSON file.

```bash
ema-scanner config-save OUTPUT_PATH [OPTIONS]
```

| Argument      | Required | Description            |
| ------------- | -------- | ---------------------- |
| `OUTPUT_PATH` | Yes      | Path to save config to |

| Option          | Description              |
| --------------- | ------------------------ |
| `--style`, `-s` | Trading style to save    |
| `--force`, `-f` | Overwrite if file exists |

---

## Environment Variables

All settings can be configured via environment variables. Use `EMA_` prefix for scanner settings and specific prefixes for providers.

**See**: [CLI_SETTINGS.md](CLI_SETTINGS.md) for complete environment variable documentation.

---

## Configuration Files

Save complex configurations as JSON files:

```bash
# Create config
ema-scanner config-save my_config.json --style swing

# Use config
ema-scanner --config my_config.json
```

**See**: [CONFIGURATION_MANAGEMENT.md](CONFIGURATION_MANAGEMENT.md) for configuration precedence and management.

---

## Quick Examples

### Basic Scanning

```bash
# Quick test
ema-scanner --once

# Swing trading
ema-scanner --style swing --subset growth_sectors

# Custom ETFs
ema-scanner --etfs XLK XLF --refresh-rate 10
```

### Holdings Scanning

```bash
# Enable with defaults
ema-scanner --scan-holdings

# Custom settings
ema-scanner --scan-holdings --holdings-count 20 --holdings-concurrent 3
```

### Data Providers

```bash
# Alpaca real-time
ema-scanner --provider alpaca --alpaca-key KEY --alpaca-secret SECRET

# Polygon
export POLYGON_API_KEY="your_key"
ema-scanner --provider polygon
```

### Filter Customization

```bash
# Minimal filters
ema-scanner --disable-rsi --disable-adx

# All filters enabled
ema-scanner --enable-macd --volume-multiplier 2.0
```

For comprehensive examples and use cases, see the topic-specific documentation:

- **Advanced Features**: [CLI_ADVANCED_FEATURES.md](CLI_ADVANCED_FEATURES.md)
- **Configuration**: [CONFIGURATION_MANAGEMENT.md](CONFIGURATION_MANAGEMENT.md)
- **Alerts**: [ALERTS.md](ALERTS.md)
- **Holdings**: [HOLDINGS_SCANNING.md](HOLDINGS_SCANNING.md)
- **Backtesting**: [BACKTESTING.md](BACKTESTING.md)
- **Monitoring**: [MONITORING.md](MONITORING.md)

---

## Getting Help

```bash
# General help
ema-scanner --help

# Command-specific help
ema-scanner backtest --help
```

---

## See Also

- [Main README](../README.md) - Project overview and quick start
- [CLI Advanced Features](CLI_ADVANCED_FEATURES.md) - Multi-timeframe and cloud customization
- [Configuration Management](CONFIGURATION_MANAGEMENT.md) - Configuration precedence and persistence
- [CLI Settings](CLI_SETTINGS.md) - Environment variables reference
- [Monitoring](MONITORING.md) - System management and statistics
