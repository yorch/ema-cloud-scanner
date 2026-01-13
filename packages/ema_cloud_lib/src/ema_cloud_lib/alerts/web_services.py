"""
Web Service Alert Handlers

Handlers that deliver alerts via web service APIs:
- TelegramAlertHandler: Telegram Bot API
- DiscordAlertHandler: Discord Webhook API
"""

import logging
import os

from .base import AlertMessage, BaseAlertHandler, rate_limit

logger = logging.getLogger(__name__)


class TelegramAlertHandler(BaseAlertHandler):
    """Telegram bot alert handler"""

    def __init__(
        self,
        enabled: bool = False,
        bot_token: str | None = None,
        chat_id: str | None = None,
        timeout: int = 10,
    ):
        super().__init__(enabled)
        # Support environment variables for credentials
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.timeout = timeout
        self._validate_config()

    def _validate_config(self):
        """Validate Telegram configuration and dependencies"""
        if self.enabled:
            # Check for aiohttp dependency
            try:
                import aiohttp  # noqa: F401
            except ImportError:
                logger.error("aiohttp not installed. Install with: pip install aiohttp")
                self.enabled = False
                return

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

    @rate_limit(max_per_minute=20)  # Telegram allows 30 msgs/sec, we use conservative limit
    async def send_alert(self, message: AlertMessage) -> bool:
        """Send Telegram message"""
        if not self.enabled or not self.bot_token or not self.chat_id:
            return False

        try:
            import aiohttp

            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

            # Format message with proper Markdown (fixed escaping)
            arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
            text = (
                f"{arrow} *{message.symbol}* Signal\n"
                f"\n"
                f"*Type:* {message.signal_type.replace('_', ' ').title()}\n"
                f"*Direction:* {message.direction.upper()}\n"
                f"*Price:* ${message.price:.2f}\n"
                f"*Strength:* {message.strength}\n"
                f"*Time:* {message.timestamp.strftime('%H:%M:%S')}"
            )

            # Add extra data if available using shared formatter
            if message.extra_data:
                fields = self._format_extra_data_fields(message.extra_data)
                if fields:
                    text += "\n\n*Details:*\n"
                    for label, value in fields:
                        if label == "RSI":
                            text += f"RSI: {value:.1f}\n"
                        elif label == "ADX":
                            text += f"ADX: {value:.1f}\n"
                        elif label == "Volume Ratio":
                            text += f"Volume: {value:.2f}x\n"
                        elif label == "Stop Loss":
                            text += f"Stop: ${value:.2f}\n"
                        elif label == "Target":
                            text += f"Target: ${value:.2f}\n"
                        elif label == "R/R Ratio":
                            text += f"R/R: {value:.2f}\n"
                        elif label == "Sector":
                            text += f"Sector: {value}\n"

            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    if response.status == 200:
                        logger.debug(f"Telegram alert sent successfully for {message.symbol}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Telegram API error {response.status}: {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Telegram alert error: {e}")
            return False


class DiscordAlertHandler(BaseAlertHandler):
    """Discord webhook alert handler"""

    def __init__(
        self,
        enabled: bool = False,
        webhook_url: str | None = None,
        timeout: int = 10,
    ):
        super().__init__(enabled)
        # Support environment variables for credentials
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.timeout = timeout
        self._validate_config()

    def _validate_config(self):
        """Validate Discord configuration and dependencies"""
        if self.enabled:
            # Check for aiohttp dependency
            try:
                import aiohttp  # noqa: F401
            except ImportError:
                logger.error("aiohttp not installed. Install with: pip install aiohttp")
                self.enabled = False
                return

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

    @rate_limit(max_per_minute=30)  # Discord rate limit is 30 per minute per webhook
    async def send_alert(self, message: AlertMessage) -> bool:
        """Send Discord message via webhook"""
        if not self.enabled or not self.webhook_url:
            return False

        try:
            import aiohttp

            # Build embed fields
            fields = [
                {"name": "Type", "value": message.signal_type.replace("_", " ").title(), "inline": True},
                {"name": "Direction", "value": message.direction.upper(), "inline": True},
                {"name": "Price", "value": f"${message.price:.2f}", "inline": True},
                {"name": "Strength", "value": message.strength, "inline": True},
            ]

            # Add extra data fields using shared formatter
            if message.extra_data:
                extra_fields = self._format_extra_data_fields(message.extra_data)
                for label, value in extra_fields:
                    if label == "RSI":
                        fields.append({"name": "RSI", "value": f"{value:.1f}", "inline": True})
                    elif label == "ADX":
                        fields.append({"name": "ADX", "value": f"{value:.1f}", "inline": True})
                    elif label == "Volume Ratio":
                        fields.append({"name": "Volume", "value": f"{value:.2f}x", "inline": True})
                    elif label == "Stop Loss":
                        fields.append({"name": "Stop", "value": f"${value:.2f}", "inline": True})
                    elif label == "Target":
                        fields.append({"name": "Target", "value": f"${value:.2f}", "inline": True})
                    elif label == "R/R Ratio":
                        fields.append({"name": "R/R", "value": f"{value:.2f}", "inline": True})
                    elif label == "Sector":
                        fields.append({"name": "Sector", "value": str(value), "inline": True})

            # Create embed
            arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
            embed = {
                "title": f"{arrow} {message.symbol} Signal",
                "description": message.signal_type.replace("_", " ").title(),
                "color": 0x00FF00 if message.direction == "long" else 0xFF0000,
                "fields": fields,
                "timestamp": message.timestamp.isoformat(),
                "footer": {"text": "EMA Cloud Scanner"},
            }

            payload = {"embeds": [embed], "username": "EMA Cloud Scanner"}

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.webhook_url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                ) as response:
                    if response.status == 204:
                        logger.debug(f"Discord alert sent successfully for {message.symbol}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Discord webhook error {response.status}: {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Discord alert error: {e}")
            return False
