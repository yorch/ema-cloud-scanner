"""
Enhanced CLI with comprehensive feature support.

Adds support for:
- Backtesting
- Multiple data providers
- Email notifications
- Custom symbols
- Filter controls
- Monitoring/stats
- Cache management
- Signal cooldown configuration
"""

import asyncio
import json
import logging
import os
import re
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_cache_dir, user_log_dir
from pydantic import SecretStr
from rich.console import Console
from rich.table import Table

from ema_cloud_cli.config_store import load_config_from_path, load_user_config
from ema_cloud_cli.constants import APP_NAME
from ema_cloud_cli.dashboard import SimpleDashboard, TerminalDashboard
from ema_cloud_cli.settings import get_cli_settings
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle
from ema_cloud_lib.backtesting.engine import Backtester
from ema_cloud_lib.config.settings import ETF_SUBSETS, SYMBOL_TO_SECTOR
from ema_cloud_lib.data_providers.base import DataProviderManager, api_call_tracker
from ema_cloud_lib.reports import CompositeDashboard, ReportDashboard

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(
    name="ema-scanner",
    help="EMA Cloud Sector Scanner - Real-time trading signal scanner with comprehensive features",
    add_completion=False,
)


def _parse_log_rotation(rotation: str | None) -> int | None:
    """Parse size-based rotation strings like 'size:10MB'."""
    if not rotation:
        return None
    match = re.match(r"^size:(\d+)(KB|MB|GB)$", rotation.strip(), re.IGNORECASE)
    if not match:
        return None
    size = int(match.group(1))
    unit = match.group(2).upper()
    multiplier = {"KB": 1024, "MB": 1024**2, "GB": 1024**3}[unit]
    return size * multiplier


def _parse_log_retention(retention: str | None) -> int | None:
    """Parse retention strings like '7 days' to backup count."""
    if not retention:
        return None
    match = re.match(r"^(\d+)", retention.strip())
    if not match:
        return None
    return int(match.group(1))


def _param_is_default(ctx: typer.Context, name: str) -> bool:
    """
    Return True if parameter came from defaults (not explicitly provided by user).

    Args:
        ctx: Typer context
        name: Parameter name to check

    Returns:
        True if parameter is using default value
    """
    try:
        # Typer uses Click internally - check if param was explicitly set
        # If parameter wasn't explicitly set, it won't be in params
        if name not in ctx.params:
            return True

        # Find the parameter definition in the command's params list
        for param in ctx.command.params:
            if param.name == name:
                # Compare current value with default
                return ctx.params.get(name) == param.default

        # If we couldn't find the param definition, assume it's default
        return True
    except (AttributeError, KeyError, IndexError):
        # If we can't determine, assume it's default
        return True


def _parse_bool(value: str) -> bool | None:
    """Parse common truthy/falsey strings."""
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None


def _determine_log_level(verbose: int, cli_settings) -> int:
    """
    Determine log level with clear precedence: CLI flag > settings > default.

    Args:
        verbose: Verbose count from CLI (-v = 1, -vv = 2)
        cli_settings: CLI settings instance

    Returns:
        Logging level constant
    """
    if verbose >= 2:
        return logging.DEBUG
    elif verbose == 1:
        return logging.INFO
    elif cli_settings.log_level:
        return getattr(logging, cli_settings.log_level, logging.INFO)
    return logging.INFO


def setup_logging(verbose: int = 0, use_dashboard: bool = True):
    """
    Configure logging with file or console output.

    Args:
        verbose: Verbosity level (0=INFO, 1=INFO, 2+=DEBUG)
        use_dashboard: Whether dashboard is being used (affects output target)
    """
    cli_settings = get_cli_settings()
    level = _determine_log_level(verbose, cli_settings)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    if use_dashboard:
        # Write logs to file when using TUI dashboard
        log_dir = cli_settings.log_dir or Path(user_log_dir(APP_NAME, appauthor=False))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / cli_settings.log_filename
        max_bytes = _parse_log_rotation(cli_settings.log_rotation)
        backup_count = _parse_log_retention(cli_settings.log_retention) or 0
        handler: logging.Handler
        if max_bytes:
            handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        else:
            handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger.addHandler(handler)
        root_logger.setLevel(level)

        # Suppress noisy third-party loggers when using dashboard
        logging.getLogger("aiohttp").setLevel(logging.WARNING)
        logging.getLogger("yfinance").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    else:
        # Console output when no dashboard
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )


async def async_main(
    scanner_config: ScannerConfig,
    no_dashboard: bool,
    all_hours: bool,
    once: bool,
    report_dir: Path | None = None,
):
    """Async main logic"""
    # Create scanner
    scanner = EMACloudScanner(scanner_config)

    # Initialize report writer if requested
    report_dashboard: ReportDashboard | None = None
    if report_dir:
        report_dashboard = ReportDashboard(report_dir)
        scanner.add_cycle_callback(report_dashboard.flush_report)

    # Initialize dashboard if requested
    dashboard: TerminalDashboard | SimpleDashboard | CompositeDashboard | None = None
    dashboard_task = None
    scanner_task = None
    shutdown_event = asyncio.Event()

    def request_shutdown():
        logger.info("Shutting down...")
        scanner.stop()
        shutdown_event.set()
        if dashboard:
            dashboard.stop()

    if not no_dashboard:
        try:
            dashboard = TerminalDashboard(
                refresh_rate=scanner_config.dashboard_refresh_rate,
                config=scanner_config,
                on_quit=request_shutdown,
                on_config_update=scanner.apply_config,
            )
        except (RuntimeError, ImportError, AttributeError, OSError):
            dashboard = SimpleDashboard()

        # Compose with report dashboard if both are active
        if report_dashboard:
            dashboard = CompositeDashboard(dashboard, report_dashboard)

        scanner.set_dashboard(dashboard)
    elif report_dashboard:
        # Headless with reports: use report dashboard as the dashboard
        scanner.set_dashboard(report_dashboard)

    # Handle shutdown signals
    def signal_handler(sig, frame):
        request_shutdown()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start dashboard in background if available
    if dashboard and hasattr(dashboard, "run_async"):
        dashboard_task = asyncio.create_task(dashboard.run_async())

    try:
        # Run scanner
        if once:
            await scanner.run_scan_cycle()
        else:
            scanner_task = asyncio.create_task(
                scanner.run(
                    scan_interval_seconds=None,
                    market_hours_only=not all_hours,
                )
            )
            await shutdown_event.wait()
    finally:
        if scanner_task:
            scanner_task.cancel()
            try:
                await scanner_task
            except asyncio.CancelledError:
                pass
        if dashboard:
            dashboard.stop()
        if dashboard_task:
            dashboard_task.cancel()
            try:
                await dashboard_task
            except asyncio.CancelledError:
                pass


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    # Trading style
    style: Annotated[
        str,
        typer.Option(
            "--style",
            "-s",
            help="Trading style preset",
            case_sensitive=False,
        ),
    ] = "intraday",
    # Symbols
    etfs: Annotated[
        list[str] | None,
        typer.Option("--etfs", "-e", help="Specific sector ETFs to scan (e.g., XLK XLF XLV)"),
    ] = None,
    subset: Annotated[
        str | None,
        typer.Option("--subset", help="ETF subset to scan", case_sensitive=False),
    ] = None,
    custom_symbols: Annotated[
        list[str] | None,
        typer.Option("--custom-symbols", help="Additional custom symbols (stocks, ETFs, indices)"),
    ] = None,
    # Scan configuration
    interval: Annotated[
        int,
        typer.Option("--interval", "-i", help="Scan interval in seconds"),
    ] = 60,
    once: Annotated[
        bool,
        typer.Option("--once", help="Run a single scan and exit"),
    ] = False,
    all_hours: Annotated[
        bool,
        typer.Option("--all-hours", help="Scan during extended hours (not just market hours)"),
    ] = False,
    # Timeframe configuration
    primary_timeframe: Annotated[
        str | None,
        typer.Option("--timeframe", "-t", help="Primary timeframe (e.g., 1m, 5m, 10m, 1h, 4h, 1d)"),
    ] = None,
    confirmation_timeframes: Annotated[
        list[str] | None,
        typer.Option(
            "--confirm-timeframes",
            help="Confirmation timeframes for multi-timeframe analysis (can specify multiple)",
        ),
    ] = None,
    disable_mtf: Annotated[
        bool,
        typer.Option("--disable-mtf", help="Disable multi-timeframe confirmation"),
    ] = False,
    # EMA Cloud configuration
    enable_clouds: Annotated[
        list[str] | None,
        typer.Option(
            "--enable-clouds",
            help="Enable specific clouds: trend_line, pullback, momentum, trend_confirmation, long_term, major_trend",
        ),
    ] = None,
    disable_clouds: Annotated[
        list[str] | None,
        typer.Option("--disable-clouds", help="Disable specific clouds by name"),
    ] = None,
    cloud_thickness: Annotated[
        float | None,
        typer.Option(
            "--cloud-thickness", help="Minimum cloud thickness percentage (e.g., 0.05 for 0.05%)"
        ),
    ] = None,
    # Holdings
    scan_holdings: Annotated[
        bool,
        typer.Option(
            "--scan-holdings", help="Enable scanning of individual stocks within sector holdings"
        ),
    ] = False,
    holdings_count: Annotated[
        int,
        typer.Option("--holdings-count", help="Number of top holdings to scan per ETF"),
    ] = 10,
    holdings_concurrent: Annotated[
        int,
        typer.Option("--holdings-concurrent", help="Maximum concurrent stock scans per ETF"),
    ] = 5,
    # Dashboard
    no_dashboard: Annotated[
        bool,
        typer.Option("--no-dashboard", help="Disable terminal dashboard"),
    ] = False,
    refresh_rate: Annotated[
        int | None,
        typer.Option("--refresh-rate", help="Dashboard refresh rate in seconds"),
    ] = None,
    # Data provider
    provider: Annotated[
        str | None,
        typer.Option("--provider", help="Data provider: yahoo, alpaca, polygon"),
    ] = None,
    alpaca_key: Annotated[
        str | None,
        typer.Option("--alpaca-key", help="Alpaca API key", envvar="ALPACA_API_KEY"),
    ] = None,
    alpaca_secret: Annotated[
        str | None,
        typer.Option("--alpaca-secret", help="Alpaca secret key", envvar="ALPACA_SECRET_KEY"),
    ] = None,
    alpaca_paper: Annotated[
        bool,
        typer.Option("--alpaca-paper/--alpaca-live", help="Use Alpaca paper trading"),
    ] = True,
    polygon_key: Annotated[
        str | None,
        typer.Option("--polygon-key", help="Polygon.io API key", envvar="POLYGON_API_KEY"),
    ] = None,
    # Filters
    enable_volume: Annotated[
        bool | None,
        typer.Option("--enable-volume/--disable-volume", help="Volume filter"),
    ] = None,
    enable_rsi: Annotated[
        bool | None,
        typer.Option("--enable-rsi/--disable-rsi", help="RSI filter"),
    ] = None,
    enable_adx: Annotated[
        bool | None,
        typer.Option("--enable-adx/--disable-adx", help="ADX filter"),
    ] = None,
    enable_vwap: Annotated[
        bool | None,
        typer.Option("--enable-vwap/--disable-vwap", help="VWAP filter"),
    ] = None,
    enable_atr: Annotated[
        bool | None,
        typer.Option("--enable-atr/--disable-atr", help="ATR filter"),
    ] = None,
    enable_macd: Annotated[
        bool | None,
        typer.Option("--enable-macd/--disable-macd", help="MACD filter"),
    ] = None,
    # Filter parameters
    rsi_period: Annotated[
        int | None,
        typer.Option("--rsi-period", help="RSI calculation period"),
    ] = None,
    adx_period: Annotated[
        int | None,
        typer.Option("--adx-period", help="ADX calculation period"),
    ] = None,
    volume_multiplier: Annotated[
        float | None,
        typer.Option("--volume-multiplier", help="Volume multiplier threshold (e.g., 1.5)"),
    ] = None,
    # Telegram notifications
    telegram_alerts: Annotated[
        bool,
        typer.Option("--telegram-alerts", help="Enable Telegram notifications"),
    ] = False,
    telegram_token: Annotated[
        str | None,
        typer.Option("--telegram-token", help="Telegram bot token", envvar="TELEGRAM_BOT_TOKEN"),
    ] = None,
    telegram_chat_id: Annotated[
        str | None,
        typer.Option("--telegram-chat-id", help="Telegram chat ID", envvar="TELEGRAM_CHAT_ID"),
    ] = None,
    # Discord notifications
    discord_alerts: Annotated[
        bool,
        typer.Option("--discord-alerts", help="Enable Discord notifications"),
    ] = False,
    discord_webhook: Annotated[
        str | None,
        typer.Option("--discord-webhook", help="Discord webhook URL", envvar="DISCORD_WEBHOOK_URL"),
    ] = None,
    # Email notifications
    email_alerts: Annotated[
        bool,
        typer.Option("--email-alerts", help="Enable email notifications"),
    ] = False,
    email_smtp_server: Annotated[
        str | None,
        typer.Option(
            "--smtp-server", help="SMTP server (e.g., smtp.gmail.com)", envvar="SMTP_SERVER"
        ),
    ] = None,
    email_smtp_port: Annotated[
        int | None,
        typer.Option("--smtp-port", help="SMTP port (587 for TLS, 465 for SSL)"),
    ] = None,
    email_username: Annotated[
        str | None,
        typer.Option("--smtp-username", help="SMTP username", envvar="SMTP_USERNAME"),
    ] = None,
    email_password: Annotated[
        str | None,
        typer.Option("--smtp-password", help="SMTP password", envvar="SMTP_PASSWORD"),
    ] = None,
    email_from: Annotated[
        str | None,
        typer.Option("--email-from", help="From email address"),
    ] = None,
    email_to: Annotated[
        list[str] | None,
        typer.Option("--email-to", help="Recipient email addresses (can specify multiple)"),
    ] = None,
    # Filter weights
    filter_weights: Annotated[
        str | None,
        typer.Option(
            "--filter-weights",
            help='Filter weights as JSON (e.g., \'{"volume":2.0,"adx":2.0}\')',
        ),
    ] = None,
    # Signal cooldown
    signal_cooldown: Annotated[
        int | None,
        typer.Option("--signal-cooldown", help="Signal cooldown in minutes (default: 15)"),
    ] = None,
    # Report output
    report_dir: Annotated[
        Path | None,
        typer.Option(
            "--report-dir",
            help="Write JSON scan reports to this directory (enables headless report output)",
            envvar="EMA_SCANNER_REPORT_DIR",
        ),
    ] = None,
    # Configuration
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config JSON file", exists=True),
    ] = None,
    print_config: Annotated[
        bool,
        typer.Option("--print-config", help="Print effective configuration and exit"),
    ] = False,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Enable verbose logging (-vv for extra detail)"
        ),
    ] = 0,
):
    """Run the EMA Cloud scanner with real-time monitoring."""
    # If a subcommand is being invoked, skip the main scanning logic
    if ctx.invoked_subcommand is not None:
        return

    # Load CLI settings
    cli_settings = get_cli_settings()

    # Apply CLI settings defaults
    if verbose == 0 and cli_settings.verbose:
        verbose = 1
    if not no_dashboard and cli_settings.no_dashboard:
        no_dashboard = True
    if not all_hours and cli_settings.all_hours:
        all_hours = True

    # Environment variable overrides for scanner defaults
    if _param_is_default(ctx, "style"):
        env_style = os.getenv("EMA_SCANNER_TRADING_STYLE")
        if env_style:
            style = env_style

    if _param_is_default(ctx, "interval"):
        env_interval = os.getenv("EMA_SCANNER_SCAN_INTERVAL")
        if env_interval:
            try:
                interval = int(env_interval)
            except ValueError:
                logger.warning("Invalid EMA_SCANNER_SCAN_INTERVAL '%s', ignoring", env_interval)

    if _param_is_default(ctx, "all_hours"):
        env_market_hours_only = os.getenv("EMA_SCANNER_MARKET_HOURS_ONLY")
        if env_market_hours_only:
            market_hours_only = _parse_bool(env_market_hours_only)
            if market_hours_only is None:
                logger.warning(
                    "Invalid EMA_SCANNER_MARKET_HOURS_ONLY '%s', ignoring",
                    env_market_hours_only,
                )
            else:
                all_hours = not market_hours_only

    if _param_is_default(ctx, "provider"):
        env_provider = os.getenv("EMA_DATA_PROVIDER")
        if env_provider:
            provider = env_provider

    if _param_is_default(ctx, "scan_holdings"):
        env_scan_holdings = os.getenv("EMA_SCANNER_SCAN_HOLDINGS")
        if env_scan_holdings:
            parsed = _parse_bool(env_scan_holdings)
            if parsed is None:
                logger.warning(
                    "Invalid EMA_SCANNER_SCAN_HOLDINGS '%s', ignoring", env_scan_holdings
                )
            else:
                scan_holdings = parsed

    if _param_is_default(ctx, "holdings_count"):
        env_holdings_count = os.getenv("EMA_SCANNER_HOLDINGS_COUNT")
        if env_holdings_count:
            try:
                holdings_count = int(env_holdings_count)
            except ValueError:
                logger.warning(
                    "Invalid EMA_SCANNER_HOLDINGS_COUNT '%s', ignoring", env_holdings_count
                )

    if _param_is_default(ctx, "holdings_concurrent"):
        env_holdings_concurrent = os.getenv("EMA_SCANNER_HOLDINGS_CONCURRENT")
        if env_holdings_concurrent:
            try:
                holdings_concurrent = int(env_holdings_concurrent)
            except ValueError:
                logger.warning(
                    "Invalid EMA_SCANNER_HOLDINGS_CONCURRENT '%s', ignoring",
                    env_holdings_concurrent,
                )

    setup_logging(verbose, use_dashboard=not no_dashboard)

    # Inform user where logs are written when using dashboard
    if not no_dashboard:
        log_dir = cli_settings.log_dir or Path(user_log_dir(APP_NAME, appauthor=False))
        log_file = log_dir / cli_settings.log_filename
        typer.echo(f"Logs: {log_file}")

    # Validate style choice
    valid_styles = ["scalping", "intraday", "swing", "position", "long_term"]
    if style.lower() not in valid_styles:
        typer.echo(f"Error: Invalid style '{style}'. Choose from: {', '.join(valid_styles)}")
        raise typer.Exit(1)

    # Validate subset if provided
    if subset and subset not in ETF_SUBSETS:
        typer.echo(
            f"Error: Invalid subset '{subset}'. Choose from: {', '.join(ETF_SUBSETS.keys())}"
        )
        raise typer.Exit(1)

    # Validate provider
    if provider and provider.lower() not in ["yahoo", "alpaca", "polygon"]:
        typer.echo(f"Error: Invalid provider '{provider}'. Choose from: yahoo, alpaca, polygon")
        raise typer.Exit(1)

    # Load or create config
    if config:
        scanner_config = load_config_from_path(str(config))
    else:
        scanner_config = load_user_config() or ScannerConfig()

    # Apply trading style
    style_map = {
        "scalping": TradingStyle.SCALPING,
        "intraday": TradingStyle.INTRADAY,
        "swing": TradingStyle.SWING,
        "position": TradingStyle.POSITION,
        "long_term": TradingStyle.LONG_TERM,
    }
    scanner_config.trading_style = style_map.get(style.lower(), TradingStyle.INTRADAY)

    # Apply symbols
    if etfs:
        # Convert ETF symbols to sector names
        etf_list = etfs if isinstance(etfs, list) else list(etfs)
        sectors = []
        for etf in etf_list:
            etf_upper = etf.upper()
            if etf_upper in SYMBOL_TO_SECTOR:
                sectors.append(SYMBOL_TO_SECTOR[etf_upper])
            else:
                typer.echo(f"Warning: Unknown ETF symbol '{etf}', treating as custom symbol")
                scanner_config.custom_symbols.append(etf_upper)
        if sectors:
            scanner_config.active_sectors = sectors
    if subset:
        if subset in ETF_SUBSETS:
            scanner_config.active_sectors = ETF_SUBSETS[subset].copy()
        else:
            typer.echo(f"Warning: Unknown subset '{subset}'")
    if custom_symbols:
        custom_list = custom_symbols if isinstance(custom_symbols, list) else list(custom_symbols)
        scanner_config.custom_symbols.extend([s.upper() for s in custom_list])
        typer.echo(f"Custom symbols: {', '.join(scanner_config.custom_symbols)}")

    scanner_config.scan_interval = interval

    # Apply timeframe configuration
    preset = scanner_config.get_preset()
    if primary_timeframe:
        from ema_cloud_lib.config.settings import TimeframeConfig

        preset["primary_timeframe"] = TimeframeConfig(
            interval=primary_timeframe,
            display_name=primary_timeframe,
            bars_to_fetch=preset["primary_timeframe"].bars_to_fetch,
        )
        typer.echo(f"Primary timeframe: {primary_timeframe}")

    if confirmation_timeframes:
        from ema_cloud_lib.config.settings import TimeframeConfig

        preset["confirmation_timeframes"] = [
            TimeframeConfig(interval=tf, display_name=tf, bars_to_fetch=200)
            for tf in confirmation_timeframes
        ]
        typer.echo(f"Confirmation timeframes: {', '.join(confirmation_timeframes)}")

    if disable_mtf:
        preset["confirmation_timeframes"] = []
        typer.echo("Multi-timeframe confirmation disabled")

    # Apply EMA cloud configuration
    if enable_clouds:
        # Disable all clouds first, then enable specified ones
        for cloud_name in scanner_config.ema_clouds:
            scanner_config.ema_clouds[cloud_name].enabled = cloud_name in enable_clouds
        typer.echo(f"Enabled clouds: {', '.join(enable_clouds)}")

    if disable_clouds:
        for cloud_name in disable_clouds:
            if cloud_name in scanner_config.ema_clouds:
                scanner_config.ema_clouds[cloud_name].enabled = False
        typer.echo(f"Disabled clouds: {', '.join(disable_clouds)}")

    if cloud_thickness is not None:
        preset["min_cloud_thickness_pct"] = cloud_thickness
        typer.echo(f"Cloud thickness threshold: {cloud_thickness}%")

    # Apply holdings configuration
    if scan_holdings:
        scanner_config.scan_holdings = True
        scanner_config.top_holdings_count = holdings_count
        scanner_config.holdings_max_concurrent = holdings_concurrent
        typer.echo(
            f"Holdings scanning: {holdings_count} stocks per ETF, max {holdings_concurrent} concurrent"
        )

    # Apply dashboard refresh rate
    if refresh_rate:
        scanner_config.dashboard_refresh_rate = refresh_rate
    elif scanner_config.dashboard_refresh_rate == 1:
        scanner_config.dashboard_refresh_rate = cli_settings.dashboard_refresh_rate

    # Apply data provider configuration
    if provider:
        provider_lower = provider.lower()
        if provider_lower == "yahoo":
            scanner_config.data_provider.yahoo_enabled = True
            scanner_config.data_provider.alpaca_enabled = False
            scanner_config.data_provider.polygon_enabled = False
        elif provider_lower == "alpaca":
            if not alpaca_key or not alpaca_secret:
                typer.echo("Error: Alpaca requires --alpaca-key and --alpaca-secret")
                raise typer.Exit(1)
            scanner_config.data_provider.yahoo_enabled = False
            scanner_config.data_provider.alpaca_enabled = True
            scanner_config.data_provider.alpaca_api_key = SecretStr(alpaca_key)
            scanner_config.data_provider.alpaca_secret_key = SecretStr(alpaca_secret)
            scanner_config.data_provider.alpaca_paper = alpaca_paper
            typer.echo(f"Data provider: Alpaca ({'paper' if alpaca_paper else 'live'})")
        elif provider_lower == "polygon":
            if not polygon_key:
                typer.echo("Error: Polygon requires --polygon-key")
                raise typer.Exit(1)
            scanner_config.data_provider.yahoo_enabled = False
            scanner_config.data_provider.polygon_enabled = True
            scanner_config.data_provider.polygon_api_key = SecretStr(polygon_key)
            typer.echo("Data provider: Polygon.io")

    # Apply filter settings
    if enable_volume is not None:
        scanner_config.filters.volume_enabled = enable_volume
    if enable_rsi is not None:
        scanner_config.filters.rsi_enabled = enable_rsi
    if enable_adx is not None:
        scanner_config.filters.adx_enabled = enable_adx
    if enable_vwap is not None:
        scanner_config.filters.vwap_enabled = enable_vwap
    if enable_atr is not None:
        scanner_config.filters.atr_enabled = enable_atr
    if enable_macd is not None:
        scanner_config.filters.macd_enabled = enable_macd

    # Apply filter parameters
    if rsi_period:
        scanner_config.filters.rsi_period = rsi_period
    if adx_period:
        scanner_config.filters.adx_period = adx_period
    if volume_multiplier:
        scanner_config.filters.volume_multiplier = volume_multiplier

    # Apply filter weights
    if filter_weights:
        try:
            weights = json.loads(filter_weights)
            if not isinstance(weights, dict):
                typer.echo("Error: --filter-weights must be a JSON object")
                raise typer.Exit(1)
            scanner_config.filters.filter_weights.update(weights)
            typer.echo(f"Filter weights: {scanner_config.filters.filter_weights}")
        except json.JSONDecodeError as e:
            typer.echo(f"Error: Invalid JSON for --filter-weights: {e}")
            raise typer.Exit(1) from None

    # Apply Telegram configuration
    if telegram_alerts:
        if not telegram_token or not telegram_chat_id:
            typer.echo("Error: Telegram alerts require --telegram-token and --telegram-chat-id")
            raise typer.Exit(1)
        scanner_config.alerts.telegram_enabled = True
        scanner_config.alerts.telegram_bot_token = SecretStr(telegram_token)
        scanner_config.alerts.telegram_chat_id = telegram_chat_id
        typer.echo(f"Telegram alerts enabled: chat {telegram_chat_id}")
    elif telegram_token and telegram_chat_id:
        # Auto-enable if both credentials provided via env vars
        scanner_config.alerts.telegram_enabled = True
        scanner_config.alerts.telegram_bot_token = SecretStr(telegram_token)
        scanner_config.alerts.telegram_chat_id = telegram_chat_id
        typer.echo(f"Telegram alerts enabled: chat {telegram_chat_id}")

    # Apply Discord configuration
    if discord_alerts:
        if not discord_webhook:
            typer.echo("Error: Discord alerts require --discord-webhook")
            raise typer.Exit(1)
        scanner_config.alerts.discord_enabled = True
        scanner_config.alerts.discord_webhook_url = SecretStr(discord_webhook)
        typer.echo("Discord alerts enabled")
    elif discord_webhook:
        # Auto-enable if webhook provided via env var
        scanner_config.alerts.discord_enabled = True
        scanner_config.alerts.discord_webhook_url = SecretStr(discord_webhook)
        typer.echo("Discord alerts enabled")

    # Apply email configuration
    if email_alerts:
        if not all([email_smtp_server, email_username, email_password, email_from, email_to]):
            typer.echo(
                "Error: Email alerts require --smtp-server, --smtp-username, --smtp-password, --email-from, --email-to"
            )
            raise typer.Exit(1)
        scanner_config.alerts.email_enabled = True
        scanner_config.alerts.email_smtp_server = email_smtp_server
        scanner_config.alerts.email_smtp_port = email_smtp_port or 587
        scanner_config.alerts.email_username = email_username
        scanner_config.alerts.email_password = SecretStr(email_password) if email_password else None
        scanner_config.alerts.email_from_address = email_from
        scanner_config.alerts.email_recipients = list(email_to) if email_to else []
        typer.echo(f"Email alerts enabled: {', '.join(email_to or [])}")

    # Apply signal cooldown
    if signal_cooldown is not None:
        scanner_config.signal_cooldown_minutes = signal_cooldown
        typer.echo(f"Signal cooldown: {signal_cooldown} minutes")

    if print_config:
        config_dict = scanner_config.model_dump(mode="json", exclude_none=True)
        console.print_json(data=config_dict)
        raise typer.Exit(0)

    # Apply report directory from CLI settings if not explicitly set
    cli_report_dir = report_dir
    if cli_report_dir is None and cli_settings.report_dir:
        cli_report_dir = cli_settings.report_dir

    # Run async main
    asyncio.run(async_main(scanner_config, no_dashboard, all_hours, once, cli_report_dir))


@app.command()
def backtest(
    symbols: Annotated[
        list[str],
        typer.Argument(help="Symbols to backtest (e.g., XLK XLF SPY)"),
    ],
    start_date: Annotated[
        str,
        typer.Option("--start-date", help="Start date (YYYY-MM-DD)"),
    ],
    end_date: Annotated[
        str,
        typer.Option("--end-date", help="End date (YYYY-MM-DD)"),
    ],
    style: Annotated[
        str,
        typer.Option("--style", help="Trading style preset"),
    ] = "intraday",
    initial_capital: Annotated[
        float,
        typer.Option("--capital", help="Initial capital"),
    ] = 100000.0,
    position_size: Annotated[
        float,
        typer.Option("--position-size", help="Position size as % of capital"),
    ] = 10.0,
    commission: Annotated[
        float,
        typer.Option("--commission", help="Commission per trade"),
    ] = 0.0,
    slippage: Annotated[
        float,
        typer.Option("--slippage", help="Slippage as % of price"),
    ] = 0.05,
    report: Annotated[
        Path | None,
        typer.Option("--report", help="Save detailed report to JSON file"),
    ] = None,
    walk_forward: Annotated[
        bool,
        typer.Option("--walk-forward", help="Enable walk-forward validation"),
    ] = False,
    wf_in_sample: Annotated[
        int,
        typer.Option("--wf-in-sample", help="Walk-forward in-sample window size (bars)"),
    ] = 500,
    wf_out_sample: Annotated[
        int,
        typer.Option("--wf-out-sample", help="Walk-forward out-of-sample window size (bars)"),
    ] = 100,
    verbose: Annotated[
        int,
        typer.Option(
            "--verbose", "-v", count=True, help="Enable verbose logging (-vv for extra detail)"
        ),
    ] = 0,
):
    """Run backtests on historical data."""
    setup_logging(verbose, use_dashboard=False)

    mode_label = "Walk-Forward Backtest" if walk_forward else "Backtest"
    console.print(f"\n[bold cyan]Running {mode_label}[/bold cyan]")
    console.print(f"Period: {start_date} to {end_date}")
    console.print(f"Symbols: {', '.join(symbols)}")
    console.print(f"Capital: ${initial_capital:,.2f}")
    if walk_forward:
        console.print(f"Walk-forward: IS={wf_in_sample} bars, OOS={wf_out_sample} bars")
    console.print()

    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        console.print(f"[red]Error parsing dates: {e}[/red]")
        raise typer.Exit(1) from None

    # Create data manager for fetching historical data
    data_manager = DataProviderManager({"yahoo": {"enabled": True}})

    async def run_backtest():
        results = {}
        for symbol in symbols:
            console.print(f"Backtesting {symbol}...")

            # Fetch historical data
            df = await data_manager.get_historical_data(
                symbol=symbol,
                interval="1d",
                start=start_dt,
                end=end_dt,
            )

            if df is None or len(df) < 50:
                console.print(f"[yellow]Insufficient data for {symbol}[/yellow]")
                continue

            if walk_forward:
                from ema_cloud_lib.backtesting.engine import WalkForwardBacktester

                wf_backtester = WalkForwardBacktester(
                    in_sample_size=wf_in_sample,
                    out_of_sample_size=wf_out_sample,
                    initial_capital=initial_capital,
                    position_size_pct=position_size,
                    commission=commission,
                    slippage_pct=slippage,
                )
                wf_result = wf_backtester.run(df, symbol)
                console.print(wf_result.format_summary())
                results[symbol] = wf_result
            else:
                backtester = Backtester(
                    initial_capital=initial_capital,
                    position_size_pct=position_size,
                    commission=commission,
                    slippage_pct=slippage,
                )
                result = backtester.run(df, symbol)
                results[symbol] = result
                result.print_summary()

        # Comparison table (standard backtest only)
        if not walk_forward and len(results) > 1:
            backtester = Backtester(
                initial_capital=initial_capital,
                position_size_pct=position_size,
                commission=commission,
                slippage_pct=slippage,
            )
            comparison_df = backtester.compare_results(results)
            console.print("\n[bold]Comparison Across Symbols:[/bold]")

            table = Table(show_header=True, header_style="bold magenta")
            for col in comparison_df.columns:
                table.add_column(col)

            for _, row in comparison_df.iterrows():
                table.add_row(*[str(val) for val in row])

            console.print(table)

        # Save report if requested
        if report:
            report_data = {}
            for symbol, result in results.items():
                if hasattr(result, "to_dict"):
                    report_data[symbol] = result.to_dict()
                else:
                    report_data[symbol] = result.model_dump(mode="json")
            report.write_text(json.dumps(report_data, indent=2, default=str))
            console.print(f"\n[green]Report saved to {report}[/green]")

    asyncio.run(run_backtest())


@app.command()
def stats():
    """Show API usage statistics and system status."""
    console.print("\n[bold cyan]System Statistics[/bold cyan]\n")

    # API call stats
    table = Table(title="API Call Statistics", show_header=True)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Total API Calls", str(api_call_tracker.total_calls))
    table.add_row("Calls Per Minute", f"{api_call_tracker.calls_per_minute:.1f}")

    console.print(table)

    # Cache status
    cache_dir = Path(user_cache_dir(APP_NAME, appauthor=False))
    if cache_dir.exists():
        cache_files = list(cache_dir.glob("*.json"))
        cache_size = sum(f.stat().st_size for f in cache_files) / 1024  # KB

        cache_table = Table(title="Cache Status", show_header=True)
        cache_table.add_column("Metric", style="cyan")
        cache_table.add_column("Value", style="green")

        cache_table.add_row("Cache Directory", str(cache_dir))
        cache_table.add_row("Cached Files", str(len(cache_files)))
        cache_table.add_row("Cache Size", f"{cache_size:.2f} KB")

        console.print("\n")
        console.print(cache_table)
    else:
        console.print("\n[yellow]No cache directory found[/yellow]")


@app.command()
def clear_cache(
    confirm: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip confirmation"),
    ] = False,
):
    """Clear all cached data (holdings, historical data)."""
    cache_dir = Path(user_cache_dir(APP_NAME, appauthor=False))

    if not cache_dir.exists():
        console.print("[yellow]No cache directory found[/yellow]")
        return

    cache_files = list(cache_dir.glob("*.json"))

    if not cache_files:
        console.print("[yellow]Cache is already empty[/yellow]")
        return

    if not confirm:
        response = typer.confirm(f"Delete {len(cache_files)} cached files?")
        if not response:
            console.print("[yellow]Cancelled[/yellow]")
            return

    # Delete cache files
    for cache_file in cache_files:
        cache_file.unlink()

    console.print(f"[green]Cleared {len(cache_files)} cached files[/green]")


@app.command()
def config_show(
    config_path: Annotated[
        Path | None,
        typer.Argument(help="Path to config file (default: user config)"),
    ] = None,
):
    """Display configuration settings."""
    if config_path:
        if not config_path.exists():
            console.print(f"[red]Config file not found: {config_path}[/red]")
            raise typer.Exit(1)
        config = load_config_from_path(str(config_path))
    else:
        config_or_none = load_user_config()
        if not config_or_none:
            console.print("[yellow]No user config found. Using defaults.[/yellow]")
            config = ScannerConfig()
        else:
            config = config_or_none

    # Display as formatted JSON (mode='json' serializes enums to their values)
    config_dict = config.model_dump(mode="json", exclude_none=True)
    console.print_json(data=config_dict)


@app.command()
def config_save(
    output_path: Annotated[
        Path,
        typer.Argument(help="Path where to save the configuration file"),
    ],
    style: Annotated[
        str | None,
        typer.Option("--style", "-s", help="Trading style preset to save"),
    ] = None,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing file"),
    ] = False,
):
    """Save configuration to a JSON file."""
    # Check if file exists
    if output_path.exists() and not force:
        overwrite = typer.confirm(f"File {output_path} exists. Overwrite?")
        if not overwrite:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

    # Create config
    config = load_user_config() or ScannerConfig()

    # Apply style if specified
    if style:
        valid_styles = ["scalping", "intraday", "swing", "position", "long_term"]
        if style.lower() not in valid_styles:
            console.print(
                f"[red]Invalid style '{style}'. Choose from: {', '.join(valid_styles)}[/red]"
            )
            raise typer.Exit(1)

        style_map = {
            "scalping": TradingStyle.SCALPING,
            "intraday": TradingStyle.INTRADAY,
            "swing": TradingStyle.SWING,
            "position": TradingStyle.POSITION,
            "long_term": TradingStyle.LONG_TERM,
        }
        config.trading_style = style_map[style.lower()]

    # Save configuration
    try:
        config.save(str(output_path))
        console.print(f"[green]Configuration saved to {output_path}[/green]")
        console.print(f"Load with: --config {output_path}")
    except (OSError, TypeError, ValueError) as e:
        console.print(f"[red]Error saving config: {e}[/red]")
        raise typer.Exit(1) from None


def run():
    """Entry point for console script"""
    app()


if __name__ == "__main__":
    run()
