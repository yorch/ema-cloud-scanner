# Utility Scripts

Helper scripts for testing and development.

## Alert Testing

### test_alerts.py

Test all alert handlers (console, desktop, Telegram, Discord, Email).

**Usage:**

```bash
# Test all handlers
python scripts/test_alerts.py

# With Telegram configuration
export EMA_TELEGRAM_BOT_TOKEN="your_token"
export EMA_TELEGRAM_CHAT_ID="your_chat_id"
python scripts/test_alerts.py

# With Discord configuration
export EMA_DISCORD_WEBHOOK_URL="your_webhook_url"
python scripts/test_alerts.py

# With Email configuration
export EMA_EMAIL_SMTP_SERVER="smtp.gmail.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USERNAME="your-email@gmail.com"
export EMA_EMAIL_PASSWORD="your-app-password"
export EMA_EMAIL_FROM_ADDRESS="your-email@gmail.com"
export EMA_EMAIL_RECIPIENTS="recipient@example.com"
python scripts/test_alerts.py

# With all alerts configured
export EMA_TELEGRAM_BOT_TOKEN="your_token"
export EMA_TELEGRAM_CHAT_ID="your_chat_id"
export EMA_DISCORD_WEBHOOK_URL="your_webhook_url"
export EMA_EMAIL_SMTP_SERVER="smtp.gmail.com"
export EMA_EMAIL_USERNAME="your-email@gmail.com"
export EMA_EMAIL_PASSWORD="your-app-password"
export EMA_EMAIL_RECIPIENTS="recipient@example.com"
python scripts/test_alerts.py
```

**What it tests:**
- Console alerts (colored output)
- Desktop notifications
- Telegram bot messages
- Discord webhook messages
- Email SMTP notifications
- AlertManager integration

**Requirements:**
- `aiohttp` for Telegram and Discord
- `plyer` for desktop notifications (optional)
- Standard library `smtplib` for email (included with Python)
