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
                        │ (Terminal UI)│     │ (Main Loop) │
                        └──────────────┘     └─────────────┘
```

**Key Design Decisions:**

- Async Python for concurrent data fetching
- Modular plugin architecture (swap data providers, add alert channels)
- Configuration-driven (JSON presets per trading style)
- Fallback data providers (Yahoo → Alpaca → Polygon)

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

- `pandas`, `numpy` — Data processing
- `yfinance` — Free market data (primary)
- `alpaca-py` — Real-time data (optional)
- `rich` — Terminal dashboard
- `plyer` — Desktop notifications

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
# Install
pip install -r requirements.txt

# Run with defaults (intraday, all sectors)
python scanner.py

# Custom configuration
python scanner.py --style swing --etfs XLK,XLF,XLE --interval 1h

# Backtest mode
python scanner.py --backtest --days 90 --symbol XLK
```
