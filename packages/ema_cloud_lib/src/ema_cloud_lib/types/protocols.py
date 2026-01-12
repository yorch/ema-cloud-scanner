"""
Protocol definitions for dependency injection.

These protocols define interfaces that can be implemented by different
frontends (CLI, web, etc.) to interact with the core library.
"""

from typing import Protocol, runtime_checkable

from .display import ETFDisplayData, SignalDisplayData


@runtime_checkable
class DashboardProtocol(Protocol):
    """Interface for dashboard implementations."""

    def update_etf_data(self, data: ETFDisplayData) -> None:
        """Update ETF display data."""
        ...

    def add_signal(self, signal: SignalDisplayData) -> None:
        """Add a new signal to the display."""
        ...

    def stop(self) -> None:
        """Stop the dashboard."""
        ...
