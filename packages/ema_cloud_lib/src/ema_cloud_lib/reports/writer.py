"""
Report writer for headless scanner output.

Implements DashboardProtocol to collect scan cycle data and write
structured JSON report files to a configurable directory.
"""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

from ema_cloud_lib.constants import TrendDirection
from ema_cloud_lib.data_providers.base import api_call_tracker
from ema_cloud_lib.market_hours import MarketHours
from ema_cloud_lib.types.display import (
    ETFDisplayData,
    HoldingsETFDisplayData,
    SignalDisplayData,
)
from ema_cloud_lib.types.protocols import DashboardProtocol

logger = logging.getLogger(__name__)


class ReportDashboard:
    """
    DashboardProtocol implementation that writes JSON report files.

    Collects ETF data, signals, and holdings during each scan cycle,
    then writes a timestamped JSON report when flush_report() is called.

    Each report includes:
    - ETF analysis data (price, trend, indicators, stacking, MTF)
    - Signals with full metadata
    - Holdings per ETF with individual stock signals
    - Market hours status
    - API/cache performance metrics
    - Scan cycle metadata (duration, timestamp)
    - Summary statistics (bullish/bearish/neutral counts)
    """

    def __init__(self, report_dir: Path, max_reports: int = 500):
        self._report_dir = report_dir
        self._report_dir.mkdir(parents=True, exist_ok=True)
        self._max_reports = max_reports

        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._holdings_data: dict[str, HoldingsETFDisplayData] = {}
        self._cycle_start: float | None = None

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Collect ETF display data for the current cycle."""
        if self._cycle_start is None:
            self._cycle_start = time.monotonic()
        self._etf_data[data.symbol] = data

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Collect signals for the current cycle."""
        self._signals.append(signal)

    def update_holdings_data(self, data: HoldingsETFDisplayData) -> None:
        """Collect holdings data for the current cycle."""
        self._holdings_data[data.etf_symbol] = data

    def stop(self) -> None:
        """No-op for report dashboard."""

    def flush_report(self) -> Path | None:
        """
        Write collected data to a JSON report file and reset for next cycle.

        Returns:
            Path to the written report file, or None if no data was collected.
        """
        if not self._etf_data:
            return None

        timestamp = datetime.now(UTC)
        filename = f"scan_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.json"
        filepath = self._report_dir / filename

        # Scan duration
        cycle_duration = None
        if self._cycle_start is not None:
            cycle_duration = round(time.monotonic() - self._cycle_start, 2)

        # Build summary stats
        bullish = sum(1 for d in self._etf_data.values() if d.trend == TrendDirection.BULLISH.value)
        bearish = sum(1 for d in self._etf_data.values() if d.trend == TrendDirection.BEARISH.value)
        neutral = len(self._etf_data) - bullish - bearish

        # Market hours status
        market_status = MarketHours.get_market_status()

        report = {
            "scan_timestamp": timestamp.isoformat(),
            "scan_metadata": {
                "cycle_duration_seconds": cycle_duration,
            },
            "market_status": {
                "status": market_status["status"],
                "message": market_status["message"],
                "time_info": market_status["time_info"],
            },
            "api_metrics": api_call_tracker.get_stats(),
            "etfs": {sym: data.model_dump(mode="json") for sym, data in self._etf_data.items()},
            "signals": [sig.model_dump(mode="json") for sig in self._signals],
            "holdings": {
                sym: data.model_dump(mode="json") for sym, data in self._holdings_data.items()
            },
            "summary": {
                "total_etfs": len(self._etf_data),
                "bullish": bullish,
                "bearish": bearish,
                "neutral": neutral,
                "total_signals": len(self._signals),
                "holdings_etfs_scanned": len(self._holdings_data),
                "total_holdings": sum(
                    (h.total_holdings or 0) for h in self._holdings_data.values()
                ),
            },
        }

        filepath.write_text(json.dumps(report, indent=2, default=str))
        logger.info("Report written: %s", filepath)

        # Rotate old reports
        self._rotate_reports()

        # Reset for next cycle
        self._signals.clear()
        self._cycle_start = None

        return filepath

    def _rotate_reports(self) -> None:
        """Remove oldest reports if over the max limit."""
        reports = sorted(self._report_dir.glob("scan_*.json"))
        excess = len(reports) - self._max_reports
        if excess > 0:
            for old_report in reports[:excess]:
                old_report.unlink()
                logger.debug("Rotated old report: %s", old_report.name)


class CompositeDashboard:
    """
    Delegates DashboardProtocol calls to multiple dashboard implementations.

    Useful for combining e.g. SimpleDashboard (console output) with
    ReportDashboard (file output) in headless mode.
    """

    def __init__(self, *dashboards: DashboardProtocol):
        self._dashboards = list(dashboards)

    def update_etf_data(self, data: ETFDisplayData) -> None:
        for d in self._dashboards:
            d.update_etf_data(data)

    def add_signal(self, signal: SignalDisplayData) -> None:
        for d in self._dashboards:
            d.add_signal(signal)

    def update_holdings_data(self, data: HoldingsETFDisplayData) -> None:
        for d in self._dashboards:
            d.update_holdings_data(data)

    def stop(self) -> None:
        for d in self._dashboards:
            d.stop()
