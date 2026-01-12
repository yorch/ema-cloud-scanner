"""Alerts module for EMA Cloud Library."""

from .handlers import (
    AlertManager,
    AlertMessage,
    BaseAlertHandler,
    ConsoleAlertHandler,
    DesktopAlertHandler,
    DiscordAlertHandler,
    TelegramAlertHandler,
    create_alert_from_signal,
)

__all__ = [
    "AlertManager",
    "AlertMessage",
    "BaseAlertHandler",
    "ConsoleAlertHandler",
    "create_alert_from_signal",
    "DesktopAlertHandler",
    "DiscordAlertHandler",
    "TelegramAlertHandler",
]
