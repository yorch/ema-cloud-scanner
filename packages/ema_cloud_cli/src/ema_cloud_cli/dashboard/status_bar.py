"""
Status bar widget for the terminal dashboard.
"""

from textual.reactive import reactive
from textual.widgets import Static


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
