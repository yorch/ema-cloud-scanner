"""
Protocol definitions for dependency injection.

These protocols define interfaces that can be implemented by different
frontends (CLI, web, etc.) to interact with the core library.
"""

from typing import Protocol, runtime_checkable

from .display import ETFDisplayData, HoldingsETFDisplayData, SignalDisplayData


@runtime_checkable
class DashboardProtocol(Protocol):
    """Interface for dashboard implementations."""

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Update ETF display data."""
        ...

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Add a new signal to the display."""
        ...

    def update_holdings_data(self, data: HoldingsETFDisplayData) -> None:
        """Update holdings display data."""
        ...

    def stop(self) -> None:
        """Stop the dashboard."""
        ...
