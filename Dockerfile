# EMA Cloud Sector Scanner
# Multi-stage build: installs all data providers and alert dependencies

FROM python:3.12-slim AS base

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy workspace manifests first for layer caching
COPY pyproject.toml uv.lock ./
COPY packages/ema_cloud_lib/pyproject.toml packages/ema_cloud_lib/
COPY packages/ema_cloud_cli/pyproject.toml packages/ema_cloud_cli/

# Install all dependencies (all providers: yahoo, alpaca, polygon + notifications)
# aiohttp is required for Telegram and Discord alert handlers
RUN uv sync --frozen --no-dev --extra all

# Copy source code
COPY packages/ packages/

# Create a non-root user for security
RUN useradd -m -u 1000 scanner
USER scanner

# Logs go to stdout/stderr in container (console handler); no TUI
ENV EMA_SCANNER_NO_DASHBOARD=1

ENTRYPOINT ["uv", "run", "ema-scanner"]
CMD ["--no-dashboard"]
