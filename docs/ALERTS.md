# Alert System

Complete guide to configuring and using the EMA Cloud Scanner alert system.

## Overview

The scanner supports multiple alert channels for real-time signal notifications:

- **Console** - Terminal output with color coding (always enabled)
- **Desktop** - Native OS notifications with sound
- **Telegram** - Bot messages to your phone or group
- **Discord** - Webhook messages to Discord channels
- **Email** - SMTP notifications via Gmail, Outlook, or custom servers

## Quick Setup

### Console Alerts (Default)

Console alerts are enabled by default and require no configuration:

```bash
# Signals appear in terminal with color coding
uv run python run.py
```

### Desktop Notifications

Requires the `plyer` library:

```bash
# Install desktop notification support
uv pip install -e "packages/ema_cloud_lib[notifications]"

# Run scanner (desktop notifications enabled by default)
uv run python run.py
```

### Telegram Alerts

#### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` and follow the prompts
3. Copy the bot token (looks like `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### 2. Get Your Chat ID

**For personal messages:**

1. Start a conversation with your bot
2. Send any message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Look for `"chat":{"id":123456789}` in the response

**For group messages:**

1. Add your bot to a Telegram group
2. Send a message in the group
3. Visit the same URL as above
4. Look for the chat ID (negative number for groups)

#### 3. Configure the Scanner

**Option A: Environment Variables**

```bash
export EMA_TELEGRAM_ENABLED=true
export EMA_TELEGRAM_BOT_TOKEN="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
export EMA_TELEGRAM_CHAT_ID="123456789"

uv run python run.py
```

**Option B: Configuration File**

```json
{
  "alerts": {
    "telegram_enabled": true,
    "telegram_bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "telegram_chat_id": "123456789"
  }
}
```

```bash
uv run python run.py --config config.json
```

**Option C: Python API**

```python
from ema_cloud_lib import ScannerConfig

config = ScannerConfig()
config.alerts.telegram_enabled = True
config.alerts.telegram_bot_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
config.alerts.telegram_chat_id = "123456789"

scanner = EMACloudScanner(config)
```

### Discord Alerts

#### 1. Create a Discord Webhook

1. Open Discord and go to your server
2. Right-click the channel → **Edit Channel**
3. Go to **Integrations** → **Webhooks**
4. Click **New Webhook** or **Create Webhook**
5. Copy the webhook URL (looks like `https://discord.com/api/webhooks/...`)

#### 2. Configure the Scanner

**Option A: Environment Variables**

```bash
export EMA_DISCORD_ENABLED=true
export EMA_DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."

uv run python run.py
```

**Option B: Configuration File**

```json
{
  "alerts": {
    "discord_enabled": true,
    "discord_webhook_url": "https://discord.com/api/webhooks/..."
  }
}
```

**Option C: Python API**

```python
from ema_cloud_lib import ScannerConfig

config = ScannerConfig()
config.alerts.discord_enabled = True
config.alerts.discord_webhook_url = "https://discord.com/api/webhooks/..."

scanner = EMACloudScanner(config)
```

### Email Alerts

#### Option A: Gmail

**1. Enable 2-Factor Authentication**

1. Go to Google Account settings
2. Security → 2-Step Verification → Enable

**2. Generate App Password**

1. Google Account → Security → App passwords
2. Select app: Mail, Select device: Other (Custom name)
3. Enter "EMA Cloud Scanner" → Generate
4. Copy the 16-character password

**3. Configure the Scanner**

**Environment Variables:**

```bash
export EMA_EMAIL_ENABLED=true
export EMA_EMAIL_SMTP_SERVER="smtp.gmail.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USERNAME="your-email@gmail.com"
export EMA_EMAIL_PASSWORD="your-app-password"
export EMA_EMAIL_FROM_ADDRESS="your-email@gmail.com"
export EMA_EMAIL_RECIPIENTS="recipient1@example.com,recipient2@example.com"

uv run python run.py
```

**Configuration File:**

```json
{
  "alerts": {
    "email_enabled": true,
    "email_smtp_server": "smtp.gmail.com",
    "email_smtp_port": 587,
    "email_use_tls": true,
    "email_username": "your-email@gmail.com",
    "email_password": "your-app-password",
    "email_from_address": "your-email@gmail.com",
    "email_from_name": "EMA Cloud Scanner",
    "email_recipients": ["recipient1@example.com", "recipient2@example.com"],
    "email_subject_prefix": "[EMA Signal]"
  }
}
```

**Python API:**

```python
from ema_cloud_lib import ScannerConfig

config = ScannerConfig()
config.alerts.email_enabled = True
config.alerts.email_smtp_server = "smtp.gmail.com"
config.alerts.email_smtp_port = 587
config.alerts.email_use_tls = True
config.alerts.email_username = "your-email@gmail.com"
config.alerts.email_password = "your-app-password"
config.alerts.email_from_address = "your-email@gmail.com"
config.alerts.email_recipients = ["recipient1@example.com"]

scanner = EMACloudScanner(config)
```

#### Option B: Outlook/Office 365

**Configuration:**

```bash
export EMA_EMAIL_ENABLED=true
export EMA_EMAIL_SMTP_SERVER="smtp.office365.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USERNAME="your-email@outlook.com"
export EMA_EMAIL_PASSWORD="your-password"
export EMA_EMAIL_FROM_ADDRESS="your-email@outlook.com"
export EMA_EMAIL_RECIPIENTS="recipient@example.com"

uv run python run.py
```

#### Option C: Custom SMTP Server

**With TLS (Port 587):**

```bash
export EMA_EMAIL_ENABLED=true
export EMA_EMAIL_SMTP_SERVER="smtp.yourserver.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USERNAME="user@yourserver.com"
export EMA_EMAIL_PASSWORD="your-password"
export EMA_EMAIL_FROM_ADDRESS="user@yourserver.com"
export EMA_EMAIL_RECIPIENTS="recipient@example.com"
```

**With SSL (Port 465):**

```bash
export EMA_EMAIL_ENABLED=true
export EMA_EMAIL_SMTP_SERVER="smtp.yourserver.com"
export EMA_EMAIL_SMTP_PORT=465
export EMA_EMAIL_USE_SSL=true
export EMA_EMAIL_USE_TLS=false
export EMA_EMAIL_USERNAME="user@yourserver.com"
export EMA_EMAIL_PASSWORD="your-password"
export EMA_EMAIL_FROM_ADDRESS="user@yourserver.com"
export EMA_EMAIL_RECIPIENTS="recipient@example.com"
```

#### Common SMTP Providers

| Provider | SMTP Server | Port | Security |
|----------|-------------|------|----------|
| Gmail | `smtp.gmail.com` | 587 | TLS |
| Outlook/Office365 | `smtp.office365.com` | 587 | TLS |
| Yahoo | `smtp.mail.yahoo.com` | 587 | TLS |
| iCloud | `smtp.mail.me.com` | 587 | TLS |
| SendGrid | `smtp.sendgrid.net` | 587 | TLS |
| Mailgun | `smtp.mailgun.org` | 587 | TLS |
| AWS SES | `email-smtp.region.amazonaws.com` | 587 | TLS |

## Alert Configuration Reference

### AlertConfig Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `console_enabled` | `bool` | `True` | Enable console alerts |
| `console_colors` | `bool` | `True` | Use colors in console |
| `desktop_enabled` | `bool` | `True` | Enable desktop notifications |
| `desktop_sound` | `bool` | `True` | Play sound with notifications |
| `telegram_enabled` | `bool` | `False` | Enable Telegram alerts |
| `telegram_bot_token` | `str` | `None` | Telegram bot token |
| `telegram_chat_id` | `str` | `None` | Telegram chat ID |
| `discord_enabled` | `bool` | `False` | Enable Discord alerts |
| `discord_webhook_url` | `str` | `None` | Discord webhook URL |
| `email_enabled` | `bool` | `False` | Enable email alerts |
| `email_smtp_server` | `str` | `None` | SMTP server address |
| `email_smtp_port` | `int` | `587` | SMTP port (587=TLS, 465=SSL) |
| `email_use_tls` | `bool` | `True` | Use TLS encryption |
| `email_use_ssl` | `bool` | `False` | Use SSL encryption |
| `email_username` | `str` | `None` | SMTP username |
| `email_password` | `str` | `None` | SMTP password |
| `email_from_address` | `str` | `None` | From email address |
| `email_from_name` | `str` | `"EMA Cloud Scanner"` | From name |
| `email_recipients` | `list[str]` | `[]` | Recipient email addresses |
| `email_subject_prefix` | `str` | `"[EMA Signal]"` | Email subject prefix |

### Environment Variable Mapping

All alert settings can be configured via environment variables:

```bash
# Console
export EMA_CONSOLE_ENABLED=true
export EMA_CONSOLE_COLORS=true

# Desktop
export EMA_DESKTOP_ENABLED=true
export EMA_DESKTOP_SOUND=true

# Telegram
export EMA_TELEGRAM_ENABLED=true
export EMA_TELEGRAM_BOT_TOKEN="your_token"
export EMA_TELEGRAM_CHAT_ID="your_chat_id"

# Discord
export EMA_DISCORD_ENABLED=true
export EMA_DISCORD_WEBHOOK_URL="your_webhook_url"

# Email
export EMA_EMAIL_ENABLED=true
export EMA_EMAIL_SMTP_SERVER="smtp.gmail.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USE_SSL=false
export EMA_EMAIL_USERNAME="your-email@gmail.com"
export EMA_EMAIL_PASSWORD="your-app-password"
export EMA_EMAIL_FROM_ADDRESS="your-email@gmail.com"
export EMA_EMAIL_FROM_NAME="EMA Cloud Scanner"
export EMA_EMAIL_RECIPIENTS="recipient1@example.com,recipient2@example.com"
export EMA_EMAIL_SUBJECT_PREFIX="[EMA Signal]"
```

## Alert Message Format

### Console Format

```
🟢 ↑ XLK: cloud_flip @ $180.45 [STRONG]
```

### Desktop Notification

**Title:** 🟢 XLK Signal
**Body:**

```
cloud_flip
$180.45 | STRONG
```

### Telegram Format

```
🟢 ↗️ *XLK* Signal

*Type:* Cloud Flip
*Direction:* LONG
*Price:* $180.45
*Strength:* STRONG
*Time:* 14:30:25

*Details:*
RSI: 62.5
ADX: 28.3
Volume: 1.8x
Stop: $178.20
Target: $184.50
R/R: 2.15
```

### Discord Format

**Embed:**

- **Title:** 🟢 ↗️ XLK Signal
- **Description:** Cloud Flip
- **Color:** Green (long) / Red (short)
- **Fields:**
  - Type, Direction, Price, Strength
  - RSI, ADX, Volume
  - Stop, Target, R/R Ratio
- **Timestamp:** Signal generation time

### Email Format

**HTML Email:**

- Color-coded header (green/red)
- Formatted table with signal details
- Additional details section if available
- Professional styling with EMA Cloud Scanner branding

**Plain Text Email:**

```
↑ XLK Signal
==================================================

Signal Type: Cloud Flip
Direction: LONG
Price: $180.45
Strength: STRONG
Time: 2026-01-12 14:30:25

Additional Details:
--------------------------------------------------
RSI: 62.5
ADX: 28.3
Volume Ratio: 1.80x
Stop Loss: $178.20
Target: $184.50
Risk/Reward: 2.15

==================================================
EMA Cloud Scanner - Automated Trading Signal Notification
```

## Advanced Usage

### Multiple Alert Channels

Enable all channels simultaneously:

```python
config = ScannerConfig()

# Console
config.alerts.console_enabled = True
config.alerts.console_colors = True

# Desktop
config.alerts.desktop_enabled = True
config.alerts.desktop_sound = True

# Telegram
config.alerts.telegram_enabled = True
config.alerts.telegram_bot_token = "..."
config.alerts.telegram_chat_id = "..."

# Discord
config.alerts.discord_enabled = True
config.alerts.discord_webhook_url = "..."

# Email
config.alerts.email_enabled = True
config.alerts.email_smtp_server = "smtp.gmail.com"
config.alerts.email_smtp_port = 587
config.alerts.email_use_tls = True
config.alerts.email_username = "your-email@gmail.com"
config.alerts.email_password = "your-app-password"
config.alerts.email_from_address = "your-email@gmail.com"
config.alerts.email_recipients = ["recipient@example.com"]

scanner = EMACloudScanner(config)
```

### Custom Alert Handlers

Create your own alert handler:

```python
from ema_cloud_lib.alerts import BaseAlertHandler, AlertMessage

class CustomAlertHandler(BaseAlertHandler):
    @property
    def name(self) -> str:
        return "Custom"

    async def send_alert(self, message: AlertMessage) -> bool:
        # Your custom logic here
        print(f"Custom alert: {message.symbol}")
        return True

# Add to scanner
from ema_cloud_lib import EMACloudScanner

scanner = EMACloudScanner(config)
scanner.alert_manager.add_handler(CustomAlertHandler())
```

### Programmatic Alert Management

```python
# Disable specific handler
scanner.alert_manager.disable_handler("Desktop")

# Enable specific handler
scanner.alert_manager.enable_handler("Telegram")

# Remove handler
scanner.alert_manager.remove_handler("Discord")

# Get alert history
recent_alerts = scanner.alert_manager.get_history(limit=10)
```

## Troubleshooting

### Telegram Issues

**Bot not responding:**

- Verify bot token is correct
- Ensure you've started a conversation with the bot
- Check that bot hasn't been blocked

**Can't get chat ID:**

```bash
# Send a message to your bot, then run:
curl https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

**Group messages not working:**

- Add bot to group as admin
- Send a message in the group
- Use negative chat ID for groups

### Discord Issues

**Webhook not working:**

- Verify webhook URL is complete
- Check webhook hasn't been deleted
- Ensure channel permissions allow webhooks

**Messages not appearing:**

- Check webhook URL starts with `https://discord.com/api/webhooks/`
- Verify channel is correct
- Check Discord server status

### Desktop Notifications

**No notifications appearing:**

**macOS:**

```bash
# Check if notifications are allowed
# System Preferences → Notifications → Allow notifications
```

**Linux:**

```bash
# Install notification daemon
sudo apt-get install libnotify-bin  # Debian/Ubuntu
sudo pacman -S libnotify  # Arch
```

**Windows:**

- Notifications should work by default
- Check Windows notification settings

### Email Issues

**Authentication failures:**

**Gmail - "Username and Password not accepted":**

1. Enable 2-Factor Authentication
2. Generate App Password (not regular password)
3. Use app password in configuration

**Gmail - "Less secure app access":**

- Gmail no longer supports this
- Must use App Passwords with 2FA

**Outlook - Authentication errors:**

```bash
# Verify correct SMTP settings
export EMA_EMAIL_SMTP_SERVER="smtp.office365.com"
export EMA_EMAIL_SMTP_PORT=587
export EMA_EMAIL_USE_TLS=true
```

**Connection timeouts:**

```python
# Check firewall/network settings
# Port 587 (TLS) or 465 (SSL) must be open
# Try ping smtp server first
ping smtp.gmail.com
```

**SSL/TLS errors:**

```bash
# For TLS (port 587):
export EMA_EMAIL_USE_TLS=true
export EMA_EMAIL_USE_SSL=false

# For SSL (port 465):
export EMA_EMAIL_USE_TLS=false
export EMA_EMAIL_USE_SSL=true
```

**Emails not arriving:**

1. Check spam/junk folder
2. Verify recipient addresses are correct
3. Check SMTP server allows sending
4. Review SMTP server logs

**"From address must match authenticated user":**

```bash
# Set from_address to match username
export EMA_EMAIL_FROM_ADDRESS="${EMA_EMAIL_USERNAME}"
```

### General Issues

**aiohttp import errors:**

```bash
# Install aiohttp (required for Telegram and Discord)
pip install aiohttp
```

**Alerts not sending:**

1. Check handler is enabled: `scanner.alert_manager.handlers`
2. Verify configuration is loaded
3. Check logs for error messages
4. Test with simple configuration first

## Security Best Practices

### Protecting API Credentials

**Never commit credentials to Git:**

```bash
# Add to .gitignore
echo "config.json" >> .gitignore
echo ".env" >> .gitignore
```

**Use environment variables:**

```bash
# Set in shell profile (~/.bashrc or ~/.zshrc)
export EMA_TELEGRAM_BOT_TOKEN="your_token"
export EMA_TELEGRAM_CHAT_ID="your_chat_id"
```

**Use .env files:**

```bash
# Create .env file (not committed)
cat > .env << EOF
EMA_TELEGRAM_BOT_TOKEN=your_token
EMA_TELEGRAM_CHAT_ID=your_chat_id
EMA_DISCORD_WEBHOOK_URL=your_webhook
EOF

# Load with python-dotenv
pip install python-dotenv
```

**For production:**

- Use secrets management (AWS Secrets Manager, Azure Key Vault)
- Rotate tokens regularly
- Use separate bots/webhooks for dev/prod

## Performance Considerations

### Rate Limiting

**Telegram:**

- 30 messages per second to individual users
- 20 messages per minute to groups
- Scanner respects these limits automatically

**Discord:**

- 30 requests per minute per webhook
- 5 requests per second burst
- Scanner implements backoff for rate limits

### Network Latency

Alerts are sent asynchronously and won't block scanning:

```python
# Alerts sent in parallel, scanner continues immediately
await scanner.scan_etfs()  # This doesn't wait for alerts
```

### Error Handling

Alert failures don't stop the scanner:

```python
# If Telegram fails, other alerts still send
# Scanner continues scanning regardless of alert status
```

## Examples

### Production Configuration

```json
{
  "alerts": {
    "console_enabled": false,
    "desktop_enabled": false,
    "telegram_enabled": true,
    "telegram_bot_token": "${TELEGRAM_BOT_TOKEN}",
    "telegram_chat_id": "${TELEGRAM_CHAT_ID}",
    "discord_enabled": true,
    "discord_webhook_url": "${DISCORD_WEBHOOK_URL}"
  }
}
```

### Development Configuration

```json
{
  "alerts": {
    "console_enabled": true,
    "console_colors": true,
    "desktop_enabled": true,
    "desktop_sound": false,
    "telegram_enabled": false,
    "discord_enabled": false
  }
}
```

### Testing Configuration

```python
from ema_cloud_lib import ScannerConfig

config = ScannerConfig()

# Console only for testing
config.alerts.console_enabled = True
config.alerts.desktop_enabled = False
config.alerts.telegram_enabled = False
config.alerts.discord_enabled = False

scanner = EMACloudScanner(config)
```

## Further Reading

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Discord Webhook Guide](https://support.discord.com/hc/en-us/articles/228383668)
- [Configuration Management](CONFIGURATION_MANAGEMENT.md)
- [Security Guide](SECURITY.md)
