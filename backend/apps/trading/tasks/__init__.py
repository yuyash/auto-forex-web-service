"""Backtesting and Trading tasks package.

This package contains Celery tasks for backtesting and live trading,
as well as task execution infrastructure.
"""

from typing import List

from apps.trading.tasks.backtest import run_backtest_task, stop_backtest_task
from apps.trading.tasks.executor import BacktestExecutor, TaskExecutor, TradingExecutor
from apps.trading.tasks.recovery import recover_orphaned_tasks_beat, recover_orphaned_tasks_startup
from apps.trading.tasks.source import (
    LiveTickDataSource,
    RedisStreamTickDataSource,
    RedisTickDataSource,
    TickDataSource,
)
from apps.trading.tasks.trading import run_trading_task, stop_trading_task

__all__: List[str] = [
    "run_backtest_task",
    "run_trading_task",
    "stop_backtest_task",
    "stop_trading_task",
    "recover_orphaned_tasks_beat",
    "recover_orphaned_tasks_startup",
    "TaskExecutor",
    "BacktestExecutor",
    "TradingExecutor",
    "TickDataSource",
    "RedisTickDataSource",
    "RedisStreamTickDataSource",
    "LiveTickDataSource",
]
