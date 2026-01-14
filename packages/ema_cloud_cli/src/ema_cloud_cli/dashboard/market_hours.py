"""
Market hours indicator widget for the dashboard.
"""

from textual.reactive import reactive
from textual.widgets import Static

from ema_cloud_lib.market_hours import MarketHours


class MarketHoursIndicator(Static):
    """
    Widget displaying current market status with emoji indicator and time info.

    Displays one of:
    - 🟢 MARKET OPEN | 2h 34m to close
    - 🟡 PRE-MARKET | 1h 15m to open
    - 🟠 AFTER-HOURS | Next: Mon 9:30 AM
    - 🔴 MARKET CLOSED | Next: Mon 9:30 AM
    """

    market_status = reactive("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.update_market_status()

    def on_mount(self) -> None:
        """Set up auto-refresh timer."""
        # Refresh every 30 seconds to keep time info current
        self.set_interval(30, self.update_market_status)

    def update_market_status(self) -> None:
        """Update the market status display."""
        status = MarketHours.get_market_status()

        # Format: 🟢 MARKET OPEN | 2h 34m to close
        display_text = f"{status['emoji']} {status['message']}"
        if status['time_info']:
            display_text += f" | {status['time_info']}"

        self.market_status = display_text

    def watch_market_status(self, new_status: str) -> None:
        """React to market status changes."""
        self.update(new_status)
