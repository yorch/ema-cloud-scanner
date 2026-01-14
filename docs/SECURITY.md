# Security Guide

Best practices for API key management, secrets handling, and secure deployment of the EMA Cloud Scanner.

## Table of Contents

- [API Key Management](#api-key-management)
- [Environment Variables](#environment-variables)
- [Secrets Storage](#secrets-storage)
- [Configuration Security](#configuration-security)
- [Production Deployment](#production-deployment)
- [Network Security](#network-security)

---

## API Key Management

### Supported Data Providers

| Provider      | Authentication Required | Free Tier | API Keys Needed      |
| ------------- | ----------------------- | --------- | -------------------- |
| Yahoo Finance | ❌ No                    | ✅ Yes     | None                 |
| Alpaca        | ✅ Yes                   | ✅ Yes     | API Key + Secret Key |
| Polygon.io    | ✅ Yes                   | ✅ Yes     | API Key              |

### Never Hard-Code API Keys

**❌ WRONG - Never do this:**

```python
# DON'T: Hard-coded keys in source code
config = ScannerConfig(
    data_provider=DataProviderConfig(
        primary="alpaca",
        api_keys={
            "ALPACA_API_KEY": "PK1234567890ABCDEF",  # ❌ EXPOSED IN CODE
            "ALPACA_SECRET_KEY": "secretkey123"      # ❌ SECURITY RISK
        }
    )
)
```

**✅ CORRECT - Use environment variables:**

```python
import os

# DO: Load from environment variables
config = ScannerConfig(
    data_provider=DataProviderConfig(
        primary="alpaca",
        api_keys={
            "ALPACA_API_KEY": os.getenv("ALPACA_API_KEY"),
            "ALPACA_SECRET_KEY": os.getenv("ALPACA_SECRET_KEY"),
        }
    )
)
```

---

## Environment Variables

### Setting API Keys

**Linux/macOS:**

```bash
# Set temporarily (current session only)
export ALPACA_API_KEY="your_api_key_here"
export ALPACA_SECRET_KEY="your_secret_key_here"
export POLYGON_API_KEY="your_polygon_key_here"

# Set permanently (add to ~/.bashrc or ~/.zshrc)
echo 'export ALPACA_API_KEY="your_api_key_here"' >> ~/.bashrc
echo 'export ALPACA_SECRET_KEY="your_secret_key_here"' >> ~/.bashrc
source ~/.bashrc
```

**Windows (PowerShell):**

```powershell
# Set temporarily (current session only)
$env:ALPACA_API_KEY = "your_api_key_here"
$env:ALPACA_SECRET_KEY = "your_secret_key_here"

# Set permanently (system-wide)
[System.Environment]::SetEnvironmentVariable('ALPACA_API_KEY', 'your_api_key_here', 'User')
[System.Environment]::SetEnvironmentVariable('ALPACA_SECRET_KEY', 'your_secret_key_here', 'User')
```

**Windows (Command Prompt):**

```cmd
REM Set temporarily
set ALPACA_API_KEY=your_api_key_here
set ALPACA_SECRET_KEY=your_secret_key_here

REM Set permanently
setx ALPACA_API_KEY "your_api_key_here"
setx ALPACA_SECRET_KEY "your_secret_key_here"
```

### Verifying Environment Variables

```bash
# Check if variables are set
echo $ALPACA_API_KEY
echo $ALPACA_SECRET_KEY
echo $POLYGON_API_KEY

# List all EMA-related environment variables
env | grep -E "(ALPACA|POLYGON|EMA_)"
```

---

## Secrets Storage

### .env Files (Local Development)

Create a `.env` file in your config directory for local development:

```bash
# .env file (DO NOT COMMIT TO GIT)
ALPACA_API_KEY=PK1234567890ABCDEF
ALPACA_SECRET_KEY=sk_live_1234567890abcdef
POLYGON_API_KEY=1234567890abcdef

# CLI settings
EMA_CLI_LOG_LEVEL=INFO
EMA_CLI_CONFIG_DIR=~/.config/ema-cloud-scanner
```

**Load .env file with python-dotenv:**

```python
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Access variables
api_key = os.getenv("ALPACA_API_KEY")
```

**⚠️ CRITICAL: Add .env to .gitignore**

```bash
# .gitignore
.env
.env.*
*.env
config/*_keys.json
secrets/
```

### .env.example Template

Create a template file that CAN be committed to git:

```bash
# .env.example - Template for environment variables
# Copy this to .env and fill in your actual keys

# Alpaca API Keys (https://alpaca.markets)
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here

# Polygon.io API Key (https://polygon.io)
POLYGON_API_KEY=your_polygon_key_here

# Optional: Telegram Bot (for alerts)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Optional: Discord Webhook (for alerts)
DISCORD_WEBHOOK_URL=your_webhook_url_here

# CLI Configuration
EMA_CLI_LOG_LEVEL=INFO
EMA_CLI_CONFIG_DIR=~/.config/ema-cloud-scanner
```

### Cloud Secrets Management

For production deployments, use cloud-native secrets management:

#### AWS Secrets Manager

```python
import boto3
import json

def get_api_keys_from_aws():
    """Retrieve API keys from AWS Secrets Manager"""
    client = boto3.client('secretsmanager', region_name='us-east-1')

    response = client.get_secret_value(SecretId='ema-scanner/api-keys')
    secrets = json.loads(response['SecretString'])

    return {
        "ALPACA_API_KEY": secrets['alpaca_api_key'],
        "ALPACA_SECRET_KEY": secrets['alpaca_secret_key'],
        "POLYGON_API_KEY": secrets['polygon_api_key'],
    }

# Use in configuration
api_keys = get_api_keys_from_aws()
config = ScannerConfig(
    data_provider=DataProviderConfig(
        primary="alpaca",
        api_keys=api_keys
    )
)
```

#### Azure Key Vault

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_api_keys_from_azure():
    """Retrieve API keys from Azure Key Vault"""
    credential = DefaultAzureCredential()
    vault_url = "https://ema-scanner-keys.vault.azure.net/"
    client = SecretClient(vault_url=vault_url, credential=credential)

    return {
        "ALPACA_API_KEY": client.get_secret("alpaca-api-key").value,
        "ALPACA_SECRET_KEY": client.get_secret("alpaca-secret-key").value,
        "POLYGON_API_KEY": client.get_secret("polygon-api-key").value,
    }
```

#### Google Cloud Secret Manager

```python
from google.cloud import secretmanager

def get_api_keys_from_gcp(project_id="ema-scanner-project"):
    """Retrieve API keys from Google Cloud Secret Manager"""
    client = secretmanager.SecretManagerServiceClient()

    def get_secret(secret_id):
        name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode('UTF-8')

    return {
        "ALPACA_API_KEY": get_secret("alpaca-api-key"),
        "ALPACA_SECRET_KEY": get_secret("alpaca-secret-key"),
        "POLYGON_API_KEY": get_secret("polygon-api-key"),
    }
```

---

## Configuration Security

### Config File Security

**Default config location is secure** (user-only read/write permissions). See [CLI_SETTINGS.md - Default Platform Paths](CLI_SETTINGS.md#default-platform-paths) for complete path information across all platforms.

Default permissions by platform:

| Platform | Permissions        |
| -------- | ------------------ |
| Linux    | `0600` (rw-------) |
| macOS    | User-only          |
| Windows  | User-only          |

### Verify File Permissions (Linux/macOS)

```bash
# Check permissions on config file
ls -la ~/.config/ema-cloud-scanner/config.json

# Should show: -rw-------  (600)
# If not, fix permissions:
chmod 600 ~/.config/ema-cloud-scanner/config.json

# Check directory permissions
ls -ld ~/.config/ema-cloud-scanner

# Should show: drwx------ (700)
# If not, fix permissions:
chmod 700 ~/.config/ema-cloud-scanner
```

### Exclude API Keys from Config Files

**Never store API keys in config.json:**

```json
{
  "trading_style": "swing",
  "data_provider": {
    "primary": "alpaca",
    "api_keys": {}  // ✅ Keep empty - use environment variables
  }
}
```

### Separate Credentials File

If you must use a file for credentials, keep it separate and restrict permissions:

```bash
# Create secure credentials file
touch ~/.ema-scanner/credentials.json
chmod 600 ~/.ema-scanner/credentials.json

# credentials.json (separate from config.json)
{
  "alpaca_api_key": "your_key_here",
  "alpaca_secret_key": "your_secret_here"
}

# Load in code
import json
from pathlib import Path

creds_file = Path.home() / ".ema-scanner" / "credentials.json"
with open(creds_file) as f:
    credentials = json.load(f)
```

**Add to .gitignore:**

```bash
# .gitignore
credentials.json
*_credentials.json
secrets/
```

---

## Production Deployment

### Docker Deployment

Use Docker secrets for secure credential management:

```dockerfile
# Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install uv && uv pip install -e .

# Copy application
COPY packages/ ./packages/
COPY run.py .

# Run as non-root user
RUN useradd -m scanner
USER scanner

# API keys passed via environment variables
CMD ["python", "run.py"]
```

**docker-compose.yml with secrets:**

```yaml
version: '3.8'

services:
  ema-scanner:
    build: .
    environment:
      - ALPACA_API_KEY_FILE=/run/secrets/alpaca_api_key
      - ALPACA_SECRET_KEY_FILE=/run/secrets/alpaca_secret_key
    secrets:
      - alpaca_api_key
      - alpaca_secret_key
    volumes:
      - scanner-data:/app/data
    restart: unless-stopped

secrets:
  alpaca_api_key:
    file: ./secrets/alpaca_api_key.txt
  alpaca_secret_key:
    file: ./secrets/alpaca_secret_key.txt

volumes:
  scanner-data:
```

**Read secrets in application:**

```python
import os

def get_secret(secret_name: str) -> str:
    """Read secret from file (Docker secrets pattern)"""
    secret_file = os.getenv(f"{secret_name}_FILE")
    if secret_file:
        with open(secret_file) as f:
            return f.read().strip()
    return os.getenv(secret_name, "")

# Usage
api_key = get_secret("ALPACA_API_KEY")
secret_key = get_secret("ALPACA_SECRET_KEY")
```

### Kubernetes Deployment

Use Kubernetes secrets:

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ema-scanner-secrets
type: Opaque
stringData:
  alpaca-api-key: "your_api_key_here"
  alpaca-secret-key: "your_secret_key_here"
  polygon-api-key: "your_polygon_key_here"
```

**Apply secret:**

```bash
kubectl apply -f secret.yaml
```

**Reference in deployment:**

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ema-scanner
spec:
  template:
    spec:
      containers:
      - name: scanner
        image: ema-scanner:latest
        env:
        - name: ALPACA_API_KEY
          valueFrom:
            secretKeyRef:
              name: ema-scanner-secrets
              key: alpaca-api-key
        - name: ALPACA_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: ema-scanner-secrets
              key: alpaca-secret-key
```

### CI/CD Security

**GitHub Actions:**

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Run tests
        env:
          ALPACA_API_KEY: ${{ secrets.ALPACA_API_KEY }}
          ALPACA_SECRET_KEY: ${{ secrets.ALPACA_SECRET_KEY }}
        run: |
          uv pip install -e "packages/ema_cloud_lib[dev]"
          pytest
```

**Set secrets in GitHub:**

1. Go to repository Settings → Secrets and variables → Actions
2. Add repository secrets:
   - `ALPACA_API_KEY`
   - `ALPACA_SECRET_KEY`
   - `POLYGON_API_KEY`

---

## Network Security

### API Rate Limiting

Implement rate limiting to avoid account suspension:

```python
from datetime import datetime, timedelta
from collections import deque

class RateLimiter:
    """Rate limiter for API calls"""

    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window  # seconds
        self.calls = deque()

    async def acquire(self):
        """Wait if rate limit would be exceeded"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=self.time_window)

        # Remove old calls
        while self.calls and self.calls[0] < cutoff:
            self.calls.popleft()

        # Check if limit reached
        if len(self.calls) >= self.max_calls:
            sleep_time = (self.calls[0] - cutoff).total_seconds()
            await asyncio.sleep(sleep_time)

        # Record this call
        self.calls.append(now)

# Usage with Alpaca (200 requests per minute)
rate_limiter = RateLimiter(max_calls=200, time_window=60)

async def fetch_data(symbol):
    await rate_limiter.acquire()
    # Make API call
    return await provider.fetch_bars(symbol)
```

### HTTPS-Only Connections

All API connections use HTTPS by default:

```python
# Data providers use secure connections
ALPACA_BASE_URL = "https://data.alpaca.markets"  # ✅ HTTPS
POLYGON_BASE_URL = "https://api.polygon.io"      # ✅ HTTPS
```

### Network Timeouts

Configure appropriate timeouts to prevent hanging connections:

```python
config = ScannerConfig(
    data_provider=DataProviderConfig(
        timeout_seconds=30,  # Connection timeout
        max_retries=3,       # Retry failed requests
    )
)
```

---

## Best Practices Checklist

### Development

- [ ] Use `.env` file for local API keys
- [ ] Add `.env` to `.gitignore`
- [ ] Create `.env.example` template (without actual keys)
- [ ] Never commit API keys to version control
- [ ] Use environment variables, not hard-coded values
- [ ] Verify file permissions on config directory (700) and files (600)

### Production

- [ ] Use cloud secrets manager (AWS/Azure/GCP)
- [ ] Rotate API keys regularly (every 90 days)
- [ ] Use separate keys for dev/staging/production
- [ ] Enable audit logging for secret access
- [ ] Monitor API key usage for suspicious activity
- [ ] Implement rate limiting to stay within provider limits
- [ ] Use HTTPS for all API connections
- [ ] Set appropriate connection timeouts

### Code Review

- [ ] No hard-coded credentials in source code
- [ ] No API keys in configuration files committed to git
- [ ] Secrets loaded from environment or secrets manager
- [ ] Error messages don't leak sensitive information
- [ ] Logging doesn't expose API keys or secrets

---

## Incident Response

### If API Keys Are Exposed

**Immediate Actions:**

1. **Revoke compromised keys** immediately via provider dashboard
2. **Generate new keys** and update in secure storage
3. **Review account activity** for unauthorized usage
4. **Rotate all related secrets** (assume lateral movement)
5. **Remove exposed keys** from git history if committed

**GitHub Key Removal:**

```bash
# Use BFG Repo-Cleaner to remove sensitive data
# https://rtyley.github.io/bfg-repo-cleaner/

# Remove API keys from history
bfg --replace-text passwords.txt

# Force push (coordinate with team)
git push --force
```

**Alpaca API Key Rotation:**

1. Log in to <https://alpaca.markets>
2. Navigate to API Keys section
3. Revoke old key
4. Generate new key pair
5. Update environment variables/secrets manager

**Polygon API Key Rotation:**

1. Log in to <https://polygon.io>
2. Dashboard → API Keys
3. Revoke compromised key
4. Generate new key
5. Update environment variables/secrets manager

---

## See Also

- [Configuration Management](CONFIGURATION_MANAGEMENT.md) - Config file handling
- [CLI Settings](CLI_SETTINGS.md) - Environment variables reference
- [Main README](../README.md) - Data provider setup
- [Project Guidelines](../AGENTS.md) - Development best practices
