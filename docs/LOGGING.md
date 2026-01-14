# Logging Configuration

## Overview

The EMA Cloud Scanner uses intelligent logging configuration that adapts based on whether the TUI dashboard is enabled.

## Log Output Behavior

### With Dashboard (Default)

When running with the terminal dashboard (default mode):

```bash
uv run python run.py
```

- **Logs written to file**: `~/Library/Logs/ema-cloud-scanner/scanner.log` (macOS) or equivalent platform-specific location
- **Console output**: Clean TUI interface only, no log messages
- **Third-party loggers**: Suppressed to WARNING level (aiohttp, yfinance, urllib3, asyncio)
- **Log file location displayed**: Shown when the scanner starts

### Without Dashboard

When running without the dashboard:

```bash
uv run python run.py --no-dashboard
```

- **Logs written to**: Console (stdout/stderr)
- **Format**: `YYYY-MM-DD HH:MM:SS - module - LEVEL - message`
- **Console output**: Log messages and simple dashboard output

## Log Levels

### Normal Mode (Default)

```bash
uv run python run.py
```

- Application logs: `INFO` level
- Third-party logs: `WARNING` level (when using dashboard)

### Verbose Mode

```bash
uv run python run.py --verbose
```

- Application logs: `DEBUG` level
- Third-party logs: `WARNING` level (when using dashboard)
- More detailed information about scanner operations

You can also override the log level via environment variable:

```bash
export EMA_CLI_LOG_LEVEL=DEBUG
```

## Log File Location

The log file location is platform-specific. See [CLI_SETTINGS.md - Default Platform Paths](CLI_SETTINGS.md#default-platform-paths) for the complete table of log file, configuration, cache, and state directory locations for all platforms.

The exact log file path is displayed when starting the scanner with the dashboard.

You can override logging paths and filenames with environment variables:

```bash
export EMA_CLI_LOG_DIR="/path/to/logs"
export EMA_CLI_LOG_FILENAME="ema-scanner.log"
```

## Viewing Logs

### Real-time Monitoring

```bash
# macOS/Linux
tail -f ~/Library/Logs/ema-cloud-scanner/scanner.log

# Or find the location first
uv run python run.py  # Shows log path, then Ctrl+C
tail -f <displayed-path>
```

### View Last N Lines

```bash
tail -n 100 ~/Library/Logs/ema-cloud-scanner/scanner.log
```

### Search Logs

```bash
# Find errors
grep ERROR ~/Library/Logs/ema-cloud-scanner/scanner.log

# Find specific symbol
grep XLK ~/Library/Logs/ema-cloud-scanner/scanner.log
```

## Log Rotation

Logs are not rotated by default. You can enable size-based rotation using environment variables:

```bash
export EMA_CLI_LOG_ROTATION="size:10MB"
export EMA_CLI_LOG_RETENTION="7"
```

`EMA_CLI_LOG_RETENTION` controls the number of rotated files to keep.

## Troubleshooting

### Logs appearing in TUI

If you see log messages appearing in the TUI interface:

1. Ensure you're running the latest version
2. Check that `platformdirs` is installed: `uv pip list | grep platformdirs`
3. Verify log file is being created: `ls ~/Library/Logs/ema-cloud-scanner/`

### No log file created

If the log file isn't being created:

1. Check directory permissions
2. Verify `platformdirs` is installed
3. Run with `--verbose` to see configuration details

### Excessive log file size

If the log file grows too large:

1. Use log rotation (see above)
2. Reduce logging verbosity (remove `--verbose` flag)
3. Run with `--no-dashboard` for console-only logging during development

## Implementation Details

The logging configuration is handled in [cli.py](packages/ema_cloud_cli/src/ema_cloud_cli/cli.py):

- `setup_logging(verbose, use_dashboard)` function configures the logging subsystem
- Dashboard mode: Uses `FileHandler` to write to platform-specific log directory
- Console mode: Uses `basicConfig` for stdout/stderr output
- Third-party loggers are set to WARNING level to reduce noise
