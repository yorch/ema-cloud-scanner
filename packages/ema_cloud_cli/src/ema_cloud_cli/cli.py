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
import signal
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_cache_dir, user_log_dir
from rich.console import Console
from rich.table import Table

from ema_cloud_cli.config_store import load_config_from_path, load_user_config
from ema_cloud_cli.constants import APP_NAME
from ema_cloud_cli.dashboard import SimpleDashboard, TerminalDashboard
from ema_cloud_cli.settings import get_cli_settings
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle
from ema_cloud_lib.config.settings import ETF_SUBSETS, SYMBOL_TO_SECTOR
from ema_cloud_lib.backtesting.engine import Backtester, BacktestResult
from ema_cloud_lib.data_providers.base import DataProviderManager, api_call_tracker

logger = logging.getLogger(__name__)
console = Console()

app = typer.Typer(
    name="ema-scanner",
    help="EMA Cloud Sector Scanner - Real-time trading signal scanner with comprehensive features",
    add_completion=False,
)


def setup_logging(verbose: bool = False, use_dashboard: bool = True):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    if use_dashboard:
        # Write logs to file when using TUI dashboard
        log_dir = Path(user_log_dir(APP_NAME, appauthor=False))
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "scanner.log"

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
):
    """Async main logic"""
    # Create scanner
    scanner = EMACloudScanner(scanner_config)

    # Initialize dashboard if requested
    dashboard = None
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
        except Exception:
            dashboard = SimpleDashboard()

        scanner.set_dashboard(dashboard)

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

    # Holdings
    scan_holdings: Annotated[
        bool,
        typer.Option("--scan-holdings", help="Enable scanning of individual stocks within sector holdings"),
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

    # Email notifications
    email_alerts: Annotated[
        bool,
        typer.Option("--email-alerts", help="Enable email notifications"),
    ] = False,
    email_smtp_server: Annotated[
        str | None,
        typer.Option("--smtp-server", help="SMTP server (e.g., smtp.gmail.com)", envvar="SMTP_SERVER"),
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

    # Signal cooldown
    signal_cooldown: Annotated[
        int | None,
        typer.Option("--signal-cooldown", help="Signal cooldown in minutes (default: 15)"),
    ] = None,

    # Configuration
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config JSON file", exists=True),
    ] = None,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging"),
    ] = False,
):
    """Run the EMA Cloud scanner with real-time monitoring."""
    # If a subcommand is being invoked, skip the main scanning logic
    if ctx.invoked_subcommand is not None:
        return

    # Load CLI settings
    cli_settings = get_cli_settings()

    # Apply CLI settings defaults
    if not verbose and cli_settings.verbose:
        verbose = True
    if not no_dashboard and cli_settings.no_dashboard:
        no_dashboard = True
    if not all_hours and cli_settings.all_hours:
        all_hours = True

    setup_logging(verbose, use_dashboard=not no_dashboard)

    # Inform user where logs are written when using dashboard
    if not no_dashboard:
        log_dir = Path(user_log_dir(APP_NAME, appauthor=False))
        log_file = log_dir / "scanner.log"
        typer.echo(f"Logs: {log_file}")

    # Validate style choice
    valid_styles = ["scalping", "intraday", "swing", "position", "long_term"]
    if style.lower() not in valid_styles:
        typer.echo(f"Error: Invalid style '{style}'. Choose from: {', '.join(valid_styles)}")
        raise typer.Exit(1)

    # Validate subset if provided
    if subset and subset not in ETF_SUBSETS:
        typer.echo(f"Error: Invalid subset '{subset}'. Choose from: {', '.join(ETF_SUBSETS.keys())}")
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

    # Apply holdings configuration
    if scan_holdings:
        scanner_config.scan_holdings = True
        scanner_config.top_holdings_count = holdings_count
        scanner_config.holdings_max_concurrent = holdings_concurrent
        typer.echo(f"Holdings scanning: {holdings_count} stocks per ETF, max {holdings_concurrent} concurrent")

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
            scanner_config.data_provider.alpaca_api_key = alpaca_key
            scanner_config.data_provider.alpaca_secret_key = alpaca_secret
            scanner_config.data_provider.alpaca_paper = alpaca_paper
            typer.echo(f"Data provider: Alpaca ({'paper' if alpaca_paper else 'live'})")
        elif provider_lower == "polygon":
            if not polygon_key:
                typer.echo("Error: Polygon requires --polygon-key")
                raise typer.Exit(1)
            scanner_config.data_provider.yahoo_enabled = False
            scanner_config.data_provider.polygon_enabled = True
            scanner_config.data_provider.polygon_api_key = polygon_key
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

    # Apply email configuration
    if email_alerts:
        if not all([email_smtp_server, email_username, email_password, email_from, email_to]):
            typer.echo("Error: Email alerts require --smtp-server, --smtp-username, --smtp-password, --email-from, --email-to")
            raise typer.Exit(1)
        scanner_config.alerts.email_enabled = True
        scanner_config.alerts.email_smtp_server = email_smtp_server
        scanner_config.alerts.email_smtp_port = email_smtp_port or 587
        scanner_config.alerts.email_username = email_username
        scanner_config.alerts.email_password = email_password
        scanner_config.alerts.email_from_address = email_from
        scanner_config.alerts.email_recipients = list(email_to)
        typer.echo(f"Email alerts enabled: {', '.join(email_to)}")

    # Apply signal cooldown
    if signal_cooldown is not None:
        scanner_config.signal_cooldown_minutes = signal_cooldown
        typer.echo(f"Signal cooldown: {signal_cooldown} minutes")

    # Run async main
    asyncio.run(async_main(scanner_config, no_dashboard, all_hours, once))


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
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging"),
    ] = False,
):
    """Run backtests on historical data."""
    setup_logging(verbose, use_dashboard=False)

    console.print(f"\n[bold cyan]Running Backtest[/bold cyan]")
    console.print(f"Period: {start_date} to {end_date}")
    console.print(f"Symbols: {', '.join(symbols)}")
    console.print(f"Capital: ${initial_capital:,.2f}\n")

    # Parse dates
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        console.print(f"[red]Error parsing dates: {e}[/red]")
        raise typer.Exit(1)

    # Create backtester
    backtester = Backtester(
        initial_capital=initial_capital,
        position_size_pct=position_size,
        commission=commission,
        slippage_pct=slippage,
    )

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

            # Run backtest
            result = backtester.run(df, symbol)
            results[symbol] = result

            # Print summary
            result.print_summary()

        # Comparison table
        if len(results) > 1:
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
            report_data = {
                symbol: result.to_dict()
                for symbol, result in results.items()
            }
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
        config = load_user_config()
        if not config:
            console.print("[yellow]No user config found. Using defaults.[/yellow]")
            config = ScannerConfig()

    # Display as formatted JSON (mode='json' serializes enums to their values)
    config_dict = config.model_dump(mode='json', exclude_none=True)
    console.print_json(data=config_dict)


def run():
    """Entry point for console script"""
    app()


if __name__ == "__main__":
    run()
