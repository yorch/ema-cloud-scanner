# Interactive Features Guide

Complete guide to the interactive terminal dashboard features, keyboard shortcuts, and real-time configuration management.

## Table of Contents

- [Dashboard Overview](#dashboard-overview)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Settings Modal](#settings-modal)
- [Real-Time Configuration Updates](#real-time-configuration-updates)
- [Log Viewer](#log-viewer)
- [Navigation](#navigation)

---

## Dashboard Overview

The terminal dashboard is built with **Textual** (not Rich) and provides a fully interactive TUI (Terminal User Interface) for monitoring sector ETFs in real-time.

### Dashboard Layout

```text
╔═══════════════════════════════════════════════════════════════════════╗
║ EMA Cloud Sector Scanner                                             ║
╠═══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  ┌─────────────────────────────┬─────────────────────────────────┐  ║
║  │ Sector ETF Overview         │ Recent Signals                  │  ║
║  ├─────────────────────────────┼─────────────────────────────────┤  ║
║  │ Symbol │ Sector   │ Price   │ Time     │ Symbol │ Dir │ Type │  ║
║  │ XLK    │ Tech     │ $234.56 │ 14:32:15 │ XLE    │ ↑   │ Flip │  ║
║  │ XLF    │ Finance  │ $45.23  │ 14:28:45 │ XLK    │ ↑   │ Pull │  ║
║  │ XLV    │ Health   │ $156.78 │ 14:15:22 │ XLV    │ ↓   │ Xros │  ║
║  └─────────────────────────────┴─────────────────────────────────┘  ║
║                                                                       ║
║  ┌──────────────────────────────────────────────────────────────┐   ║
║  │ Application Logs (press 'l' to toggle)                       │   ║
║  │ [14:35:22] INFO: Scan cycle completed - 11 ETFs analyzed     │   ║
║  │ [14:35:20] INFO: XLE signal detected: CLOUD_FLIP (STRONG)    │   ║
║  └──────────────────────────────────────────────────────────────┘   ║
║                                                                       ║
╠═══════════════════════════════════════════════════════════════════════╣
║ ETFs: 11 │ 🟢 6 🔴 3 ⚪ 2 │ Signals: 47 │ Scan: 2s ago            ║
╠═══════════════════════════════════════════════════════════════════════╣
║ q: Quit │ r: Refresh │ d: Dark Mode │ s: Settings │ l: Logs         ║
╚═══════════════════════════════════════════════════════════════════════╝
```

### Dashboard Components

| Component         | Description                              | Auto-Update |
|-------------------|------------------------------------------|-------------|
| **Header**        | Application title and current time       | Every scan  |
| **ETF Table**     | Real-time sector ETF data and trends     | Every scan  |
| **Signals Table** | Recent signal alerts (last 50)           | On signal   |
| **Log Viewer**    | Live application logs (toggleable)       | Continuous  |
| **Status Bar**    | System stats, ETF counts, last scan time | Every scan  |
| **Footer**        | Keyboard shortcuts reference             | Static      |

---

## Keyboard Shortcuts

### Global Shortcuts (Available Anywhere)

| Key | Action              | Description                                      |
|-----|---------------------|--------------------------------------------------|
| `q` | **Quit**            | Exit the application gracefully                  |
| `r` | **Refresh**         | Force immediate scan cycle                       |
| `d` | **Toggle Dark Mode** | Switch between dark and light themes            |
| `s` | **Settings**        | Open interactive settings modal                  |
| `l` | **Toggle Logs**     | Show/hide the application log viewer             |

### Settings Modal Shortcuts

| Key       | Action              | Description                                |
|-----------|---------------------|--------------------------------------------|
| `↑` / `↓` | **Navigate**        | Move between settings options              |
| `Enter`   | **Select/Confirm**  | Apply selected setting or confirm changes  |
| `Esc`     | **Cancel**          | Close settings modal without saving        |
| `Tab`     | **Next Field**      | Move to next input field                   |
| `Shift+Tab` | **Previous Field** | Move to previous input field               |
| `Space`   | **Toggle Checkbox** | Enable/disable filter checkboxes           |

### Table Navigation Shortcuts

| Key       | Action              | Description                        |
|-----------|---------------------|------------------------------------|
| `↑` / `↓` | **Row Navigation**  | Move cursor up/down in table       |
| `PgUp`    | **Page Up**         | Scroll up one page                 |
| `PgDn`    | **Page Down**       | Scroll down one page               |
| `Home`    | **First Row**       | Jump to first table row            |
| `End`     | **Last Row**        | Jump to last table row             |

---

## Settings Modal

The settings modal allows **live configuration updates** without restarting the scanner.

### Opening Settings

Press `s` to open the settings modal.

### Available Settings

#### 1. Trading Style Selection

```text
┌────────────────────────────────────────┐
│ Trading Style                          │
├────────────────────────────────────────┤
│ ○ Scalping     (1m/5m charts)         │
│ ● Intraday     (5m/10m charts)        │  ← Current selection
│ ○ Swing        (1h/4h charts)         │
│ ○ Position     (Daily charts)         │
│ ○ Long-term    (Daily/Weekly charts)  │
└────────────────────────────────────────┘
```

**Effect**: Changes timeframes, enabled clouds, and confirmation bars based on preset.

#### 2. ETF Selection

```text
┌────────────────────────────────────────┐
│ ETF Selection                          │
├────────────────────────────────────────┤
│ ● All Sectors       (11 ETFs)         │  ← Current selection
│ ○ Growth Sectors    (XLK, XLY, XLC)   │
│ ○ Defensive Sectors (XLP, XLV, XLU)   │
│ ○ Cyclical Sectors  (XLI, XLB, XLE)   │
│ ○ Rate Sensitive    (XLF, XLRE, XLU)  │
│ ○ Commodity Linked  (XLE, XLB)        │
│ ○ Custom...                            │
└────────────────────────────────────────┘
```

**Effect**: Filters which ETFs are monitored during scanning.

#### 3. Signal Filters

```text
┌────────────────────────────────────────┐
│ Signal Confirmation Filters            │
├────────────────────────────────────────┤
│ [×] Volume     (> 1.5x average)       │  ← Enabled
│ [×] RSI        (14-period, 70/30)     │  ← Enabled
│ [×] ADX        (> 20 trending)        │  ← Enabled
│ [ ] VWAP       (price alignment)      │  ← Disabled
│ [ ] ATR        (0.5%-5% range)        │  ← Disabled
│ [ ] MACD       (histogram confirm)    │  ← Disabled
│ [×] Time-of-Day (avoid first/last 15min) │
└────────────────────────────────────────┘
```

**Effect**: Enables/disables confirmation filters for signal validation.

#### 4. Display Options

```text
┌────────────────────────────────────────┐
│ Display Options                        │
├────────────────────────────────────────┤
│ Refresh Rate: [  5 ] seconds          │
│                                        │
│ [×] Show all ETFs (even no signals)   │
│ [×] Show signal history (last 50)     │
│ [×] Color-coded trends                │
│ [ ] Detailed signal notes             │
└────────────────────────────────────────┘
```

**Effect**: Controls dashboard update frequency and display preferences.

### Applying Settings

1. **Make Changes**: Navigate and modify settings using arrow keys and Space/Enter
2. **Confirm**: Press Enter on "Apply Changes" button or use `Ctrl+S`
3. **Cancel**: Press `Esc` to close without saving
4. **Auto-Save**: Settings are automatically saved to user config on apply

---

## Real-Time Configuration Updates

### Configuration Flow

```text
User opens settings (press 's')
    ↓
Modify configuration in modal
    ↓
Apply changes (Enter on button)
    ↓
on_config_update callback triggered
    ↓
Scanner.apply_config(new_config)
    ↓
Rebuild indicators and filters
    ↓
Continue scanning with new settings
    ↓
Save to user config file
```

### What Updates Immediately

| Setting Category | Hot Reload | Requires Restart |
|------------------|------------|------------------|
| Trading Style    | ✅ Yes     | No               |
| ETF Selection    | ✅ Yes     | No               |
| Signal Filters   | ✅ Yes     | No               |
| Refresh Rate     | ✅ Yes     | No               |
| Display Options  | ✅ Yes     | No               |
| Data Provider    | ❌ No      | Yes              |
| API Keys         | ❌ No      | Yes              |

### Configuration Precedence

Settings are loaded in the following priority order (highest to lowest):

1. **CLI Arguments** → `ema-scanner --style swing --etfs XLK XLF`
2. **Environment Variables** → `EMA_SCANNER_*` and `EMA_CLI_*`
3. **User Config File** → `~/.config/ema-cloud-scanner/config.json` (Linux/macOS) or `%APPDATA%\ema-cloud-scanner\config.json` (Windows)
4. **Default Values** → Built-in presets from `TRADING_PRESETS`

### Configuration Persistence

#### User Config Location

The configuration is stored in platform-appropriate locations. See [CLI_SETTINGS.md - Default Platform Paths](CLI_SETTINGS.md#default-platform-paths) for the complete table of configuration file, log file, cache, and state directory locations for all platforms.

#### Custom Config Location

Override default locations using environment variables. See [CLI_SETTINGS.md - Customizing Paths](CLI_SETTINGS.md#customizing-paths) for the complete list of available environment variables.

#### Auto-Save Behavior

- Settings are **automatically saved** when applied via the settings modal
- Changes made via CLI arguments are **not saved** to user config
- Manual config file edits are **loaded on startup** but can be overridden by CLI args

---

## Log Viewer

### Toggling Log Viewer

Press `l` to show/hide the application log viewer.

### Log Viewer Features

- **Real-time streaming**: Logs appear instantly as events occur
- **Configurable buffer**: Default 100 lines, adjustable via dashboard settings
- **Color coding**: Different log levels have distinct colors
- **Auto-scroll**: Automatically scrolls to newest logs
- **Manual scroll**: Use arrow keys to review history

### Log Levels and Colors

| Level     | Color  | Description                        |
|-----------|--------|------------------------------------|
| DEBUG     | Gray   | Detailed diagnostic information    |
| INFO      | Blue   | Normal operational messages        |
| WARNING   | Yellow | Warning messages (non-critical)    |
| ERROR     | Red    | Error messages (critical)          |
| CRITICAL  | Red Bold | Critical failures                |

### Example Log Output

```text
[14:35:22] INFO: Starting scan cycle for 11 ETFs
[14:35:23] DEBUG: Fetching data for XLK from Yahoo Finance
[14:35:24] INFO: XLE signal detected: CLOUD_FLIP (STRONG)
[14:35:24] DEBUG: Signal strength: 85% (6/6 clouds aligned)
[14:35:25] WARNING: XLV: ADX below threshold (18.5 < 20.0)
[14:35:26] INFO: Scan cycle completed in 4.2 seconds
```

### Filtering Logs

Use the settings modal to adjust log verbosity:

```text
┌────────────────────────────────────────┐
│ Logging Options                        │
├────────────────────────────────────────┤
│ Log Level: [INFO     ▼]               │
│                                        │
│ [×] Show DEBUG messages                │
│ [×] Show INFO messages                 │
│ [×] Show WARNING messages              │
│ [×] Show ERROR messages                │
└────────────────────────────────────────┘
```

### Log File Location

In addition to the dashboard log viewer, logs are written to files:

| Platform | Default Path                                      |
|----------|---------------------------------------------------|
| Linux    | `~/.local/state/ema-cloud-scanner/scanner.log`          |
| macOS    | `~/Library/Logs/ema-cloud-scanner/scanner.log`          |
| Windows  | `%LOCALAPPDATA%\ema-cloud-scanner\Logs\scanner.log`     |

See [Logging Guide](LOGGING.md) for complete log management documentation.

---

## Navigation

### Table Navigation

Both the ETF table and Signals table support keyboard navigation:

#### Moving Between Tables

1. Press `Tab` to move focus to the next table
2. Press `Shift+Tab` to move focus to the previous table
3. Currently focused table has a highlighted border

#### Scrolling Within Tables

- **Arrow Keys**: `↑` and `↓` to move row by row
- **Page Navigation**: `PgUp` and `PgDn` to scroll by page
- **Jump Navigation**: `Home` to top, `End` to bottom
- **Mouse Wheel**: Scroll with mouse wheel (if terminal supports it)

### Cursor Behavior

- **Zebra Stripes**: Alternating row colors for readability
- **Row Highlighting**: Current row is highlighted with cursor
- **Auto-scroll**: New signals automatically scroll to bottom
- **Manual Override**: Manual scrolling temporarily disables auto-scroll

---

## Advanced Features

### Dashboard Refresh Control

The dashboard refreshes at configurable intervals:

```python
# Default refresh rate: 2 seconds
# Configurable via settings modal: 1-60 seconds

# Manual refresh
Press 'r' to force immediate refresh
```

### Dark Mode Toggle

Press `d` to toggle between dark and light themes:

- **Dark Mode** (default): Dark background, light text
- **Light Mode**: Light background, dark text
- **System Theme**: Follows terminal color scheme (if supported)

### Status Bar Information

The status bar displays real-time system information:

```text
ETFs: 11 │ 🟢 6 🔴 3 ⚪ 2 │ Signals: 47 │ Scan: 2s ago │ API: 142 calls
```

| Indicator      | Description                                    |
|----------------|------------------------------------------------|
| **ETFs**       | Total number of ETFs being monitored           |
| **🟢 Bullish** | Count of ETFs in bullish trend (above 34-50)   |
| **🔴 Bearish** | Count of ETFs in bearish trend (below 34-50)   |
| **⚪ Neutral** | Count of ETFs in neutral/choppy trend          |
| **Signals**    | Total signals generated this session           |
| **Scan**       | Time since last scan cycle                     |
| **API**        | Total API calls made to data providers         |

---

## Troubleshooting

### Dashboard Not Updating

**Symptom**: Tables show stale data, no new signals appearing

**Solutions**:

1. Press `r` to force manual refresh
2. Check if market is open: `MarketHours.is_market_open()`
3. Verify scan interval setting (Settings → Display Options)
4. Check logs (`l`) for error messages

### Settings Not Persisting

**Symptom**: Settings reset on restart

**Solutions**:

1. Verify config file location: check `EMA_CLI_CONFIG_DIR` environment variable
2. Ensure write permissions on config directory
3. Check for CLI argument overrides (CLI args take precedence)
4. Review logs for "Failed to save config" errors

### Keyboard Shortcuts Not Working

**Symptom**: Key presses don't trigger actions

**Solutions**:

1. Ensure terminal emulator supports key bindings
2. Check for conflicting terminal shortcuts
3. Try alternative keys: `Ctrl+C` for quit if `q` doesn't work
4. Verify Textual version: `pip show textual` (requires ≥0.40)

### Log Viewer Performance

**Symptom**: Dashboard slows down with log viewer open

**Solutions**:

1. Reduce log buffer size in settings (default: 100 lines)
2. Increase log level to INFO or WARNING (hide DEBUG messages)
3. Toggle logs off (`l`) when not needed
4. Check for excessive logging in custom handlers

---

## Best Practices

### Efficient Dashboard Usage

1. **Hide logs when not debugging**: Toggle off (`l`) to improve performance
2. **Use appropriate refresh rate**: 2-5 seconds for live trading, 10-30 seconds for casual monitoring
3. **Filter ETFs strategically**: Monitor only relevant sectors to reduce noise
4. **Enable only necessary filters**: Disable unused confirmation filters to speed up processing

### Configuration Management

1. **Save presets**: Create multiple config files for different trading styles
2. **Use CLI args for temporary changes**: Test settings without affecting saved config
3. **Document custom configs**: Add comments in JSON for complex configurations
4. **Backup configs regularly**: Copy `config.json` before major changes

### Monitoring Best Practices

1. **Check status bar regularly**: Monitor ETF counts and API call usage
2. **Review logs periodically**: Press `l` to check for warnings or errors
3. **Force refresh when needed**: Use `r` after market events (news, earnings)
4. **Adjust refresh rate dynamically**: Slow down during quiet periods, speed up during volatility

---

## See Also

- [CLI Settings Guide](CLI_SETTINGS.md) - Environment variables and configuration management
- [Logging Guide](LOGGING.md) - Log file management and troubleshooting
- [Main README](../README.md) - Installation and quick start guide
- [Project Guidelines](../AGENTS.md) - Development patterns and architecture
