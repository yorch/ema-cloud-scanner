"""Types module - display dataclasses and protocols."""

from .display import ETFDisplayData, HoldingDisplayData, HoldingsETFDisplayData, SignalDisplayData
from .protocols import DashboardProtocol

__all__ = [
    "ETFDisplayData",
    "HoldingDisplayData",
    "HoldingsETFDisplayData",
    "SignalDisplayData",
    "DashboardProtocol",
]
