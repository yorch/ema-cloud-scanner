"""
Tests for CLI settings using pydantic-settings.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError

from ema_cloud_cli.settings import CLISettings, get_cli_settings, reset_cli_settings


def test_cli_settings_defaults():
    """Test CLI settings with default values."""
    settings = CLISettings()

    assert settings.config_filename == "config.json"
    assert settings.verbose is False
    assert settings.no_dashboard is False
    assert settings.all_hours is False
    assert settings.dashboard_refresh_rate == 1


def test_cli_settings_custom_values():
    """Test CLI settings with custom values."""
    settings = CLISettings(
        verbose=True,
        no_dashboard=True,
        all_hours=True,
        dashboard_refresh_rate=5,
    )

    assert settings.verbose is True
    assert settings.no_dashboard is True
    assert settings.all_hours is True
    assert settings.dashboard_refresh_rate == 5


def test_cli_settings_config_dir():
    """Test custom config directory."""
    custom_dir = Path("/tmp/ema_test")
    settings = CLISettings(config_dir=str(custom_dir))

    assert settings.config_dir == custom_dir.resolve()
    # Use resolve() to handle symlinks like /tmp -> /private/tmp on macOS
    assert settings.get_config_path() == (custom_dir / "config.json").resolve()


def test_cli_settings_from_env(monkeypatch):
    """Test loading CLI settings from environment variables."""
    monkeypatch.setenv("EMA_CLI_VERBOSE", "true")
    monkeypatch.setenv("EMA_CLI_NO_DASHBOARD", "true")
    monkeypatch.setenv("EMA_CLI_DASHBOARD_REFRESH_RATE", "3")
    monkeypatch.setenv("EMA_CLI_CONFIG_DIR", "/tmp/custom_config")

    settings = CLISettings()

    assert settings.verbose is True
    assert settings.no_dashboard is True
    assert settings.dashboard_refresh_rate == 3
    assert settings.config_dir == Path("/tmp/custom_config").resolve()


def test_get_config_path_default():
    """Test getting default config path based on platform."""
    settings = CLISettings()
    config_path = settings.get_config_path()

    assert config_path.name == "config.json"
    assert "ema_cloud_cli" in str(config_path)


def test_get_config_path_custom():
    """Test getting custom config path."""
    settings = CLISettings(
        config_dir="/tmp/my_config",
        config_filename="my_scanner.json",
    )
    config_path = settings.get_config_path()

    # Use resolve() to handle symlinks like /tmp -> /private/tmp on macOS
    assert config_path == Path("/tmp/my_config/my_scanner.json").resolve()


def test_ensure_config_dir(tmp_path):
    """Test ensuring config directory exists."""
    config_dir = tmp_path / "test_config"
    settings = CLISettings(config_dir=str(config_dir))

    assert not config_dir.exists()

    result_dir = settings.ensure_config_dir()

    assert config_dir.exists()
    assert result_dir == config_dir


def test_get_cli_settings_singleton():
    """Test that get_cli_settings returns a singleton instance."""
    reset_cli_settings()  # Clear any existing instance

    settings1 = get_cli_settings()
    settings2 = get_cli_settings()

    assert settings1 is settings2


def test_reset_cli_settings():
    """Test resetting the global settings instance."""
    settings1 = get_cli_settings()
    reset_cli_settings()
    settings2 = get_cli_settings()

    assert settings1 is not settings2


def test_dashboard_refresh_rate_validation():
    """Test dashboard refresh rate validation."""
    # Valid values
    settings = CLISettings(dashboard_refresh_rate=1)
    assert settings.dashboard_refresh_rate == 1

    settings = CLISettings(dashboard_refresh_rate=60)
    assert settings.dashboard_refresh_rate == 60

    # Invalid values should raise validation error
    with pytest.raises(ValidationError):
        CLISettings(dashboard_refresh_rate=0)

    with pytest.raises(ValidationError):
        CLISettings(dashboard_refresh_rate=61)


def test_expand_home_directory():
    """Test expansion of ~ in config_dir."""
    settings = CLISettings(config_dir="~/my_config")

    assert "~" not in str(settings.config_dir)
    assert settings.config_dir.is_absolute()
