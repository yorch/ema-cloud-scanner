"""
Terminal dashboard application and helpers.
"""

import logging
from collections.abc import Callable
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
    setup_holdings_table,
    setup_signals_table,
    update_etf_table,
    update_holdings_table,
    update_signals_table,
)
from ema_cloud_lib import api_call_tracker
from ema_cloud_lib.config.settings import ScannerConfig
from ema_cloud_lib.constants import MAX_LOG_LINES, MAX_SIGNALS_DISPLAY, TrendDirection
from ema_cloud_lib.types.display import ETFDisplayData, HoldingsETFDisplayData, SignalDisplayData

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
        Binding("h", "toggle_holdings", "Toggle Holdings"),
        Binding("left", "show_etf_view", "ETF View"),
    ]

    def __init__(
        self,
        refresh_rate: int = 2,
        config: ScannerConfig | None = None,
        on_quit: Callable[[], None] | None = None,
        on_config_update: Callable[[ScannerConfig], None] | None = None,
    ):
        super().__init__()
        self.refresh_rate = refresh_rate
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._max_signals = MAX_SIGNALS_DISPLAY
        self._update_timer = None
        self._is_mounted = False
        self._on_quit = on_quit
        self._config = config or ScannerConfig()
        self._on_config_update = on_config_update
        self._log_handler = None
        self._logs_visible = False
        self._holdings_visible = False
        self._holdings_data: dict[str, HoldingsETFDisplayData] = {}
        self._selected_holdings_etf: str | None = None
        # Performance optimization: cache computed values
        self._cached_holdings_total: int = 0
        self._cached_holdings_signals: int = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="content"):
            with Vertical(id="etf-container"):
                yield Static("Sector ETF Overview", id="etf-title", classes="table-title")
                yield DataTable(id="etf-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="signals-container"):
                yield Static("Recent Signals", id="signals-title", classes="table-title")
                yield DataTable(id="signals-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="holdings-container"):
                yield Static("Holdings Scanner", id="holdings-title", classes="table-title")
                yield DataTable(id="holdings-table", cursor_type="row", zebra_stripes=True)
            with Vertical(id="logs-container"):
                yield Static("Application Logs", id="logs-title", classes="table-title")
                yield LogViewer(max_lines=MAX_LOG_LINES, id="log-viewer")
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize tables and start refresh timer."""
        setup_etf_table(self)
        setup_signals_table(self)
        setup_holdings_table(self)
        self._is_mounted = True
        self._refresh_display()
        self._update_timer = self.set_interval(self.refresh_rate, self._refresh_display)

        # Setup log handler
        try:
            log_viewer = self.query_one("#log-viewer", LogViewer)
            self._log_handler = TextualLogHandler(log_viewer)
            self._log_handler.setLevel(logging.DEBUG)

            # Add handler to root logger to capture all logs
            # This handler will coexist with the file handler set up by CLI
            root_logger = logging.getLogger()
            root_logger.addHandler(self._log_handler)

            # Set root logger to DEBUG to ensure all messages reach handlers
            # Individual handlers can filter as needed
            if root_logger.level > logging.DEBUG:
                root_logger.setLevel(logging.DEBUG)

            # Flush any buffered logs
            self._log_handler.flush_buffer()

            # Add an initial log message to verify logging is working
            logger.info("Log viewer initialized - logs will appear here")
            logger.debug("Debug logging is enabled")

            # Hide logs and holdings containers by default
            self._toggle_logs_visibility(False)
            self._toggle_holdings_visibility(False)

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

    def update_holdings_data(self, data: HoldingsETFDisplayData) -> None:
        """Update holdings display data."""
        self._holdings_data[data.etf_symbol] = data
        if not self._selected_holdings_etf:
            self._selected_holdings_etf = data.etf_symbol
        # Update cached counts
        self._update_holdings_cache()
        if self._is_mounted:
            if self._holdings_visible:
                self._refresh_holdings_table()
            self._update_status_bar()

    def _update_status_bar(self) -> None:
        """Update the status bar with current statistics."""
        if not self._is_mounted:
            return
        try:
            status_bar = self.query_one("#status-bar", StatusBar)
        except NoMatches:
            return

        # Single-pass ETF trend counting for efficiency
        bullish = bearish = 0
        for etf in self._etf_data.values():
            if etf.trend == TrendDirection.BULLISH.value:
                bullish += 1
            elif etf.trend == TrendDirection.BEARISH.value:
                bearish += 1
        neutral = len(self._etf_data) - bullish - bearish

        status_bar.bullish_count = bullish
        status_bar.bearish_count = bearish
        status_bar.neutral_count = neutral
        status_bar.signals_count = len(self._signals)
        status_bar.api_calls = api_call_tracker.total_calls
        status_bar.api_calls_per_min = api_call_tracker.calls_per_minute
        # Use cached values instead of recalculating
        status_bar.holdings_count = self._cached_holdings_total
        status_bar.holdings_signals_count = self._cached_holdings_signals

    def _refresh_display(self) -> None:
        """Periodic refresh of the display."""
        if not self._is_mounted:
            return
        update_etf_table(self, self._etf_data)
        update_signals_table(self, self._signals)
        if self._holdings_visible:
            self._refresh_holdings_table()
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

    def action_toggle_holdings(self) -> None:
        """Toggle holdings view."""
        self._holdings_visible = not self._holdings_visible
        self._toggle_holdings_visibility(self._holdings_visible)
        if self._holdings_visible:
            self._refresh_holdings_table()
        status = "shown" if self._holdings_visible else "hidden"
        self.notify(f"Holdings {status}")

    def action_show_etf_view(self) -> None:
        """Switch back to ETF/signal view."""
        if self._holdings_visible:
            self._holdings_visible = False
            self._toggle_holdings_visibility(False)
            self.notify("Holdings hidden")

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

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Keep holdings view synced to the selected ETF."""
        data_table = getattr(event, "data_table", None) or getattr(event, "control", None)
        if not data_table or data_table.id != "etf-table":
            return
        row_key = getattr(event, "row_key", None)
        if row_key:
            self._selected_holdings_etf = str(row_key)
            if self._holdings_visible:
                self._refresh_holdings_table()

    def _refresh_holdings_table(self) -> None:
        """Refresh holdings table for the selected ETF."""
        if not self._selected_holdings_etf and self._holdings_data:
            self._selected_holdings_etf = next(iter(self._holdings_data))
        if not self._selected_holdings_etf:
            return
        holdings_data = self._holdings_data.get(self._selected_holdings_etf)
        if holdings_data:
            update_holdings_table(self, holdings_data.holdings)
            self._update_holdings_title(holdings_data)
        else:
            update_holdings_table(self, [])
            self._update_holdings_title(None)

    def _update_holdings_title(self, data: HoldingsETFDisplayData | None) -> None:
        """
        Update holdings title with ETF context.

        Args:
            data: Holdings data for display, or None to show default title
        """
        try:
            title = self.query_one("#holdings-title", Static)
        except NoMatches:
            return

        if not data or not data.sector_trend:
            title.update("Holdings Scanner")
            return

        trend = data.sector_trend.lower()
        if TrendDirection.BULLISH.value in trend:
            trend_icon = "🟢"
        elif TrendDirection.BEARISH.value in trend:
            trend_icon = "🔴"
        else:
            trend_icon = "⚪"

        sector = data.sector or data.etf_symbol
        title.update(
            f"Holdings Scanner - {data.etf_symbol} ({sector}) [{trend_icon} {trend.upper()}]"
        )

    def _toggle_holdings_visibility(self, visible: bool) -> None:
        """Toggle holdings and signals containers visibility."""
        try:
            holdings_container = self.query_one("#holdings-container")
            signals_container = self.query_one("#signals-container")
            holdings_container.display = visible
            signals_container.display = not visible
        except NoMatches:
            pass

    def _update_holdings_cache(self) -> None:
        """Update cached holdings counts for performance optimization."""
        total = 0
        signals = 0
        for data in self._holdings_data.values():
            total += data.total_holdings or len(data.holdings)
            signals += sum(1 for holding in data.holdings if holding.signal_type)
        self._cached_holdings_total = total
        self._cached_holdings_signals = signals


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
        self._signals = self._signals[:MAX_SIGNALS_DISPLAY]
        self._print_signal(signal)

    def update_holdings_data(self, data: HoldingsETFDisplayData) -> None:
        """No-op for simple dashboard."""
        return None

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
                if etf.trend == TrendDirection.BULLISH.value
                else ("🔴" if etf.trend == TrendDirection.BEARISH.value else "⚪")
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
