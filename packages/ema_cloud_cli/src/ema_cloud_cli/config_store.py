"""
Config persistence helpers for the CLI.
"""

import json
import logging
import os
import sys
from pathlib import Path

from ema_cloud_lib.config.settings import ScannerConfig

logger = logging.getLogger(__name__)


def get_user_config_path() -> Path:
    """Return the default user config path for this CLI."""
    home = Path.home()

    if sys.platform == "darwin":
        base_dir = home / "Library" / "Application Support"
    elif os.name == "nt":
        base_dir = Path(
            os.environ.get("APPDATA")
            or os.environ.get("LOCALAPPDATA")
            or (home / "AppData" / "Roaming")
        )
    else:
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))

    return base_dir / "ema_cloud_cli" / "config.json"


def load_config_from_path(path: str | Path) -> ScannerConfig:
    """Load a config file, supporting both full and partial formats."""
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
    """Load the user config if it exists."""
    path = get_user_config_path()
    if not path.exists():
        return None
    try:
        return load_config_from_path(path)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        logger.warning("Failed to load user config %s: %s", path, exc)
        return None


def save_user_config(config: ScannerConfig) -> Path:
    """Save the full config to the user config path."""
    path = get_user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config.to_full_dict(), indent=2))
    return path
