"""
Alert Manager

Orchestrates multiple alert handlers and provides utility functions.
"""

import logging

from .base import AlertMessage, BaseAlertHandler
from .console_desktop import ConsoleAlertHandler, DesktopAlertHandler
from .email import EmailAlertHandler
from .web_services import DiscordAlertHandler, TelegramAlertHandler

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages multiple alert handlers and dispatches alerts.
    """

    def __init__(self):
        self.handlers: dict[str, BaseAlertHandler] = {}
        self._alert_history: list[AlertMessage] = []
        self._max_history = 1000

    def add_handler(self, handler: BaseAlertHandler):
        """Add an alert handler"""
        self.handlers[handler.name] = handler
        logger.info(f"Added alert handler: {handler.name}")

    def remove_handler(self, name: str):
        """Remove an alert handler"""
        if name in self.handlers:
            del self.handlers[name]

    def enable_handler(self, name: str):
        """Enable a handler"""
        if name in self.handlers:
            self.handlers[name].enabled = True

    def disable_handler(self, name: str):
        """Disable a handler"""
        if name in self.handlers:
            self.handlers[name].enabled = False

    async def send_alert(self, message: AlertMessage) -> dict[str, bool]:
        """
        Send alert to all enabled handlers.

        Returns:
            Dict mapping handler name to success status
        """
        results = {}

        for name, handler in self.handlers.items():
            if handler.enabled:
                try:
                    results[name] = await handler.send_alert(message)
                except (OSError, TimeoutError, ValueError, RuntimeError) as e:
                    logger.error(f"Handler {name} failed: {e}")
                    results[name] = False

        # Add to history
        self._alert_history.append(message)
        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history :]

        return results

    async def send_batch(self, messages: list[AlertMessage]) -> dict[str, int]:
        """
        Send multiple alerts to all handlers.

        Returns:
            Dict mapping handler name to success count
        """
        results = {}

        for name, handler in self.handlers.items():
            if handler.enabled:
                try:
                    results[name] = await handler.send_batch(messages)
                except (OSError, TimeoutError, ValueError, RuntimeError) as e:
                    logger.error(f"Handler {name} batch failed: {e}")
                    results[name] = 0

        # Add to history
        for message in messages:
            self._alert_history.append(message)

        if len(self._alert_history) > self._max_history:
            self._alert_history = self._alert_history[-self._max_history :]

        return results

    def get_history(self, limit: int = 50) -> list[AlertMessage]:
        """Get recent alert history"""
        return self._alert_history[-limit:]

    @classmethod
    def create_default(cls, config: dict | None = None) -> "AlertManager":
        """Create manager with default handlers based on config"""
        config = config or {}
        manager = cls()

        # Console handler (always enabled)
        console_config = config.get("console", {})
        manager.add_handler(
            ConsoleAlertHandler(
                enabled=console_config.get("enabled", True),
                use_colors=console_config.get("colors", True),
                verbose=console_config.get("verbose", False),
            )
        )

        # Desktop notifications
        desktop_config = config.get("desktop", {})
        manager.add_handler(
            DesktopAlertHandler(
                enabled=desktop_config.get("enabled", True),
                play_sound=desktop_config.get("sound", True),
            )
        )

        # Telegram (if configured)
        telegram_config = config.get("telegram", {})
        if telegram_config.get("enabled"):
            manager.add_handler(
                TelegramAlertHandler(
                    enabled=True,
                    bot_token=telegram_config.get("bot_token"),
                    chat_id=telegram_config.get("chat_id"),
                    timeout=telegram_config.get("timeout", 10),
                )
            )

        # Discord (if configured)
        discord_config = config.get("discord", {})
        if discord_config.get("enabled"):
            manager.add_handler(
                DiscordAlertHandler(
                    enabled=True,
                    webhook_url=discord_config.get("webhook_url"),
                    timeout=discord_config.get("timeout", 10),
                )
            )

        # Email (if configured)
        email_config = config.get("email", {})
        if email_config.get("enabled"):
            manager.add_handler(
                EmailAlertHandler(
                    enabled=True,
                    smtp_server=email_config.get("smtp_server"),
                    smtp_port=email_config.get("smtp_port", 587),
                    smtp_username=email_config.get("username"),
                    smtp_password=email_config.get("password"),
                    from_address=email_config.get("from_address"),
                    to_addresses=email_config.get("recipients", []),
                    use_tls=email_config.get("use_tls", True),
                    timeout=email_config.get("timeout", 30),
                )
            )

        return manager


def create_alert_from_signal(signal) -> AlertMessage:
    """Create AlertMessage from a Signal object"""
    return AlertMessage(
        title=f"{signal.symbol} {signal.signal_type.value.replace('_', ' ').title()}",
        body=f"{'Long' if signal.direction == 'long' else 'Short'} signal at ${signal.price:.2f}",
        symbol=signal.symbol,
        signal_type=signal.signal_type.value,
        direction=signal.direction,
        strength=signal.strength.name,
        price=signal.price,
        timestamp=signal.timestamp,
        extra_data={
            "RSI": signal.rsi,
            "ADX": signal.adx,
            "Volume Ratio": signal.volume_ratio,
            "Stop Loss": signal.suggested_stop,
            "Target": signal.suggested_target,
            "R/R Ratio": signal.risk_reward_ratio,
            "Sector": signal.sector,
            "Valid": signal.is_valid(),
        },
    )
