#!/usr/bin/env python3
"""
Test script for alert system

Tests all configured alert handlers with sample signals.
"""

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path


# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "ema_cloud_lib" / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "packages" / "ema_cloud_cli" / "src"))

from ema_cloud_lib.alerts import (
    AlertManager,
    AlertMessage,
    ConsoleAlertHandler,
    DesktopAlertHandler,
    DiscordAlertHandler,
    EmailAlertHandler,
    TelegramAlertHandler,
)


def create_test_message(direction: str = "long") -> AlertMessage:
    """Create a test alert message"""
    return AlertMessage(
        title="XLK Test Signal",
        body=f"{'Long' if direction == 'long' else 'Short'} signal test",
        symbol="XLK",
        signal_type="cloud_flip",
        direction=direction,
        strength="STRONG",
        price=180.45,
        timestamp=datetime.now(),
        extra_data={
            "RSI": 62.5,
            "ADX": 28.3,
            "Volume Ratio": 1.8,
            "Stop Loss": 178.20,
            "Target": 184.50,
            "R/R Ratio": 2.15,
            "Sector": "Technology",
        },
    )


async def test_console():
    """Test console alerts"""
    print("\n" + "=" * 60)
    print("Testing Console Alerts")
    print("=" * 60)

    handler = ConsoleAlertHandler(enabled=True, use_colors=True, verbose=False)
    message = create_test_message("long")

    print("\nShort format:")
    success = await handler.send_alert(message)
    print(f"✓ Console alert sent: {success}")

    print("\nVerbose format:")
    handler.verbose = True
    message2 = create_test_message("short")
    success = await handler.send_alert(message2)
    print(f"✓ Console verbose alert sent: {success}")


async def test_desktop():
    """Test desktop notifications"""
    print("\n" + "=" * 60)
    print("Testing Desktop Notifications")
    print("=" * 60)

    handler = DesktopAlertHandler(enabled=True, play_sound=True)
    message = create_test_message("long")

    print("\nSending desktop notification...")
    success = await handler.send_alert(message)

    if success:
        print("✓ Desktop notification sent successfully")
        print("  Check your system notifications!")
    else:
        print("✗ Desktop notification failed")
        print("  Install plyer: pip install plyer")


async def test_telegram():
    """Test Telegram alerts"""
    print("\n" + "=" * 60)
    print("Testing Telegram Alerts")
    print("=" * 60)

    bot_token = os.getenv("EMA_TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("EMA_TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("⚠ Telegram not configured")
        print("  Set EMA_TELEGRAM_BOT_TOKEN and EMA_TELEGRAM_CHAT_ID")
        return

    handler = TelegramAlertHandler(enabled=True, bot_token=bot_token, chat_id=chat_id)
    message = create_test_message("long")

    print(f"\nBot Token: {bot_token[:10]}...")
    print(f"Chat ID: {chat_id}")
    print("\nSending Telegram message...")

    success = await handler.send_alert(message)

    if success:
        print("✓ Telegram alert sent successfully")
        print("  Check your Telegram!")
    else:
        print("✗ Telegram alert failed")
        print("  Check your bot token and chat ID")


async def test_discord():
    """Test Discord alerts"""
    print("\n" + "=" * 60)
    print("Testing Discord Alerts")
    print("=" * 60)

    webhook_url = os.getenv("EMA_DISCORD_WEBHOOK_URL")

    if not webhook_url:
        print("⚠ Discord not configured")
        print("  Set EMA_DISCORD_WEBHOOK_URL")
        return

    handler = DiscordAlertHandler(enabled=True, webhook_url=webhook_url)
    message = create_test_message("short")

    print(f"\nWebhook URL: {webhook_url[:50]}...")
    print("\nSending Discord message...")

    success = await handler.send_alert(message)

    if success:
        print("✓ Discord alert sent successfully")
        print("  Check your Discord channel!")
    else:
        print("✗ Discord alert failed")
        print("  Check your webhook URL")


async def test_email():
    """Test email alerts"""
    print("\n" + "=" * 60)
    print("Testing Email Alerts")
    print("=" * 60)

    smtp_server = os.getenv("EMA_EMAIL_SMTP_SERVER")
    username = os.getenv("EMA_EMAIL_USERNAME")
    password = os.getenv("EMA_EMAIL_PASSWORD")
    recipients = os.getenv("EMA_EMAIL_RECIPIENTS")

    if not smtp_server or not username or not password or not recipients:
        print("⚠ Email not configured")
        print("  Set EMA_EMAIL_SMTP_SERVER, EMA_EMAIL_USERNAME,")
        print("  EMA_EMAIL_PASSWORD, and EMA_EMAIL_RECIPIENTS")
        return

    # Parse recipients (comma-separated)
    recipient_list = [r.strip() for r in recipients.split(",")]

    handler = EmailAlertHandler(
        enabled=True,
        smtp_server=smtp_server,
        smtp_port=int(os.getenv("EMA_EMAIL_SMTP_PORT", "587")),
        use_tls=os.getenv("EMA_EMAIL_USE_TLS", "true").lower() == "true",
        use_ssl=os.getenv("EMA_EMAIL_USE_SSL", "false").lower() == "true",
        username=username,
        password=password,
        from_address=os.getenv("EMA_EMAIL_FROM_ADDRESS", username),
        from_name=os.getenv("EMA_EMAIL_FROM_NAME", "EMA Cloud Scanner"),
        recipients=recipient_list,
        subject_prefix=os.getenv("EMA_EMAIL_SUBJECT_PREFIX", "[EMA Signal]"),
    )
    message = create_test_message("long")

    print(f"\nSMTP Server: {smtp_server}")
    print(f"Username: {username}")
    print(f"Recipients: {', '.join(recipient_list)}")
    print("\nSending email...")

    success = await handler.send_alert(message)

    if success:
        print("✓ Email alert sent successfully")
        print("  Check your inbox!")
    else:
        print("✗ Email alert failed")
        print("  Check your SMTP settings and credentials")


async def test_alert_manager():
    """Test AlertManager with multiple handlers"""
    print("\n" + "=" * 60)
    print("Testing Alert Manager")
    print("=" * 60)

    # Create manager
    recipients_str = os.getenv("EMA_EMAIL_RECIPIENTS")
    recipients = [r.strip() for r in recipients_str.split(",")] if recipients_str else []

    config = {
        "console": {"enabled": True, "colors": True},
        "desktop": {"enabled": True, "sound": False},
        "telegram": {
            "enabled": bool(os.getenv("EMA_TELEGRAM_BOT_TOKEN")),
            "bot_token": os.getenv("EMA_TELEGRAM_BOT_TOKEN"),
            "chat_id": os.getenv("EMA_TELEGRAM_CHAT_ID"),
        },
        "discord": {
            "enabled": bool(os.getenv("EMA_DISCORD_WEBHOOK_URL")),
            "webhook_url": os.getenv("EMA_DISCORD_WEBHOOK_URL"),
        },
        "email": {
            "enabled": bool(os.getenv("EMA_EMAIL_SMTP_SERVER") and recipients),
            "smtp_server": os.getenv("EMA_EMAIL_SMTP_SERVER"),
            "smtp_port": int(os.getenv("EMA_EMAIL_SMTP_PORT", "587")),
            "use_tls": os.getenv("EMA_EMAIL_USE_TLS", "true").lower() == "true",
            "use_ssl": os.getenv("EMA_EMAIL_USE_SSL", "false").lower() == "true",
            "username": os.getenv("EMA_EMAIL_USERNAME"),
            "password": os.getenv("EMA_EMAIL_PASSWORD"),
            "from_address": os.getenv("EMA_EMAIL_FROM_ADDRESS"),
            "from_name": os.getenv("EMA_EMAIL_FROM_NAME", "EMA Cloud Scanner"),
            "recipients": recipients,
            "subject_prefix": os.getenv("EMA_EMAIL_SUBJECT_PREFIX", "[EMA Signal]"),
        },
    }

    manager = AlertManager.create_default(config)

    print(f"\nConfigured handlers: {list(manager.handlers.keys())}")
    print("\nSending test alert to all handlers...")

    message = create_test_message("long")
    results = await manager.send_alert(message)

    print("\nResults:")
    for handler_name, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {handler_name}: {success}")

    # Test history
    history = manager.get_history(limit=5)
    print(f"\nAlert history: {len(history)} messages")


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("EMA Cloud Scanner - Alert System Tests")
    print("=" * 60)

    # Test individual handlers
    await test_console()
    await test_desktop()
    await test_telegram()
    await test_discord()
    await test_email()

    # Test manager
    await test_alert_manager()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
