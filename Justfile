# EMA Cloud Sector Scanner - Justfile
# Run `just` to see available commands

set dotenv-load := true

# Default: list available recipes
default:
    @just --list

# ── Development ──────────────────────────────────────────────────────────────

# Run scanner once (no loop)
once *args:
    uv run python run.py --once {{ args }}

# Run scanner continuously
run *args:
    uv run python run.py {{ args }}

# Run with swing style
swing *args:
    uv run python run.py --style swing {{ args }}

# Run with intraday style
intraday *args:
    uv run python run.py --style intraday {{ args }}

# Run with scalping style
scalp *args:
    uv run python run.py --style scalping {{ args }}

# Run outside market hours (for testing)
dev *args:
    uv run python run.py --all-hours --once {{ args }}

# ── Testing ───────────────────────────────────────────────────────────────────

# Run all tests
test *args:
    uv run --extra dev pytest {{ args }}

# Run tests verbosely
test-v *args:
    uv run --extra dev pytest -v {{ args }}

# Run a specific test file
test-file file *args:
    uv run --extra dev pytest {{ file }} -v {{ args }}

# Run only unit tests (excludes integration and slow markers) — used by CI
test-unit *args:
    uv run --extra dev pytest -m "not integration and not slow" {{ args }}

# Run only integration tests
test-integration *args:
    uv run --extra dev pytest -m "integration" {{ args }}

# Test alert handlers
test-alerts:
    uv run python scripts/test_alerts.py

# ── Code Quality ──────────────────────────────────────────────────────────────

# Lint all packages and tests
lint:
    uv run --extra dev ruff check packages/ tests/

# Auto-fix lint issues
fix:
    uv run --extra dev ruff check --fix packages/ tests/

# Format code
fmt:
    uv run --extra dev ruff format packages/ tests/

# Check formatting without modifying files (used in CI)
fmt-check:
    uv run --extra dev ruff format --check packages/ tests/

# Run lint + format
check: lint fmt

# Type check
types:
    uv run --extra dev mypy packages/

# Run all quality checks
qa: fmt lint types

# ── Installation ──────────────────────────────────────────────────────────────

# Install both packages in editable mode
install:
    uv pip install -e packages/ema_cloud_lib
    uv pip install -e packages/ema_cloud_cli

# Install with all optional providers
install-all:
    uv pip install -e "packages/ema_cloud_lib[all]"
    uv pip install -e packages/ema_cloud_cli

# Install dev tools
install-dev:
    uv pip install -e "packages/ema_cloud_lib[dev]"
    uv pip install -e packages/ema_cloud_cli

# Install pre-commit hooks
hooks:
    uv run --extra dev pre-commit install

# ── Docker ────────────────────────────────────────────────────────────────────

# Build Docker image
docker-build:
    docker compose build

# Start scanner container (detached)
docker-up:
    docker compose up -d

# Stop scanner container
docker-down:
    docker compose down

# Restart scanner container
docker-restart:
    docker compose restart scanner

# Tail live container logs
docker-logs:
    docker compose logs -f scanner

# Run scanner once inside Docker (for testing)
docker-once:
    docker compose run --rm scanner --no-dashboard --once

# Open a shell inside the scanner image
docker-shell:
    docker compose run --rm --entrypoint /bin/bash scanner

# Remove container, image, and named volumes (full reset)
docker-clean:
    docker compose down -v --rmi local

# ── Utilities ─────────────────────────────────────────────────────────────────

# Show scanner help
help:
    uv run python run.py --help

# Clear holdings cache
clear-cache:
    rm -rf holdings_cache/*
    @echo "Holdings cache cleared."
