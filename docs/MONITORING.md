# Monitoring & Observability Guide

Complete guide to health monitoring, performance metrics, error handling, and troubleshooting the EMA Cloud Scanner.

## Table of Contents

- [Health Monitoring](#health-monitoring)
- [Performance Metrics](#performance-metrics)
- [API Usage Tracking](#api-usage-tracking)
- [Error Handling](#error-handling)
- [Troubleshooting](#troubleshooting)

---

> **Note**: For logging configuration, log levels, file locations, and log management, see [LOGGING.md](LOGGING.md).

---

## Health Monitoring

### System Health Checks

Monitor scanner health in real-time:

```python
from ema_cloud_lib import EMACloudScanner

class HealthMonitor:
    """Monitor scanner health and performance"""

    def __init__(self, scanner: EMACloudScanner):
        self.scanner = scanner
        self.last_successful_scan = None
        self.consecutive_failures = 0
        self.total_scans = 0
        self.failed_scans = 0

    def check_health(self) -> dict:
        """Perform health check and return status"""
        checks = {
            "scanner_running": self.scanner._running,
            "data_provider_connected": self._check_data_provider(),
            "last_scan_success": self._check_last_scan(),
            "failure_rate": self.failed_scans / self.total_scans if self.total_scans > 0 else 0,
            "consecutive_failures": self.consecutive_failures,
        }

        health_status = "healthy" if all([
            checks["scanner_running"],
            checks["data_provider_connected"],
            checks["consecutive_failures"] < 3,
            checks["failure_rate"] < 0.1,  # < 10% failure rate
        ]) else "unhealthy"

        return {
            "status": health_status,
            "checks": checks,
            "timestamp": datetime.now().isoformat(),
        }

    def _check_data_provider(self) -> bool:
        """Check if data provider is responsive"""
        try:
            # Attempt simple health check request
            asyncio.run(self.scanner.data_manager.primary_provider.health_check())
            return True
        except Exception:
            return False

    def _check_last_scan(self) -> bool:
        """Check if last scan was successful"""
        if not self.last_successful_scan:
            return False

        time_since_scan = datetime.now() - self.last_successful_scan
        # Scan should succeed at least once per 5 minutes
        return time_since_scan.total_seconds() < 300

# Usage
monitor = HealthMonitor(scanner)
health = monitor.check_health()

if health["status"] == "unhealthy":
    logger.error(f"Health check failed: {health}")
    # Send alert, restart scanner, etc.
```

### Health Check Endpoint (Future Enhancement)

For production deployments, expose HTTP health check endpoint:

```python
from aiohttp import web

async def health_check_handler(request):
    """HTTP health check endpoint"""
    monitor = request.app['health_monitor']
    health = monitor.check_health()

    status = 200 if health["status"] == "healthy" else 503
    return web.json_response(health, status=status)

# Run health check server alongside scanner
app = web.Application()
app['health_monitor'] = HealthMonitor(scanner)
app.router.add_get('/health', health_check_handler)

web.run_app(app, host='0.0.0.0', port=8080)
```

**Health check in Docker Compose:**

```yaml
services:
  ema-scanner:
    build: .
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

---

## Performance Metrics

### Scan Cycle Metrics

Track scanner performance over time:

```python
from dataclasses import dataclass
from datetime import datetime
from collections import deque

@dataclass
class ScanMetrics:
    """Metrics for a single scan cycle"""
    timestamp: datetime
    duration: float  # seconds
    etfs_scanned: int
    signals_generated: int
    api_calls_made: int
    errors_encountered: int

class MetricsCollector:
    """Collect and track scanner performance metrics"""

    def __init__(self, max_history: int = 1000):
        self.metrics_history: deque[ScanMetrics] = deque(maxlen=max_history)

    def record_scan(self, metrics: ScanMetrics):
        """Record metrics from completed scan"""
        self.metrics_history.append(metrics)

    def get_stats(self, window_minutes: int = 60) -> dict:
        """Get aggregate statistics for recent scans"""
        cutoff = datetime.now() - timedelta(minutes=window_minutes)
        recent = [m for m in self.metrics_history if m.timestamp > cutoff]

        if not recent:
            return {"status": "no_data"}

        return {
            "scan_count": len(recent),
            "avg_duration": sum(m.duration for m in recent) / len(recent),
            "max_duration": max(m.duration for m in recent),
            "min_duration": min(m.duration for m in recent),
            "total_signals": sum(m.signals_generated for m in recent),
            "total_api_calls": sum(m.api_calls_made for m in recent),
            "total_errors": sum(m.errors_encountered for m in recent),
            "error_rate": sum(m.errors_encountered for m in recent) / len(recent),
        }

# Usage
collector = MetricsCollector()

# After each scan cycle
metrics = ScanMetrics(
    timestamp=datetime.now(),
    duration=5.2,
    etfs_scanned=11,
    signals_generated=3,
    api_calls_made=11,
    errors_encountered=0
)
collector.record_scan(metrics)

# Get hourly stats
stats = collector.get_stats(window_minutes=60)
logger.info(f"Hourly stats: {stats}")
```

### Performance Monitoring Dashboard

Display performance metrics in terminal dashboard:

```python
class PerformanceWidget(Static):
    """Dashboard widget showing performance metrics"""

    def __init__(self, collector: MetricsCollector):
        super().__init__()
        self.collector = collector

    def render(self) -> str:
        stats = self.collector.get_stats(window_minutes=60)

        return f"""
        Performance (Last Hour):
        ┌────────────────────────────────────────┐
        │ Scans: {stats['scan_count']}            │
        │ Avg Duration: {stats['avg_duration']:.2f}s │
        │ Signals: {stats['total_signals']}       │
        │ API Calls: {stats['total_api_calls']}   │
        │ Error Rate: {stats['error_rate']:.1%}   │
        └────────────────────────────────────────┘
        """
```

---

## API Usage Tracking

### Tracking API Calls

Monitor API usage to stay within provider rate limits:

```python
from ema_cloud_lib import api_call_tracker

# Get current API call count
total_calls = api_call_tracker.get_total_calls()
calls_by_provider = api_call_tracker.get_calls_by_provider()

logger.info(f"Total API calls: {total_calls}")
logger.info(f"Yahoo Finance: {calls_by_provider.get('yahoo', 0)} calls")
logger.info(f"Alpaca: {calls_by_provider.get('alpaca', 0)} calls")

# Reset counter (e.g., daily)
api_call_tracker.reset()
```

### API Rate Limit Monitoring

```python
class RateLimitMonitor:
    """Monitor API usage against rate limits"""

    # Provider rate limits
    LIMITS = {
        "yahoo": {"calls_per_minute": 2000, "calls_per_day": 10000},
        "alpaca": {"calls_per_minute": 200, "calls_per_day": 10000},
        "polygon": {"calls_per_minute": 100, "calls_per_day": 5000},
    }

    def __init__(self):
        self.calls_per_minute = {}
        self.calls_per_day = {}
        self.last_minute_reset = datetime.now()
        self.last_day_reset = datetime.now()

    def record_call(self, provider: str):
        """Record API call"""
        # Reset counters if needed
        now = datetime.now()
        if (now - self.last_minute_reset).total_seconds() >= 60:
            self.calls_per_minute = {}
            self.last_minute_reset = now

        if (now - self.last_day_reset).total_seconds() >= 86400:
            self.calls_per_day = {}
            self.last_day_reset = now

        # Increment counters
        self.calls_per_minute[provider] = self.calls_per_minute.get(provider, 0) + 1
        self.calls_per_day[provider] = self.calls_per_day.get(provider, 0) + 1

        # Check limits
        self._check_limits(provider)

    def _check_limits(self, provider: str):
        """Check if approaching or exceeding limits"""
        limits = self.LIMITS.get(provider, {})

        minute_usage = self.calls_per_minute.get(provider, 0)
        minute_limit = limits.get("calls_per_minute", float('inf'))
        minute_pct = minute_usage / minute_limit if minute_limit else 0

        day_usage = self.calls_per_day.get(provider, 0)
        day_limit = limits.get("calls_per_day", float('inf'))
        day_pct = day_usage / day_limit if day_limit else 0

        # Warning at 80%
        if minute_pct > 0.8:
            logger.warning(
                f"{provider}: Approaching minute rate limit "
                f"({minute_usage}/{minute_limit} calls)"
            )

        if day_pct > 0.8:
            logger.warning(
                f"{provider}: Approaching daily rate limit "
                f"({day_usage}/{day_limit} calls)"
            )

        # Error at 95%
        if minute_pct > 0.95 or day_pct > 0.95:
            logger.error(f"{provider}: Rate limit nearly exceeded, slowing down...")
            # Implement backoff or switch provider

# Usage
rate_monitor = RateLimitMonitor()

# Record each API call
await provider.fetch_bars(symbol)
rate_monitor.record_call("yahoo")
```

---

## Error Handling

### Error Categories

| Category            | Severity | Recovery Strategy                    |
|---------------------|----------|--------------------------------------|
| **Network Timeout** | Medium   | Retry with exponential backoff       |
| **API Rate Limit**  | High     | Switch to fallback provider          |
| **Invalid Data**    | Low      | Skip bar, log warning                |
| **Provider Down**   | High     | Failover to backup provider          |
| **Disk Full**       | Critical | Stop scanner, alert admin            |

### Retry Logic

```python
import asyncio
from typing import TypeVar, Callable

T = TypeVar('T')

async def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0
) -> T:
    """
    Retry function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts
        initial_delay: Initial retry delay in seconds
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
                delay = min(delay * backoff_factor, max_delay)
            else:
                logger.error(f"All {max_retries + 1} attempts failed: {e}")

    raise last_exception

# Usage
data = await retry_with_backoff(
    lambda: provider.fetch_bars(symbol),
    max_retries=3,
    initial_delay=1.0,
    backoff_factor=2.0
)
```

### Circuit Breaker Pattern

Prevent cascading failures:

```python
from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """Circuit breaker for external service calls"""

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout  # seconds

        self.failure_count = 0
        self.success_count = 0
        self.state = CircuitState.CLOSED
        self.last_failure_time = None

    async def call(self, func: Callable) -> T:
        """Execute function through circuit breaker"""

        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker: Attempting reset (HALF_OPEN)")
            else:
                raise Exception("Circuit breaker is OPEN - rejecting call")

        try:
            result = await func()
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info("Circuit breaker: Reset successful (CLOSED)")

    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        self.success_count = 0

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker: Tripped (OPEN) after "
                f"{self.failure_count} failures"
            )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.timeout

# Usage
breaker = CircuitBreaker(failure_threshold=5, timeout=60)

try:
    data = await breaker.call(
        lambda: provider.fetch_bars(symbol)
    )
except Exception as e:
    logger.error(f"Call rejected by circuit breaker: {e}")
    # Use fallback provider or cached data
```

---

## Troubleshooting

### Common Issues

#### Scanner Not Running

**Symptoms**:

- Dashboard shows "Not running"
- No scan cycles executing
- No log output

**Checks**:

1. Verify market hours: `MarketHours.is_market_open()`
2. Check if `--all-hours` flag needed for extended hours
3. Review logs for startup errors
4. Confirm config file is valid

#### High API Usage

**Symptoms**:

- Approaching rate limits
- Slow scan cycles
- Increased costs

**Solutions**:

1. Reduce scan frequency: Increase `scan_interval`
2. Filter ETF list: Use subsets instead of all sectors
3. Enable data caching (future enhancement)
4. Switch to higher-tier API plan

#### Memory Leaks

**Symptoms**:

- Memory usage grows over time
- Scanner slowdown after hours of operation
- System becomes unresponsive

**Checks**:

```python
import psutil
import os

def check_memory_usage():
    """Monitor process memory usage"""
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()

    print(f"RSS: {memory_info.rss / 1024 / 1024:.1f} MB")
    print(f"VMS: {memory_info.vms / 1024 / 1024:.1f} MB")

    if memory_info.rss > 500 * 1024 * 1024:  # > 500 MB
        logger.warning("High memory usage detected")
```

**Solutions**:

1. Reduce signal history buffer size
2. Clear old log entries periodically
3. Restart scanner daily via cron/scheduler
4. Profile with memory_profiler

#### Disk Space Issues

**Symptoms**:

- Log files growing too large
- "Disk full" errors
- Scanner crashes

**Solutions**:

1. Configure log rotation:

   ```bash
   export EMA_CLI_LOG_ROTATION="size:10MB"
   export EMA_CLI_LOG_RETENTION="7"
   ```

2. Monitor disk usage:

   ```bash
   df -h ~/.local/state/ema-cloud-scanner
   ```

3. Clean old logs:

   ```bash
   find ~/.local/state/ema-cloud-scanner -name "*.log.*" -mtime +7 -delete
   ```

---

## Best Practices

### Production Monitoring Checklist

- [ ] Configure INFO-level logging minimum
- [ ] Set up log rotation and retention
- [ ] Monitor API usage against rate limits
- [ ] Implement health check endpoint
- [ ] Track scan cycle performance metrics
- [ ] Set up alerts for errors and failures
- [ ] Monitor memory and disk usage
- [ ] Review logs daily for warnings/errors
- [ ] Test circuit breakers and failover logic
- [ ] Document incident response procedures

### Development Debugging

- [ ] Use DEBUG log level for development
- [ ] Enable verbose output (`-v` or `-vv` flag)
- [ ] Review full stack traces in logs
- [ ] Test with single ETF (`--etfs XLK --once`)
- [ ] Verify data provider responses
- [ ] Check filter configurations
- [ ] Profile performance bottlenecks
- [ ] Test error handling and recovery

---

## See Also

- [Logging Guide](LOGGING.md) - Complete log file management
- [Interactive Features](INTERACTIVE_FEATURES.md) - Dashboard log viewer
- [Security Guide](SECURITY.md) - API key management and security
- [Project Guidelines](../AGENTS.md) - Development patterns
