"""
Alert System

Modular alert notification system with multiple handler types.
"""

from .base import AlertMessage, BaseAlertHandler, rate_limit
from .console_desktop import ConsoleAlertHandler, DesktopAlertHandler
from .email import EmailAlertHandler
from .manager import AlertManager, create_alert_from_signal
from .web_services import DiscordAlertHandler, TelegramAlertHandler

__all__ = [
    # Base classes and utilities
    "AlertMessage",
    "BaseAlertHandler",
    "rate_limit",
    # Local handlers
    "ConsoleAlertHandler",
    "DesktopAlertHandler",
    # Network handlers
    "TelegramAlertHandler",
    "DiscordAlertHandler",
    "EmailAlertHandler",
    # Manager and utilities
    "AlertManager",
    "create_alert_from_signal",
]
