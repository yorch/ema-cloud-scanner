"""
Config persistence helpers for the CLI.

This module provides functions for loading and saving scanner configurations
using pydantic-settings for path management and validation.
"""

import json
import logging
from pathlib import Path

from ema_cloud_lib.config.settings import ScannerConfig

from .settings import get_cli_settings

logger = logging.getLogger(__name__)


def get_user_config_path() -> Path:
    """Return the user config path from CLI settings.

    Uses pydantic-settings to determine platform-appropriate config location.
    Can be overridden via EMA_CLI_CONFIG_DIR environment variable.
    """
    cli_settings = get_cli_settings()
    return cli_settings.get_config_path()


def load_config_from_path(path: str | Path) -> ScannerConfig:
    """Load a config file, supporting both full and partial formats.

    Args:
        path: Path to the configuration file (JSON format)

    Returns:
        ScannerConfig instance loaded from the file

    Raises:
        FileNotFoundError: If the config file doesn't exist
        json.JSONDecodeError: If the file contains invalid JSON
        ValueError: If the config format is invalid
    """
    path = Path(path)
    config_dict = json.loads(path.read_text())

    if isinstance(config_dict, dict) and (
        "ema_clouds" in config_dict
        or "filters" in config_dict
        or "alerts" in config_dict
        or "data_provider" in config_dict
        or "backtest" in config_dict
    ):
        return ScannerConfig.from_full_dict(config_dict)

    return ScannerConfig.load(str(path))


def load_user_config() -> ScannerConfig | None:
    """Load the user config if it exists.

    Reads from the platform-appropriate config location determined by
    CLI settings (can be customized via environment variables).

    Returns:
        ScannerConfig if file exists and is valid, None otherwise
    """
    path = get_user_config_path()
    if not path.exists():
        logger.debug("No user config found at %s", path)
        return None

    try:
        logger.info("Loading user config from %s", path)
        return load_config_from_path(path)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Failed to load user config %s: %s", path, exc)
        return None


def save_user_config(config: ScannerConfig) -> Path:
    """Save the full config to the user config path.

    Creates the config directory if it doesn't exist. Uses pydantic-settings
    to determine the appropriate location.

    Args:
        config: ScannerConfig instance to save

    Returns:
        Path where the config was saved

    Raises:
        OSError: If unable to create directory or write file
    """
    cli_settings = get_cli_settings()
    cli_settings.ensure_config_dir()  # Ensure directory exists
    path = cli_settings.get_config_path()

    logger.info("Saving config to %s", path)
    path.write_text(json.dumps(config.to_full_dict(), indent=2))
    logger.debug("Config saved successfully to %s", path)

    return path


def get_config_directory() -> Path:
    """Get the config directory path (without filename).

    Useful for storing additional configuration files or logs.

    Returns:
        Path to the config directory
    """
    return get_user_config_path().parent


def config_exists() -> bool:
    """Check if a user config file exists.

    Returns:
        True if config file exists, False otherwise
    """
    return get_user_config_path().exists()
