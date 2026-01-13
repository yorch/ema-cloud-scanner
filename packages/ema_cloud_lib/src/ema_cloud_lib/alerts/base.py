"""
Core Alert System Abstractions

Provides base classes and utilities for the alert notification system.
"""

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from functools import wraps
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


def rate_limit(max_per_minute: int):
    """
    Rate limiting decorator for async methods.

    Args:
        max_per_minute: Maximum number of calls allowed per minute
    """
    def decorator(func):
        last_called = deque(maxlen=max_per_minute)

        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            now = time.time()
            # Remove timestamps older than 60 seconds
            while last_called and now - last_called[0] >= 60:
                last_called.popleft()

            if len(last_called) >= max_per_minute:
                logger.warning(f"{self.name} handler rate limit reached ({max_per_minute}/min)")
                return False

            last_called.append(now)
            return await func(self, *args, **kwargs)

        return wrapper
    return decorator


class AlertMessage(BaseModel):
    """Standardized alert message"""

    title: str = Field(..., description="Alert title")
    body: str = Field(..., description="Alert body text")
    symbol: str = Field(..., description="Symbol for alert")
    signal_type: str = Field(..., description="Type of signal")
    direction: str = Field(..., description="Signal direction")
    strength: str = Field(..., description="Signal strength")
    price: float = Field(..., description="Price at signal")
    timestamp: datetime = Field(..., description="Alert timestamp")
    extra_data: dict[str, Any] = Field(default_factory=dict, description="Additional alert data")

    def to_short_string(self) -> str:
        """Short format for console"""
        arrow = "🟢 ↑" if self.direction == "long" else "🔴 ↓"
        return f"{arrow} {self.symbol}: {self.signal_type} @ ${self.price:.2f} [{self.strength}]"

    def to_full_string(self) -> str:
        """Full format with details"""
        lines = [
            f"{'=' * 50}",
            f"🔔 SIGNAL ALERT: {self.title}",
            f"{'=' * 50}",
            f"Symbol: {self.symbol}",
            f"Type: {self.signal_type}",
            f"Direction: {self.direction.upper()}",
            f"Strength: {self.strength}",
            f"Price: ${self.price:.2f}",
            f"Time: {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        if self.extra_data:
            lines.append("-" * 50)
            for key, value in self.extra_data.items():
                if value is not None:
                    if isinstance(value, float):
                        lines.append(f"{key}: {value:.2f}")
                    else:
                        lines.append(f"{key}: {value}")

        lines.append("=" * 50)
        return "\n".join(lines)


class BaseAlertHandler(ABC):
    """Base class for alert handlers"""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled

    @property
    @abstractmethod
    def name(self) -> str:
        """Handler name"""
        pass

    @abstractmethod
    async def send_alert(self, message: AlertMessage) -> bool:
        """
        Send an alert message.

        Returns:
            True if successful, False otherwise
        """
        pass

    async def send_batch(self, messages: list[AlertMessage]) -> int:
        """
        Send multiple alerts.

        Returns:
            Number of successful sends
        """
        if not self.enabled:
            return 0

        success_count = 0
        for message in messages:
            if await self.send_alert(message):
                success_count += 1
        return success_count

    @staticmethod
    def _format_extra_data_fields(extra_data: dict[str, Any]) -> list[tuple[str, Any]]:
        """
        Extract and format extra_data fields consistently across handlers.

        Returns:
            List of (label, value) tuples for present fields
        """
        fields = []

        if extra_data.get("RSI") is not None:
            fields.append(("RSI", extra_data["RSI"]))
        if extra_data.get("ADX") is not None:
            fields.append(("ADX", extra_data["ADX"]))
        if extra_data.get("Volume Ratio") is not None:
            fields.append(("Volume Ratio", extra_data["Volume Ratio"]))
        if extra_data.get("Stop Loss") is not None:
            fields.append(("Stop Loss", extra_data["Stop Loss"]))
        if extra_data.get("Target") is not None:
            fields.append(("Target", extra_data["Target"]))
        if extra_data.get("R/R Ratio") is not None:
            fields.append(("R/R Ratio", extra_data["R/R Ratio"]))
        if extra_data.get("Sector") is not None:
            fields.append(("Sector", extra_data["Sector"]))

        return fields
