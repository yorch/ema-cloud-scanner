# Configuration Management Guide

Complete guide to configuration persistence, precedence, and management in the EMA Cloud Scanner.

## Table of Contents

- [Configuration Sources](#configuration-sources)
- [Configuration Precedence](#configuration-precedence)
- [User Config Persistence](#user-config-persistence)
- [Environment Variables](#environment-variables)
- [Configuration Files](#configuration-files)
- [Programmatic Configuration](#programmatic-configuration)
- [Configuration Updates](#configuration-updates)

---

## Configuration Sources

The scanner loads configuration from multiple sources in priority order:

```text
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Priority                    │
├─────────────────────────────────────────────────────────────┤
│ 1. CLI Arguments     (--style swing --etfs XLK XLF)        │  ← Highest
│ 2. Environment Vars  (EMA_CLI_*, EMA_SCANNER_*)            │
│ 3. User Config File  (~/.config/ema-cloud-scanner/config.json)   │
│ 4. Default Values    (TRADING_PRESETS)                     │  ← Lowest
└─────────────────────────────────────────────────────────────┘
```

### Source Characteristics

| Source          | Persistence | Scope       | Override | Use Case             |
| --------------- | ----------- | ----------- | -------- | -------------------- |
| **CLI Args**    | None        | Single run  | All      | Temporary testing    |
| **Env Vars**    | Session     | Session     | Config   | CI/CD, containers    |
| **Config File** | Permanent   | User        | Defaults | Personal preferences |
| **Defaults**    | Built-in    | Application | None     | Fallback values      |

---

## Configuration Precedence

### How Precedence Works

```python
# Example: Trading style configuration

# 1. CLI argument (highest priority)
ema-scanner --style swing
# Result: Uses SWING preset

# 2. Environment variable
export EMA_SCANNER_TRADING_STYLE=intraday
ema-scanner
# Result: Uses INTRADAY preset

# 3. User config file
# ~/.config/ema-cloud-scanner/config.json: {"trading_style": "position"}
ema-scanner
# Result: Uses POSITION preset

# 4. Default value (lowest priority)
ema-scanner
# Result: Uses INTRADAY preset (built-in default)
```

### Precedence Rules

1. **CLI arguments override everything**: Explicit user intent for current run
2. **Environment variables override files**: Useful for automation and CI/CD
3. **User config overrides defaults**: Personal preferences persist across sessions
4. **Defaults provide fallback**: Ensures system always has valid configuration

### Partial Overrides

Configuration sources can partially override settings:

```bash
# User config file contains full configuration
# ~/.config/ema-cloud-scanner/config.json
{
  "trading_style": "swing",
  "active_sectors": ["XLK", "XLF", "XLV"],
  "filters": {
    "volume_enabled": true,
    "rsi_enabled": true,
    "adx_enabled": true
  }
}

# CLI override only trading style
ema-scanner --style intraday

# Result: Uses INTRADAY style but keeps:
# - active_sectors from config file
# - filters from config file
```

---

## User Config Persistence

### Config File Location

The user configuration is stored in platform-appropriate locations following OS conventions:

#### Default Locations

| Platform    | Config Path                                                   |
| ----------- | ------------------------------------------------------------- |
| **Linux**   | `~/.config/ema-cloud-scanner/config.json`                     |
| **macOS**   | `~/Library/Application Support/ema-cloud-scanner/config.json` |
| **Windows** | `%APPDATA%\ema-cloud-scanner\config.json`                     |

#### Custom Location

Override the default location using environment variables:

```bash
# Custom config directory
export EMA_CLI_CONFIG_DIR="/opt/trading/configs"

# Custom config filename
export EMA_CLI_CONFIG_FILENAME="my_scanner_config.json"

# Combined result
# /opt/trading/configs/my_scanner_config.json
```

See [CLI Settings Guide](CLI_SETTINGS.md) for complete environment variable documentation.

### Auto-Save Behavior

Configuration is automatically saved in the following scenarios:

| Trigger                  | Auto-Save | Location    | Notes                        |
| ------------------------ | --------- | ----------- | ---------------------------- |
| **Settings Modal Apply** | ✅ Yes     | User config | Immediate save on "Apply"    |
| **CLI Argument**         | ❌ No      | N/A         | Temporary override only      |
| **Programmatic Change**  | ❌ No      | N/A         | Must call `.save()` manually |
| **First Run**            | ✅ Yes     | User config | Creates default config       |

### Manual Save/Load

```python
from ema_cloud_lib.config.settings import ScannerConfig

# Load from file
config = ScannerConfig.load("/path/to/config.json")

# Modify configuration
config.trading_style = TradingStyle.SWING
config.filters.volume_enabled = True

# Save to file
config.save("/path/to/config.json")
```

### Config File Format

User config files are stored as JSON with Pydantic v2 serialization:

```json
{
  "trading_style": "intraday",
  "active_sectors": [
    "technology",
    "financials",
    "healthcare",
    "energy"
  ],
  "custom_symbols": [],
  "ema_clouds": {
    "trendline": {
      "fast_period": 5,
      "slow_period": 12,
      "enabled": true
    },
    "pullback": {
      "fast_period": 8,
      "slow_period": 9,
      "enabled": true
    },
    "momentum": {
      "fast_period": 20,
      "slow_period": 21,
      "enabled": true
    },
    "trend_confirmation": {
      "fast_period": 34,
      "slow_period": 50,
      "enabled": true
    },
    "long_term": {
      "fast_period": 72,
      "slow_period": 89,
      "enabled": false
    },
    "major_trend": {
      "fast_period": 200,
      "slow_period": 233,
      "enabled": false
    }
  },
  "filters": {
    "volume_enabled": true,
    "volume_multiplier": 1.5,
    "volume_lookback_periods": 20,
    "rsi_enabled": true,
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "adx_enabled": true,
    "adx_period": 14,
    "adx_min": 20,
    "vwap_enabled": false,
    "atr_enabled": false,
    "atr_period": 14,
    "atr_min_percent": 0.5,
    "atr_max_percent": 5.0,
    "macd_enabled": false,
    "time_filter_enabled": true,
    "time_filter_start": "09:45",
    "time_filter_end": "15:45",
    "min_cloud_thickness_percent": 0.1
  },
  "data_provider": {
    "primary": "yahoo",
    "fallback_providers": ["alpaca", "polygon"],
    "timeout_seconds": 30,
    "max_retries": 3,
    "api_keys": {}
  },
  "alerts": {
    "console_enabled": true,
    "console_colors": true,
    "desktop_enabled": false,
    "desktop_sound": true,
    "telegram_enabled": false,
    "telegram_bot_token": null,
    "telegram_chat_id": null,
    "discord_enabled": false,
    "discord_webhook_url": null
  },
  "scan_interval": 60,
  "dashboard_refresh_rate": 2,
  "show_all_etfs": true
}
```

---

## Environment Variables

All configuration settings can be overridden via environment variables. This is useful for:

- **CI/CD pipelines**: Set credentials and behavior without config files
- **Containers**: Configure scanner behavior at runtime
- **Security**: Keep API keys out of committed configuration files

**Complete reference**: See [CLI_SETTINGS.md](CLI_SETTINGS.md) for comprehensive environment variable documentation including:

- CLI behavior and logging configuration
- Scanner operational settings
- Data provider API keys
- Alert service credentials
- Filter and signal parameters

---

## Configuration Files

### Multiple Config Files

Manage multiple configurations for different scenarios:

```bash
# Create separate configs
mkdir -p ~/trading/configs

# Scalping config
cat > ~/trading/configs/scalping.json <<EOF
{
  "trading_style": "scalping",
  "active_sectors": ["technology", "financials"],
  "scan_interval": 30
}
EOF

# Swing config
cat > ~/trading/configs/swing.json <<EOF
{
  "trading_style": "swing",
  "active_sectors": ["all"],
  "scan_interval": 300
}
EOF

# Use specific config
ema-scanner --config ~/trading/configs/scalping.json
```

### Config File Validation

The scanner validates configuration on load using Pydantic v2:

```python
from ema_cloud_lib.config.settings import ScannerConfig
from pydantic import ValidationError

try:
    config = ScannerConfig.load("config.json")
except ValidationError as e:
    print(f"Invalid configuration: {e}")
    # Example errors:
    # - trading_style: Invalid enum value
    # - scan_interval: Must be >= 1 second
    # - rsi_period: Must be positive integer
```

### Config File Migration

Configuration files include a `schema_version` field and are automatically migrated when loaded:

```python
from ema_cloud_lib.config.settings import ScannerConfig, migrate_config

# migrate_config() is called automatically by ScannerConfig.load()
# It detects the schema version and applies sequential migrations

# Manual migration example:
old_config = {"trading_style": "swing", "filters": {"volume_enabled": True}}
migrated = migrate_config(old_config)
# Result: schema_version set to current, filter_weights added to filters
```

#### Schema Versions

| Version | Changes |
|---------|---------|
| 1 (implicit) | Original schema, no `schema_version` field |
| 2 (current) | Added `schema_version`, `filter_weights` in filters section |

#### How Migration Works

1. On `ScannerConfig.load()`, config JSON is parsed
2. `migrate_config()` detects the current version (defaults to 1 if missing)
3. Registered migration functions are applied sequentially (v1→v2, v2→v3, etc.)
4. The migrated config is validated by Pydantic

```python
# Example config file (current schema v2)
{
  "schema_version": 2,
  "trading_style": "swing",
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

#### Adding New Migrations

New migrations are registered with the `@_register_migration` decorator in `settings.py`:

```python
@_register_migration(2)  # Migrates from v2 → v3
def _migrate_v2_to_v3(config: dict) -> dict:
    # Apply changes for v3
    return config
```

---

## Programmatic Configuration

### Python API Usage

```python
from ema_cloud_lib import EMACloudScanner
from ema_cloud_lib.config.settings import (
    ScannerConfig,
    TradingStyle,
    FilterConfig,
    AlertConfig,
)

# Create config from defaults
config = ScannerConfig()

# Create config from preset
config = ScannerConfig(trading_style=TradingStyle.SWING)

# Create config with custom settings
config = ScannerConfig(
    trading_style=TradingStyle.INTRADAY,
    active_sectors=["technology", "financials", "healthcare"],
    filters=FilterConfig(
        volume_enabled=True,
        volume_multiplier=2.0,
        rsi_enabled=True,
        adx_enabled=True,
        adx_min=25,
    ),
    alerts=AlertConfig(
        console_enabled=True,
        desktop_enabled=True,
        telegram_enabled=False,
    ),
    scan_interval=30,
)

# Use config with scanner
scanner = EMACloudScanner(config)
```

### Loading from File

```python
# Load existing config
config = ScannerConfig.load("~/trading/configs/my_config.json")

# Modify and save
config.trading_style = TradingStyle.SWING
config.filters.adx_min = 30
config.save("~/trading/configs/my_config.json")
```

### Config Builder Pattern

```python
from ema_cloud_lib.config.settings import ScannerConfig, TradingStyle

# Start with preset
config = ScannerConfig(trading_style=TradingStyle.SWING)

# Customize incrementally
config.active_sectors = ["technology", "healthcare"]
config.filters.volume_multiplier = 2.0
config.filters.adx_min = 25
config.scan_interval = 120

# Save final config
config.save("custom_swing.json")
```

---

## Configuration Updates

### Live Updates (Hot Reload)

Some configuration changes can be applied without restarting:

#### Hot-Reloadable Settings

| Setting Category  | Hot Reload | Notes                           |
| ----------------- | ---------- | ------------------------------- |
| Trading Style     | ✅ Yes      | Rebuilds indicators and filters |
| ETF Selection     | ✅ Yes      | Updates active symbol list      |
| Signal Filters    | ✅ Yes      | Reconfigures filter thresholds  |
| Scan Interval     | ✅ Yes      | Updates timer immediately       |
| Dashboard Refresh | ✅ Yes      | Changes UI update frequency     |
| Display Options   | ✅ Yes      | UI-only changes                 |

#### Restart-Required Settings

| Setting Category | Hot Reload | Reason                               |
| ---------------- | ---------- | ------------------------------------ |
| Data Provider    | ❌ No       | Requires connection teardown/rebuild |
| API Keys         | ❌ No       | Security: avoid in-memory key change |
| Alert Channels   | ❌ No       | Handler initialization required      |

### Updating via Settings Modal

```python
# Settings modal workflow (handled automatically)

# 1. User opens modal (press 's')
# 2. User modifies settings
# 3. User applies changes
# 4. Dashboard triggers callback:

def on_config_update(new_config: ScannerConfig):
    # Apply hot-reloadable changes
    scanner.apply_config(new_config)

    # Save to user config
    from ema_cloud_cli.config_store import save_user_config
    save_user_config(new_config)

    # Dashboard continues with new config
```

### Updating via API

```python
# Programmatic update during runtime

scanner = EMACloudScanner(config)
await scanner.start()

# Update configuration
new_config = ScannerConfig(trading_style=TradingStyle.POSITION)
scanner.apply_config(new_config)

# Scanner continues with new config
```

### Config Change Notifications

Monitor configuration changes:

```python
import logging

logger = logging.getLogger("ema_cloud_lib.config")
logger.setLevel(logging.INFO)

# Log output on config changes:
# [INFO] Configuration updated: trading_style changed from INTRADAY to SWING
# [INFO] Rebuilding indicators with new preset
# [INFO] Active clouds: 20-21, 34-50, 72-89
# [INFO] Configuration applied successfully
```

---

## Best Practices

### Development vs Production

```bash
# Development: Use CLI args for quick testing
ema-scanner --style scalping --once -v

# Production: Use config files for consistency
ema-scanner --config /opt/trading/production.json
```

### Config File Organization

```text
~/trading/configs/
├── base.json              # Base configuration
├── scalping.json          # 1m/5m charts
├── intraday.json          # 5m/10m charts
├── swing.json             # 1h/4h charts
├── position.json          # Daily charts
└── custom_tech_only.json  # Custom sector focus
```

### Version Control

```bash
# Store configs in git
git add configs/*.json
git commit -m "Add trading configurations"

# Exclude API keys
echo "configs/*_keys.json" >> .gitignore

# Use templates for sensitive data
cp config.template.json config.json
# Edit config.json with actual API keys
```

### Configuration Documentation

Add comments to JSON (using special `_comment` keys):

```json
{
  "_comment_trading": "Swing trading preset for 1-4 hour timeframes",
  "trading_style": "swing",

  "_comment_sectors": "Focus on growth and tech sectors only",
  "active_sectors": ["technology", "consumer_discretionary"],

  "_comment_filters": "Aggressive filtering for high-quality signals",
  "filters": {
    "volume_multiplier": 2.0,
    "adx_min": 25
  }
}
```

### Config Backup Strategy

```bash
# Manual backup before changes
cp ~/.config/ema-cloud-scanner/config.json \
   ~/.config/ema-cloud-scanner/config.json.backup

# Automated backup on save (handled by config_store.py)
# Creates config.json.bak automatically

# Restore from backup
cp ~/.config/ema-cloud-scanner/config.json.bak \
   ~/.config/ema-cloud-scanner/config.json
```

---

## Troubleshooting

### Config Not Loading

**Symptom**: Scanner uses defaults instead of saved config

**Solutions**:

1. Verify config file location:

   ```bash
   python -c "from ema_cloud_cli.config_store import get_user_config_path; print(get_user_config_path())"
   ```

2. Check file permissions: ensure config file is readable
3. Validate JSON syntax: use `python -m json.tool config.json`
4. Check for environment variable overrides: `env | grep EMA_`

### Settings Not Persisting

**Symptom**: Settings reset after restart

**Solutions**:

1. Check if CLI arguments are overriding config
2. Verify write permissions on config directory
3. Look for "Failed to save config" in logs
4. Ensure config directory exists

### Invalid Configuration Errors

**Symptom**: ValidationError on config load

**Solutions**:

1. Check error message for specific field
2. Validate against schema in `ScannerConfig` class
3. Use default config as template: `ScannerConfig().save("template.json")`
4. Remove invalid fields and let defaults apply

### Precedence Confusion

**Symptom**: Settings don't match expectations

**Solutions**:

1. Check all config sources: CLI args > env vars > file > defaults
2. Use `--verbose` flag to see config loading process
3. Print effective config: `ema-scanner --print-config`
4. Remove conflicting environment variables

---

## See Also

- [CLI Settings Guide](CLI_SETTINGS.md) - Environment variables and pydantic-settings
- [Interactive Features](INTERACTIVE_FEATURES.md) - Settings modal and dashboard
- [Logging Guide](LOGGING.md) - Log configuration and management
- [Main README](../README.md) - Installation and quick start guide
