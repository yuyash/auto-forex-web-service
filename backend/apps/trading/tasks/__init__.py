"""Trading tasks package.

This package contains Celery task runners for backtesting and live trading.
"""

from apps.trading.tasks.backtest import BacktestTaskRunner, _run_backtest_task_wrapper
from apps.trading.tasks.trading import TradingTaskRunner

# Create singleton instances
backtest_runner = BacktestTaskRunner()
trading_runner = TradingTaskRunner()

# Export task functions for Celery autodiscovery
run_backtest_task = _run_backtest_task_wrapper
run_trading_task = trading_runner.run
stop_trading_task = trading_runner.stop

__all__ = [
    "BacktestTaskRunner",
    "TradingTaskRunner",
    "backtest_runner",
    "trading_runner",
    "run_backtest_task",
    "run_trading_task",
    "stop_trading_task",
]
