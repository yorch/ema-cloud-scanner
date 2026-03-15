"""
Unit tests for the alert system.

Covers AlertMessage formatting, BaseAlertHandler, ConsoleAlertHandler,
DesktopAlertHandler, TelegramAlertHandler, DiscordAlertHandler,
EmailAlertHandler, AlertManager orchestration, and rate limiting.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ema_cloud_lib.alerts.base import AlertMessage, BaseAlertHandler, rate_limit
from ema_cloud_lib.alerts.console_desktop import ConsoleAlertHandler, DesktopAlertHandler
from ema_cloud_lib.alerts.email import EmailAlertHandler
from ema_cloud_lib.alerts.manager import AlertManager, create_alert_from_signal
from ema_cloud_lib.alerts.web_services import DiscordAlertHandler, TelegramAlertHandler


def _make_alert(
    symbol: str = "XLK",
    direction: str = "long",
    price: float = 150.25,
    signal_type: str = "cloud_flip",
    strength: str = "STRONG",
) -> AlertMessage:
    """Create an AlertMessage for testing."""
    return AlertMessage(
        title=f"{symbol} Signal",
        body=f"Test signal at ${price:.2f}",
        symbol=symbol,
        signal_type=signal_type,
        direction=direction,
        strength=strength,
        price=price,
        timestamp=datetime(2024, 6, 15, 10, 30, 0, tzinfo=UTC),
    )


def _make_alert_with_extras(**kwargs) -> AlertMessage:
    """Create an AlertMessage with extra_data."""
    alert = _make_alert(**kwargs)
    alert.extra_data = {
        "RSI": 55.3,
        "ADX": 28.7,
        "Volume Ratio": 1.45,
        "Stop Loss": 148.50,
        "Target": 155.00,
        "R/R Ratio": 2.15,
        "Sector": "Technology",
    }
    return alert


class TestAlertMessage:
    def test_to_short_string_long(self):
        alert = _make_alert(direction="long")
        short = alert.to_short_string()
        assert "XLK" in short
        assert "150.25" in short
        assert "STRONG" in short

    def test_to_short_string_short(self):
        alert = _make_alert(direction="short")
        short = alert.to_short_string()
        assert "XLK" in short

    def test_to_full_string(self):
        alert = _make_alert()
        full = alert.to_full_string()
        assert "SIGNAL ALERT" in full
        assert "XLK" in full
        assert "cloud_flip" in full
        assert "LONG" in full
        assert "150.25" in full
        assert "STRONG" in full
        assert "2024-06-15" in full

    def test_to_full_string_with_extra_data(self):
        alert = _make_alert_with_extras()
        full = alert.to_full_string()
        assert "55.30" in full  # RSI
        assert "Technology" in full

    def test_to_full_string_skips_none_extra_data(self):
        alert = _make_alert()
        alert.extra_data = {"RSI": 55.0, "ADX": None}
        full = alert.to_full_string()
        assert "55.00" in full
        assert "ADX" not in full


class TestBaseAlertHandler:
    @pytest.mark.asyncio
    async def test_send_batch_disabled(self):
        """send_batch returns 0 when disabled."""

        class DummyHandler(BaseAlertHandler):
            @property
            def name(self):
                return "Dummy"

            async def send_alert(self, message):
                return True

        handler = DummyHandler(enabled=False)
        count = await handler.send_batch([_make_alert(), _make_alert()])
        assert count == 0

    @pytest.mark.asyncio
    async def test_send_batch_counts_successes(self):
        """send_batch returns count of successful sends."""

        class PartialHandler(BaseAlertHandler):
            @property
            def name(self):
                return "Partial"

            async def send_alert(self, message):
                return message.direction == "long"

        handler = PartialHandler(enabled=True)
        alerts = [_make_alert(direction="long"), _make_alert(direction="short")]
        count = await handler.send_batch(alerts)
        assert count == 1

    def test_format_extra_data_fields(self):
        """_format_extra_data_fields extracts present fields."""
        extra = {
            "RSI": 55.0,
            "ADX": None,
            "Volume Ratio": 1.5,
            "Stop Loss": 148.0,
            "Target": 155.0,
            "R/R Ratio": 2.1,
            "Sector": "Tech",
        }
        fields = BaseAlertHandler._format_extra_data_fields(extra)
        labels = [f[0] for f in fields]
        assert "RSI" in labels
        assert "Volume Ratio" in labels
        assert "Sector" in labels
        # ADX is None, should not be included
        assert "ADX" not in labels


class TestConsoleAlertHandler:
    @pytest.mark.asyncio
    async def test_send_alert_enabled(self, capsys):
        handler = ConsoleAlertHandler(enabled=True, use_colors=False, verbose=False)
        result = await handler.send_alert(_make_alert())
        assert result is True
        captured = capsys.readouterr()
        assert "XLK" in captured.out

    @pytest.mark.asyncio
    async def test_send_alert_disabled(self, capsys):
        handler = ConsoleAlertHandler(enabled=False)
        result = await handler.send_alert(_make_alert())
        assert result is False
        captured = capsys.readouterr()
        assert captured.out == ""

    @pytest.mark.asyncio
    async def test_send_alert_verbose(self, capsys):
        handler = ConsoleAlertHandler(enabled=True, use_colors=False, verbose=True)
        result = await handler.send_alert(_make_alert())
        assert result is True
        captured = capsys.readouterr()
        assert "SIGNAL ALERT" in captured.out

    def test_name(self):
        assert ConsoleAlertHandler().name == "Console"

    def test_colorize_enabled(self):
        handler = ConsoleAlertHandler(use_colors=True)
        colored = handler._colorize("test", "green")
        assert "\033[92m" in colored
        assert "test" in colored

    def test_colorize_disabled(self):
        handler = ConsoleAlertHandler(use_colors=False)
        result = handler._colorize("test", "green")
        assert result == "test"

    @pytest.mark.asyncio
    async def test_long_direction_gets_green(self, capsys):
        handler = ConsoleAlertHandler(enabled=True, use_colors=True, verbose=False)
        await handler.send_alert(_make_alert(direction="long"))
        captured = capsys.readouterr()
        assert "\033[92m" in captured.out  # Green

    @pytest.mark.asyncio
    async def test_short_direction_gets_red(self, capsys):
        handler = ConsoleAlertHandler(enabled=True, use_colors=True, verbose=False)
        await handler.send_alert(_make_alert(direction="short"))
        captured = capsys.readouterr()
        assert "\033[91m" in captured.out  # Red


class TestDesktopAlertHandler:
    def test_name(self):
        assert DesktopAlertHandler().name == "Desktop"

    @pytest.mark.asyncio
    async def test_disabled_returns_false(self):
        handler = DesktopAlertHandler(enabled=False)
        result = await handler.send_alert(_make_alert())
        assert result is False

    @pytest.mark.asyncio
    async def test_no_notifier_returns_false(self):
        handler = DesktopAlertHandler(enabled=True)
        handler._notifier = None
        # Force _get_notifier to return None (plyer not installed)
        with patch.object(handler, "_get_notifier", return_value=None):
            result = await handler.send_alert(_make_alert())
        assert result is False

    @pytest.mark.asyncio
    async def test_sends_notification(self):
        handler = DesktopAlertHandler(enabled=True, play_sound=False)
        mock_notifier = MagicMock()
        handler._notifier = mock_notifier

        result = await handler.send_alert(_make_alert())
        assert result is True
        mock_notifier.notify.assert_called_once()
        call_kwargs = mock_notifier.notify.call_args
        assert "XLK" in call_kwargs.kwargs.get("title", "") or "XLK" in str(call_kwargs)


class TestTelegramAlertHandler:
    def test_name(self):
        handler = TelegramAlertHandler(enabled=False)
        assert handler.name == "Telegram"

    def test_disabled_without_token(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = TelegramAlertHandler(enabled=True, bot_token=None, chat_id="123")
        assert handler.enabled is False

    def test_disabled_without_chat_id(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = TelegramAlertHandler(enabled=True, bot_token="token", chat_id=None)
        assert handler.enabled is False

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self):
        handler = TelegramAlertHandler(enabled=False)
        result = await handler.send_alert(_make_alert())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Successful Telegram send returns True."""
        handler = TelegramAlertHandler.__new__(TelegramAlertHandler)
        handler.enabled = True
        handler.bot_token = "test_token"
        handler.chat_id = "12345"
        handler.timeout = 5

        mock_response = AsyncMock()
        mock_response.status = 200

        mock_session = MagicMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.post = MagicMock(
            return_value=MagicMock(
                __aenter__=AsyncMock(return_value=mock_response),
                __aexit__=AsyncMock(return_value=False),
            )
        )

        with patch.dict(
            "sys.modules",
            {
                "aiohttp": MagicMock(
                    ClientSession=MagicMock(return_value=mock_session),
                    ClientTimeout=MagicMock(),
                )
            },
        ):
            # Bypass rate limit decorator for testing
            result = await TelegramAlertHandler.send_alert.__wrapped__(handler, _make_alert())

        assert result is True


class TestDiscordAlertHandler:
    def test_name(self):
        handler = DiscordAlertHandler(enabled=False)
        assert handler.name == "Discord"

    def test_disabled_without_webhook(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = DiscordAlertHandler(enabled=True, webhook_url=None)
        assert handler.enabled is False

    def test_disabled_with_invalid_webhook(self):
        handler = DiscordAlertHandler(enabled=True, webhook_url="https://example.com/bad")
        assert handler.enabled is False

    def test_enabled_with_valid_webhook(self):
        handler = DiscordAlertHandler(
            enabled=True,
            webhook_url="https://discord.com/api/webhooks/123/abc",
        )
        assert handler.enabled is True

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self):
        handler = DiscordAlertHandler(enabled=False)
        result = await handler.send_alert(_make_alert())
        assert result is False


class TestEmailAlertHandler:
    def test_name(self):
        handler = EmailAlertHandler(enabled=False)
        assert handler.name == "Email"

    def test_disabled_without_server(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = EmailAlertHandler(
                enabled=True,
                smtp_server=None,
                smtp_username="u",
                smtp_password="p",
                from_address="a@b.com",
                to_addresses=["c@d.com"],
            )
        assert handler.enabled is False

    def test_disabled_without_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = EmailAlertHandler(
                enabled=True,
                smtp_server="smtp.test.com",
                smtp_username=None,
                smtp_password=None,
                from_address="a@b.com",
                to_addresses=["c@d.com"],
            )
        assert handler.enabled is False

    def test_disabled_without_from_address(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = EmailAlertHandler(
                enabled=True,
                smtp_server="smtp.test.com",
                smtp_username="u",
                smtp_password="p",
                from_address=None,
                to_addresses=["c@d.com"],
            )
        assert handler.enabled is False

    def test_disabled_without_recipients(self):
        with patch.dict("os.environ", {}, clear=True):
            handler = EmailAlertHandler(
                enabled=True,
                smtp_server="smtp.test.com",
                smtp_username="u",
                smtp_password="p",
                from_address="a@b.com",
                to_addresses=[],
            )
        assert handler.enabled is False

    def test_enabled_with_all_config(self):
        handler = EmailAlertHandler(
            enabled=True,
            smtp_server="smtp.test.com",
            smtp_username="u",
            smtp_password="p",
            from_address="a@b.com",
            to_addresses=["c@d.com"],
        )
        assert handler.enabled is True

    def test_create_html_message(self):
        handler = EmailAlertHandler(enabled=False)
        alert = _make_alert_with_extras()
        html = handler._create_html_message(alert)
        assert "<html>" in html
        assert "XLK" in html
        assert "150.25" in html

    def test_create_text_message(self):
        handler = EmailAlertHandler(enabled=False)
        alert = _make_alert_with_extras()
        text = handler._create_text_message(alert)
        assert "XLK" in text
        assert "150.25" in text
        assert "RSI" in text

    @pytest.mark.asyncio
    async def test_send_disabled_returns_false(self):
        handler = EmailAlertHandler(enabled=False)
        result = await handler.send_alert(_make_alert())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_success(self):
        """Email send via SMTP mock succeeds."""
        handler = EmailAlertHandler(
            enabled=True,
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_username="user",
            smtp_password="pass",
            from_address="from@test.com",
            to_addresses=["to@test.com"],
        )
        with patch.object(handler, "_send_smtp_sync"):
            # Bypass rate limit decorator
            result = await EmailAlertHandler.send_alert.__wrapped__(handler, _make_alert())
        assert result is True


class TestRateLimitDecorator:
    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        """Calls under rate limit are allowed."""

        class TestHandler(BaseAlertHandler):
            @property
            def name(self):
                return "Test"

            @rate_limit(max_per_minute=5)
            async def send_alert(self, message):
                return True

        handler = TestHandler(enabled=True)
        results = []
        for _ in range(5):
            results.append(await handler.send_alert(_make_alert()))
        assert all(r is True for r in results)

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        """Calls over rate limit return False."""

        class TestHandler(BaseAlertHandler):
            @property
            def name(self):
                return "Test"

            @rate_limit(max_per_minute=2)
            async def send_alert(self, message):
                return True

        handler = TestHandler(enabled=True)
        r1 = await handler.send_alert(_make_alert())
        r2 = await handler.send_alert(_make_alert())
        r3 = await handler.send_alert(_make_alert())  # Should be blocked
        assert r1 is True
        assert r2 is True
        assert r3 is False


class TestAlertManager:
    def test_add_handler(self):
        manager = AlertManager()
        handler = ConsoleAlertHandler(enabled=True)
        manager.add_handler(handler)
        assert "Console" in manager.handlers

    def test_remove_handler(self):
        manager = AlertManager()
        manager.add_handler(ConsoleAlertHandler(enabled=True))
        manager.remove_handler("Console")
        assert "Console" not in manager.handlers

    def test_remove_nonexistent_handler(self):
        manager = AlertManager()
        manager.remove_handler("Nonexistent")  # Should not raise

    def test_enable_handler(self):
        manager = AlertManager()
        handler = ConsoleAlertHandler(enabled=False)
        manager.add_handler(handler)
        manager.enable_handler("Console")
        assert handler.enabled is True

    def test_disable_handler(self):
        manager = AlertManager()
        handler = ConsoleAlertHandler(enabled=True)
        manager.add_handler(handler)
        manager.disable_handler("Console")
        assert handler.enabled is False

    def test_enable_nonexistent_handler(self):
        manager = AlertManager()
        manager.enable_handler("Nonexistent")  # Should not raise

    @pytest.mark.asyncio
    async def test_send_alert_to_all_enabled(self):
        """send_alert dispatches to all enabled handlers."""
        manager = AlertManager()

        handler1 = MagicMock(spec=BaseAlertHandler)
        handler1.name = "H1"
        handler1.enabled = True
        handler1.send_alert = AsyncMock(return_value=True)

        handler2 = MagicMock(spec=BaseAlertHandler)
        handler2.name = "H2"
        handler2.enabled = True
        handler2.send_alert = AsyncMock(return_value=True)

        manager.add_handler(handler1)
        manager.add_handler(handler2)

        results = await manager.send_alert(_make_alert())
        assert results == {"H1": True, "H2": True}

    @pytest.mark.asyncio
    async def test_send_alert_skips_disabled(self):
        """send_alert skips disabled handlers."""
        manager = AlertManager()

        enabled = MagicMock(spec=BaseAlertHandler)
        enabled.name = "Enabled"
        enabled.enabled = True
        enabled.send_alert = AsyncMock(return_value=True)

        disabled = MagicMock(spec=BaseAlertHandler)
        disabled.name = "Disabled"
        disabled.enabled = False

        manager.add_handler(enabled)
        manager.add_handler(disabled)

        results = await manager.send_alert(_make_alert())
        assert "Enabled" in results
        assert "Disabled" not in results

    @pytest.mark.asyncio
    async def test_send_alert_no_handlers(self):
        """send_alert returns empty dict with no enabled handlers."""
        manager = AlertManager()
        results = await manager.send_alert(_make_alert())
        assert results == {}

    @pytest.mark.asyncio
    async def test_send_alert_handler_exception(self):
        """send_alert catches handler exceptions and returns False."""
        manager = AlertManager()

        handler = MagicMock(spec=BaseAlertHandler)
        handler.name = "Broken"
        handler.enabled = True
        handler.send_alert = AsyncMock(side_effect=RuntimeError("broken"))

        manager.add_handler(handler)

        results = await manager.send_alert(_make_alert())
        assert results == {"Broken": False}

    @pytest.mark.asyncio
    async def test_send_alert_updates_history(self):
        """send_alert adds message to history."""
        manager = AlertManager()
        handler = MagicMock(spec=BaseAlertHandler)
        handler.name = "H"
        handler.enabled = True
        handler.send_alert = AsyncMock(return_value=True)
        manager.add_handler(handler)

        alert = _make_alert()
        await manager.send_alert(alert)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0] is alert

    @pytest.mark.asyncio
    async def test_history_truncated_at_max(self):
        """History is truncated when exceeding max."""
        manager = AlertManager()
        manager._max_history = 5

        handler = MagicMock(spec=BaseAlertHandler)
        handler.name = "H"
        handler.enabled = True
        handler.send_alert = AsyncMock(return_value=True)
        manager.add_handler(handler)

        for i in range(10):
            await manager.send_alert(_make_alert(price=float(i)))

        assert len(manager._alert_history) == 5

    @pytest.mark.asyncio
    async def test_send_batch(self):
        """send_batch dispatches multiple messages."""
        manager = AlertManager()

        handler = MagicMock(spec=BaseAlertHandler)
        handler.name = "H"
        handler.enabled = True
        handler.send_batch = AsyncMock(return_value=3)
        manager.add_handler(handler)

        alerts = [_make_alert() for _ in range(3)]
        results = await manager.send_batch(alerts)
        assert results == {"H": 3}

    def test_get_history_with_limit(self):
        manager = AlertManager()
        for i in range(10):
            manager._alert_history.append(_make_alert(price=float(i)))

        history = manager.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_empty(self):
        manager = AlertManager()
        assert manager.get_history() == []


class TestAlertManagerCreateDefault:
    def test_default_handlers(self):
        """create_default always adds Console and Desktop."""
        manager = AlertManager.create_default({})
        assert "Console" in manager.handlers
        assert "Desktop" in manager.handlers

    def test_telegram_added_when_configured(self):
        manager = AlertManager.create_default(
            {
                "telegram": {
                    "enabled": True,
                    "bot_token": "test_token",
                    "chat_id": "12345",
                },
            }
        )
        assert "Telegram" in manager.handlers

    def test_telegram_not_added_when_disabled(self):
        manager = AlertManager.create_default(
            {
                "telegram": {"enabled": False},
            }
        )
        assert "Telegram" not in manager.handlers

    def test_discord_added_when_configured(self):
        manager = AlertManager.create_default(
            {
                "discord": {
                    "enabled": True,
                    "webhook_url": "https://discord.com/api/webhooks/123/abc",
                },
            }
        )
        assert "Discord" in manager.handlers

    def test_email_added_when_configured(self):
        manager = AlertManager.create_default(
            {
                "email": {
                    "enabled": True,
                    "smtp_server": "smtp.test.com",
                    "username": "user",
                    "password": "pass",
                    "from_address": "from@test.com",
                    "recipients": ["to@test.com"],
                },
            }
        )
        assert "Email" in manager.handlers


class TestCreateAlertFromSignal:
    def test_creates_alert_from_signal(self):
        """create_alert_from_signal produces correct AlertMessage."""
        from ema_cloud_lib.config.settings import SignalType
        from ema_cloud_lib.indicators.ema_cloud import CloudState, PriceRelation
        from ema_cloud_lib.signals.generator import Signal, SignalStrength

        signal = Signal(
            symbol="XLK",
            signal_type=SignalType.CLOUD_FLIP_BULLISH,
            direction="long",
            strength=SignalStrength.STRONG,
            price=150.0,
            timestamp=datetime(2024, 6, 15, tzinfo=UTC),
            cloud_name="trend_confirmation",
            description="Cloud flip",
            primary_cloud_state=CloudState.BULLISH,
            price_relation=PriceRelation.ABOVE,
            filters_passed=["volume", "rsi"],
            filters_failed=[],
            rsi=55.0,
            adx=28.0,
            volume_ratio=1.5,
            suggested_stop=148.0,
            suggested_target=155.0,
            risk_reward_ratio=2.5,
            sector="Technology",
        )

        alert = create_alert_from_signal(signal)
        assert alert.symbol == "XLK"
        assert alert.direction == "long"
        assert alert.price == 150.0
        assert alert.strength == "STRONG"
        assert alert.extra_data["RSI"] == 55.0
        assert alert.extra_data["Sector"] == "Technology"
