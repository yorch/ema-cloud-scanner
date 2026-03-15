"""Tests for ema_cloud_cli.cli utility functions and CLI argument handling."""

import logging
import re
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ema_cloud_cli.cli import (
    _determine_log_level,
    _parse_bool,
    _parse_log_retention,
    _parse_log_rotation,
    app,
)

# Strip ANSI escape sequences from CLI output so string assertions work
# consistently across Python versions and operating systems.
# On Linux CI, typer/click emits colour codes even in non-TTY test mode
# regardless of the NO_COLOR env var (behaviour varies by Click version).
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# ── Pure utility functions ────────────────────────────────────────────────────


class TestParseLogRotation:
    def test_none_returns_none(self):
        assert _parse_log_rotation(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_log_rotation("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_log_rotation("10MB") is None
        assert _parse_log_rotation("size:abc") is None
        assert _parse_log_rotation("size:10TB") is None

    def test_mb(self):
        assert _parse_log_rotation("size:10MB") == 10 * 1024**2

    def test_kb(self):
        assert _parse_log_rotation("size:512KB") == 512 * 1024

    def test_gb(self):
        assert _parse_log_rotation("size:1GB") == 1 * 1024**3

    def test_case_insensitive(self):
        assert _parse_log_rotation("size:5mb") == 5 * 1024**2
        assert _parse_log_rotation("size:5Mb") == 5 * 1024**2

    def test_whitespace_stripped(self):
        assert _parse_log_rotation("  size:10MB  ") == 10 * 1024**2


class TestParseLogRetention:
    def test_none_returns_none(self):
        assert _parse_log_retention(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_log_retention("") is None

    def test_plain_number(self):
        assert _parse_log_retention("7") == 7

    def test_days_suffix(self):
        assert _parse_log_retention("7 days") == 7
        assert _parse_log_retention("30 days") == 30

    def test_single_digit(self):
        assert _parse_log_retention("1") == 1

    def test_non_numeric_returns_none(self):
        assert _parse_log_retention("daily") is None

    def test_whitespace_stripped(self):
        assert _parse_log_retention("  14 days  ") == 14


class TestParseBool:
    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"])
    def test_truthy_values(self, value):
        assert _parse_bool(value) is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "FALSE", "no", "NO", "off", "OFF"])
    def test_falsy_values(self, value):
        assert _parse_bool(value) is False

    def test_unknown_value_returns_none(self):
        assert _parse_bool("maybe") is None
        assert _parse_bool("2") is None
        assert _parse_bool("") is None

    def test_whitespace_stripped(self):
        assert _parse_bool("  true  ") is True
        assert _parse_bool("  false  ") is False


class TestDetermineLogLevel:
    def _make_settings(self, log_level=None):
        mock = MagicMock()
        mock.log_level = log_level
        return mock

    def test_verbose_2_returns_debug(self):
        assert _determine_log_level(2, self._make_settings()) == logging.DEBUG

    def test_verbose_3_also_debug(self):
        assert _determine_log_level(3, self._make_settings()) == logging.DEBUG

    def test_verbose_1_returns_info(self):
        assert _determine_log_level(1, self._make_settings()) == logging.INFO

    def test_verbose_0_no_settings_returns_info(self):
        assert _determine_log_level(0, self._make_settings(log_level=None)) == logging.INFO

    def test_verbose_0_with_settings_level(self):
        assert _determine_log_level(0, self._make_settings(log_level="DEBUG")) == logging.DEBUG
        assert _determine_log_level(0, self._make_settings(log_level="WARNING")) == logging.WARNING

    def test_verbose_flag_overrides_settings(self):
        # -v always wins over settings
        assert _determine_log_level(1, self._make_settings(log_level="DEBUG")) == logging.INFO
        assert _determine_log_level(2, self._make_settings(log_level="WARNING")) == logging.DEBUG


# ── CLI invocation via typer.testing.CliRunner ────────────────────────────────


class _InvokeResult:
    """Thin wrapper around Click's Result with ANSI codes stripped from output."""

    def __init__(self, result: object) -> None:
        self._result = result
        self.output: str = _ANSI_RE.sub("", result.output)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._result, name)


class _CLITestBase:
    """Mixin that strips ANSI escape sequences from invoke() output.

    Typer/Click emits ANSI escape sequences on Linux (CI) even through the
    test runner regardless of NO_COLOR, which splits flag names like
    ``--style`` into ``\\x1b[1;36m-\\x1b[0m\\x1b[1;36m-style\\x1b[0m``.
    We wrap the result so plain-string assertions work uniformly across all
    Python versions and operating systems.
    """

    def setup_method(self) -> None:
        self.runner = CliRunner()

    def invoke(self, args: list[str], **kwargs: object) -> _InvokeResult:
        return _InvokeResult(self.runner.invoke(app, args, **kwargs))


class TestCLIHelp(_CLITestBase):
    def test_help_exits_zero(self):
        result = self.invoke(["--help"])
        assert result.exit_code == 0

    def test_help_mentions_style(self):
        result = self.invoke(["--help"])
        assert "--style" in result.output

    def test_help_mentions_no_dashboard(self):
        result = self.invoke(["--help"])
        assert "--no-dashboard" in result.output

    def test_backtest_help(self):
        result = self.invoke(["backtest", "--help"])
        assert result.exit_code == 0
        assert "--start-date" in result.output

    def test_config_save_help(self):
        result = self.invoke(["config-save", "--help"])
        assert result.exit_code == 0


class TestCLIValidation(_CLITestBase):
    def test_alpaca_provider_requires_keys(self):
        result = self.invoke(["--provider", "alpaca", "--no-dashboard", "--once"])
        assert result.exit_code != 0
        assert "alpaca-key" in result.output.lower() or "alpaca" in result.output.lower()

    def test_polygon_provider_requires_key(self):
        # Clear POLYGON_API_KEY so the envvar fallback doesn't bypass validation
        result = self.invoke(
            ["--provider", "polygon", "--no-dashboard", "--once"],
            env={"POLYGON_API_KEY": ""},
        )
        assert result.exit_code != 0
        assert "polygon" in result.output.lower()

    def test_telegram_alerts_require_credentials(self):
        result = self.invoke(["--telegram-alerts", "--no-dashboard", "--once"])
        assert result.exit_code != 0
        assert "telegram" in result.output.lower()

    def test_discord_alerts_require_webhook(self):
        result = self.invoke(["--discord-alerts", "--no-dashboard", "--once"])
        assert result.exit_code != 0
        assert "discord" in result.output.lower()

    def test_invalid_filter_weights_json(self):
        result = self.invoke(
            ["--filter-weights", "not-valid-json", "--no-dashboard", "--once"],
        )
        assert result.exit_code != 0
        assert "json" in result.output.lower() or "invalid" in result.output.lower()

    def test_filter_weights_non_object_json(self):
        result = self.invoke(
            ["--filter-weights", "[1,2,3]", "--no-dashboard", "--once"],
        )
        assert result.exit_code != 0
        assert "json object" in result.output.lower() or "json" in result.output.lower()

    def test_print_config_exits_cleanly(self):
        result = self.invoke(["--print-config"])
        assert result.exit_code == 0

    def test_unknown_subset_rejected(self):
        """Unknown subset should produce an error message and exit non-zero."""
        result = self.invoke(["--subset", "nonexistent_subset", "--no-dashboard", "--once"])
        assert result.exit_code != 0
        assert "subset" in result.output.lower()

    def test_valid_yahoo_provider_accepted(self):
        """Yahoo provider requires no credentials — scanner setup should proceed."""
        with patch("ema_cloud_cli.cli.asyncio.run"):
            result = self.invoke(["--provider", "yahoo", "--no-dashboard", "--once"])
        assert "Error:" not in result.output or result.exit_code == 0


class TestCLIConfigPrint(_CLITestBase):
    """--print-config should dump valid JSON and exit 0 without running the scanner."""

    def test_print_config_outputs_json(self):
        result = self.invoke(["--print-config"])
        assert result.exit_code == 0
        assert "{" in result.output

    def test_print_config_with_style(self):
        result = self.invoke(["--style", "swing", "--print-config"])
        assert result.exit_code == 0

    def test_print_config_with_interval(self):
        result = self.invoke(["--interval", "120", "--print-config"])
        assert result.exit_code == 0
        assert "120" in result.output
