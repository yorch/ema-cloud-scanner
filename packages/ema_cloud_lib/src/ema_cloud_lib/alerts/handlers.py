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
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
    """Telegram bot alert handler"""

    def __init__(
        self, enabled: bool = False, bot_token: str | None = None, chat_id: str | None = None
    ):
        super().__init__(enabled)
        self.bot_token = bot_token
        self.chat_id = chat_id
        self._validate_config()

    def _validate_config(self):
        """Validate Telegram configuration"""
        if self.enabled:
            if not self.bot_token:
                logger.warning("Telegram enabled but bot_token not provided. Disabling Telegram alerts.")
                self.enabled = False
            elif not self.chat_id:
                logger.warning("Telegram enabled but chat_id not provided. Disabling Telegram alerts.")
                self.enabled = False
            else:
                logger.info("Telegram alerts configured and enabled")

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

            # Format message with Markdown
            arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
            text = (
                f"{arrow} *{message.symbol}* Signal\\n"
                f"\\n"
                f"*Type:* {message.signal_type.replace('_', ' ').title()}\\n"
                f"*Direction:* {message.direction.upper()}\\n"
                f"*Price:* ${message.price:.2f}\\n"
                f"*Strength:* {message.strength}\\n"
                f"*Time:* {message.timestamp.strftime('%H:%M:%S')}"
            )

            # Add extra data if available
            if message.extra_data:
                text += "\\n\\n*Details:*\\n"
                if message.extra_data.get("RSI"):
                    text += f"RSI: {message.extra_data['RSI']:.1f}\\n"
                if message.extra_data.get("ADX"):
                    text += f"ADX: {message.extra_data['ADX']:.1f}\\n"
                if message.extra_data.get("Volume Ratio"):
                    text += f"Volume: {message.extra_data['Volume Ratio']:.2f}x\\n"
                if message.extra_data.get("Stop Loss"):
                    text += f"Stop: ${message.extra_data['Stop Loss']:.2f}\\n"
                if message.extra_data.get("Target"):
                    text += f"Target: ${message.extra_data['Target']:.2f}\\n"
                if message.extra_data.get("R/R Ratio"):
                    text += f"R/R: {message.extra_data['R/R Ratio']:.2f}\\n"

            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        logger.debug(f"Telegram alert sent successfully for {message.symbol}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram API error {response.status}: {error_text}")
                        return False

        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            self.enabled = False
            return False
        except Exception as e:
            logger.error(f"Telegram alert error: {e}")
            return False


class DiscordAlertHandler(BaseAlertHandler):
    """Discord webhook alert handler"""

    def __init__(self, enabled: bool = False, webhook_url: str | None = None):
        super().__init__(enabled)
        self.webhook_url = webhook_url
        self._validate_config()

    def _validate_config(self):
        """Validate Discord configuration"""
        if self.enabled:
            if not self.webhook_url:
                logger.warning("Discord enabled but webhook_url not provided. Disabling Discord alerts.")
                self.enabled = False
            elif not self.webhook_url.startswith("https://discord.com/api/webhooks/"):
                logger.warning("Discord webhook URL appears invalid. Disabling Discord alerts.")
                self.enabled = False
            else:
                logger.info("Discord alerts configured and enabled")

    @property
    def name(self) -> str:
        return "Discord"

    async def send_alert(self, message: AlertMessage) -> bool:
        """Send Discord message via webhook"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            import aiohttp

            # Build embed fields
            fields = [
                {"name": "Type", "value": message.signal_type.replace('_', ' ').title(), "inline": True},
                {"name": "Direction", "value": message.direction.upper(), "inline": True},
                {"name": "Price", "value": f"${message.price:.2f}", "inline": True},
                {"name": "Strength", "value": message.strength, "inline": True},
            ]

            # Add extra data fields
            if message.extra_data:
                if message.extra_data.get("RSI"):
                    fields.append({"name": "RSI", "value": f"{message.extra_data['RSI']:.1f}", "inline": True})
                if message.extra_data.get("ADX"):
                    fields.append({"name": "ADX", "value": f"{message.extra_data['ADX']:.1f}", "inline": True})
                if message.extra_data.get("Volume Ratio"):
                    fields.append({"name": "Volume", "value": f"{message.extra_data['Volume Ratio']:.2f}x", "inline": True})
                if message.extra_data.get("Stop Loss") and message.extra_data.get("Target"):
                    fields.append({"name": "Stop", "value": f"${message.extra_data['Stop Loss']:.2f}", "inline": True})
                    fields.append({"name": "Target", "value": f"${message.extra_data['Target']:.2f}", "inline": True})
                if message.extra_data.get("R/R Ratio"):
                    fields.append({"name": "R/R", "value": f"{message.extra_data['R/R Ratio']:.2f}", "inline": True})

            # Create embed
            arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
            embed = {
                "title": f"{arrow} {message.symbol} Signal",
                "description": message.signal_type.replace('_', ' ').title(),
                "color": 0x00FF00 if message.direction == "long" else 0xFF0000,
                "fields": fields,
                "timestamp": message.timestamp.isoformat(),
                "footer": {
                    "text": "EMA Cloud Scanner"
                }
            }

            payload = {
                "embeds": [embed],
                "username": "EMA Cloud Scanner"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url, 
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 204:
                        logger.debug(f"Discord alert sent successfully for {message.symbol}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook error {response.status}: {error_text}")
                        return False

        except ImportError:
            logger.error("aiohttp not installed. Install with: pip install aiohttp")
            self.enabled = False
            return False
        except Exception as e:
            logger.error(f"Discord alert error: {e}")
            return False


class EmailAlertHandler(BaseAlertHandler):
    """Email alert handler via SMTP"""

    def __init__(
        self,
        enabled: bool = False,
        smtp_server: str | None = None,
        smtp_port: int = 587,
        use_tls: bool = True,
        use_ssl: bool = False,
        username: str | None = None,
        password: str | None = None,
        from_address: str | None = None,
        from_name: str = "EMA Cloud Scanner",
        recipients: list[str] | None = None,
        subject_prefix: str = "[EMA Signal]",
    ):
        super().__init__(enabled)
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.username = username
        self.password = password
        self.from_address = from_address or username
        self.from_name = from_name
        self.recipients = recipients or []
        self.subject_prefix = subject_prefix
        self._validate_config()

    def _validate_config(self):
        """Validate email configuration"""
        if self.enabled:
            if not self.smtp_server:
                logger.warning("Email enabled but smtp_server not provided. Disabling email alerts.")
                self.enabled = False
            elif not self.username:
                logger.warning("Email enabled but username not provided. Disabling email alerts.")
                self.enabled = False
            elif not self.password:
                logger.warning("Email enabled but password not provided. Disabling email alerts.")
                self.enabled = False
            elif not self.recipients:
                logger.warning("Email enabled but no recipients provided. Disabling email alerts.")
                self.enabled = False
            elif not self.from_address:
                logger.warning("Email enabled but from_address not provided. Disabling email alerts.")
                self.enabled = False
            else:
                logger.info(f"Email alerts configured for {len(self.recipients)} recipient(s)")

    @property
    def name(self) -> str:
        return "Email"

    def _create_html_message(self, message: AlertMessage) -> str:
        """Create HTML email body"""
        arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
        color = "#00AA00" if message.direction == "long" else "#AA0000"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: {color}; color: white; padding: 20px; text-align: center; border-radius: 5px 5px 0 0; }}
                .content {{ background-color: #f9f9f9; padding: 20px; border: 1px solid #ddd; border-top: none; }}
                .signal-info {{ margin: 20px 0; }}
                .info-row {{ display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #ddd; }}
                .info-label {{ font-weight: bold; color: #666; }}
                .info-value {{ color: #333; }}
                .details {{ margin-top: 20px; background-color: white; padding: 15px; border-radius: 5px; }}
                .footer {{ text-align: center; margin-top: 20px; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>{arrow} {message.symbol} Signal</h1>
                    <p>{message.signal_type.replace('_', ' ').title()}</p>
                </div>
                <div class="content">
                    <div class="signal-info">
                        <div class="info-row">
                            <span class="info-label">Symbol:</span>
                            <span class="info-value">{message.symbol}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Type:</span>
                            <span class="info-value">{message.signal_type.replace('_', ' ').title()}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Direction:</span>
                            <span class="info-value" style="color: {color}; font-weight: bold;">{message.direction.upper()}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Price:</span>
                            <span class="info-value">${message.price:.2f}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Strength:</span>
                            <span class="info-value">{message.strength}</span>
                        </div>
                        <div class="info-row">
                            <span class="info-label">Time:</span>
                            <span class="info-value">{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</span>
                        </div>
                    </div>
        """
        
        # Add extra data if available
        if message.extra_data:
            html += '<div class="details"><h3>Additional Details</h3>'
            if message.extra_data.get("RSI"):
                html += f'<div class="info-row"><span class="info-label">RSI:</span><span class="info-value">{message.extra_data["RSI"]:.1f}</span></div>'
            if message.extra_data.get("ADX"):
                html += f'<div class="info-row"><span class="info-label">ADX:</span><span class="info-value">{message.extra_data["ADX"]:.1f}</span></div>'
            if message.extra_data.get("Volume Ratio"):
                html += f'<div class="info-row"><span class="info-label">Volume Ratio:</span><span class="info-value">{message.extra_data["Volume Ratio"]:.2f}x</span></div>'
            if message.extra_data.get("Stop Loss"):
                html += f'<div class="info-row"><span class="info-label">Stop Loss:</span><span class="info-value">${message.extra_data["Stop Loss"]:.2f}</span></div>'
            if message.extra_data.get("Target"):
                html += f'<div class="info-row"><span class="info-label">Target:</span><span class="info-value">${message.extra_data["Target"]:.2f}</span></div>'
            if message.extra_data.get("R/R Ratio"):
                html += f'<div class="info-row"><span class="info-label">Risk/Reward:</span><span class="info-value">{message.extra_data["R/R Ratio"]:.2f}</span></div>'
            if message.extra_data.get("Sector"):
                html += f'<div class="info-row"><span class="info-label">Sector:</span><span class="info-value">{message.extra_data["Sector"]}</span></div>'
            html += '</div>'
        
        html += """
                </div>
                <div class="footer">
                    <p>EMA Cloud Scanner - Automated Trading Signal Notification</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html

    def _create_text_message(self, message: AlertMessage) -> str:
        """Create plain text email body"""
        arrow = "↑" if message.direction == "long" else "↓"
        
        text = f"""
{arrow} {message.symbol} Signal
{'=' * 50}

Signal Type: {message.signal_type.replace('_', ' ').title()}
Direction: {message.direction.upper()}
Price: ${message.price:.2f}
Strength: {message.strength}
Time: {message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        # Add extra data if available
        if message.extra_data:
            text += "Additional Details:\n"
            text += "-" * 50 + "\n"
            if message.extra_data.get("RSI"):
                text += f"RSI: {message.extra_data['RSI']:.1f}\n"
            if message.extra_data.get("ADX"):
                text += f"ADX: {message.extra_data['ADX']:.1f}\n"
            if message.extra_data.get("Volume Ratio"):
                text += f"Volume Ratio: {message.extra_data['Volume Ratio']:.2f}x\n"
            if message.extra_data.get("Stop Loss"):
                text += f"Stop Loss: ${message.extra_data['Stop Loss']:.2f}\n"
            if message.extra_data.get("Target"):
                text += f"Target: ${message.extra_data['Target']:.2f}\n"
            if message.extra_data.get("R/R Ratio"):
                text += f"Risk/Reward: {message.extra_data['R/R Ratio']:.2f}\n"
            if message.extra_data.get("Sector"):
                text += f"Sector: {message.extra_data['Sector']}\n"
        
        text += "\n" + "=" * 50 + "\n"
        text += "EMA Cloud Scanner - Automated Trading Signal Notification\n"
        
        return text

    async def send_alert(self, message: AlertMessage) -> bool:
        """Send email alert"""
        if not self.enabled:
            return False

        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"{self.subject_prefix} {message.symbol} - {message.signal_type.replace('_', ' ').title()}"
            msg['From'] = f"{self.from_name} <{self.from_address}>"
            msg['To'] = ", ".join(self.recipients)

            # Create both plain text and HTML versions
            text_body = self._create_text_message(message)
            html_body = self._create_html_message(message)

            # Attach both versions
            part1 = MIMEText(text_body, 'plain')
            part2 = MIMEText(html_body, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            if self.use_ssl:
                # SSL connection
                server = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            else:
                # Regular connection with optional TLS
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()

            # Login and send
            server.login(self.username, self.password)
            server.sendmail(self.from_address, self.recipients, msg.as_string())
            server.quit()

            logger.debug(f"Email alert sent successfully for {message.symbol} to {len(self.recipients)} recipient(s)")
            return True

        except ImportError:
            logger.error("smtplib not available. Email alerts require Python standard library.")
            self.enabled = False
            return False
        except Exception as e:
            logger.error(f"Email alert error: {e}")
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

        # Email (if configured)
        email_config = config.get("email", {})
        if email_config.get("enabled"):
            manager.add_handler(
                EmailAlertHandler(
                    enabled=True,
                    smtp_server=email_config.get("smtp_server"),
                    smtp_port=email_config.get("smtp_port", 587),
                    use_tls=email_config.get("use_tls", True),
                    use_ssl=email_config.get("use_ssl", False),
                    username=email_config.get("username"),
                    password=email_config.get("password"),
                    from_address=email_config.get("from_address"),
                    from_name=email_config.get("from_name", "EMA Cloud Scanner"),
                    recipients=email_config.get("recipients", []),
                    subject_prefix=email_config.get("subject_prefix", "[EMA Signal]"),
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
