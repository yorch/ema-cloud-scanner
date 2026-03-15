"""
CLI-specific settings using pydantic-settings.

This module provides settings management for CLI preferences and configuration paths
using pydantic-settings for automatic environment variable support and validation.
Uses platformdirs for cross-platform config directory detection.
"""

import os
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from ema_cloud_cli.constants import APP_NAME


class CLISettings(BaseSettings):
    """CLI application settings with environment variable support.

    Settings can be configured via:
    1. Environment variables (prefixed with EMA_CLI_)
    2. .env file in the config directory
    3. Direct initialization

    Example:
        # From environment
        export EMA_CLI_CONFIG_DIR="~/my_configs"

        # From code
        settings = CLISettings(config_dir="/custom/path")
    """

    model_config = SettingsConfigDict(
        env_prefix="EMA_CLI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Configuration paths
    config_dir: Path | None = Field(
        default=None,
        description="Custom config directory path. If None, uses platform default.",
    )

    config_filename: str = Field(
        default="config.json",
        description="Configuration file name",
    )

    # CLI preferences
    verbose: bool = Field(
        default=False,
        description="Enable verbose logging by default",
    )

    no_dashboard: bool = Field(
        default=False,
        description="Disable terminal dashboard by default",
    )

    all_hours: bool = Field(
        default=False,
        description="Scan during extended hours by default",
    )

    # Dashboard preferences
    dashboard_refresh_rate: int = Field(
        default=1,
        ge=1,
        le=60,
        description="Dashboard refresh rate in seconds",
    )

    # Report output
    report_dir: Path | None = Field(
        default=None,
        description="Directory for JSON scan reports. If set, enables headless report output.",
    )

    # Logging preferences
    log_dir: Path | None = Field(
        default=None,
        description="Custom log directory path. If None, uses platform default.",
    )

    log_filename: str = Field(
        default="scanner.log",
        description="Log filename when dashboard logging is enabled",
    )

    log_level: str | None = Field(
        default=None,
        description="Override log level (DEBUG/INFO/WARNING/ERROR/CRITICAL)",
    )

    log_rotation: str | None = Field(
        default=None,
        description="Log rotation policy (e.g., 'size:10MB')",
    )

    log_retention: str | None = Field(
        default=None,
        description="Log retention policy (e.g., '7 days')",
    )

    @field_validator("config_dir", mode="before")
    @classmethod
    def expand_config_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home directory in config path."""
        if v is None:
            return None
        path = Path(v)
        return path.expanduser().resolve()

    @field_validator("report_dir", mode="before")
    @classmethod
    def expand_report_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home directory in report path."""
        if v is None:
            return None
        path = Path(v)
        return path.expanduser().resolve()

    @field_validator("log_dir", mode="before")
    @classmethod
    def expand_log_dir(cls, v: str | Path | None) -> Path | None:
        """Expand user home directory in log path."""
        if v is None:
            return None
        path = Path(v)
        return path.expanduser().resolve()

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, v: str | None) -> str | None:
        """Normalize log level values to uppercase."""
        if v is None:
            return None
        return v.upper()

    def get_config_path(self) -> Path:
        """Get the full path to the configuration file.

        Uses platformdirs for cross-platform config directory detection:
        - macOS: ~/Library/Application Support/ema_cloud_cli/
        - Windows: %APPDATA%/ema_cloud_cli/
        - Linux: ~/.config/ema_cloud_cli/
        """
        if self.config_dir:
            config_dir = self.config_dir
        else:
            config_dir = self._get_default_config_dir()

        return config_dir / self.config_filename

    @staticmethod
    def _get_default_config_dir() -> Path:
        """Return the platform-appropriate default config directory using platformdirs."""
        return Path(user_config_dir(APP_NAME, appauthor=False))

    def ensure_config_dir(self) -> Path:
        """Ensure the config directory exists and return its path."""
        config_path = self.get_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        return config_path.parent


# Global settings instance
_settings: CLISettings | None = None


def get_cli_settings() -> CLISettings:
    """Get or create the global CLI settings instance.

    This function ensures a single settings instance is used throughout
    the application lifecycle.
    """
    global _settings
    if _settings is None:
        config_dir_env = os.getenv("EMA_CLI_CONFIG_DIR")
        if config_dir_env:
            config_dir = Path(config_dir_env).expanduser().resolve()
        else:
            config_dir = CLISettings._get_default_config_dir()
        env_file = config_dir / ".env"
        _settings = CLISettings(_env_file=env_file)  # type: ignore[call-arg]
    return _settings


def reset_cli_settings() -> None:
    """Reset the global settings instance (useful for testing)."""
    global _settings
    _settings = None
