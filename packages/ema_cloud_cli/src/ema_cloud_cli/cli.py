"""
EMA Cloud Scanner CLI

Command-line interface for the EMA Cloud Sector Scanner.
"""

import argparse
import asyncio
import logging
import signal
import sys

from ema_cloud_cli.config_store import load_config_from_path, load_user_config
from ema_cloud_cli.dashboard import SimpleDashboard, TerminalDashboard
from ema_cloud_lib import EMACloudScanner, ScannerConfig, TradingStyle
from ema_cloud_lib.config.settings import ETF_SUBSETS

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False):
    """Configure logging"""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="EMA Cloud Sector Scanner - Real-time trading signal scanner"
    )

    parser.add_argument(
        "--style",
        "-s",
        type=str,
        choices=["scalping", "intraday", "swing", "position", "long_term"],
        default="intraday",
        help="Trading style preset (default: intraday)",
    )

    parser.add_argument(
        "--etfs", "-e", type=str, nargs="+", help="Specific ETFs to scan (e.g., XLK XLF XLV)"
    )

    parser.add_argument(
        "--subset", type=str, choices=list(ETF_SUBSETS.keys()), help="ETF subset to scan"
    )

    parser.add_argument(
        "--interval", "-i", type=int, default=60, help="Scan interval in seconds (default: 60)"
    )

    parser.add_argument("--no-dashboard", action="store_true", help="Disable terminal dashboard")

    parser.add_argument(
        "--all-hours",
        action="store_true",
        help="Scan during extended hours (not just market hours)",
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    parser.add_argument("--config", "-c", type=str, help="Path to config JSON file")

    parser.add_argument("--once", action="store_true", help="Run a single scan and exit")

    return parser.parse_args()


async def main():
    """Main entry point"""
    args = parse_args()

    setup_logging(args.verbose)

    # Load or create config
    if args.config:
        config = load_config_from_path(args.config)
    else:
        config = load_user_config() or ScannerConfig()

    # Apply CLI overrides
    style_map = {
        "scalping": TradingStyle.SCALPING,
        "intraday": TradingStyle.INTRADAY,
        "swing": TradingStyle.SWING,
        "position": TradingStyle.POSITION,
        "long_term": TradingStyle.LONG_TERM,
    }
    config.trading_style = style_map.get(args.style, TradingStyle.INTRADAY)

    if args.etfs:
        config.etf_symbols = [e.upper() for e in args.etfs]

    if args.subset:
        config.etf_subset = args.subset
    config.scan_interval = args.interval

    # Create scanner
    scanner = EMACloudScanner(config)

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

    if not args.no_dashboard:
        try:
            dashboard = TerminalDashboard(
                refresh_rate=config.dashboard_refresh_rate,
                config=config,
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
        if args.once:
            await scanner.run_scan_cycle()
        else:
            scanner_task = asyncio.create_task(
                scanner.run(
                    scan_interval_seconds=None,
                    market_hours_only=not args.all_hours,
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


def run():
    """Entry point for console script"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
