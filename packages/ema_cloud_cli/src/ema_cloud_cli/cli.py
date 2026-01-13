"""
EMA Cloud Scanner CLI

Command-line interface for the EMA Cloud Sector Scanner.
"""

import asyncio
import logging
import signal
from pathlib import Path
from typing import Annotated

import typer
from platformdirs import user_log_dir

from ema_cloud_cli.config_store import load_config_from_path, load_user_config
from ema_cloud_cli.constants import APP_NAME
from ema_cloud_cli.dashboard import SimpleDashboard, TerminalDashboard
from ema_cloud_cli.settings import get_cli_settings
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle
from ema_cloud_lib.config.settings import ETF_SUBSETS

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="ema-scanner",
    help="EMA Cloud Sector Scanner - Real-time trading signal scanner",
    add_completion=False,
)


def setup_logging(verbose: bool = False, use_dashboard: bool = True):
    """
    Configure logging.

    When dashboard is enabled, logs go to file to avoid interfering with TUI.
    When dashboard is disabled, logs go to console.
    """
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


@app.command()
def main(
    style: Annotated[
        str,
        typer.Option(
            "--style",
            "-s",
            help="Trading style preset",
            case_sensitive=False,
        ),
    ] = "intraday",
    etfs: Annotated[
        list[str] | None,
        typer.Option("--etfs", "-e", help="Specific ETFs to scan (e.g., XLK XLF XLV)"),
    ] = None,
    subset: Annotated[
        str | None,
        typer.Option("--subset", help="ETF subset to scan", case_sensitive=False),
    ] = None,
    interval: Annotated[
        int,
        typer.Option("--interval", "-i", help="Scan interval in seconds"),
    ] = 60,
    no_dashboard: Annotated[
        bool,
        typer.Option("--no-dashboard", help="Disable terminal dashboard"),
    ] = False,
    all_hours: Annotated[
        bool,
        typer.Option("--all-hours", help="Scan during extended hours (not just market hours)"),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose logging"),
    ] = False,
    config: Annotated[
        Path | None,
        typer.Option("--config", "-c", help="Path to config JSON file", exists=True),
    ] = None,
    once: Annotated[
        bool,
        typer.Option("--once", help="Run a single scan and exit"),
    ] = False,
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
):
    """Main entry point"""
    # Load CLI settings (can be customized via environment variables)
    cli_settings = get_cli_settings()

    # Apply CLI settings defaults if not explicitly set
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

    # Load or create config
    if config:
        scanner_config = load_config_from_path(str(config))
    else:
        scanner_config = load_user_config() or ScannerConfig()

    # Apply CLI overrides
    style_map = {
        "scalping": TradingStyle.SCALPING,
        "intraday": TradingStyle.INTRADAY,
        "swing": TradingStyle.SWING,
        "position": TradingStyle.POSITION,
        "long_term": TradingStyle.LONG_TERM,
    }
    scanner_config.trading_style = style_map.get(style.lower(), TradingStyle.INTRADAY)

    if etfs:
        scanner_config.etf_symbols = [e.upper() for e in etfs]

    if subset:
        scanner_config.etf_subset = subset
    scanner_config.scan_interval = interval

    # Apply holdings scanning options
    if scan_holdings:
        scanner_config.scan_holdings = True
        scanner_config.top_holdings_count = holdings_count
        scanner_config.holdings_max_concurrent = holdings_concurrent
        typer.echo(f"Holdings scanning enabled: {holdings_count} stocks per ETF, max {holdings_concurrent} concurrent")

    # Apply CLI settings for dashboard refresh rate if not customized
    if scanner_config.dashboard_refresh_rate == 1:  # Default value
        scanner_config.dashboard_refresh_rate = cli_settings.dashboard_refresh_rate

    # Run async main
    asyncio.run(async_main(scanner_config, no_dashboard, all_hours, once))


def run():
    """Entry point for console script"""
    app()


if __name__ == "__main__":
    run()
