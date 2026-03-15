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

    def flush_summary(self) -> Path | None:
        """
        Write a human-readable plain-text summary to latest_summary.txt.

        Overwrites the file each cycle so it always reflects the latest scan.
        Does NOT clear internal state — flush_report() handles the reset.

        Returns:
            Path to the written summary file, or None if no data was collected.
        """
        if not self._etf_data:
            return None

        timestamp = datetime.now(UTC)
        filepath = self._report_dir / "latest_summary.txt"

        cycle_duration = None
        if self._cycle_start is not None:
            cycle_duration = round(time.monotonic() - self._cycle_start, 2)

        market_status = MarketHours.get_market_status()
        api_stats = api_call_tracker.get_stats()

        bullish = sum(1 for d in self._etf_data.values() if d.trend == TrendDirection.BULLISH.value)
        bearish = sum(1 for d in self._etf_data.values() if d.trend == TrendDirection.BEARISH.value)
        neutral = len(self._etf_data) - bullish - bearish

        lines: list[str] = []

        # Header
        lines.append(f"EMA Cloud Scanner — {timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("=" * 72)
        if cycle_duration is not None:
            lines.append(f"Cycle duration: {cycle_duration}s")
        lines.append(f"Market status:  {market_status['status']}")
        lines.append("")

        # ETF table — sort: bullish first, then neutral, then bearish
        trend_order = {
            TrendDirection.BULLISH.value: 0,
            "neutral": 1,
            TrendDirection.BEARISH.value: 2,
        }
        sorted_etfs = sorted(
            self._etf_data.values(),
            key=lambda d: (trend_order.get(d.trend, 1), d.symbol),
        )

        trend_icons = {
            TrendDirection.BULLISH.value: "▲",
            TrendDirection.BEARISH.value: "▼",
        }

        lines.append(
            f"{'Symbol':<8} {'Sector':<14} {'Price':>8} {'Chg%':>7} "
            f"{'Trend':>5} {'Str%':>5} {'Sigs':>4} {'RSI':>6} {'ADX':>6}"
        )
        lines.append("-" * 72)
        for d in sorted_etfs:
            icon = trend_icons.get(d.trend, "─")
            rsi_str = f"{d.rsi:.1f}" if d.rsi is not None else "—"
            adx_str = f"{d.adx:.1f}" if d.adx is not None else "—"
            lines.append(
                f"{d.symbol:<8} {d.sector:<14} {d.price:>8.2f} {d.change_pct:>+6.1f}% "
                f"{icon:>5} {d.trend_strength * 100:>4.0f}% {d.signals_count:>4} "
                f"{rsi_str:>6} {adx_str:>6}"
            )
        lines.append("")

        # Signals section
        if self._signals:
            lines.append("Signals")
            lines.append("-" * 72)
            for sig in self._signals:
                dir_icon = "↑" if sig.direction == "long" else "↓"
                wfs = (
                    f"{sig.weighted_filter_score:.2f}"
                    if sig.weighted_filter_score is not None
                    else "—"
                )
                lines.append(
                    f"  {sig.timestamp.strftime('%H:%M:%S')} {sig.symbol:<6} {dir_icon} "
                    f"{sig.signal_type:<24} {sig.price:>8.2f}  {sig.strength:<12} wfs={wfs}"
                )
            lines.append("")

        # Holdings section
        holdings_with_signals = {sym: h for sym, h in self._holdings_data.items() if h.holdings}
        if holdings_with_signals:
            lines.append("Holdings")
            lines.append("-" * 72)
            for _sym, h in sorted(holdings_with_signals.items()):
                lines.append(f"  {h.etf_symbol} ({h.sector_trend})")
                for stock in h.holdings:
                    if stock.signal_type:
                        weight_str = f"{stock.weight:.1f}%" if stock.weight is not None else "—"
                        price_str = f"{stock.price:.2f}" if stock.price is not None else "—"
                        lines.append(
                            f"    {stock.symbol:<8} {stock.signal_type:<24} "
                            f"{stock.strength or '—':<12} {price_str:>8}  {weight_str:>6}"
                        )
            lines.append("")

        # Footer
        lines.append("=" * 72)
        lines.append(
            f"ETFs: {len(self._etf_data)} total  "
            f"({bullish} bullish, {bearish} bearish, {neutral} neutral)  |  "
            f"Signals: {len(self._signals)}  |  "
            f"Holdings ETFs: {len(self._holdings_data)}"
        )

        # API metrics
        lines.append(
            f"API: {api_stats.get('total_calls', 0)} calls  "
            f"{api_stats.get('calls_per_minute', 0):.1f}/min  "
            f"cache {api_stats.get('cache_hit_rate', 0):.0f}%  "
            f"success {api_stats.get('success_rate', 0):.0f}%"
        )
        lines.append("")

        filepath.write_text("\n".join(lines))
        logger.info("Summary written: %s", filepath)
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
