# Holdings Scanning

## Overview

The Holdings Scanning feature extends the EMA Cloud Sector Scanner to analyze individual stocks within sector ETF holdings. This provides a powerful filter mechanism: sector ETF trend direction determines which signal types are valid for individual stocks.

## Key Concepts

### Sector Trend Filtering

The core principle of holdings scanning is **sector-based signal filtering**:

- **Bullish Sector** → Only LONG signals for stocks in that sector
- **Bearish Sector** → Only SHORT signals for stocks in that sector
- **Neutral Sector** → Both LONG and SHORT signals allowed

This approach leverages the idea that individual stocks tend to move with their sector. If the Technology sector (XLK) is in a strong bullish trend, short signals on individual tech stocks (AAPL, MSFT, etc.) are filtered out as low-probability setups.

### Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                   Scan Sector ETFs                          │
│              (XLK, XLF, XLV, XLE, etc.)                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │  Determine Sector    │
           │   Trend Direction    │
           │  (Bullish/Bearish/   │
           │      Neutral)        │
           └──────────┬───────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   Fetch Top Holdings        │
        │   (AAPL, MSFT, NVDA, etc.)  │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │  Scan Individual Stocks     │
        │  with EMA Cloud Signals     │
        └─────────────┬───────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   Filter by Sector Trend    │
        │  (Block conflicting signals)│
        └─────────────┬───────────────┘
                      │
                      ▼
           ┌──────────────────────┐
           │   Generate Alerts    │
           │   for Valid Signals  │
           └──────────────────────┘
```

## Usage

### Command Line Interface

**Basic Usage:**

```bash
# Enable holdings scanning with defaults
ema-scanner --scan-holdings

# Specify number of holdings per ETF
ema-scanner --scan-holdings --holdings-count 15

# Control concurrent scans to avoid rate limits
ema-scanner --scan-holdings --holdings-concurrent 3

# Combine with other options
ema-scanner --style swing --subset growth_sectors --scan-holdings --holdings-count 20
```

**CLI Options:**

| Option                  | Default | Description                            |
| ----------------------- | ------- | -------------------------------------- |
| `--scan-holdings`       | False   | Enable holdings scanning               |
| `--holdings-count`      | 10      | Number of top holdings to scan per ETF |
| `--holdings-concurrent` | 5       | Maximum concurrent stock scans per ETF |

### Python API

**Basic Configuration:**

```python
from ema_cloud_lib import EMACloudScanner, ScannerConfig

# Create configuration with holdings scanning enabled
config = ScannerConfig()
config.scan_holdings = True
config.top_holdings_count = 10
config.holdings_max_concurrent = 5

# Create scanner
scanner = EMACloudScanner(config)

# Run continuous monitoring
await scanner.run()
```

**Advanced Usage:**

```python
from ema_cloud_lib.holdings import HoldingsScanner, SectorTrend

# Access holdings scanner directly
if scanner.holdings_scanner:
    # Update sector trend manually
    scanner.holdings_scanner.update_sector_trend(
        etf_symbol="XLK",
        trend=SectorTrend.BULLISH,
        strength=85
    )

    # Set custom holdings
    scanner.holdings_scanner.set_holdings({
        "XLK": ["AAPL", "MSFT", "NVDA", "GOOGL", "META"],
        "XLF": ["JPM", "BAC", "WFC", "C", "GS"]
    })

    # Scan specific ETF holdings
    results = await scanner.holdings_scanner.scan_holdings("XLK")

    # Get filter statistics
    stats = scanner.holdings_scanner.get_sector_filter_stats()
    print(f"Tracking {stats['sectors_tracked']} sectors")
    print(f"Loaded {stats['total_stocks']} stocks")
```

## Filtering Examples

### Example 1: Bullish Technology Sector

**Scenario:**

- XLK (Technology) shows strong bullish trend
- Cloud alignment: All 6 clouds bullish
- Sector strength: 85%

**Stock Scanning:**

- AAPL generates LONG signal → ✅ **Allowed** (matches sector trend)
- MSFT generates SHORT signal → ❌ **Blocked** (conflicts with sector)
- NVDA generates LONG signal → ✅ **Allowed** (matches sector trend)

**Result:** Only LONG signals are alerted for tech stocks.

### Example 2: Bearish Financial Sector

**Scenario:**

- XLF (Financials) shows bearish trend
- Cloud alignment: 34-50 and 72-89 clouds bearish
- Sector strength: 70%

**Stock Scanning:**

- JPM generates SHORT signal → ✅ **Allowed** (matches sector trend)
- BAC generates LONG signal → ❌ **Blocked** (conflicts with sector)
- WFC generates SHORT signal → ✅ **Allowed** (matches sector trend)

**Result:** Only SHORT signals are alerted for financial stocks.

### Example 3: Neutral Healthcare Sector

**Scenario:**

- XLV (Healthcare) shows neutral/choppy trend
- Cloud alignment: Mixed signals
- Sector strength: 45%

**Stock Scanning:**

- JNJ generates LONG signal → ✅ **Allowed** (neutral sector)
- UNH generates SHORT signal → ✅ **Allowed** (neutral sector)
- PFE generates LONG signal → ✅ **Allowed** (neutral sector)

**Result:** Both LONG and SHORT signals are allowed.

## Configuration

### ScannerConfig Settings

```python
class ScannerConfig(BaseModel):
    # Holdings scanning
    scan_holdings: bool = False            # Enable/disable feature
    top_holdings_count: int = 10           # Holdings per ETF (1-50)
    holdings_max_concurrent: int = 5       # Concurrent scans (1-20)
    fetch_holdings: bool = True            # Auto-fetch holdings data
```

**Validation:**

- `top_holdings_count` must be ≥ 1
- `holdings_max_concurrent` must be between 1-20 (to avoid rate limits)

### Holdings Manager Integration

The scanner automatically uses `HoldingsManager` to fetch top holdings:

```python
# Automatic holdings fetching
holdings_data = await scanner.holdings_manager.get_all_sector_holdings(
    etf_symbols=["XLK", "XLF", "XLV"],
    top_n=config.top_holdings_count
)

# Result: {"XLK": ["AAPL", "MSFT", ...], "XLF": ["JPM", "BAC", ...]}
```

Holdings are cached for 24 hours to minimize API calls.

## Alert Format

Stock signals include sector context:

```text
🎯 HOLDINGS SIGNAL: AAPL (XLK)
  Signal: cloud_flip ↑
  Strength: STRONG
  Price: $185.42
  Sector Trend: BULLISH
  Filters: ['volume', 'rsi', 'adx', 'vwap']
```

**Alert Fields:**

- **Symbol**: Individual stock symbol
- **Sector ETF**: Parent sector (e.g., XLK)
- **Signal Type**: cloud_flip, price_cross, pullback, alignment
- **Direction**: ↑ (LONG) or ↓ (SHORT)
- **Strength**: VERY_STRONG, STRONG, MODERATE, WEAK, VERY_WEAK
- **Price**: Current stock price
- **Sector Trend**: BULLISH, BEARISH, or NEUTRAL
- **Filters**: Confirmation filters passed

## Performance Considerations

### Rate Limiting

**Problem:** Scanning many stocks can hit data provider rate limits.

**Solutions:**

1. **Control Concurrency**: Use `holdings_max_concurrent` to limit parallel requests
2. **Limit Holdings**: Reduce `top_holdings_count` to scan fewer stocks
3. **Increase Scan Interval**: Use longer intervals between scan cycles

```bash
# Conservative settings to avoid rate limits
ema-scanner --scan-holdings --holdings-count 5 --holdings-concurrent 2 --interval 120
```

### Data Provider Recommendations

| Provider | Rate Limit     | Recommended Settings                 |
| -------- | -------------- | ------------------------------------ |
| Yahoo    | ~2000 req/hour | `holdings_concurrent=3`, `count=10`  |
| Alpaca   | 200 req/min    | `holdings_concurrent=5`, `count=15`  |
| Polygon  | Higher limits  | `holdings_concurrent=10`, `count=20` |

## Testing

### Unit Tests

```bash
# Run holdings scanner tests
pytest tests/test_holdings_scanner.py -v

# Run with coverage
pytest tests/test_holdings_scanner.py --cov=ema_cloud_lib.holdings
```

### Test Coverage

- ✅ Holdings scanner initialization
- ✅ Sector trend filtering logic
- ✅ Signal strength ordering
- ✅ Bullish sector blocks shorts
- ✅ Bearish sector blocks longs
- ✅ Neutral sector allows both directions
- ✅ Concurrent scanning with limits
- ✅ Statistics and reporting

## Troubleshooting

### No Stock Signals Generated

**Symptoms:** Holdings scanning enabled but no stock signals appear.

**Possible Causes:**

1. **Sector trend filtering**: All signals may be filtered due to sector trends
2. **No holdings data**: Holdings may not be loaded for the ETFs
3. **Strict filters**: Signal strength requirements too high

**Solutions:**

```python
# Check if holdings scanner is active
if scanner.holdings_scanner:
    stats = scanner.holdings_scanner.get_sector_filter_stats()
    print(stats)  # Should show loaded holdings

# Check sector trends
for symbol, state in scanner._sector_states.items():
    print(f"{symbol}: {state.trend}")
```

### Rate Limit Errors

**Symptoms:** Data provider errors, incomplete scans.

**Solutions:**

```bash
# Reduce concurrent scans
ema-scanner --scan-holdings --holdings-concurrent 2

# Reduce holdings count
ema-scanner --scan-holdings --holdings-count 5

# Increase scan interval
ema-scanner --scan-holdings --interval 180
```

### Memory Usage

**Symptoms:** High memory consumption with many holdings.

**Solutions:**

1. Reduce `top_holdings_count`
2. Scan fewer sector ETFs with `--subset`
3. Use `--once` for single scans instead of continuous monitoring

## Future Enhancements

Planned improvements for v1.3+:

- [ ] **Multi-timeframe confirmation**: Check daily trend before intraday signals
- [ ] **Holdings strength scoring**: Weight signals by holding position size
- [ ] **Correlation analysis**: Identify stocks moving independently of sector
- [ ] **Custom stock lists**: User-defined watchlists beyond top holdings
- [ ] **Holdings performance tracking**: Track hit rate per sector
- [ ] **Advanced filters**: Stock-specific filters (market cap, liquidity, etc.)

## References

- [PRD: Holdings Integration](../PRD_Detailed.md#48-holdings-integration)
- [Architecture: Package Structure](../AGENTS.md#package-architecture)
- [Main README: Holdings Scanning](../README.md#holdings-scanning)
- [Tests: Holdings Scanner Tests](../tests/test_holdings_scanner.py)
