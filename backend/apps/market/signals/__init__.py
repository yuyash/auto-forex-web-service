"""Market signals package."""

from typing import List

from apps.market.signals.account import (
    AccountSignalHandler,
    account_handler,
    bootstrap_tick_pubsub_on_first_live_account,
)
from apps.market.signals.backtest import (
    BacktestSignalHandler,
    backtest_handler,
    enqueue_backtest_tick_publisher,
    request_backtest_tick_stream,
)
from apps.market.signals.base import (
    backtest_tick_stream_requested,
    market_task_cancel_requested,
)
from apps.market.signals.management import (
    TaskManagementSignalHandler,
    handle_market_task_cancel_requested,
    request_market_task_cancel,
    task_management_handler,
)


def connect_all_handlers() -> None:
    """Connect all signal handlers.

    This should be called from apps.py ready() method.
    """
    account_handler.connect()
    backtest_handler.connect()
    task_management_handler.connect()


__all__: List[str] = [
    # Signal definitions
    "backtest_tick_stream_requested",
    "market_task_cancel_requested",
    # Handler classes
    "AccountSignalHandler",
    "BacktestSignalHandler",
    "TaskManagementSignalHandler",
    # Handler instances
    "account_handler",
    "backtest_handler",
    "task_management_handler",
    # Connection function
    "connect_all_handlers",
    # Request functions
    "request_backtest_tick_stream",
    "request_market_task_cancel",
    # Handler functions (for backward compatibility)
    "bootstrap_tick_pubsub_on_first_live_account",
    "enqueue_backtest_tick_publisher",
    "handle_market_task_cancel_requested",
]
