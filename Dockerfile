# EMA Cloud Sector Scanner
# Multi-stage build: builder installs all deps; runtime carries only the venv.

# ── builder ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app

# Copy manifests first for dependency-layer caching
COPY pyproject.toml uv.lock ./
COPY packages/ema_cloud_lib/pyproject.toml packages/ema_cloud_lib/
COPY packages/ema_cloud_cli/pyproject.toml packages/ema_cloud_cli/

# Stub src/ so setuptools can resolve editable metadata before real source arrives.
# Editable installs write a .pth pointing to src/; --no-editable below replaces them.
RUN mkdir -p packages/ema_cloud_lib/src/ema_cloud_lib \
             packages/ema_cloud_cli/src/ema_cloud_cli \
    && touch packages/ema_cloud_lib/src/ema_cloud_lib/__init__.py \
             packages/ema_cloud_cli/src/ema_cloud_cli/__init__.py

# Install all dependencies (cached layer — only invalidated when manifests change)
# aiohttp is required for Telegram and Discord alert handlers
RUN uv sync --frozen --no-dev --extra all

# Copy real source and reinstall workspace packages as non-editable wheels.
# Runtime stage copies only .venv, so source must be baked in, not referenced via .pth.
COPY packages/ packages/
RUN uv sync --frozen --no-dev --extra all --no-editable

# ── runtime ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Copy only the virtualenv — no uv binary, no source, no build artifacts
COPY --from=builder /app/.venv /app/.venv

# Create a non-root user for security
RUN useradd -m -u 1000 scanner
USER scanner

ENV PATH="/app/.venv/bin:$PATH" \
    EMA_SCANNER_NO_DASHBOARD=1

ENTRYPOINT ["ema-scanner"]
CMD ["--no-dashboard"]
