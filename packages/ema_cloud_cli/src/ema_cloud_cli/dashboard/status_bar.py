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
    cache_hit_rate = reactive(0.0)
    last_call_seconds = reactive(0.0)
    holdings_count = reactive(0)
    holdings_signals_count = reactive(0)

    def render(self) -> str:
        # Format last call time
        if self.last_call_seconds == 0:
            last_call_str = "never"
        elif self.last_call_seconds < 60:
            last_call_str = f"{int(self.last_call_seconds)}s ago"
        else:
            minutes = int(self.last_call_seconds / 60)
            last_call_str = f"{minutes}m ago"

        return (
            f"ETFs: {self.bullish_count + self.bearish_count + self.neutral_count} | "
            f"🟢 {self.bullish_count} 🔴 {self.bearish_count} ⚪ {self.neutral_count} | "
            f"Signals: {self.signals_count} | "
            f"Holdings: {self.holdings_signals_count}/{self.holdings_count} | "
            f"API: {self.api_calls} ({self.api_calls_per_min:.1f}/min) | "
            f"Cache: {self.cache_hit_rate:.0f}% | "
            f"Last: {last_call_str}"
        )
