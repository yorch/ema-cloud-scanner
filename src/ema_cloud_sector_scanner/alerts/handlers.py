"""
Alert System Module

Provides extensible alert notifications for trading signals.
Supports multiple output channels:
- Console (default)
- Desktop notifications
- Future: Telegram, Discord, Email, SMS
"""

import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class AlertMessage:
    """Standardized alert message"""

    title: str
    body: str
    symbol: str
    signal_type: str
    direction: str
    strength: str
    price: float
    timestamp: datetime
    extra_data: dict[str, Any] = field(default_factory=dict)

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


class ConsoleAlertHandler(BaseAlertHandler):
    """Console/terminal alert handler"""

    def __init__(self, enabled: bool = True, use_colors: bool = True, verbose: bool = False):
        super().__init__(enabled)
        self.use_colors = use_colors
        self.verbose = verbose

    @property
    def name(self) -> str:
        return "Console"

    def _colorize(self, text: str, color: str) -> str:
        """Add ANSI color codes"""
        if not self.use_colors:
            return text

        colors = {
            "green": "\033[92m",
            "red": "\033[91m",
            "yellow": "\033[93m",
            "blue": "\033[94m",
            "bold": "\033[1m",
            "reset": "\033[0m",
        }

        return f"{colors.get(color, '')}{text}{colors['reset']}"

    async def send_alert(self, message: AlertMessage) -> bool:
        """Print alert to console"""
        if not self.enabled:
            return False

        try:
            output = message.to_full_string() if self.verbose else message.to_short_string()

            # Colorize based on direction
            if message.direction == "long":
                output = self._colorize(output, "green")
            else:
                output = self._colorize(output, "red")

            print(output)
            return True

        except Exception as e:
            logger.error(f"Console alert error: {e}")
            return False


class DesktopAlertHandler(BaseAlertHandler):
    """Desktop notification alert handler"""

    def __init__(self, enabled: bool = True, play_sound: bool = True):
        super().__init__(enabled)
        self.play_sound = play_sound
        self._notifier = None

    @property
    def name(self) -> str:
        return "Desktop"

    def _get_notifier(self):
        """Lazy load notification library"""
        if self._notifier is None:
            try:
                from plyer import notification

                self._notifier = notification
            except ImportError:
                logger.warning("plyer not installed. Desktop notifications disabled.")
                logger.warning("Install with: pip install plyer")
                self.enabled = False
        return self._notifier

    async def send_alert(self, message: AlertMessage) -> bool:
        """Send desktop notification"""
        if not self.enabled:
            return False

        notifier = self._get_notifier()
        if not notifier:
            return False

        try:
            # Format notification
            title = f"{'🟢' if message.direction == 'long' else '🔴'} {message.symbol} Signal"
            body = f"{message.signal_type}\n${message.price:.2f} | {message.strength}"

            notifier.notify(title=title, message=body, app_name="EMA Cloud Scanner", timeout=10)

            # Play sound if enabled
            if self.play_sound:
                await self._play_sound(message.direction)

            return True

        except Exception as e:
            logger.error(f"Desktop notification error: {e}")
            return False

    async def _play_sound(self, direction: str):
        """Play alert sound"""
        try:
            if sys.platform == "darwin":  # macOS
                import subprocess

                sound = "Glass" if direction == "long" else "Basso"
                subprocess.run(
                    ["afplay", f"/System/Library/Sounds/{sound}.aiff"], capture_output=True
                )
            elif sys.platform == "win32":  # Windows
                import winsound

                freq = 800 if direction == "long" else 400
                winsound.Beep(freq, 200)
            else:  # Linux
                # Try using paplay or aplay
                pass
        except Exception as e:
            logger.debug(f"Could not play sound: {e}")


class TelegramAlertHandler(BaseAlertHandler):
    """Telegram bot alert handler (placeholder for future implementation)"""

    def __init__(
        self, enabled: bool = False, bot_token: str | None = None, chat_id: str | None = None
    ):
        super().__init__(enabled)
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def name(self) -> str:
        return "Telegram"

    async def send_alert(self, message: AlertMessage) -> bool:
        """Send Telegram message"""
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        try:
            import aiohttp

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            text = (
                f"{'🟢' if message.direction == 'long' else '🔴'} *{message.symbol}* Signal\n"
                f"Type: {message.signal_type}\n"
                f"Price: ${message.price:.2f}\n"
                f"Strength: {message.strength}\n"
                f"Time: {message.timestamp.strftime('%H:%M:%S')}"
            )

            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    url, json={"chat_id": self.chat_id, "text": text, "parse_mode": "Markdown"}
                ) as response,
            ):
                return response.status == 200

        except Exception as e:
            logger.error(f"Telegram alert error: {e}")
            return False


class DiscordAlertHandler(BaseAlertHandler):
    """Discord webhook alert handler (placeholder for future implementation)"""

    def __init__(self, enabled: bool = False, webhook_url: str | None = None):
        super().__init__(enabled)
        self.webhook_url = webhook_url

    @property
    def name(self) -> str:
        return "Discord"

    async def send_alert(self, message: AlertMessage) -> bool:
        """Send Discord message via webhook"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            import aiohttp

            embed = {
                "title": f"{'🟢' if message.direction == 'long' else '🔴'} {message.symbol} Signal",
                "color": 0x00FF00 if message.direction == "long" else 0xFF0000,
                "fields": [
                    {"name": "Type", "value": message.signal_type, "inline": True},
                    {"name": "Price", "value": f"${message.price:.2f}", "inline": True},
                    {"name": "Strength", "value": message.strength, "inline": True},
                ],
                "timestamp": message.timestamp.isoformat(),
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json={"embeds": [embed]}) as response:
                    return response.status == 204

        except Exception as e:
            logger.error(f"Discord alert error: {e}")
            return False


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
                except Exception as e:
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
                except Exception as e:
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
                )
            )

        # Discord (if configured)
        discord_config = config.get("discord", {})
        if discord_config.get("enabled"):
            manager.add_handler(
                DiscordAlertHandler(enabled=True, webhook_url=discord_config.get("webhook_url"))
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
