"""
Settings UI for the EMA Cloud CLI dashboard.
"""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Collapsible,
    Input,
    Select,
    SelectionList,
    Static,
    Switch,
    TabbedContent,
    TabPane,
)
from textual.widgets._selection_list import Selection

from ema_cloud_cli.config_store import save_user_config
from ema_cloud_lib.config.settings import SECTOR_ETFS, ScannerConfig, TradingStyle


class SettingsScreen(ModalScreen[ScannerConfig]):
    """Settings editor using a form-based panel."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, config: ScannerConfig, on_apply):
        super().__init__()
        self._config = config
        self._on_apply = on_apply
        self._cloud_keys = list(config.ema_clouds.keys())

    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel"):
            yield Static("Settings", id="settings-title")
            with TabbedContent(id="settings-tabs"):
                with TabPane("General", id="tab-general"):
                    with VerticalScroll(classes="settings-tab"):
                        yield self._row(
                            "Trading Style",
                            Select(
                                [(s.value, s.value) for s in TradingStyle],
                                value=self._config.trading_style.value,
                                id="trading_style",
                            ),
                        )
                        yield self._row(
                            "Scan Interval (sec)",
                            Input(
                                str(self._config.scan_interval),
                                id="scan_interval",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Dashboard Refresh (sec)",
                            Input(
                                str(self._config.dashboard_refresh_rate),
                                id="dashboard_refresh_rate",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Show All ETFs",
                            Switch(value=self._config.show_all_etfs, id="show_all_etfs"),
                        )
                        yield self._row(
                            "Fetch Holdings",
                            Switch(value=self._config.fetch_holdings, id="fetch_holdings"),
                        )
                        yield self._row(
                            "Top Holdings Count",
                            Input(
                                str(self._config.top_holdings_count),
                                id="top_holdings_count",
                                classes="form-control",
                            ),
                        )
                with TabPane("MTF Analysis", id="tab-mtf"):
                    with VerticalScroll(classes="settings-tab"):
                        yield Static("Multi-Timeframe Analysis", classes="section-title")
                        yield self._row(
                            "MTF Enabled",
                            Switch(value=self._config.mtf.enabled, id="mtf_enabled"),
                        )
                        yield self._row(
                            "Timeframes (comma-separated)",
                            Input(
                                ", ".join(self._config.mtf.timeframes),
                                id="mtf_timeframes",
                                classes="form-control",
                                placeholder="1d, 4h, 1h",
                            ),
                        )
                        yield self._row(
                            "Minimum Confidence",
                            Select(
                                [
                                    ("Very High", "very_high"),
                                    ("High", "high"),
                                    ("Moderate", "moderate"),
                                    ("Low", "low"),
                                ],
                                value=self._config.mtf.min_confidence,
                                id="mtf_min_confidence",
                            ),
                        )
                        yield self._row(
                            "Require Alignment",
                            Switch(
                                value=self._config.mtf.require_alignment,
                                id="mtf_require_alignment",
                            ),
                        )
                        yield self._row(
                            "Bars per Timeframe",
                            Input(
                                str(self._config.mtf.bars_per_timeframe),
                                id="mtf_bars_per_timeframe",
                                classes="form-control",
                            ),
                        )
                with TabPane("Sectors", id="tab-sectors"):
                    with VerticalScroll(classes="settings-tab"):
                        selections = [
                            Selection(
                                f"{name} ({SECTOR_ETFS[name]['symbol']})",
                                name,
                                initial_state=name in self._config.active_sectors,
                            )
                            for name in SECTOR_ETFS
                        ]
                        yield Static("Active Sectors", classes="section-title")
                        yield SelectionList(*selections, id="active_sectors")
                        yield Static(
                            "Custom Symbols (comma or space separated)",
                            classes="section-title",
                        )
                        yield Input(
                            " ".join(self._config.custom_symbols),
                            id="custom_symbols",
                            classes="form-control",
                            placeholder="XLK XLF XLV",
                        )
                with TabPane("Filters", id="tab-filters"):
                    with VerticalScroll(classes="settings-tab"):
                        yield Static("Volume", classes="section-title")
                        yield self._row(
                            "Volume Enabled",
                            Switch(value=self._config.filters.volume_enabled, id="volume_enabled"),
                        )
                        yield self._row(
                            "Volume Multiplier",
                            Input(
                                str(self._config.filters.volume_multiplier),
                                id="volume_multiplier",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Volume Lookback",
                            Input(
                                str(self._config.filters.volume_lookback),
                                id="volume_lookback",
                                classes="form-control",
                            ),
                        )
                        yield Static("RSI", classes="section-title")
                        yield self._row(
                            "RSI Enabled",
                            Switch(value=self._config.filters.rsi_enabled, id="rsi_enabled"),
                        )
                        yield self._row(
                            "RSI Period",
                            Input(
                                str(self._config.filters.rsi_period),
                                id="rsi_period",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "RSI Overbought",
                            Input(
                                str(self._config.filters.rsi_overbought),
                                id="rsi_overbought",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "RSI Oversold",
                            Input(
                                str(self._config.filters.rsi_oversold),
                                id="rsi_oversold",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "RSI Neutral Low",
                            Input(
                                str(self._config.filters.rsi_neutral_zone[0]),
                                id="rsi_neutral_low",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "RSI Neutral High",
                            Input(
                                str(self._config.filters.rsi_neutral_zone[1]),
                                id="rsi_neutral_high",
                                classes="form-control",
                            ),
                        )
                        yield Static("ADX", classes="section-title")
                        yield self._row(
                            "ADX Enabled",
                            Switch(value=self._config.filters.adx_enabled, id="adx_enabled"),
                        )
                        yield self._row(
                            "ADX Period",
                            Input(
                                str(self._config.filters.adx_period),
                                id="adx_period",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "ADX Min Strength",
                            Input(
                                str(self._config.filters.adx_min_strength),
                                id="adx_min_strength",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "ADX Strong Trend",
                            Input(
                                str(self._config.filters.adx_strong_trend),
                                id="adx_strong_trend",
                                classes="form-control",
                            ),
                        )
                        yield Static("VWAP", classes="section-title")
                        yield self._row(
                            "VWAP Enabled",
                            Switch(value=self._config.filters.vwap_enabled, id="vwap_enabled"),
                        )
                        yield self._row(
                            "VWAP Confirmation",
                            Switch(
                                value=self._config.filters.vwap_confirmation,
                                id="vwap_confirmation",
                            ),
                        )
                        yield Static("ATR", classes="section-title")
                        yield self._row(
                            "ATR Enabled",
                            Switch(value=self._config.filters.atr_enabled, id="atr_enabled"),
                        )
                        yield self._row(
                            "ATR Period",
                            Input(
                                str(self._config.filters.atr_period),
                                id="atr_period",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "ATR Min %",
                            Input(
                                str(self._config.filters.atr_min_threshold),
                                id="atr_min_threshold",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "ATR Max %",
                            Input(
                                str(self._config.filters.atr_max_threshold),
                                id="atr_max_threshold",
                                classes="form-control",
                            ),
                        )
                        yield Static("MACD", classes="section-title")
                        yield self._row(
                            "MACD Enabled",
                            Switch(value=self._config.filters.macd_enabled, id="macd_enabled"),
                        )
                        yield self._row(
                            "MACD Fast",
                            Input(
                                str(self._config.filters.macd_fast),
                                id="macd_fast",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "MACD Slow",
                            Input(
                                str(self._config.filters.macd_slow),
                                id="macd_slow",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "MACD Signal",
                            Input(
                                str(self._config.filters.macd_signal),
                                id="macd_signal",
                                classes="form-control",
                            ),
                        )
                        yield Static("Time Filter", classes="section-title")
                        yield self._row(
                            "Time Filter Enabled",
                            Switch(
                                value=self._config.filters.time_filter_enabled,
                                id="time_filter_enabled",
                            ),
                        )
                        yield self._row(
                            "Avoid First Minutes",
                            Input(
                                str(self._config.filters.avoid_first_minutes),
                                id="avoid_first_minutes",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Avoid Last Minutes",
                            Input(
                                str(self._config.filters.avoid_last_minutes),
                                id="avoid_last_minutes",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Trading Start (HH:MM)",
                            Input(
                                self._config.filters.trading_start_time,
                                id="trading_start_time",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Trading End (HH:MM)",
                            Input(
                                self._config.filters.trading_end_time,
                                id="trading_end_time",
                                classes="form-control",
                            ),
                        )
                with TabPane("Alerts", id="tab-alerts"):
                    with VerticalScroll(classes="settings-tab"):
                        yield self._row(
                            "Console Alerts",
                            Switch(value=self._config.alerts.console_enabled, id="console_enabled"),
                        )
                        yield self._row(
                            "Console Colors",
                            Switch(value=self._config.alerts.console_colors, id="console_colors"),
                        )
                        yield self._row(
                            "Desktop Alerts",
                            Switch(value=self._config.alerts.desktop_enabled, id="desktop_enabled"),
                        )
                        yield self._row(
                            "Desktop Sound",
                            Switch(value=self._config.alerts.desktop_sound, id="desktop_sound"),
                        )
                        yield Static("Telegram", classes="section-title")
                        yield self._row(
                            "Telegram Enabled",
                            Switch(
                                value=self._config.alerts.telegram_enabled,
                                id="telegram_enabled",
                            ),
                        )
                        yield self._row(
                            "Telegram Bot Token",
                            Input(
                                self._config.alerts.telegram_bot_token.get_secret_value()
                                if self._config.alerts.telegram_bot_token
                                else "",
                                id="telegram_bot_token",
                                classes="form-control",
                                password=True,
                            ),
                        )
                        yield self._row(
                            "Telegram Chat ID",
                            Input(
                                self._config.alerts.telegram_chat_id or "",
                                id="telegram_chat_id",
                                classes="form-control",
                            ),
                        )
                        yield Static("Discord", classes="section-title")
                        yield self._row(
                            "Discord Enabled",
                            Switch(
                                value=self._config.alerts.discord_enabled,
                                id="discord_enabled",
                            ),
                        )
                        yield self._row(
                            "Discord Webhook",
                            Input(
                                self._config.alerts.discord_webhook_url.get_secret_value()
                                if self._config.alerts.discord_webhook_url
                                else "",
                                id="discord_webhook_url",
                                classes="form-control",
                            ),
                        )
                        yield Static("Email", classes="section-title")
                        yield self._row(
                            "Email Enabled",
                            Switch(value=self._config.alerts.email_enabled, id="email_enabled"),
                        )
                        yield self._row(
                            "SMTP Server",
                            Input(
                                self._config.alerts.email_smtp_server or "",
                                id="email_smtp_server",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Recipients",
                            Input(
                                ", ".join(self._config.alerts.email_recipients),
                                id="email_recipients",
                                classes="form-control",
                            ),
                        )
                with TabPane("Data", id="tab-data"):
                    with VerticalScroll(classes="settings-tab"):
                        yield self._row(
                            "Yahoo Enabled",
                            Switch(
                                value=self._config.data_provider.yahoo_enabled,
                                id="yahoo_enabled",
                            ),
                        )
                        yield Static("Alpaca", classes="section-title")
                        yield self._row(
                            "Alpaca Enabled",
                            Switch(
                                value=self._config.data_provider.alpaca_enabled,
                                id="alpaca_enabled",
                            ),
                        )
                        yield self._row(
                            "Alpaca API Key",
                            Input(
                                self._config.data_provider.alpaca_api_key.get_secret_value()
                                if self._config.data_provider.alpaca_api_key
                                else "",
                                id="alpaca_api_key",
                                classes="form-control",
                                password=True,
                            ),
                        )
                        yield self._row(
                            "Alpaca Secret",
                            Input(
                                self._config.data_provider.alpaca_secret_key.get_secret_value()
                                if self._config.data_provider.alpaca_secret_key
                                else "",
                                id="alpaca_secret_key",
                                classes="form-control",
                                password=True,
                            ),
                        )
                        yield self._row(
                            "Alpaca Paper",
                            Switch(
                                value=self._config.data_provider.alpaca_paper,
                                id="alpaca_paper",
                            ),
                        )
                        yield Static("Polygon", classes="section-title")
                        yield self._row(
                            "Polygon Enabled",
                            Switch(
                                value=self._config.data_provider.polygon_enabled,
                                id="polygon_enabled",
                            ),
                        )
                        yield self._row(
                            "Polygon API Key",
                            Input(
                                self._config.data_provider.polygon_api_key.get_secret_value()
                                if self._config.data_provider.polygon_api_key
                                else "",
                                id="polygon_api_key",
                                classes="form-control",
                                password=True,
                            ),
                        )
                        yield Static("Rate Limits", classes="section-title")
                        yield self._row(
                            "Request Delay (ms)",
                            Input(
                                str(self._config.data_provider.request_delay_ms),
                                id="request_delay_ms",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Max Concurrent Requests",
                            Input(
                                str(self._config.data_provider.max_concurrent_requests),
                                id="max_concurrent_requests",
                                classes="form-control",
                            ),
                        )
                with TabPane("Backtest", id="tab-backtest"):
                    with VerticalScroll(classes="settings-tab"):
                        yield self._row(
                            "Backtest Enabled",
                            Switch(value=self._config.backtest.enabled, id="backtest_enabled"),
                        )
                        yield self._row(
                            "Start Date (YYYY-MM-DD)",
                            Input(
                                self._config.backtest.start_date or "",
                                id="backtest_start_date",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "End Date (YYYY-MM-DD)",
                            Input(
                                self._config.backtest.end_date or "",
                                id="backtest_end_date",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Initial Capital",
                            Input(
                                str(self._config.backtest.initial_capital),
                                id="backtest_initial_capital",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Position Size %",
                            Input(
                                str(self._config.backtest.position_size_pct),
                                id="backtest_position_size_pct",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Commission per Trade",
                            Input(
                                str(self._config.backtest.commission_per_trade),
                                id="backtest_commission_per_trade",
                                classes="form-control",
                            ),
                        )
                        yield self._row(
                            "Slippage %",
                            Input(
                                str(self._config.backtest.slippage_pct),
                                id="backtest_slippage_pct",
                                classes="form-control",
                            ),
                        )
                with TabPane("Clouds", id="tab-clouds"):
                    with VerticalScroll(classes="settings-tab"):
                        for key in self._cloud_keys:
                            cloud = self._config.ema_clouds[key]
                            with Collapsible(title=f"{cloud.name} ({key})", collapsed=True):
                                yield self._row(
                                    "Enabled",
                                    Switch(value=cloud.enabled, id=f"cloud-{key}-enabled"),
                                )
                                yield self._row(
                                    "Fast Period",
                                    Input(
                                        str(cloud.fast_period),
                                        id=f"cloud-{key}-fast_period",
                                        classes="form-control",
                                    ),
                                )
                                yield self._row(
                                    "Slow Period",
                                    Input(
                                        str(cloud.slow_period),
                                        id=f"cloud-{key}-slow_period",
                                        classes="form-control",
                                    ),
                                )
                                yield self._row(
                                    "Name",
                                    Input(
                                        cloud.name,
                                        id=f"cloud-{key}-name",
                                        classes="form-control",
                                    ),
                                )
                                yield self._row(
                                    "Description",
                                    Input(
                                        cloud.description,
                                        id=f"cloud-{key}-description",
                                        classes="form-control",
                                    ),
                                )
                                yield self._row(
                                    "Bullish Color",
                                    Input(
                                        cloud.color_bullish,
                                        id=f"cloud-{key}-color_bullish",
                                        classes="form-control",
                                    ),
                                )
                                yield self._row(
                                    "Bearish Color",
                                    Input(
                                        cloud.color_bearish,
                                        id=f"cloud-{key}-color_bearish",
                                        classes="form-control",
                                    ),
                                )
            with Horizontal(id="settings-actions"):
                yield Button("Apply & Save", id="settings-apply", variant="success")
                yield Button("Cancel", id="settings-cancel", variant="error")

    def _row(self, label: str, widget) -> Horizontal:
        return Horizontal(
            Static(label, classes="form-label"),
            widget,
            classes="form-row",
        )

    def _read_input(self, field_id: str) -> str:
        return self.query_one(f"#{field_id}", Input).value.strip()

    def _read_int(self, field_id: str) -> int:
        value = self._read_input(field_id)
        return int(value)

    def _read_float(self, field_id: str) -> float:
        value = self._read_input(field_id)
        return float(value)

    def _read_optional(self, field_id: str) -> str | None:
        value = self._read_input(field_id)
        return value or None

    def _read_switch(self, field_id: str) -> bool:
        return self.query_one(f"#{field_id}", Switch).value

    def action_cancel(self) -> None:
        self.dismiss(self._config)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "settings-cancel":
            self.dismiss(self._config)
            return
        if event.button.id != "settings-apply":
            return

        try:
            config_dict = self._config.model_dump()
            config_dict["trading_style"] = self.query_one("#trading_style", Select).value
            config_dict["scan_interval"] = self._read_int("scan_interval")
            config_dict["dashboard_refresh_rate"] = self._read_int("dashboard_refresh_rate")
            config_dict["show_all_etfs"] = self._read_switch("show_all_etfs")
            config_dict["fetch_holdings"] = self._read_switch("fetch_holdings")
            config_dict["top_holdings_count"] = self._read_int("top_holdings_count")

            sectors = self.query_one("#active_sectors", SelectionList).selected
            config_dict["active_sectors"] = list(sectors)
            symbols_raw = self._read_input("custom_symbols")
            symbols = [
                s.strip().upper() for s in symbols_raw.replace(",", " ").split() if s.strip()
            ]
            config_dict["custom_symbols"] = symbols

            mtf = config_dict["mtf"]
            mtf["enabled"] = self._read_switch("mtf_enabled")
            timeframes_raw = self._read_input("mtf_timeframes")
            mtf["timeframes"] = [tf.strip() for tf in timeframes_raw.split(",") if tf.strip()]
            mtf["min_confidence"] = self.query_one("#mtf_min_confidence", Select).value
            mtf["require_alignment"] = self._read_switch("mtf_require_alignment")
            mtf["bars_per_timeframe"] = self._read_int("mtf_bars_per_timeframe")

            filters = config_dict["filters"]
            filters["volume_enabled"] = self._read_switch("volume_enabled")
            filters["volume_multiplier"] = self._read_float("volume_multiplier")
            filters["volume_lookback"] = self._read_int("volume_lookback")
            filters["rsi_enabled"] = self._read_switch("rsi_enabled")
            filters["rsi_period"] = self._read_int("rsi_period")
            filters["rsi_overbought"] = self._read_float("rsi_overbought")
            filters["rsi_oversold"] = self._read_float("rsi_oversold")
            filters["rsi_neutral_zone"] = (
                self._read_float("rsi_neutral_low"),
                self._read_float("rsi_neutral_high"),
            )
            filters["adx_enabled"] = self._read_switch("adx_enabled")
            filters["adx_period"] = self._read_int("adx_period")
            filters["adx_min_strength"] = self._read_float("adx_min_strength")
            filters["adx_strong_trend"] = self._read_float("adx_strong_trend")
            filters["vwap_enabled"] = self._read_switch("vwap_enabled")
            filters["vwap_confirmation"] = self._read_switch("vwap_confirmation")
            filters["atr_enabled"] = self._read_switch("atr_enabled")
            filters["atr_period"] = self._read_int("atr_period")
            filters["atr_min_threshold"] = self._read_float("atr_min_threshold")
            filters["atr_max_threshold"] = self._read_float("atr_max_threshold")
            filters["macd_enabled"] = self._read_switch("macd_enabled")
            filters["macd_fast"] = self._read_int("macd_fast")
            filters["macd_slow"] = self._read_int("macd_slow")
            filters["macd_signal"] = self._read_int("macd_signal")
            filters["time_filter_enabled"] = self._read_switch("time_filter_enabled")
            filters["avoid_first_minutes"] = self._read_int("avoid_first_minutes")
            filters["avoid_last_minutes"] = self._read_int("avoid_last_minutes")
            filters["trading_start_time"] = self._read_input("trading_start_time")
            filters["trading_end_time"] = self._read_input("trading_end_time")

            alerts = config_dict["alerts"]
            alerts["console_enabled"] = self._read_switch("console_enabled")
            alerts["console_colors"] = self._read_switch("console_colors")
            alerts["desktop_enabled"] = self._read_switch("desktop_enabled")
            alerts["desktop_sound"] = self._read_switch("desktop_sound")
            alerts["telegram_enabled"] = self._read_switch("telegram_enabled")
            alerts["telegram_bot_token"] = self._read_optional("telegram_bot_token")
            alerts["telegram_chat_id"] = self._read_optional("telegram_chat_id")
            alerts["discord_enabled"] = self._read_switch("discord_enabled")
            alerts["discord_webhook_url"] = self._read_optional("discord_webhook_url")
            alerts["email_enabled"] = self._read_switch("email_enabled")
            alerts["email_smtp_server"] = self._read_optional("email_smtp_server")
            recipients = self._read_input("email_recipients")
            alerts["email_recipients"] = [r.strip() for r in recipients.split(",") if r.strip()]

            data_provider = config_dict["data_provider"]
            data_provider["yahoo_enabled"] = self._read_switch("yahoo_enabled")
            data_provider["alpaca_enabled"] = self._read_switch("alpaca_enabled")
            data_provider["alpaca_api_key"] = self._read_optional("alpaca_api_key")
            data_provider["alpaca_secret_key"] = self._read_optional("alpaca_secret_key")
            data_provider["alpaca_paper"] = self._read_switch("alpaca_paper")
            data_provider["polygon_enabled"] = self._read_switch("polygon_enabled")
            data_provider["polygon_api_key"] = self._read_optional("polygon_api_key")
            data_provider["request_delay_ms"] = self._read_int("request_delay_ms")
            data_provider["max_concurrent_requests"] = self._read_int("max_concurrent_requests")

            backtest = config_dict["backtest"]
            backtest["enabled"] = self._read_switch("backtest_enabled")
            backtest["start_date"] = self._read_optional("backtest_start_date")
            backtest["end_date"] = self._read_optional("backtest_end_date")
            backtest["initial_capital"] = self._read_float("backtest_initial_capital")
            backtest["position_size_pct"] = self._read_float("backtest_position_size_pct")
            backtest["commission_per_trade"] = self._read_float("backtest_commission_per_trade")
            backtest["slippage_pct"] = self._read_float("backtest_slippage_pct")

            clouds = config_dict["ema_clouds"]
            for key in self._cloud_keys:
                clouds[key]["enabled"] = self._read_switch(f"cloud-{key}-enabled")
                clouds[key]["fast_period"] = self._read_int(f"cloud-{key}-fast_period")
                clouds[key]["slow_period"] = self._read_int(f"cloud-{key}-slow_period")
                clouds[key]["name"] = self._read_input(f"cloud-{key}-name")
                clouds[key]["description"] = self._read_input(f"cloud-{key}-description")
                clouds[key]["color_bullish"] = self._read_input(f"cloud-{key}-color_bullish")
                clouds[key]["color_bearish"] = self._read_input(f"cloud-{key}-color_bearish")

            new_config = ScannerConfig.model_validate(config_dict)
            issues = new_config.validate_config()
            if issues:
                self.notify("Settings validation: " + "; ".join(issues), severity="error")
                return
        except (ValueError, TypeError) as exc:
            self.notify(f"Settings error: {exc}", severity="error")
            return

        try:
            saved_path = save_user_config(new_config)
        except OSError as exc:
            self.notify(f"Settings save failed: {exc}", severity="error")
        else:
            self.notify(f"Settings saved to {saved_path}", severity="information")

        self._on_apply(new_config)
        self.dismiss(new_config)
