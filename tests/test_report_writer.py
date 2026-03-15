"""
Tests for the headless report writer (ReportDashboard and CompositeDashboard).
"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

from ema_cloud_lib.reports.writer import CompositeDashboard, ReportDashboard
from ema_cloud_lib.types.display import (
    ETFDisplayData,
    HoldingDisplayData,
    HoldingsETFDisplayData,
    MTFDisplayData,
    SignalDisplayData,
)


def _make_etf_data(symbol: str = "XLK", trend: str = "bullish") -> ETFDisplayData:
    return ETFDisplayData(
        symbol=symbol,
        name=symbol,
        sector="technology",
        price=150.0,
        change_pct=1.5,
        trend=trend,
        trend_strength=0.75,
        cloud_state="BULLISH",
        signals_count=2,
        rsi=55.0,
        adx=28.0,
        volume_ratio=1.8,
        stacking_score=0.6,
        is_waterfall=False,
    )


def _make_signal_data(symbol: str = "XLK") -> SignalDisplayData:
    return SignalDisplayData(
        timestamp=datetime(2026, 3, 15, 14, 30, 0, tzinfo=UTC),
        symbol=symbol,
        direction="long",
        signal_type="cloud_flip_bullish",
        price=150.0,
        strength="STRONG",
        is_valid=True,
        notes="",
        weighted_filter_score=0.85,
        stacking_score=0.6,
        is_waterfall=False,
    )


def _make_holdings_data(etf_symbol: str = "XLK") -> HoldingsETFDisplayData:
    return HoldingsETFDisplayData(
        etf_symbol=etf_symbol,
        etf_name="Technology Select Sector SPDR",
        sector="technology",
        sector_trend="bullish",
        total_holdings=10,
        holdings=[
            HoldingDisplayData(
                symbol="AAPL",
                company="Apple Inc.",
                weight=22.5,
                price=175.0,
                direction="long",
                signal_type="cloud_flip_bullish",
                strength="STRONG",
                timestamp=datetime(2026, 3, 15, 14, 30, 0, tzinfo=UTC),
            ),
        ],
    )


class TestReportDashboard:
    def test_creates_report_dir(self, tmp_path: Path):
        report_dir = tmp_path / "reports"
        ReportDashboard(report_dir)
        assert report_dir.exists()

    def test_flush_no_data_returns_none(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        assert rd.flush_report() is None

    def test_flush_writes_json_file(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))
        rd.update_etf_data(_make_etf_data("XLF", "bearish"))
        rd.add_signal(_make_signal_data("XLK"))
        rd.update_holdings_data(_make_holdings_data("XLK"))

        filepath = rd.flush_report()
        assert filepath is not None
        assert filepath.exists()
        assert filepath.suffix == ".json"
        assert filepath.name.startswith("scan_")

    def test_report_content_structure(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))
        rd.update_etf_data(_make_etf_data("XLF", "bearish"))
        rd.add_signal(_make_signal_data("XLK"))
        rd.update_holdings_data(_make_holdings_data("XLK"))

        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())

        # Top-level keys
        assert "scan_timestamp" in report
        assert "scan_metadata" in report
        assert "market_status" in report
        assert "api_metrics" in report
        assert "etfs" in report
        assert "signals" in report
        assert "holdings" in report
        assert "summary" in report

        # ETF data
        assert "XLK" in report["etfs"]
        assert "XLF" in report["etfs"]
        assert report["etfs"]["XLK"]["price"] == 150.0
        assert report["etfs"]["XLK"]["trend"] == "bullish"

        # Signals
        assert len(report["signals"]) == 1
        assert report["signals"][0]["symbol"] == "XLK"
        assert report["signals"][0]["strength"] == "STRONG"

        # Holdings
        assert "XLK" in report["holdings"]
        assert report["holdings"]["XLK"]["total_holdings"] == 10
        assert len(report["holdings"]["XLK"]["holdings"]) == 1

        # Summary
        summary = report["summary"]
        assert summary["total_etfs"] == 2
        assert summary["bullish"] == 1
        assert summary["bearish"] == 1
        assert summary["neutral"] == 0
        assert summary["total_signals"] == 1
        assert summary["holdings_etfs_scanned"] == 1
        assert summary["total_holdings"] == 10

    def test_report_includes_market_status(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())

        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())

        ms = report["market_status"]
        assert "status" in ms
        assert "message" in ms
        assert "time_info" in ms
        assert ms["status"] in ("OPEN", "CLOSED", "PRE_MARKET", "AFTER_HOURS", "HOLIDAY")

    def test_report_includes_api_metrics(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())

        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())

        metrics = report["api_metrics"]
        assert "total_calls" in metrics
        assert "calls_per_minute" in metrics
        assert "cache_hit_rate" in metrics
        assert "success_rate" in metrics

    def test_report_includes_scan_metadata(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())

        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())

        meta = report["scan_metadata"]
        assert "cycle_duration_seconds" in meta
        # Duration should be a small positive number (update_etf_data starts the timer)
        assert meta["cycle_duration_seconds"] is not None
        assert meta["cycle_duration_seconds"] >= 0

    def test_cycle_start_resets_between_flushes(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())
        rd.flush_report()

        # After flush, cycle_start should be reset
        assert rd._cycle_start is None

        # Next cycle
        rd.update_etf_data(_make_etf_data())
        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())
        assert report["scan_metadata"]["cycle_duration_seconds"] is not None

    def test_flush_clears_signals(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())
        rd.add_signal(_make_signal_data())

        rd.flush_report()

        # Second flush should have no signals but ETF data persists
        rd.add_signal(_make_signal_data("XLF"))
        filepath2 = rd.flush_report()
        report2 = json.loads(filepath2.read_text())
        assert len(report2["signals"]) == 1
        assert report2["signals"][0]["symbol"] == "XLF"

    def test_report_rotation(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path, max_reports=3)
        rd.update_etf_data(_make_etf_data())

        # Write 5 reports
        paths = []
        for _ in range(5):
            p = rd.flush_report()
            paths.append(p)

        # Should only keep the latest 3
        remaining = list(tmp_path.glob("scan_*.json"))
        assert len(remaining) == 3

    def test_mtf_data_included(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        etf = _make_etf_data()
        etf.mtf = MTFDisplayData(
            enabled=True,
            alignment="aligned",
            confidence="high",
            bias="long",
            bullish_count=3,
            bearish_count=0,
            neutral_count=0,
            total_timeframes=3,
            alignment_pct=100.0,
            summary="All timeframes bullish",
        )
        rd.update_etf_data(etf)

        filepath = rd.flush_report()
        report = json.loads(filepath.read_text())
        mtf = report["etfs"]["XLK"]["mtf"]
        assert mtf["enabled"] is True
        assert mtf["bias"] == "long"
        assert mtf["alignment_pct"] == 100.0

    def test_flush_summary_no_data_returns_none(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        assert rd.flush_summary() is None

    def test_flush_summary_writes_file(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))

        filepath = rd.flush_summary()
        assert filepath is not None
        assert filepath.exists()
        assert filepath.name == "latest_summary.txt"

    def test_flush_summary_overwrites_on_each_cycle(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)

        # First cycle
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))
        rd.flush_summary()
        rd.flush_report()  # resets signals/cycle_start

        # Second cycle with different data
        rd.update_etf_data(_make_etf_data("XLF", "bearish"))
        rd.flush_summary()

        content = (tmp_path / "latest_summary.txt").read_text()
        # Should contain XLF from latest cycle (ETF data persists across flushes)
        assert "XLF" in content
        # Only one summary file should exist
        summaries = list(tmp_path.glob("latest_summary*"))
        assert len(summaries) == 1

    def test_flush_summary_content(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))
        rd.update_etf_data(_make_etf_data("XLF", "bearish"))
        rd.add_signal(_make_signal_data("XLK"))

        rd.flush_summary()
        content = (tmp_path / "latest_summary.txt").read_text()

        # Scan timestamp header
        assert "EMA Cloud Scanner" in content
        # ETF symbols
        assert "XLK" in content
        assert "XLF" in content
        # Trend direction icons
        assert "▲" in content  # bullish
        assert "▼" in content  # bearish
        # Signal data
        assert "cloud_flip_bullish" in content
        assert "STRONG" in content
        # Summary counts
        assert "1 bullish" in content
        assert "1 bearish" in content
        assert "Signals: 1" in content

    def test_flush_summary_with_holdings(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data("XLK", "bullish"))
        rd.update_holdings_data(_make_holdings_data("XLK"))

        rd.flush_summary()
        content = (tmp_path / "latest_summary.txt").read_text()

        assert "Holdings" in content
        assert "AAPL" in content
        assert "22.5%" in content

    def test_flush_summary_market_status(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.update_etf_data(_make_etf_data())

        rd.flush_summary()
        content = (tmp_path / "latest_summary.txt").read_text()

        assert "Market status:" in content

    def test_stop_is_noop(self, tmp_path: Path):
        rd = ReportDashboard(tmp_path)
        rd.stop()  # Should not raise


class TestCompositeDashboard:
    def test_delegates_update_etf_data(self):
        d1 = MagicMock()
        d2 = MagicMock()
        composite = CompositeDashboard(d1, d2)

        data = _make_etf_data()
        composite.update_etf_data(data)

        d1.update_etf_data.assert_called_once_with(data)
        d2.update_etf_data.assert_called_once_with(data)

    def test_delegates_add_signal(self):
        d1 = MagicMock()
        d2 = MagicMock()
        composite = CompositeDashboard(d1, d2)

        signal = _make_signal_data()
        composite.add_signal(signal)

        d1.add_signal.assert_called_once_with(signal)
        d2.add_signal.assert_called_once_with(signal)

    def test_delegates_update_holdings_data(self):
        d1 = MagicMock()
        d2 = MagicMock()
        composite = CompositeDashboard(d1, d2)

        holdings = _make_holdings_data()
        composite.update_holdings_data(holdings)

        d1.update_holdings_data.assert_called_once_with(holdings)
        d2.update_holdings_data.assert_called_once_with(holdings)

    def test_delegates_stop(self):
        d1 = MagicMock()
        d2 = MagicMock()
        composite = CompositeDashboard(d1, d2)

        composite.stop()

        d1.stop.assert_called_once()
        d2.stop.assert_called_once()
