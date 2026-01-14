"""
Email Alert Handler

Handler that delivers alerts via SMTP email with HTML formatting.
"""

import asyncio
import logging
import os

from .base import AlertMessage, BaseAlertHandler, rate_limit

logger = logging.getLogger(__name__)


class EmailAlertHandler(BaseAlertHandler):
    """Email alert handler with non-blocking SMTP"""

    def __init__(
        self,
        enabled: bool = False,
        smtp_server: str | None = None,
        smtp_port: int = 587,
        smtp_username: str | None = None,
        smtp_password: str | None = None,
        from_address: str | None = None,
        to_addresses: list[str] | None = None,
        use_tls: bool = True,
        timeout: int = 30,
    ):
        super().__init__(enabled)
        # Support environment variables for credentials
        self.smtp_server = smtp_server or os.getenv("SMTP_SERVER")
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username or os.getenv("SMTP_USERNAME")
        self.smtp_password = smtp_password or os.getenv("SMTP_PASSWORD")
        self.from_address = from_address or os.getenv("SMTP_FROM_ADDRESS")
        self.to_addresses = to_addresses or []
        self.use_tls = use_tls
        self.timeout = timeout
        self._validate_config()

    def _validate_config(self):
        """Validate email configuration and dependencies"""
        if self.enabled:
            # Check for smtplib (standard library, should always be available)
            try:
                import smtplib  # noqa: F401
            except ImportError:
                logger.error("smtplib not available")
                self.enabled = False
                return

            if not self.smtp_server:
                logger.warning(
                    "Email enabled but smtp_server not provided. Disabling email alerts."
                )
                self.enabled = False
            elif not self.smtp_username or not self.smtp_password:
                logger.warning(
                    "Email enabled but credentials not provided. Disabling email alerts."
                )
                self.enabled = False
            elif not self.from_address:
                logger.warning(
                    "Email enabled but from_address not provided. Disabling email alerts."
                )
                self.enabled = False
            elif not self.to_addresses:
                logger.warning(
                    "Email enabled but to_addresses not provided. Disabling email alerts."
                )
                self.enabled = False
            else:
                logger.info("Email alerts configured and enabled")

    @property
    def name(self) -> str:
        return "Email"

    def _create_html_message(self, message: AlertMessage) -> str:
        """Create HTML email body"""
        arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
        color = "#28a745" if message.direction == "long" else "#dc3545"

        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: {color}; color: white; padding: 15px; border-radius: 5px; }}
                .content {{ padding: 15px; }}
                .field {{ margin: 10px 0; }}
                .label {{ font-weight: bold; color: #333; }}
                .value {{ color: #666; }}
                .footer {{ margin-top: 20px; padding-top: 10px; border-top: 1px solid #ddd; color: #999; font-size: 12px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>{arrow} {message.symbol} Signal</h2>
            </div>
            <div class="content">
                <div class="field">
                    <span class="label">Type:</span>
                    <span class="value">{message.signal_type.replace("_", " ").title()}</span>
                </div>
                <div class="field">
                    <span class="label">Direction:</span>
                    <span class="value">{message.direction.upper()}</span>
                </div>
                <div class="field">
                    <span class="label">Price:</span>
                    <span class="value">${message.price:.2f}</span>
                </div>
                <div class="field">
                    <span class="label">Strength:</span>
                    <span class="value">{message.strength}</span>
                </div>
                <div class="field">
                    <span class="label">Time:</span>
                    <span class="value">{message.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</span>
                </div>
        """

        # Add extra data fields using shared formatter
        if message.extra_data:
            html += '<div class="field"><span class="label">Details:</span></div>'
            fields = self._format_extra_data_fields(message.extra_data)
            for label, value in fields:
                if label == "RSI":
                    html += f'<div class="field"><span class="label">RSI:</span> <span class="value">{value:.1f}</span></div>'
                elif label == "ADX":
                    html += f'<div class="field"><span class="label">ADX:</span> <span class="value">{value:.1f}</span></div>'
                elif label == "Volume Ratio":
                    html += f'<div class="field"><span class="label">Volume:</span> <span class="value">{value:.2f}x</span></div>'
                elif label == "Stop Loss":
                    html += f'<div class="field"><span class="label">Stop:</span> <span class="value">${value:.2f}</span></div>'
                elif label == "Target":
                    html += f'<div class="field"><span class="label">Target:</span> <span class="value">${value:.2f}</span></div>'
                elif label == "R/R Ratio":
                    html += f'<div class="field"><span class="label">R/R:</span> <span class="value">{value:.2f}</span></div>'
                elif label == "Sector":
                    html += f'<div class="field"><span class="label">Sector:</span> <span class="value">{value}</span></div>'

        html += """
            </div>
            <div class="footer">
                EMA Cloud Scanner Alert
            </div>
        </body>
        </html>
        """
        return html

    def _create_text_message(self, message: AlertMessage) -> str:
        """Create plain text email body"""
        arrow = "🟢 ↗️" if message.direction == "long" else "🔴 ↘️"
        text = f"""{arrow} {message.symbol} Signal

Type: {message.signal_type.replace("_", " ").title()}
Direction: {message.direction.upper()}
Price: ${message.price:.2f}
Strength: {message.strength}
Time: {message.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
"""

        # Add extra data fields using shared formatter
        if message.extra_data:
            text += "\nDetails:\n"
            fields = self._format_extra_data_fields(message.extra_data)
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

        text += "\n---\nEMA Cloud Scanner Alert"
        return text

    def _send_smtp_sync(self, message: AlertMessage) -> None:
        """Synchronous SMTP operations (run in thread pool)"""
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"{'🟢' if message.direction == 'long' else '🔴'} {message.symbol} Signal"
        msg["From"] = self.from_address
        msg["To"] = ", ".join(self.to_addresses)

        # Attach both plain text and HTML versions
        text_part = MIMEText(self._create_text_message(message), "plain")
        html_part = MIMEText(self._create_html_message(message), "html")
        msg.attach(text_part)
        msg.attach(html_part)

        # Send via SMTP
        server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout)
        try:
            if self.use_tls:
                server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.sendmail(self.from_address, self.to_addresses, msg.as_string())
            logger.debug(f"Email alert sent successfully for {message.symbol}")
        finally:
            server.quit()

    @rate_limit(max_per_minute=10)  # Conservative email rate limit
    async def send_alert(self, message: AlertMessage) -> bool:
        """Send email alert (non-blocking)"""
        if not self.enabled:
            return False

        try:
            # Run blocking SMTP operations in thread pool
            await asyncio.to_thread(self._send_smtp_sync, message)
            return True

        except Exception as e:
            logger.error(f"Email alert error: {e}")
            return False
