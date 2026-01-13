# Product Requirements Document

## EMA Cloud Sector Scanner

**Version:** 1.0
**Date:** January 2026

---

### Overview

Real-time Python scanner that monitors sector ETFs using Ripster's EMA Cloud strategy to identify high-probability trading setups. Generates alerts when price action confirms trend direction across multiple EMA cloud layers.

---

### Problem Statement

Traders manually monitoring multiple sector ETFs for EMA cloud signals is time-consuming and error-prone. Key setups are missed during fast-moving markets, and there's no systematic way to filter signals by strength or confirm with technical indicators.

---

### Target Users

- Active day traders using 10-minute charts
- Swing traders monitoring daily/4-hour timeframes
- Sector rotation strategists

---

### Core Features

| Feature                     | Description                                                          | Priority |
| --------------------------- | -------------------------------------------------------------------- | -------- |
| **Multi-ETF Scanning**      | Monitor all 11 sector SPDRs (XLK, XLF, XLV, etc.) simultaneously     | P0       |
| **EMA Cloud Detection**     | Calculate 6 Ripster clouds (5-12, 8-9, 20-21, 34-50, 72-89, 200-233) | P0       |
| **Signal Generation**       | Detect cloud flips, price crosses, pullback entries                  | P0       |
| **Confirmation Filters**    | Volume (1.5x+), RSI, ADX (>20), VWAP alignment                       | P0       |
| **Signal Strength Rating**  | Score signals from Very Strong to Very Weak                          | P0       |
| **Real-time Alerts**        | Console + desktop notifications                                      | P0       |
| **Trading Style Presets**   | Scalping, Intraday, Swing, Position, Long-term configs               | P1       |
| **Terminal Dashboard**      | Live sector overview with trend status                               | P1       |
| **Holdings Lookup**         | Fetch top 10 stocks per sector ETF                                   | P1       |
| **Backtesting**             | Test strategy on historical data                                     | P2       |
| **Telegram/Discord Alerts** | Push notifications to mobile                                         | P2       |

---

### Signal Logic

**Entry Signals:**

1. **Cloud Flip** — 34-50 EMA cloud changes color (bearish→bullish or vice versa)
2. **Price Cross** — Price breaks above/below cloud with volume confirmation
3. **Pullback Entry** — Price retraces to cloud support/resistance and bounces

**Filters Required:**

- ADX > 20 (trending market)
- Volume > 1.5x 20-period average
- Price respects VWAP direction
- RSI not overbought/oversold against signal direction

**Signal Strength Factors:**

- Cloud alignment (all 6 clouds agree = strongest)
- Filter pass rate
- ADX magnitude
- Volume spike intensity
- Cloud expansion (not contracting)

---

### Technical Architecture

**Dual-Package Workspace:**

```text
ema_cloud_sector_scanner/
├── packages/
│   ├── ema_cloud_lib/          # Core library (framework-agnostic)
│   │   ├── scanner.py          # EMACloudScanner, MarketHours
│   │   ├── config/             # Settings, presets, enums
│   │   ├── indicators/         # EMA cloud calculations
│   │   ├── signals/            # Signal detection
│   │   ├── alerts/             # Alert handlers
│   │   ├── data_providers/     # Yahoo, Alpaca, Polygon
│   │   ├── holdings/           # ETF holdings management
│   │   ├── backtesting/        # Backtest engine
│   │   └── types/              # Protocols, display types
│   │
│   └── ema_cloud_cli/          # CLI application
│       ├── cli.py              # Typer entry point
│       ├── config_store.py     # User preferences
│       └── dashboard/          # Textual-based terminal UI
│
├── pyproject.toml              # Workspace config (uv)
└── run.py                      # Development runner
```

**Component Flow:**

```text
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Data Providers │────▶│  Indicators  │────▶│   Signals   │
│  (Yahoo/Alpaca) │     │  (EMA Clouds)│     │ (Generator) │
└─────────────────┘     └──────────────┘     └──────┬──────┘
                                                    │
                        ┌──────────────┐            │
                        │    Alerts    │◀───────────┤
                        │(Console/Push)│            │
                        └──────────────┘            │
                                                    ▼
                        ┌──────────────┐     ┌─────────────┐
                        │  Dashboard   │◀────│   Scanner   │
                        │ (Textual UI) │     │ (Main Loop) │
                        └──────────────┘     └─────────────┘
```

**Key Design Decisions:**

- **Dual-package architecture**: Core library (`ema_cloud_lib`) is framework-agnostic; CLI (`ema_cloud_cli`) provides terminal UI
- **Dependency injection**: Dashboard integration via `DashboardProtocol` interface
- **Async Python**: Concurrent data fetching with `asyncio` and `aiohttp`
- **Modular plugin architecture**: Swap data providers, add alert channels
- **Configuration-driven**: Pydantic v2 models with JSON serialization
- **Fallback data providers**: Yahoo → Alpaca → Polygon
- **uv workspace management**: Efficient dependency management and development workflow

---

### Configuration Options

```python
# Trading Style Presets
SCALPING:   1m/5m charts,  clouds 5-12/8-9/20-21
INTRADAY:   10m charts,    clouds 8-9/20-21/34-50
SWING:      1h/4h charts,  clouds 20-21/34-50/72-89
POSITION:   Daily charts,  clouds 34-50/72-89/200-233
LONG_TERM:  Weekly charts, clouds 72-89/200-233
```

---

### Success Metrics

| Metric                       | Target                    |
| ---------------------------- | ------------------------- |
| Signal accuracy (backtested) | >55% win rate             |
| Alert latency                | <2 seconds from bar close |
| False positive rate          | <30% of signals           |
| Uptime during market hours   | >99%                      |

---

### Dependencies

**Core Dependencies:**

- `pandas`, `numpy` — Data processing
- `yfinance` — Free market data (primary)
- `pydantic` ≥2.0 — Configuration validation and serialization
- `textual` ≥0.40 — Terminal UI framework
- `typer` — CLI framework
- `aiohttp` — Async HTTP client for data providers

**Optional Dependencies:**

- `alpaca-py` — Real-time data (optional)
- `plyer` — Desktop notifications (optional)
- `polygon-api-client` — Polygon.io data provider (optional)

---

### Out of Scope (v1)

- Web-based dashboard
- Individual stock scanning (ETFs only)
- Options chain integration
- Automated trade execution
- Machine learning signal enhancement

---

### Future Roadmap

**v1.1:** Telegram/Discord push alerts
**v1.2:** Top holdings scanning (stocks within each sector ETF)
**v2.0:** Web dashboard with charts
**v2.1:** Multi-timeframe confirmation (e.g., daily trend + 10m entry)

---

### Usage

```bash
# Installation (dual-package workspace)
# Quick start - run directly without installing (development)
uv run python run.py --once

# Or install packages for persistent use
uv pip install -e packages/ema_cloud_lib
uv pip install -e packages/ema_cloud_cli

# Install with optional dependencies
uv pip install -e "packages/ema_cloud_lib[all]"  # All optional providers

# Run with defaults (intraday, all sectors)
ema-scanner

# Or via development runner
uv run python run.py

# Custom configuration
ema-scanner --style swing --etfs XLK XLF XLE

# Use preset subset
ema-scanner --subset growth_sectors

# Single scan (no continuous monitoring)
ema-scanner --once

# Verbose logging
ema-scanner -v
```
