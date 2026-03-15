# Advanced CLI Features

This guide covers the newly exposed advanced features in the CLI that were previously only available through the Python API.

## Multi-Timeframe Analysis

### Overview

Multi-timeframe confirmation uses multiple timeframes to validate signals, reducing false positives.

### Basic Usage

**Set custom primary timeframe:**

```bash
uv run python run.py --timeframe 5m --style intraday
```

**Add confirmation timeframes:**

```bash
uv run python run.py --timeframe 1h --confirm-timeframes 4h --confirm-timeframes 1d --style swing
```

**Disable multi-timeframe confirmation:**

```bash
uv run python run.py --disable-mtf --style swing
```

### Examples

**Scalping setup (1m primary, 5m confirmation):**

```bash
uv run python run.py \
  --style scalping \
  --timeframe 1m \
  --confirm-timeframes 5m \
  --etfs XLK XLF
```

**Swing trading (4h primary, daily confirmation):**

```bash
uv run python run.py \
  --style swing \
  --timeframe 4h \
  --confirm-timeframes 1d \
  --subset growth_sectors
```

**Intraday without MTF (faster signals):**

```bash
uv run python run.py \
  --style intraday \
  --timeframe 10m \
  --disable-mtf
```

---

## EMA Cloud Customization

### Overview

Control which of the 6 EMA clouds are active for signal generation.

**Available clouds:**

- `trend_line` - 5-12 EMA (short-term trend)
- `pullback` - 8-9 EMA (entry timing)
- `momentum` - 20-21 EMA (momentum confirmation)
- `trend_confirmation` - 34-50 EMA (primary trend filter) ⭐
- `long_term` - 72-89 EMA (intermediate trend)
- `major_trend` - 200-233 EMA (long-term direction)

### Basic Usage

**Enable specific clouds only:**

```bash
uv run python run.py \
  --enable-clouds trend_confirmation \
  --enable-clouds long_term \
  --enable-clouds major_trend
```

**Disable specific clouds:**

```bash
uv run python run.py \
  --disable-clouds pullback \
  --disable-clouds major_trend
```

**Adjust cloud thickness threshold:**

```bash
uv run python run.py --cloud-thickness 0.1
```

### Examples

**Conservative signals (only major clouds):**

```bash
uv run python run.py \
  --style swing \
  --enable-clouds trend_confirmation \
  --enable-clouds long_term \
  --cloud-thickness 0.15
```

**Aggressive scalping (fast clouds only):**

```bash
uv run python run.py \
  --style scalping \
  --enable-clouds trend_line \
  --enable-clouds pullback \
  --cloud-thickness 0.02
```

**Disable noisy clouds:**

```bash
uv run python run.py \
  --style intraday \
  --disable-clouds pullback \
  --disable-clouds major_trend
```

---

## Configuration Management

### Save Configuration

**Save current config:**

```bash
uv run python run.py config-save my_config.json --style swing
```

**Save with force overwrite:**

```bash
uv run python run.py config-save my_config.json --style position --force
```

### Load Configuration

**Load saved config:**

```bash
uv run python run.py --config my_config.json
```

**Override specific settings:**

```bash
uv run python run.py \
  --config my_config.json \
  --timeframe 1h \
  --etfs XLK XLF
```

### View Configuration

**Show current config:**

```bash
uv run python run.py config-show
```

**Show specific config file:**

```bash
uv run python run.py config-show my_config.json
```

---

## Complete Examples

### Example 1: Conservative Swing Trading Setup

```bash
uv run python run.py \
  --style swing \
  --timeframe 4h \
  --confirm-timeframes 1d \
  --enable-clouds trend_confirmation \
  --enable-clouds long_term \
  --enable-clouds major_trend \
  --cloud-thickness 0.2 \
  --subset growth_sectors \
  --enable-adx \
  --enable-rsi \
  --adx-period 20 \
  --rsi-period 14
```

**What this does:**

- Uses 4-hour charts with daily confirmation
- Only signals from major clouds (34-50, 72-89, 200-233)
- Higher cloud thickness threshold (0.2%) for quality signals
- Monitors growth sectors only (XLK, XLY, XLC)
- ADX + RSI filters for trend strength

---

### Example 2: Aggressive Intraday Scalping

```bash
uv run python run.py \
  --style scalping \
  --timeframe 1m \
  --confirm-timeframes 5m \
  --enable-clouds trend_line \
  --enable-clouds pullback \
  --cloud-thickness 0.02 \
  --etfs XLK \
  --disable-adx \
  --enable-volume \
  --volume-multiplier 2.0
```

**What this does:**

- 1-minute charts with 5-minute confirmation
- Fast clouds only (5-12, 8-9) for quick entries
- Lower thickness threshold (0.02%) for more signals
- Single high-volume sector (XLK - Technology)
- Volume-focused filtering (2x average volume required)

---

### Example 3: Save Custom Configuration

```bash
# 1. Create custom config with specific settings
uv run python run.py config-save swing_conservative.json \
  --style swing \
  --force

# 2. Edit config file manually to customize further
cat swing_conservative.json | jq '.filters.adx_min_strength = 25' > swing_conservative_tmp.json
mv swing_conservative_tmp.json swing_conservative.json

# 3. Use the custom config
uv run python run.py \
  --config swing_conservative.json \
  --timeframe 4h \
  --confirm-timeframes 1d
```

---

### Example 4: Position Trading with Holdings Scanning

```bash
uv run python run.py \
  --style position \
  --timeframe 1d \
  --enable-clouds trend_confirmation \
  --enable-clouds long_term \
  --enable-clouds major_trend \
  --scan-holdings \
  --holdings-count 15 \
  --holdings-concurrent 3 \
  --subset defensive_sectors
```

**What this does:**

- Daily charts for position trading
- Major trend clouds only
- Scans top 15 holdings of each defensive sector ETF
- Limited concurrency (3) to avoid rate limits
- Focuses on defensive sectors (XLP, XLV, XLU)

---

## Comparison: Before vs After

### Before (Limited Options)

```bash
uv run python run.py --style swing --etfs XLK
```

- ✅ Choose trading style preset
- ❌ Cannot customize timeframes
- ❌ Cannot select specific clouds
- ❌ Cannot save configuration

### After (Full Control)

```bash
uv run python run.py \
  --style swing \
  --timeframe 4h \
  --confirm-timeframes 1d \
  --enable-clouds trend_confirmation long_term \
  --cloud-thickness 0.15 \
  --etfs XLK
```

- ✅ Choose trading style preset
- ✅ Custom primary timeframe
- ✅ Multi-timeframe confirmation
- ✅ Select specific clouds
- ✅ Adjust cloud sensitivity
- ✅ Can save with `config-save`

---

## Best Practices

### 1. Match Timeframes to Trading Style

- **Scalping**: 1m-5m primary, 5m-15m confirmation
- **Intraday**: 10m-30m primary, 1h-4h confirmation
- **Swing**: 1h-4h primary, 4h-1d confirmation
- **Position**: 1d primary, 1wk confirmation

### 2. Cloud Selection Strategy

- **Fast signals**: trend_line, pullback, momentum
- **Quality signals**: trend_confirmation, long_term, major_trend
- **Balanced**: trend_line, momentum, trend_confirmation

### 3. Cloud Thickness Guidelines

- **Scalping**: 0.02% - 0.05% (more signals)
- **Intraday**: 0.05% - 0.10% (balanced)
- **Swing**: 0.10% - 0.20% (quality signals)
- **Position**: 0.20%+ (high conviction)

### 4. Configuration Management

- Save base configs for each trading style
- Use `--config` to load, then override specific settings
- Version control your config files
- Document what each config file is optimized for

---

## Troubleshooting

### Issue: Too many signals

**Solution:**

```bash
# Increase cloud thickness and enable fewer clouds
uv run python run.py \
  --enable-clouds trend_confirmation long_term \
  --cloud-thickness 0.15
```

### Issue: Missing signals

**Solution:**

```bash
# Lower threshold and add more clouds
uv run python run.py \
  --cloud-thickness 0.05 \
  --enable-clouds trend_line momentum trend_confirmation
```

### Issue: Timeframe not supported by data provider

**Solution:**

```bash
# Supported intervals: 1m, 5m, 10m, 15m, 30m, 1h (or 60m), 4h, 1d, 1wk, 1mo
# Use supported intervals
uv run python run.py --timeframe 5m --confirm-timeframes 1h
```

---

## Additional Resources

- **Strategy Documentation**: See `PRD_Detailed.md` for Ripster's EMA Cloud methodology
- **Configuration Schema**: See `packages/ema_cloud_lib/src/ema_cloud_lib/config/settings.py`
- **API Examples**: See `README.md` for Python API usage
