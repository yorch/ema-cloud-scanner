"""Backtesting module for EMA Cloud Library."""

from .engine import (
    Backtester,
    BacktestResult,
    Trade,
    run_quick_backtest,
)

__all__ = [
    "BacktestResult",
    "Backtester",
    "run_quick_backtest",
    "Trade",
]
