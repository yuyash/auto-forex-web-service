"""apps.trading.services.executor

Task executors for backtest and live trading execution.

This package provides executor classes that orchestrate the execution of
trading tasks, coordinating between strategies, state management, event
emission, performance tracking, and lifecycle control.
"""

from apps.trading.services.executor.backtest import BacktestExecutor
from apps.trading.services.executor.trading import TradingExecutor

__all__ = ["BacktestExecutor", "TradingExecutor"]
