"""Trading models package.

This package organizes trading models into logical modules:
- configs: StrategyConfiguration and related
- backtest: BacktestTask
- trading: TradingTask
- state: ExecutionState
- events: TradingEvent
- celery: CeleryTaskStatus
- logs: TaskLog
- trades: Trades
- equities: Equities

Note: FloorSide enum has been moved to apps.trading.enums
"""

from apps.trading.models.backtest import (
    BacktestTask,
    BacktestTaskManager,
)
from apps.trading.models.celery import CeleryTaskStatus
from apps.trading.models.configs import (
    StrategyConfiguration,
    StrategyConfigurationManager,
)
from apps.trading.models.equities import Equity
from apps.trading.models.events import TradingEvent
from apps.trading.models.floor import Layer
from apps.trading.models.logs import TaskLog
from apps.trading.models.orders import Order
from apps.trading.models.positions import Position
from apps.trading.models.state import ExecutionState
from apps.trading.models.trades import Trade
from apps.trading.models.trading import (
    TradingTask,
    TradingTaskManager,
)

__all__ = [
    # Configs
    "StrategyConfiguration",
    "StrategyConfigurationManager",
    # Tasks
    "BacktestTask",
    "BacktestTaskManager",
    "TradingTask",
    "TradingTaskManager",
    # State
    "ExecutionState",
    # Events
    "TradingEvent",
    # Celery
    "CeleryTaskStatus",
    # Logs
    "TaskLog",
    # Execution Data
    "Order",
    "Position",
    "Trade",
    "Equity",
    # Floor Strategy
    "Layer",
]
