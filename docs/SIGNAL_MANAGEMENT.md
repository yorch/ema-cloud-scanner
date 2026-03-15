# Signal Management Guide

Complete guide to signal generation, deduplication, cooldown strategies, and state management.

## Table of Contents

- [Signal Generation Overview](#signal-generation-overview)
- [Signal Deduplication](#signal-deduplication)
- [Cooldown Strategy](#cooldown-strategy)
- [Signal State Management](#signal-state-management)
- [Historical Signal Tracking](#historical-signal-tracking)
- [Signal Validation](#signal-validation)

---

## Signal Generation Overview

### Signal Generation Pipeline

```text
┌─────────────────────────────────────────────────────────────────┐
│                     Signal Generation Pipeline                   │
└─────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                    ┌─────────────────────┐
                    │   Fetch OHLCV Data  │
                    │  (Data Providers)   │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Calculate EMA Clouds│
                    │   (All 6 Clouds)    │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Detect Patterns    │
                    │ (Cloud Flip, Cross) │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Apply Filters      │
                    │ (Volume, RSI, ADX)  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  Calculate Strength │
                    │  (VERY_STRONG → WEAK)│
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Deduplication Check │  ← THIS GUIDE
                    │   (Cooldown Logic)  │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │   Emit Signal       │
                    │ (Alerts + Dashboard)│
                    └─────────────────────┘
```

### Signal Types

| Type               | Description                             | Frequency    |
| ------------------ | --------------------------------------- | ------------ |
| **CLOUD_FLIP**     | Fast EMA crosses slow EMA (cloud)       | Moderate     |
| **PRICE_CROSS**    | Price breaks above/below cloud          | High         |
| **CLOUD_BOUNCE**   | Price bounces off cloud support/resist  | Moderate     |
| **PULLBACK_ENTRY** | Price retraces to 8-9 cloud for entry   | Low-Moderate |
| **ALIGNMENT**      | All clouds align in same direction      | Very Low     |
| **WATERFALL**      | All 6 clouds perfectly stacked in order | Very Low     |

### Signal Strength Levels

| Strength    | Criteria                                                        | Alert Priority |
| ----------- | --------------------------------------------------------------- | -------------- |
| VERY_STRONG | 6/6 clouds aligned, all filters pass, ADX > 30, waterfall bonus | 🔴 Critical     |
| STRONG      | 5+ clouds aligned, key filters pass, ADX > 25                   | 🟠 High         |
| MODERATE    | 4 clouds aligned, most filters pass, ADX > 20                   | 🟡 Medium       |
| WEAK        | 3 clouds aligned, some filters fail                             | 🟢 Low          |
| VERY_WEAK   | < 3 clouds aligned, multiple filter failures                    | ⚪ Info         |

> **Note**: Signal strength is also influenced by the **weighted filter score** and **cloud stacking bonus**. A waterfall pattern adds +5 to the strength score, while partial stacking adds a proportional bonus. See [Advanced Features](ADVANCED_FEATURES.md#cloud-stacking--waterfall-detection) for details.

---

## Signal Deduplication

### Why Deduplication is Needed

**Problem**: Without deduplication, the scanner would generate duplicate signals:

```text
Scan Cycle 1 (14:30:00): XLK CLOUD_FLIP detected → Alert sent ✅
Scan Cycle 2 (14:31:00): XLK CLOUD_FLIP still active → Alert sent again ❌ DUPLICATE
Scan Cycle 3 (14:32:00): XLK CLOUD_FLIP still active → Alert sent again ❌ DUPLICATE
```

This creates alert fatigue and makes it difficult to distinguish new signals from ongoing ones.

### Deduplication Strategy

The scanner uses **two-level deduplication**:

1. **Bar-level deduplication** (SignalGenerator)
2. **Time-based cooldown** (EMACloudScanner)

### Level 1: Bar-Level Deduplication

**Location**: `signals/generator.py`

```python
class SignalGenerator:
    def __init__(self, ...):
        # Track recent signals to avoid duplicates
        self._recent_signals: dict[str, Signal] = {}
        self._signal_cooldown_bars = 5  # Don't alert same signal within 5 bars
```

**How it works**:

```python
def _should_generate_signal(self, symbol: str, signal_type: str) -> bool:
    """Check if enough bars have passed since last signal of this type"""
    key = f"{symbol}|{signal_type}"

    last_signal = self._recent_signals.get(key)
    if last_signal:
        bars_elapsed = self._current_bar_index - last_signal.bar_index
        if bars_elapsed < self._signal_cooldown_bars:
            return False  # Too soon, skip this signal

    return True
```

**Example**: On 5-minute charts with 5-bar cooldown:

- Signal at 14:30 → Alert ✅
- Same signal at 14:35 → Suppressed (1 bar)
- Same signal at 14:40 → Suppressed (2 bars)
- Same signal at 14:50 → Suppressed (4 bars)
- Same signal at 14:55 → Alert ✅ (5 bars elapsed)

### Level 2: Time-Based Cooldown

**Location**: `scanner.py`

```python
class EMACloudScanner:
    def __init__(self, config: ScannerConfig | None = None):
        # State tracking
        self._recent_signals: dict[str, Signal] = {}
        self._signal_cooldown: dict[str, datetime] = {}

        # Cooldown period to avoid duplicate signals (minutes)
        self.signal_cooldown_minutes = 15  # Configurable
```

**Implementation**:

```python
def _should_alert_signal(self, signal: Signal) -> bool:
    """Check if we should alert for this signal (cooldown check)"""
    # Create unique key for signal type
    key = f"{signal.symbol}|{signal.direction}|{signal.signal_type.value}"

    # Check cooldown
    last_alert = self._signal_cooldown.get(key)
    if last_alert:
        elapsed = datetime.now() - last_alert
        if elapsed.total_seconds() < self.signal_cooldown_minutes * 60:
            logger.debug(
                f"Signal {key} suppressed: {elapsed.total_seconds():.0f}s "
                f"< {self.signal_cooldown_minutes * 60}s cooldown"
            )
            return False

    # Update cooldown timestamp
    self._signal_cooldown[key] = datetime.now()
    return True
```

**Example**: With 15-minute cooldown:

- XLK LONG CLOUD_FLIP at 14:30 → Alert ✅
- XLK LONG CLOUD_FLIP at 14:35 → Suppressed (5 min < 15 min)
- XLK LONG CLOUD_FLIP at 14:40 → Suppressed (10 min < 15 min)
- XLK LONG CLOUD_FLIP at 14:45 → Alert ✅ (15 min elapsed)
- XLK SHORT CLOUD_FLIP at 14:50 → Alert ✅ (different direction, separate cooldown)

---

## Cooldown Strategy

### Cooldown Parameters

| Parameter                 | Default | Range | Location        | Purpose                  |
| ------------------------- | ------- | ----- | --------------- | ------------------------ |
| `signal_cooldown_bars`    | 5       | 1-20  | SignalGenerator | Bar-level deduplication  |
| `signal_cooldown_minutes` | 15      | 1-120 | EMACloudScanner | Time-based deduplication |

### Configuring Cooldown

**Option 0: CLI Flag**

```bash
# Set cooldown to 30 minutes
ema-scanner --signal-cooldown 30
```

**Option 1: Programmatic Configuration**

```python
from ema_cloud_lib import EMACloudScanner
from ema_cloud_lib.config.settings import ScannerConfig

# Configure scanner cooldown
scanner = EMACloudScanner(config)
scanner.signal_cooldown_minutes = 30  # 30-minute cooldown

# Configure generator cooldown (access via scanner)
scanner.signal_generator._signal_cooldown_bars = 10  # 10-bar cooldown
```

**Option 2: Via Config File** (future enhancement)

```json
{
  "signal_management": {
    "cooldown_minutes": 30,
    "cooldown_bars": 10,
    "enable_deduplication": true
  }
}
```

### Cooldown Key Structure

Signals are deduplicated based on a composite key:

```python
key = f"{symbol}|{direction}|{signal_type}"

# Examples:
"XLK|LONG|CLOUD_FLIP"
"XLF|SHORT|PRICE_CROSS"
"XLV|LONG|PULLBACK_ENTRY"
```

This means:

- ✅ Same symbol + same direction + same type → Deduplicated
- ✅ Same symbol + different direction → Separate cooldowns
- ✅ Same symbol + different type → Separate cooldowns
- ✅ Different symbol → Separate cooldowns

### Cooldown Behavior Examples

#### Example 1: Same Signal Repeated

```text
| Time  | Symbol | Dir  | Type       | Action                     |
| ----- | ------ | ---- | ---------- | -------------------------- |
| 14:30 | XLK    | LONG | CLOUD_FLIP | Alert ✅ (first occurrence) |
| 14:35 | XLK    | LONG | CLOUD_FLIP | Suppress (5 min < 15 min)  |
| 14:40 | XLK    | LONG | CLOUD_FLIP | Suppress (10 min < 15 min) |
| 14:45 | XLK    | LONG | CLOUD_FLIP | Alert ✅ (15 min elapsed)   |
```

#### Example 2: Different Signal Types

```text
| Time  | Symbol | Dir  | Type        | Action                    |
| ----- | ------ | ---- | ----------- | ------------------------- |
| 14:30 | XLK    | LONG | CLOUD_FLIP  | Alert ✅ (different key)   |
| 14:32 | XLK    | LONG | PRICE_CROSS | Alert ✅ (different key)   |
| 14:35 | XLK    | LONG | CLOUD_FLIP  | Suppress (5 min < 15 min) |
| 14:35 | XLK    | LONG | PRICE_CROSS | Suppress (3 min < 15 min) |
```

#### Example 3: Direction Change

```text
| Time  | Symbol | Dir   | Type       | Action                        |
| ----- | ------ | ----- | ---------- | ----------------------------- |
| 14:30 | XLK    | LONG  | CLOUD_FLIP | Alert ✅ (first occurrence)    |
| 14:35 | XLK    | SHORT | CLOUD_FLIP | Alert ✅ (different direction) |
| 14:40 | XLK    | LONG  | CLOUD_FLIP | Suppress (10 min < 15 min)    |
| 14:45 | XLK    | SHORT | CLOUD_FLIP | Suppress (10 min < 15 min)    |
```

### Dynamic Cooldown (Future Enhancement)

Potential for adaptive cooldown based on market conditions:

```python
def get_adaptive_cooldown(self, volatility: float, signal_strength: str) -> int:
    """Adjust cooldown based on market conditions"""

    base_cooldown = self.signal_cooldown_minutes

    # Reduce cooldown in high volatility (more signals expected)
    if volatility > 2.0:
        base_cooldown *= 0.5

    # Increase cooldown for weak signals (reduce noise)
    if signal_strength in ["WEAK", "VERY_WEAK"]:
        base_cooldown *= 2.0

    # Reduce cooldown for very strong signals (don't miss opportunities)
    if signal_strength == "VERY_STRONG":
        base_cooldown *= 0.75

    return int(base_cooldown)
```

---

## Signal State Management

### State Tracking Data Structures

```python
class EMACloudScanner:
    def __init__(self, ...):
        # Sector trend states (long-term view)
        self._sector_states: dict[str, SectorTrendState] = {}

        # Recent signals (for reference and deduplication)
        self._recent_signals: dict[str, Signal] = {}

        # Cooldown timestamps (for time-based deduplication)
        self._signal_cooldown: dict[str, datetime] = {}
```

### Sector Trend State

Tracks the overall trend state for each sector ETF:

```python
@dataclass
class SectorTrendState:
    """Represents the trend state of a sector ETF"""
    symbol: str
    sector: str
    trend: TrendDirection  # BULLISH, BEARISH, NEUTRAL
    strength: float  # 0-100%
    cloud_alignment: int  # How many clouds aligned (0-6)
    last_signal: Signal | None
    last_update: datetime
```

**Usage**:

```python
# Track sector states across scan cycles
sector_state = self._sector_states.get("XLK")
if sector_state:
    print(f"XLK trend: {sector_state.trend}")
    print(f"Strength: {sector_state.strength}%")
    print(f"Clouds aligned: {sector_state.cloud_alignment}/6")
```

### Recent Signals Storage

Stores recent signals for historical reference:

```python
# Store signal with composite key
key = f"{signal.symbol}|{signal.timestamp.isoformat()}"
self._recent_signals[key] = signal

# Retrieve recent signals for a symbol
recent = [
    sig for key, sig in self._recent_signals.items()
    if sig.symbol == "XLK"
]
```

### Cooldown Timestamp Tracking

Tracks when each signal type was last alerted:

```python
# Cooldown dictionary structure
self._signal_cooldown = {
    "XLK|LONG|CLOUD_FLIP": datetime(2026, 1, 12, 14, 30, 0),
    "XLK|LONG|PRICE_CROSS": datetime(2026, 1, 12, 14, 32, 15),
    "XLF|SHORT|CLOUD_FLIP": datetime(2026, 1, 12, 14, 28, 45),
}
```

---

## Historical Signal Tracking

### Signal History Buffer

The dashboard maintains a buffer of recent signals for display:

```python
class TerminalDashboard:
    def __init__(self, ...):
        self._signals: list[SignalDisplayData] = []
        self._max_signals = 50  # Keep last 50 signals
```

### Signal Display Data

```python
@dataclass
class SignalDisplayData:
    """Display-friendly signal data for dashboard"""
    timestamp: datetime
    symbol: str
    direction: str  # "LONG" or "SHORT"
    signal_type: str  # "CLOUD_FLIP", "PRICE_CROSS", etc.
    price: float
    strength: str  # "VERY_STRONG", "STRONG", etc.
    is_valid: bool
    notes: str
```

### Adding to History

```python
def add_signal(self, signal: SignalDisplayData) -> None:
    """Add signal to history buffer"""
    # Add to beginning (newest first)
    self._signals.insert(0, signal)

    # Trim to max size
    if len(self._signals) > self._max_signals:
        self._signals = self._signals[:self._max_signals]

    # Update dashboard table
    self._refresh_signals_table()
```

### Retrieving History

```python
# Get all signals
all_signals = dashboard._signals

# Get signals for specific symbol
xlk_signals = [s for s in dashboard._signals if s.symbol == "XLK"]

# Get signals by strength
strong_signals = [
    s for s in dashboard._signals
    if s.strength in ["VERY_STRONG", "STRONG"]
]

# Get signals from last hour
from datetime import datetime, timedelta
one_hour_ago = datetime.now() - timedelta(hours=1)
recent_signals = [
    s for s in dashboard._signals
    if s.timestamp > one_hour_ago
]
```

### Signal History Persistence

**Current**: Signals are stored in-memory only (lost on restart)

**Future Enhancement**: Persist signals to database or file

```python
# Proposed signal history storage
from pathlib import Path
import json

class SignalHistory:
    """Persistent signal history storage"""

    def __init__(self, history_file: Path):
        self.history_file = history_file
        self.signals: list[SignalDisplayData] = []
        self._load()

    def add(self, signal: SignalDisplayData):
        """Add signal and save to file"""
        self.signals.insert(0, signal)
        self._save()

    def _save(self):
        """Save signals to JSON file"""
        data = [asdict(s) for s in self.signals]
        self.history_file.write_text(json.dumps(data, indent=2, default=str))

    def _load(self):
        """Load signals from JSON file"""
        if self.history_file.exists():
            data = json.loads(self.history_file.read_text())
            self.signals = [SignalDisplayData(**s) for s in data]
```

---

## Signal Validation

### Validation Criteria

Signals must pass validation before being alerted:

```python
class Signal:
    def is_valid(self) -> bool:
        """Check if signal meets minimum quality criteria"""
        checks = [
            self.strength != SignalStrength.VERY_WEAK,  # Not too weak
            self.confidence >= 0.6,  # Minimum 60% confidence
            self.filters_passed >= self.filters_enabled * 0.5,  # ≥50% filters pass
        ]
        return all(checks)
```

### Validation Process

```text
Signal Generated
    ↓
Is Valid?
    ├─ Yes → Check Cooldown
    │           ↓
    │      Cooldown OK?
    │           ├─ Yes → Send Alert ✅
    │           └─ No → Suppress (deduplicated)
    │
    └─ No → Discard (quality too low) ❌
```

### Filter Pass Rate

Track which filters contributed to signal validation:

```python
@dataclass
class Signal:
    filters_enabled: int  # Total filters enabled
    filters_passed: int   # Filters that passed
    filter_details: dict[str, bool]  # Detailed filter results

    @property
    def filter_pass_rate(self) -> float:
        """Calculate percentage of filters passed"""
        if self.filters_enabled == 0:
            return 1.0
        return self.filters_passed / self.filters_enabled

# Example usage
if signal.filter_pass_rate >= 0.75:
    print("High-quality signal: 75%+ filters passed")
```

### Invalidation Scenarios

Signals can be invalidated after generation:

```python
def check_signal_invalidation(signal: Signal, current_bar: pd.Series) -> bool:
    """Check if signal is no longer valid"""

    # Price moved against signal too much
    if signal.direction == "LONG" and current_bar.close < signal.stop_loss:
        return True  # Stop loss hit

    # Cloud flipped back (signal reversed)
    if signal.signal_type == SignalType.CLOUD_FLIP:
        if cloud_reversed(current_bar):
            return True

    # Timeframe expired (signal too old)
    age = datetime.now() - signal.timestamp
    if age > timedelta(hours=4):
        return True

    return False  # Signal still valid
```

---

## Best Practices

### Cooldown Configuration

**For Scalping (1m-5m charts)**:

```python
scanner.signal_cooldown_minutes = 5  # Short cooldown
scanner.signal_generator._signal_cooldown_bars = 3
```

**For Intraday (5m-10m charts)**:

```python
scanner.signal_cooldown_minutes = 15  # Default
scanner.signal_generator._signal_cooldown_bars = 5
```

**For Swing Trading (1h-4h charts)**:

```python
scanner.signal_cooldown_minutes = 60  # Longer cooldown
scanner.signal_generator._signal_cooldown_bars = 10
```

### Monitoring Signal Quality

```python
# Track signal statistics
total_signals = len(dashboard._signals)
strong_signals = len([s for s in dashboard._signals if s.strength in ["VERY_STRONG", "STRONG"]])
quality_rate = strong_signals / total_signals if total_signals > 0 else 0

logger.info(f"Signal quality rate: {quality_rate:.1%} ({strong_signals}/{total_signals})")
```

### Managing Alert Fatigue

1. **Enable only necessary filters**: More filters = fewer signals
2. **Increase cooldown period**: Reduce duplicate alerts
3. **Focus on strong signals**: Filter by strength in dashboard
4. **Monitor specific sectors**: Use ETF subsets to reduce noise

---

## See Also

- [Interactive Features](INTERACTIVE_FEATURES.md) - Dashboard signal display
- [Configuration Management](CONFIGURATION_MANAGEMENT.md) - Config file structure
- [Main README](../README.md) - Signal types and strategy overview
- [PRD](../PRD_Detailed.md) - Complete signal methodology
