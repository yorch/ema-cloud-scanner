"""
Tests for config_store with pydantic-settings integration.
"""

import json

import pytest

from ema_cloud_cli.config_store import (
    config_exists,
    get_config_directory,
    get_user_config_path,
    load_config_from_path,
    load_user_config,
    save_user_config,
)
from ema_cloud_cli.settings import reset_cli_settings
from ema_cloud_lib.config.settings import ScannerConfig, TradingStyle


@pytest.fixture
def temp_config_dir(tmp_path, monkeypatch):
    """Set up temporary config directory."""
    config_dir = tmp_path / "test_config"
    monkeypatch.setenv("EMA_CLI_CONFIG_DIR", str(config_dir))
    reset_cli_settings()  # Force reload of settings
    yield config_dir
    reset_cli_settings()  # Clean up after test


def test_get_user_config_path(temp_config_dir):
    """Test getting user config path from CLI settings."""
    config_path = get_user_config_path()

    assert config_path.parent == temp_config_dir
    assert config_path.name == "config.json"


def test_get_config_directory(temp_config_dir):
    """Test getting config directory."""
    config_dir = get_config_directory()

    assert config_dir == temp_config_dir


def test_config_exists_false(temp_config_dir):
    """Test config_exists when file doesn't exist."""
    assert not config_exists()


def test_config_exists_true(temp_config_dir):
    """Test config_exists when file exists."""
    config = ScannerConfig()
    save_user_config(config)

    assert config_exists()


def test_save_and_load_user_config(temp_config_dir):
    """Test saving and loading user config."""
    # Create config
    config = ScannerConfig(
        trading_style=TradingStyle.SWING,
        scan_interval=120,
    )

    # Save config
    saved_path = save_user_config(config)

    assert saved_path.exists()
    assert saved_path == get_user_config_path()

    # Load config
    loaded_config = load_user_config()

    assert loaded_config is not None
    assert loaded_config.trading_style == TradingStyle.SWING
    assert loaded_config.scan_interval == 120


def test_load_user_config_not_exists(temp_config_dir):
    """Test loading user config when file doesn't exist."""
    loaded_config = load_user_config()

    assert loaded_config is None


def test_load_config_from_path(tmp_path):
    """Test loading config from specific path."""
    config_path = tmp_path / "custom_config.json"

    # Create test config
    config = ScannerConfig(trading_style=TradingStyle.POSITION)
    config.save(str(config_path))

    # Load from path
    loaded_config = load_config_from_path(config_path)

    assert loaded_config.trading_style == TradingStyle.POSITION


def test_load_config_partial_format(tmp_path):
    """Test loading config in partial format."""
    config_path = tmp_path / "partial_config.json"

    # Create minimal config
    minimal_dict = {
        "trading_style": "swing",
        "scan_interval": 90,
    }
    config_path.write_text(json.dumps(minimal_dict, indent=2))

    # Load from path
    loaded_config = load_config_from_path(config_path)

    assert loaded_config.trading_style == TradingStyle.SWING
    assert loaded_config.scan_interval == 90


def test_load_config_full_format(tmp_path):
    """Test loading config using Pydantic serialization."""
    config_path = tmp_path / "full_config.json"

    # Create and save config
    config = ScannerConfig(trading_style=TradingStyle.INTRADAY)
    config.save(str(config_path))

    # Load from path
    loaded_config = load_config_from_path(config_path)

    assert loaded_config.trading_style == TradingStyle.INTRADAY


def test_save_creates_directory(temp_config_dir):
    """Test that save_user_config creates directory if needed."""
    assert not temp_config_dir.exists()

    config = ScannerConfig()
    saved_path = save_user_config(config)

    assert temp_config_dir.exists()
    assert saved_path.exists()


def test_load_invalid_json(tmp_path, monkeypatch):
    """Test loading config with invalid JSON."""
    config_dir = tmp_path / "invalid_config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    config_path.write_text("{ invalid json }")

    monkeypatch.setenv("EMA_CLI_CONFIG_DIR", str(config_dir))
    reset_cli_settings()

    loaded_config = load_user_config()

    assert loaded_config is None


def test_custom_config_filename(tmp_path, monkeypatch):
    """Test using custom config filename via environment."""
    config_dir = tmp_path / "custom"
    monkeypatch.setenv("EMA_CLI_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("EMA_CLI_CONFIG_FILENAME", "my_scanner.json")
    reset_cli_settings()

    config = ScannerConfig()
    saved_path = save_user_config(config)

    assert saved_path.name == "my_scanner.json"
    assert saved_path.parent == config_dir
