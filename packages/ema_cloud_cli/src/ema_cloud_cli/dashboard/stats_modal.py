"""
System statistics modal for the dashboard.
"""

from datetime import timedelta

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from ema_cloud_lib import api_call_tracker


class StatsModal(ModalScreen):
    """
    Modal screen displaying comprehensive system statistics.

    Shows:
    - API usage metrics (calls, rate, failures)
    - Cache effectiveness (hit rate, hits/misses)
    - System uptime and health
    - Performance metrics
    """

    CSS = """
    StatsModal {
        align: center middle;
    }

    #stats-dialog {
        width: 70;
        max-height: 90%;
        border: thick $primary;
        background: $panel;
        padding: 1 2;
        overflow-y: auto;
    }

    #stats-title {
        text-align: center;
        text-style: bold;
        padding: 0 0 1 0;
        color: $accent;
    }

    .stats-section {
        padding: 0 0 1 0;
    }

    .section-title {
        text-style: bold;
        color: $secondary;
        padding: 0 0 0 0;
    }

    .stat-row {
        layout: horizontal;
        height: auto;
        padding: 0 2;
    }

    .stat-label {
        width: 25;
        color: $text-muted;
    }

    .stat-value {
        width: 1fr;
        color: $text;
        text-style: bold;
    }

    .stat-good {
        color: $success;
    }

    .stat-warning {
        color: $warning;
    }

    .stat-error {
        color: $error;
    }

    #button-container {
        height: auto;
        padding: 1 0 0 0;
        align: center middle;
    }

    #close-button {
        min-width: 16;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="stats-dialog"):
            yield Label("System Statistics", id="stats-title")

            # API Statistics Section
            with Vertical(classes="stats-section"):
                yield Label("API Usage", classes="section-title")
                yield Static(id="api-stats")

            # Cache Statistics Section
            with Vertical(classes="stats-section"):
                yield Label("Cache Performance", classes="section-title")
                yield Static(id="cache-stats")

            # System Statistics Section
            with Vertical(classes="stats-section"):
                yield Label("System Status", classes="section-title")
                yield Static(id="system-stats")

            # Close button
            with Vertical(id="button-container"):
                yield Button("Close", id="close-button", variant="primary")

    def on_mount(self) -> None:
        """Initialize stats display."""
        self.update_stats()
        # Auto-refresh every 5 seconds while modal is open
        self.set_interval(5, self.update_stats)

    def update_stats(self) -> None:
        """Update all statistics displays."""
        stats = api_call_tracker.get_stats()

        # Update API stats
        api_widget = self.query_one("#api-stats", Static)
        success_class = (
            "stat-good"
            if stats["success_rate"] >= 95
            else "stat-warning"
            if stats["success_rate"] >= 80
            else "stat-error"
        )
        rate_class = (
            "stat-good"
            if stats["calls_per_minute"] < 10
            else "stat-warning"
            if stats["calls_per_minute"] < 20
            else "stat-error"
        )

        api_content = (
            f"  [dim]Total Calls:[/dim]     [bold]{stats['total_calls']}[/bold]\n"
            f"  [dim]Calls/Minute:[/dim]    [{rate_class}]{stats['calls_per_minute']:.1f}[/{rate_class}]\n"
            f"  [dim]Failed Calls:[/dim]    [bold]{stats['failed_calls']}[/bold]\n"
            f"  [dim]Success Rate:[/dim]    [{success_class}]{stats['success_rate']:.1f}%[/{success_class}]"
        )
        api_widget.update(api_content)

        # Update cache stats
        cache_widget = self.query_one("#cache-stats", Static)
        cache_class = (
            "stat-good"
            if stats["cache_hit_rate"] >= 70
            else "stat-warning"
            if stats["cache_hit_rate"] >= 50
            else "stat-error"
        )
        total_cache = stats["cache_hits"] + stats["cache_misses"]

        cache_content = (
            f"  [dim]Cache Hits:[/dim]      [bold]{stats['cache_hits']}[/bold]\n"
            f"  [dim]Cache Misses:[/dim]    [bold]{stats['cache_misses']}[/bold]\n"
            f"  [dim]Total Attempts:[/dim]  [bold]{total_cache}[/bold]\n"
            f"  [dim]Hit Rate:[/dim]        [{cache_class}]{stats['cache_hit_rate']:.1f}%[/{cache_class}]"
        )
        cache_widget.update(cache_content)

        # Update system stats
        system_widget = self.query_one("#system-stats", Static)
        uptime = timedelta(seconds=int(stats["uptime_seconds"]))

        # Format uptime nicely
        if uptime.days > 0:
            uptime_str = (
                f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
            )
        elif uptime.seconds >= 3600:
            uptime_str = f"{uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"
        else:
            uptime_str = f"{uptime.seconds // 60}m {uptime.seconds % 60}s"

        # Last call time
        last_call = stats["last_call_seconds_ago"]
        if last_call is None:
            last_call_str = "Never"
        elif last_call < 60:
            last_call_str = f"{int(last_call)}s ago"
        elif last_call < 3600:
            last_call_str = f"{int(last_call / 60)}m ago"
        else:
            last_call_str = f"{int(last_call / 3600)}h ago"

        # Provider info (if available from dashboard)
        provider = "Yahoo Finance"  # Default, could be made dynamic

        system_content = (
            f"  [dim]Data Provider:[/dim]   [bold]{provider}[/bold]\n"
            f"  [dim]Uptime:[/dim]          [bold]{uptime_str}[/bold]\n"
            f"  [dim]Last API Call:[/dim]   [bold]{last_call_str}[/bold]\n"
            f"  [dim]Health:[/dim]          [{success_class}]{'Excellent' if stats['success_rate'] >= 95 else 'Good' if stats['success_rate'] >= 80 else 'Poor'}[/{success_class}]"
        )
        system_widget.update(system_content)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "close-button":
            self.dismiss()
