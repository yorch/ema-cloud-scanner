"""
Terminal dashboard application and helpers.
"""

import logging
from datetime import datetime

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Header, Static

from ema_cloud_cli.dashboard.log_viewer import LogViewer, TextualLogHandler
from ema_cloud_cli.dashboard.settings import SettingsScreen
from ema_cloud_cli.dashboard.status_bar import StatusBar
from ema_cloud_cli.dashboard.styles import DASHBOARD_CSS
from ema_cloud_cli.dashboard.tables import (
    setup_etf_table,
    setup_signals_table,
    update_etf_table,
    update_signals_table,
)
from ema_cloud_lib import api_call_tracker
from ema_cloud_lib.config.settings import ScannerConfig
from ema_cloud_lib.types.display import ETFDisplayData, SignalDisplayData

logger = logging.getLogger(__name__)


class TerminalDashboard(App):
    """
    Terminal-based dashboard using Textual TUI framework.
    """

    CSS = DASHBOARD_CSS
    TITLE = "EMA Cloud Sector Scanner"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("d", "toggle_dark", "Toggle Dark Mode"),
        Binding("s", "settings", "Settings"),
        Binding("l", "toggle_logs", "Toggle Logs"),
    ]

    def __init__(
        self,
        refresh_rate: int = 2,
        config: ScannerConfig | None = None,
        on_quit=None,
        on_config_update=None,
    ):
        super().__init__()
        self.refresh_rate = refresh_rate
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._max_signals = 50
        self._update_timer = None
        self._is_mounted = False
        self._on_quit = on_quit
        self._config = config or ScannerConfig()
        self._on_config_update = on_config_update
        self._log_handler = None
        self._logs_visible = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with Vertical(id="etf-container"):
                yield Static("Sector ETF Overview", id="etf-title", classes="table-title")
                yield DataTable(id="etf-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="signals-container"):
                yield Static("Recent Signals", id="signals-title", classes="table-title")
                yield DataTable(id="signals-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="logs-container"):
                yield Static("Application Logs", id="logs-title", classes="table-title")
                yield LogViewer(max_lines=100, id="log-viewer")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize tables and start refresh timer."""
        setup_etf_table(self)
        setup_signals_table(self)
        self._is_mounted = True
        self._refresh_display()
        self._update_timer = self.set_interval(self.refresh_rate, self._refresh_display)

        # Setup log handler
        try:
            log_viewer = self.query_one("#log-viewer", LogViewer)
            self._log_handler = TextualLogHandler(log_viewer)
            self._log_handler.setLevel(logging.DEBUG)

            # Add handler to root logger to capture all logs
            root_logger = logging.getLogger()
            root_logger.addHandler(self._log_handler)

            # Flush any buffered logs
            self._log_handler.flush_buffer()

            # Hide logs container by default
            self._toggle_logs_visibility(False)

        except NoMatches:
            logger.warning("Log viewer widget not found")

    def on_unmount(self) -> None:
        """Mark dashboard as unmounted to prevent late updates."""
        self._is_mounted = False

        # Remove log handler
        if self._log_handler:
            self._log_handler.deactivate()
            root_logger = logging.getLogger()
            root_logger.removeHandler(self._log_handler)

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Update ETF display data."""
        self._etf_data[data.symbol] = data
        if self._is_mounted:
            update_etf_table(self, self._etf_data)
            self._update_status_bar()

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Add a new signal to the display."""
        self._signals.insert(0, signal)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[: self._max_signals]
        if self._is_mounted:
            update_signals_table(self, self._signals)
            self._update_status_bar()

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
        if not self._is_mounted:
            return
        update_etf_table(self, self._etf_data)
        update_signals_table(self, self._signals)
        self._update_status_bar()

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        super().action_toggle_dark()

    def action_refresh(self) -> None:
        """Manual refresh."""
        self._refresh_display()
        self.notify("Display refreshed")

    def action_settings(self) -> None:
        """Open settings panel."""
        self.push_screen(SettingsScreen(self._config, self.apply_config))

    def action_toggle_logs(self) -> None:
        """Toggle logs visibility."""
        self._logs_visible = not self._logs_visible
        self._toggle_logs_visibility(self._logs_visible)
        status = "shown" if self._logs_visible else "hidden"
        self.notify(f"Logs {status}")

    def _toggle_logs_visibility(self, visible: bool) -> None:
        """Toggle the logs container visibility."""
        try:
            logs_container = self.query_one("#logs-container")
            logs_container.display = visible
        except NoMatches:
            pass

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

    def apply_config(self, config: ScannerConfig) -> None:
        """Apply settings to the dashboard and propagate to scanner."""
        self._config = config
        if self._on_config_update:
            self._on_config_update(config)
        if self._update_timer:
            self._update_timer.stop()
        self.refresh_rate = config.dashboard_refresh_rate
        if self._is_mounted:
            self._update_timer = self.set_interval(self.refresh_rate, self._refresh_display)

    async def run_async(self) -> None:
        """Run the dashboard within an existing async context."""
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
    """Factory function to create appropriate dashboard."""
    if use_textual:
        try:
            from textual.app import App  # noqa: F401

            return TerminalDashboard()
        except ImportError:
            logger.warning("Textual library not installed. Using simple text output.")
            logger.warning("Install with: pip install textual")

    return SimpleDashboard()
