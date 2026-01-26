"""Trading models package.

This package organizes trading models into logical modules:
- configs: StrategyConfigurations and related
- backtest: BacktestTasks
- trading: TradingTasks
- state: ExecutionState
- events: TradingEvents
- celery: CeleryTaskStatus
- logs: TaskLog
- trades: Trades
- equities: Equities

Note: FloorSide enum has been moved to apps.trading.enums
"""

from apps.trading.models.backtest import (
    BacktestTasks,
    BacktestTasksManager,
)
from apps.trading.models.celery import CeleryTaskStatus
from apps.trading.models.configs import (
    StrategyConfigurations,
    StrategyConfigurationsManager,
)
from apps.trading.models.equities import Equities
from apps.trading.models.events import TradingEvents
from apps.trading.models.logs import TaskLog
from apps.trading.models.state import ExecutionState
from apps.trading.models.trades import Trades
from apps.trading.models.trading import (
    TradingTasks,
    TradingTasksManager,
)

__all__ = [
    # Configs
    "StrategyConfigurations",
    "StrategyConfigurationsManager",
    # Tasks
    "BacktestTasks",
    "BacktestTasksManager",
    "TradingTasks",
    "TradingTasksManager",
    # State
    "ExecutionState",
    # Events
    "TradingEvents",
    # Celery
    "CeleryTaskStatus",
    # Logs
    "TaskLog",
    # Execution Data
    "Trades",
    "Equities",
]
