# CLI Settings with Pydantic-Settings

The EMA Cloud CLI uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) for configuration management and [platformdirs](https://platformdirs.readthedocs.io/) for cross-platform directory detection, providing type-safe settings with automatic environment variable support.

## Features

- **Type-safe configuration** - All settings are validated using Pydantic models
- **Environment variable support** - Configure the CLI via environment variables
- **Cross-platform directory handling** - Uses platformdirs for standard config locations
- **Platform-aware paths** - Automatic platform-appropriate config directories
- **Validation** - Built-in validation for all settings values
- **Singleton pattern** - Efficient reuse of settings across the application

## Configuration Sources

Settings are loaded in this priority order (highest to lowest):

1. **Command-line arguments** - Explicit CLI flags always take precedence
2. **Environment variables** - Prefixed with `EMA_CLI_`
3. **`.env` file** - Located in the config directory
4. **Default values** - Built-in defaults

## Environment Variables

All CLI settings can be configured via environment variables with the `EMA_CLI_` prefix:

### Configuration Paths

```bash
# Custom config directory
export EMA_CLI_CONFIG_DIR="~/my_configs"

# Custom config filename (default: config.json)
export EMA_CLI_CONFIG_FILENAME="my_scanner.json"
```

### CLI Preferences

```bash
# Enable verbose logging by default
export EMA_CLI_VERBOSE=true

# Disable terminal dashboard by default
export EMA_CLI_NO_DASHBOARD=true

# Scan during extended hours by default
export EMA_CLI_ALL_HOURS=true

# Dashboard refresh rate in seconds (1-60)
export EMA_CLI_DASHBOARD_REFRESH_RATE=3
```

### Logging

```bash
# Log level override
export EMA_CLI_LOG_LEVEL=INFO

# Log directory and filename
export EMA_CLI_LOG_DIR="~/logs"
export EMA_CLI_LOG_FILENAME="scanner.log"

# Log rotation and retention
export EMA_CLI_LOG_ROTATION="size:10MB"
export EMA_CLI_LOG_RETENTION="7"
```

## Usage Examples

### Using Environment Variables

```bash
# Set config directory and enable verbose logging
export EMA_CLI_CONFIG_DIR="/tmp/my_scanner"
export EMA_CLI_VERBOSE=true

# Run scanner (will use environment settings)
uv run python run.py --once
```

### Using .env File

Create a `.env` file in your config directory:

```env
# .env file example
EMA_CLI_VERBOSE=true
EMA_CLI_DASHBOARD_REFRESH_RATE=5
EMA_CLI_NO_DASHBOARD=false
```

The `.env` file is read from the config directory (default platform path or `EMA_CLI_CONFIG_DIR`).

### Programmatic Access

```python
from ema_cloud_cli.settings import get_cli_settings, CLISettings

# Get global settings instance
settings = get_cli_settings()
print(f"Config path: {settings.get_config_path()}")

# Create custom settings instance
custom_settings = CLISettings(
    verbose=True,
    config_dir="/custom/path",
    dashboard_refresh_rate=5
)
```

### Testing with Custom Settings

```python
from ema_cloud_cli.settings import reset_cli_settings, CLISettings

# Reset global instance for testing
reset_cli_settings()

# Create test settings
test_settings = CLISettings(config_dir="/tmp/test")
```

## Default Platform Paths

The scanner uses platform-specific directories for configuration, logs, and cache following OS conventions via [platformdirs](https://platformdirs.readthedocs.io/):

| Resource Type          | Linux                                                                                              | macOS                                                         | Windows                                             |
| ---------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- | --------------------------------------------------- |
| **Configuration File** | `~/.config/ema-cloud-scanner/config.json`                                                          | `~/Library/Application Support/ema-cloud-scanner/config.json` | `%APPDATA%\ema-cloud-scanner\config.json`           |
| **Log Files**          | `~/.local/state/ema-cloud-scanner/log/scanner.log` or `~/.cache/ema-cloud-scanner/log/scanner.log` | `~/Library/Logs/ema-cloud-scanner/scanner.log`                | `%LOCALAPPDATA%\ema-cloud-scanner\Logs\scanner.log` |
| **Cache Directory**    | `~/.cache/ema-cloud-scanner/`                                                                      | `~/Library/Caches/ema-cloud-scanner/`                         | `%LOCALAPPDATA%\ema-cloud-scanner\Cache\`           |
| **State Directory**    | `~/.local/state/ema-cloud-scanner/`                                                                | `~/Library/Application Support/ema-cloud-scanner/`            | `%LOCALAPPDATA%\ema-cloud-scanner\`                 |

**Benefits of platformdirs:**

- Follows platform standards and best practices
- Handles edge cases and special directories automatically
- Respects XDG Base Directory specification on Linux
- Tested across all major platforms

### Customizing Paths

Override default locations using environment variables:

```bash
# Custom config directory
export EMA_CLI_CONFIG_DIR="/path/to/custom/config"

# Custom config file name
export EMA_CLI_CONFIG_FILENAME="my_config.json"

# Custom log directory (affects log file location)
export EMA_CLI_LOG_DIR="/path/to/custom/logs"

# Custom log filename
export EMA_CLI_LOG_FILENAME="ema-scanner.log"

# Log level override
export EMA_CLI_LOG_LEVEL="DEBUG"

# Log rotation (size-based)
export EMA_CLI_LOG_ROTATION="size:10MB"

# Log retention (backup file count)
export EMA_CLI_LOG_RETENTION="7"
```

**Note**: When using the dashboard, the exact log file path is displayed at startup.

## Settings Reference

### CLISettings

All available settings and their defaults:

| Setting                  | Type           | Default         | Description                           |
| ------------------------ | -------------- | --------------- | ------------------------------------- |
| `config_dir`             | `Path \| None` | `None`          | Custom config directory path          |
| `config_filename`        | `str`          | `"config.json"` | Configuration file name               |
| `verbose`                | `bool`         | `False`         | Enable verbose logging                |
| `no_dashboard`           | `bool`         | `False`         | Disable terminal dashboard            |
| `all_hours`              | `bool`         | `False`         | Scan during extended hours            |
| `dashboard_refresh_rate` | `int`          | `1`             | Dashboard refresh rate (1-60 seconds) |
| `log_dir`                | `Path \| None` | `None`          | Custom log directory path             |
| `log_filename`           | `str`          | `"scanner.log"` | Log filename                          |
| `log_level`              | `str \| None`  | `None`          | Log level override                    |
| `log_rotation`           | `str \| None`  | `None`          | Log rotation policy (size)            |
| `log_retention`          | `str \| None`  | `None`          | Log retention (backup count)          |

## Validation

Settings are automatically validated:

```python
from ema_cloud_cli.settings import CLISettings
from pydantic import ValidationError

# This will raise a validation error
try:
    settings = CLISettings(dashboard_refresh_rate=100)  # Max is 60
except ValidationError as e:
    print(e)
```

## Migration from Old Config System

The new pydantic-settings system is **backward compatible** with existing configuration files. Your existing `config.json` files will continue to work without changes.

### Benefits of Migration

1. **Type Safety** - Settings are validated at runtime
2. **Environment Variables** - Easy configuration without editing files
3. **Better Error Messages** - Clear validation errors with helpful messages
4. **Modern Standards** - Uses industry-standard Pydantic and platformdirs libraries
5. **Cross-Platform Compatibility** - Robust directory handling via platformdirs
6. **Testing Support** - Easy to mock and test settings

### What Changed

- Added new `settings.py` module with `CLISettings` model
- Integrated platformdirs for cross-platform config directory detection
- Updated `config_store.py` to use pydantic-settings for path management
- Added environment variable support with `EMA_CLI_` prefix
- Enhanced validation for all settings values
- Improved error handling and logging

### Backward Compatibility

All existing functionality is preserved:

```python
# These still work exactly as before
from ema_cloud_cli.config_store import (
    load_user_config,
    save_user_config,
    get_user_config_path,
)

config = load_user_config()  # Still works
save_user_config(config)     # Still works
```

## Testing

Comprehensive tests are included:

```bash
# Run settings tests
uv run pytest packages/ema_cloud_cli/tests/test_settings.py -v

# Run config_store tests
uv run pytest packages/ema_cloud_cli/tests/test_config_store.py -v
```

## Best Practices

1. **Use environment variables for deployment** - Set config paths and preferences via env vars in production
2. **Use .env files for development** - Keep local development settings in a `.env` file (don't commit it)
3. **Use command-line args for one-offs** - Override specific settings for individual runs
4. **Use config.json for scanner settings** - Scanner-specific settings (filters, clouds) still use JSON config

## Troubleshooting

### Config not found

```bash
# Check where the CLI is looking for config
python -c "from ema_cloud_cli.settings import get_cli_settings; print(get_cli_settings().get_config_path())"
```

### Environment variables not working

```bash
# Verify environment variables are set
env | grep EMA_CLI

# Test loading
python -c "from ema_cloud_cli.settings import get_cli_settings; s = get_cli_settings(); print(f'Verbose: {s.verbose}')"
```

### Validation errors

```python
from ema_cloud_cli.settings import CLISettings

# This will show detailed validation errors
try:
    settings = CLISettings(dashboard_refresh_rate=-1)
except Exception as e:
    print(e)
```

## Further Reading

- [Pydantic Settings Documentation](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [platformdirs Documentation](https://platformdirs.readthedocs.io/)
- [Environment Variables Best Practices](https://12factor.net/config)
- [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html)
- [EMA Cloud Scanner README](../../README.md)
