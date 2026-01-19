"""Trading tasks package.

This package contains Celery task runners for backtesting and live trading.
"""

from typing import List

from apps.trading.tasks.backtest import BacktestTaskRunner, _run_backtest_task_wrapper
from apps.trading.tasks.trading import (
    TradingTaskRunner,
    run_trading_task,
    stop_trading_task,
)

# Create singleton instances
backtest_runner = BacktestTaskRunner()
trading_runner = TradingTaskRunner()

# Export task functions for Celery autodiscovery
run_backtest_task = _run_backtest_task_wrapper
# run_trading_task and stop_trading_task are imported directly from trading module

__all__: List[str] = [
    "BacktestTaskRunner",
    "TradingTaskRunner",
    "backtest_runner",
    "trading_runner",
    "run_backtest_task",
    "run_trading_task",
    "stop_trading_task",
]
