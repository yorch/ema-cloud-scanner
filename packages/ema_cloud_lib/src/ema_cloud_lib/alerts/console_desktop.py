"""
Local Alert Handlers

Handlers that deliver alerts locally without network communication:
- ConsoleAlertHandler: Terminal/console output
- DesktopAlertHandler: OS native notifications
"""

import logging
import sys

from .base import AlertMessage, BaseAlertHandler

logger = logging.getLogger(__name__)


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
