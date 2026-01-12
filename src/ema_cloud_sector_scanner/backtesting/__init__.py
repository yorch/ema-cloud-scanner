"""Backtesting module"""

from .engine import (
    Trade,
    BacktestResult,
    Backtester,
    run_quick_backtest
)

__all__ = [
    'Trade',
    'BacktestResult',
    'Backtester',
    'run_quick_backtest'
]
