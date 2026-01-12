"""
Terminal-Based Visualization Dashboard

Provides a real-time terminal UI for monitoring sector ETF trends
and signals using the Textual TUI framework.

Features:
- Sector ETF overview with trend status
- Live signal feed
- Keyboard navigation
- Auto-refresh display
"""

import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Header, Static

from ema_cloud_lib import api_call_tracker
from ema_cloud_lib.types.display import ETFDisplayData, SignalDisplayData

logger = logging.getLogger(__name__)


class StatusBar(Static):
    """Status bar widget showing summary statistics."""

    bullish_count = reactive(0)
    bearish_count = reactive(0)
    neutral_count = reactive(0)
    signals_count = reactive(0)
    api_calls = reactive(0)
    api_calls_per_min = reactive(0.0)

    def render(self) -> str:
        return (
            f"ETFs: {self.bullish_count + self.bearish_count + self.neutral_count} | "
            f"🟢 {self.bullish_count} 🔴 {self.bearish_count} ⚪ {self.neutral_count} | "
            f"Signals: {self.signals_count} | "
            f"API: {self.api_calls} ({self.api_calls_per_min:.0f}/min)"
        )


class TerminalDashboard(App):
    """
    Terminal-based dashboard using Textual TUI framework.
    """

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: auto 1fr auto;
    }

    #content {
        layout: horizontal;
    }

    #etf-container {
        width: 2fr;
        border: solid $primary;
        padding: 0 1;
    }

    #signals-container {
        width: 1fr;
        border: solid $secondary;
        padding: 0 1;
    }

    #etf-table {
        height: 100%;
    }

    #signals-table {
        height: 100%;
    }

    .table-title {
        text-align: center;
        text-style: bold;
        padding: 1 0;
        color: $text;
        background: $surface;
    }

    #etf-title {
        color: cyan;
    }

    #signals-title {
        color: magenta;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        padding: 0 1;
        background: $surface;
        color: $text;
    }

    DataTable {
        height: 1fr;
    }

    DataTable > .datatable--cursor {
        background: $accent;
    }

    /* Row styling for trends */
    .bullish {
        color: $success;
    }

    .bearish {
        color: $error;
    }

    .neutral {
        color: $text-muted;
    }
    """

    TITLE = "EMA Cloud Sector Scanner"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
    ]

    def __init__(self, refresh_rate: int = 2, on_quit=None):
        super().__init__()
        self.refresh_rate = refresh_rate
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._max_signals = 50
        self._update_timer = None
        self._is_mounted = False
        self._on_quit = on_quit

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with Vertical(id="etf-container"):
                yield Static("Sector ETF Overview", id="etf-title", classes="table-title")
                yield DataTable(id="etf-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="signals-container"):
                yield Static("Recent Signals", id="signals-title", classes="table-title")
                yield DataTable(id="signals-table", cursor_type="row", zebra_stripes=True)
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize tables and start refresh timer."""
        self._setup_etf_table()
        self._setup_signals_table()
        self._is_mounted = True
        # Update tables with any data received before mount
        self._update_etf_table()
        self._update_signals_table()
        self._update_status_bar()
        self._update_timer = self.set_interval(self.refresh_rate, self._refresh_display)

    def on_unmount(self) -> None:
        """Mark dashboard as unmounted to prevent late updates."""
        self._is_mounted = False

    def _setup_etf_table(self) -> None:
        """Setup ETF overview table columns."""
        try:
            table = self.query_one("#etf-table", DataTable)
        except NoMatches:
            return
        table.add_column("Symbol", key="symbol", width=8)
        table.add_column("Sector", key="sector", width=18)
        table.add_column("Price", key="price", width=10)
        table.add_column("Change", key="change", width=9)
        table.add_column("Trend", key="trend", width=10)
        table.add_column("Strength", key="strength", width=9)
        table.add_column("RSI", key="rsi", width=7)
        table.add_column("ADX", key="adx", width=7)
        table.add_column("Sigs", key="signals", width=5)

    def _setup_signals_table(self) -> None:
        """Setup signals table columns."""
        try:
            table = self.query_one("#signals-table", DataTable)
        except NoMatches:
            return
        table.add_column("Time", key="time", width=9)
        table.add_column("Sym", key="symbol", width=6)
        table.add_column("Dir", key="direction", width=5)
        table.add_column("Signal", key="signal", width=22)
        table.add_column("Price", key="price", width=9)
        table.add_column("Str", key="strength", width=8)

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Update ETF display data."""
        self._etf_data[data.symbol] = data
        if self._is_mounted:
            self._update_etf_table()
            self._update_status_bar()

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Add a new signal to the display."""
        self._signals.insert(0, signal)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[: self._max_signals]
        if self._is_mounted:
            self._update_signals_table()
            self._update_status_bar()

    def _update_etf_table(self) -> None:
        """Refresh the ETF table with current data."""
        if not self._is_mounted:
            return
        try:
            table = self.query_one("#etf-table", DataTable)
        except NoMatches:
            return
        table.clear()

        # Sort by trend strength
        sorted_etfs = sorted(
            self._etf_data.values(), key=lambda x: x.trend_strength, reverse=True
        )

        for etf in sorted_etfs:
            # Format trend
            if etf.trend == "bullish":
                trend_text = "🟢 BULL"
            elif etf.trend == "bearish":
                trend_text = "🔴 BEAR"
            else:
                trend_text = "⚪ FLAT"

            # Format change
            change_text = f"{etf.change_pct:+.2f}%"

            # Format strength
            strength_text = f"{etf.trend_strength:.0f}%"

            # Format RSI
            rsi_text = f"{etf.rsi:.1f}" if etf.rsi is not None else "-"

            # Format ADX
            adx_text = f"{etf.adx:.1f}" if etf.adx is not None else "-"

            # Signals count
            signals_text = str(etf.signals_count)

            table.add_row(
                etf.symbol,
                etf.sector[:16],
                f"${etf.price:.2f}",
                change_text,
                trend_text,
                strength_text,
                rsi_text,
                adx_text,
                signals_text,
                key=etf.symbol,
            )

    def _update_signals_table(self) -> None:
        """Refresh the signals table with current data."""
        if not self._is_mounted:
            return
        try:
            table = self.query_one("#signals-table", DataTable)
        except NoMatches:
            return
        table.clear()

        for i, signal in enumerate(self._signals[:15]):  # Show last 15
            # Direction
            dir_text = "🟢 ↑" if signal.direction == "long" else "🔴 ↓"

            # Truncate signal type
            signal_type = signal.signal_type[:20]

            table.add_row(
                signal.timestamp.strftime("%H:%M:%S"),
                signal.symbol,
                dir_text,
                signal_type,
                f"${signal.price:.2f}",
                signal.strength[:6],
                key=f"sig-{i}",
            )

    def _update_status_bar(self) -> None:
        """Update the status bar with current statistics."""
        if not self._is_mounted:
            return
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
        except NoMatches:
            return

        bullish = sum(1 for e in self._etf_data.values() if e.trend == "bullish")
        bearish = sum(1 for e in self._etf_data.values() if e.trend == "bearish")
        neutral = len(self._etf_data) - bullish - bearish

        status_bar.bullish_count = bullish
        status_bar.bearish_count = bearish
        status_bar.neutral_count = neutral
        status_bar.signals_count = len(self._signals)
        status_bar.api_calls = api_call_tracker.total_calls
        status_bar.api_calls_per_min = api_call_tracker.calls_per_minute

    def _refresh_display(self) -> None:
        """Periodic refresh of the display."""
        self._update_etf_table()
        self._update_signals_table()
        self._update_status_bar()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.dark = not self.dark

    def action_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_display()
        self.notify("Display refreshed")

    def action_quit(self) -> None:
        """Quit the dashboard and signal shutdown."""
        if self._on_quit:
            self._on_quit()
        self.stop()

    def stop(self) -> None:
        """Stop the dashboard."""
        if self._update_timer:
            self._update_timer.stop()
        self._is_mounted = False
        self.exit()

    async def run_async(self) -> None:
        """Run the dashboard within an existing async context.

        Use this method when calling from an already running event loop.
        """
        await super().run_async()


class SimpleDashboard:
    """
    Simpler dashboard that doesn't require Textual.
    Prints updates to console in a formatted way.
    """

    def __init__(self):
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._running = False

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Update ETF display data."""
        self._etf_data[data.symbol] = data

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Add a new signal."""
        self._signals.insert(0, signal)
        self._signals = self._signals[:50]
        self._print_signal(signal)

    def _print_signal(self, signal: SignalDisplayData) -> None:
        """Print a signal to console."""
        arrow = "🟢 ↑" if signal.direction == "long" else "🔴 ↓"
        valid = "✓" if signal.is_valid else "✗"

        print(f"\n{'-' * 60}")
        print(f"{arrow} SIGNAL: {signal.symbol} @ ${signal.price:.2f}")
        print(f"   Type: {signal.signal_type}")
        print(f"   Strength: {signal.strength} | Valid: {valid}")
        print(f"   Time: {signal.timestamp.strftime('%H:%M:%S')}")
        if signal.notes:
            print(f"   Note: {signal.notes}")
        print(f"{'-' * 60}")

    def print_summary(self) -> None:
        """Print current summary."""
        print(f"\n{'=' * 60}")
        print(f"SECTOR ETF SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")

        for etf in sorted(
            self._etf_data.values(), key=lambda x: x.trend_strength, reverse=True
        ):
            trend_icon = (
                "🟢"
                if etf.trend == "bullish"
                else ("🔴" if etf.trend == "bearish" else "⚪")
            )
            print(
                f"{trend_icon} {etf.symbol:6} | {etf.sector:20} | "
                f"${etf.price:8.2f} | Trend: {etf.trend_strength:5.1f}%"
            )

        print(f"{'=' * 60}\n")

    def run(self) -> None:
        """Run in simple mode (just prints, no interactive TUI)."""
        self._running = True
        self.print_summary()

    async def run_async(self) -> None:
        """Async version of run for compatibility."""
        self.run()

    def stop(self) -> None:
        """Stop the dashboard."""
        self._running = False


def create_dashboard(use_textual: bool = True) -> TerminalDashboard | SimpleDashboard:
    """Factory function to create appropriate dashboard.

    Args:
        use_textual: If True, create a full Textual TUI dashboard.
                    If False, create a simple console output dashboard.

    Returns:
        Either a TerminalDashboard (Textual) or SimpleDashboard instance.
    """
    if use_textual:
        try:
            # Verify textual is available
            from textual.app import App  # noqa: F401

            return TerminalDashboard()
        except ImportError:
            logger.warning("Textual library not installed. Using simple text output.")
            logger.warning("Install with: pip install textual")

    return SimpleDashboard()
