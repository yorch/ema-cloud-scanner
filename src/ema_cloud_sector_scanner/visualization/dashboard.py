"""
Terminal-Based Visualization Dashboard

Provides a real-time terminal UI for monitoring sector ETF trends
and signals using the Rich library.

Features:
- Sector ETF overview with trend status
- Live signal feed
- Detailed view for selected ETF
- Keyboard navigation
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class ETFDisplayData:
    """Data structure for ETF display"""

    symbol: str
    name: str
    sector: str
    price: float
    change_pct: float
    trend: str  # "bullish", "bearish", "neutral"
    trend_strength: float
    cloud_state: str
    signals_count: int
    last_signal: str | None = None
    last_signal_time: datetime | None = None
    rsi: float | None = None
    adx: float | None = None
    volume_ratio: float | None = None


@dataclass
class SignalDisplayData:
    """Data structure for signal display"""

    timestamp: datetime
    symbol: str
    direction: str
    signal_type: str
    price: float
    strength: str
    is_valid: bool
    notes: str


class TerminalDashboard:
    """
    Terminal-based dashboard using Rich library.
    """

    def __init__(self, refresh_rate: int = 2):
        self.refresh_rate = refresh_rate
        self._running = False
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._max_signals = 50
        self._selected_etf: str | None = None
        self._console = None
        self._layout = None

    def _init_rich(self):
        """Initialize Rich components"""
        try:
            from rich import box
            from rich.console import Console
            from rich.layout import Layout
            from rich.live import Live
            from rich.panel import Panel
            from rich.table import Table
            from rich.text import Text

            self._console = Console()
            self._rich_available = True

        except ImportError:
            logger.warning("Rich library not installed. Using simple text output.")
            logger.warning("Install with: pip install rich")
            self._rich_available = False
            self._console = None

    def update_etf_data(self, data: ETFDisplayData):
        """Update ETF display data"""
        self._etf_data[data.symbol] = data

    def add_signal(self, signal: SignalDisplayData):
        """Add a new signal to the display"""
        self._signals.insert(0, signal)
        if len(self._signals) > self._max_signals:
            self._signals = self._signals[: self._max_signals]

    def _create_header(self) -> Any:
        """Create header panel"""
        if not self._rich_available:
            return None
        try:
            from rich.panel import Panel
            from rich.text import Text

            title = Text()
            title.append("📊 ", style="bold")
            title.append("EMA Cloud Sector Scanner", style="bold blue")
            title.append(" | ", style="dim")
            title.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="cyan")

            return Panel(title, style="white on blue", height=3)
        except Exception as e:
            logger.debug(f"Error creating header: {e}")
            return None

    def _create_etf_table(self) -> Any:
        """Create sector ETF overview table"""
        if not self._rich_available:
            return None
        try:
            from rich import box
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            return None

        table = Table(
            title="Sector ETF Overview",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )

        table.add_column("Symbol", style="bold", width=8)
        table.add_column("Sector", width=20)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Change", justify="right", width=10)
        table.add_column("Trend", justify="center", width=12)
        table.add_column("Strength", justify="center", width=10)
        table.add_column("RSI", justify="right", width=8)
        table.add_column("ADX", justify="right", width=8)
        table.add_column("Signals", justify="center", width=8)

        # Sort by trend strength
        sorted_etfs = sorted(self._etf_data.values(), key=lambda x: x.trend_strength, reverse=True)

        for etf in sorted_etfs:
            # Format trend
            if etf.trend == "bullish":
                trend_text = Text("🟢 BULL", style="bold green")
            elif etf.trend == "bearish":
                trend_text = Text("🔴 BEAR", style="bold red")
            else:
                trend_text = Text("⚪ FLAT", style="dim")

            # Format change
            change_style = "green" if etf.change_pct >= 0 else "red"
            change_text = Text(f"{etf.change_pct:+.2f}%", style=change_style)

            # Format strength
            if etf.trend_strength >= 70:
                strength_style = "bold green"
            elif etf.trend_strength >= 50:
                strength_style = "yellow"
            else:
                strength_style = "dim"
            strength_text = Text(f"{etf.trend_strength:.0f}%", style=strength_style)

            # Format RSI
            rsi_text = ""
            if etf.rsi is not None:
                if etf.rsi > 70:
                    rsi_text = Text(f"{etf.rsi:.1f}", style="red")
                elif etf.rsi < 30:
                    rsi_text = Text(f"{etf.rsi:.1f}", style="green")
                else:
                    rsi_text = Text(f"{etf.rsi:.1f}", style="dim")

            # Format ADX
            adx_text = ""
            if etf.adx is not None:
                if etf.adx > 30:
                    adx_text = Text(f"{etf.adx:.1f}", style="bold")
                else:
                    adx_text = Text(f"{etf.adx:.1f}", style="dim")

            # Signals count
            signals_style = "bold yellow" if etf.signals_count > 0 else "dim"
            signals_text = Text(str(etf.signals_count), style=signals_style)

            table.add_row(
                etf.symbol,
                etf.sector[:18],
                f"${etf.price:.2f}",
                change_text,
                trend_text,
                strength_text,
                rsi_text,
                adx_text,
                signals_text,
            )

        return table

    def _create_signals_table(self) -> Any:
        """Create recent signals table"""
        if not self._rich_available:
            return None
        try:
            from rich import box
            from rich.table import Table
            from rich.text import Text
        except ImportError:
            return None

        table = Table(
            title="Recent Signals",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            expand=True,
        )

        table.add_column("Time", width=10)
        table.add_column("Symbol", style="bold", width=8)
        table.add_column("Dir", justify="center", width=6)
        table.add_column("Signal", width=25)
        table.add_column("Price", justify="right", width=10)
        table.add_column("Strength", justify="center", width=12)
        table.add_column("Valid", justify="center", width=6)

        for signal in self._signals[:15]:  # Show last 15
            # Direction
            if signal.direction == "long":
                dir_text = Text("🟢 ↑", style="bold green")
            else:
                dir_text = Text("🔴 ↓", style="bold red")

            # Strength
            strength_colors = {
                "VERY_STRONG": "bold green",
                "STRONG": "green",
                "MODERATE": "yellow",
                "WEAK": "dim",
                "VERY_WEAK": "dim red",
            }
            strength_text = Text(signal.strength, style=strength_colors.get(signal.strength, "dim"))

            # Valid
            valid_text = Text("✓", style="green") if signal.is_valid else Text("✗", style="red")

            table.add_row(
                signal.timestamp.strftime("%H:%M:%S"),
                signal.symbol,
                dir_text,
                signal.signal_type[:23],
                f"${signal.price:.2f}",
                strength_text,
                valid_text,
            )

        return table

    def _create_status_bar(self) -> Any:
        """Create status bar"""
        if not self._rich_available:
            return None
        try:
            from rich.panel import Panel
            from rich.text import Text
        except ImportError:
            return None

        status = Text()

        # Count trends
        bullish = sum(1 for e in self._etf_data.values() if e.trend == "bullish")
        bearish = sum(1 for e in self._etf_data.values() if e.trend == "bearish")
        neutral = len(self._etf_data) - bullish - bearish

        status.append(f"ETFs: {len(self._etf_data)} | ", style="dim")
        status.append(f"🟢 {bullish} ", style="green")
        status.append(f"🔴 {bearish} ", style="red")
        status.append(f"⚪ {neutral} ", style="dim")
        status.append("| ", style="dim")
        status.append(f"Signals: {len(self._signals)}", style="yellow")
        status.append(" | Press Ctrl+C to exit", style="dim")

        return Panel(status, height=3)

    def _create_layout(self) -> Any:
        """Create the dashboard layout"""
        if not self._rich_available:
            return None
        try:
            from rich.layout import Layout
        except ImportError:
            return None

        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3), Layout(name="body"), Layout(name="footer", size=3)
        )

        layout["body"].split_row(Layout(name="left", ratio=2), Layout(name="right", ratio=1))

        return layout

    def _render(self) -> Any:
        """Render the complete dashboard"""
        if not self._rich_available:
            return self._render_simple()

        layout = self._create_layout()

        layout["header"].update(self._create_header())
        layout["left"].update(self._create_etf_table())
        layout["right"].update(self._create_signals_table())
        layout["footer"].update(self._create_status_bar())

        return layout

    def _render_simple(self) -> str:
        """Simple text rendering when Rich is not available"""
        lines = [
            "=" * 80,
            f"EMA Cloud Sector Scanner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 80,
            "",
            "SECTOR ETF OVERVIEW",
            "-" * 80,
        ]

        for etf in sorted(self._etf_data.values(), key=lambda x: x.trend_strength, reverse=True):
            trend_icon = "↑" if etf.trend == "bullish" else ("↓" if etf.trend == "bearish" else "-")
            lines.append(
                f"{etf.symbol:6} | {etf.sector:20} | ${etf.price:8.2f} | "
                f"{etf.change_pct:+6.2f}% | {trend_icon} {etf.trend:8} | "
                f"Str: {etf.trend_strength:5.1f}%"
            )

        lines.extend(["", "RECENT SIGNALS", "-" * 80])

        for signal in self._signals[:10]:
            arrow = "↑" if signal.direction == "long" else "↓"
            lines.append(
                f"{signal.timestamp.strftime('%H:%M:%S')} | {arrow} {signal.symbol:6} | "
                f"{signal.signal_type:25} | ${signal.price:.2f} | {signal.strength}"
            )

        lines.append("=" * 80)
        return "\n".join(lines)

    async def run(self):
        """Run the dashboard with live updates"""
        self._init_rich()
        self._running = True

        if not self._rich_available:
            # Simple mode - just print periodically
            while self._running:
                print("\033[2J\033[H")  # Clear screen
                print(self._render_simple())
                await asyncio.sleep(self.refresh_rate)
        else:
            from rich.live import Live

            with Live(
                self._render(), console=self._console, refresh_per_second=1, screen=True
            ) as live:
                while self._running:
                    live.update(self._render())
                    await asyncio.sleep(self.refresh_rate)

    def stop(self):
        """Stop the dashboard"""
        self._running = False


class SimpleDashboard:
    """
    Simpler dashboard that doesn't require Rich.
    Prints updates to console in a formatted way.
    """

    def __init__(self):
        self._etf_data: dict[str, ETFDisplayData] = {}
        self._signals: list[SignalDisplayData] = []
        self._running = False

    def update_etf_data(self, data: ETFDisplayData):
        """Update ETF display data"""
        self._etf_data[data.symbol] = data

    def add_signal(self, signal: SignalDisplayData):
        """Add a new signal"""
        self._signals.insert(0, signal)
        self._signals = self._signals[:50]
        self._print_signal(signal)

    def _print_signal(self, signal: SignalDisplayData):
        """Print a signal to console"""
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

    def print_summary(self):
        """Print current summary"""
        print(f"\n{'=' * 60}")
        print(f"SECTOR ETF SUMMARY - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 60}")

        for etf in sorted(self._etf_data.values(), key=lambda x: x.trend_strength, reverse=True):
            trend_icon = (
                "🟢" if etf.trend == "bullish" else ("🔴" if etf.trend == "bearish" else "⚪")
            )
            print(
                f"{trend_icon} {etf.symbol:6} | {etf.sector:20} | "
                f"${etf.price:8.2f} | Trend: {etf.trend_strength:5.1f}%"
            )

        print(f"{'=' * 60}\n")


def create_dashboard(use_rich: bool = True) -> Any:
    """Factory function to create appropriate dashboard"""
    if use_rich:
        try:
            import rich

            return TerminalDashboard()
        except ImportError:
            pass

    return SimpleDashboard()
