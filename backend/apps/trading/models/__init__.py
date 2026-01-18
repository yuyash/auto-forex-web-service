"""Trading models package.

This package organizes trading models into logical modules:
- configs: StrategyConfigurations and related
- tasks: BacktestTasks, TradingTasks
- floor_state: FloorStrategyTaskState, FloorStrategyLayerState
- execution: Executions, TaskExecutionResult
- metrics: ExecutionMetrics, ExecutionMetricsCheckpoint, TradingMetrics
- events: StrategyEvents, TradeLogs, ExecutionEquityPoint, TradingEvent
- state: ExecutionStateSnapshot
- celery: CeleryTaskStatus
"""

from apps.trading.models.celery import CeleryTaskStatus
from apps.trading.models.configs import (
    StrategyConfigurations,
    StrategyConfigurationsManager,
)
from apps.trading.models.events import (
    ExecutionEquityPoint,
    StrategyEvents,
    TradeLogs,
    TradingEvent,
)
from apps.trading.models.execution import (
    Executions,
    ExecutionsManager,
    TaskExecutionResult,
)
from apps.trading.models.floor import (
    FloorSide,
    FloorStrategyLayerState,
    FloorStrategyTaskState,
)
from apps.trading.models.metrics import (
    ExecutionMetrics,
    ExecutionMetricsCheckpoint,
    ExecutionMetricsManager,
    TradingMetrics,
)
from apps.trading.models.state import ExecutionStateSnapshot
from apps.trading.models.tasks import (
    BacktestTasks,
    BacktestTasksManager,
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
    # Floor State
    "FloorSide",
    "FloorStrategyTaskState",
    "FloorStrategyLayerState",
    # Execution
    "Executions",
    "ExecutionsManager",
    "TaskExecutionResult",
    # Metrics
    "ExecutionMetrics",
    "ExecutionMetricsManager",
    "ExecutionMetricsCheckpoint",
    "TradingMetrics",
    # Events
    "StrategyEvents",
    "TradeLogs",
    "ExecutionEquityPoint",
    "TradingEvent",
    # State
    "ExecutionStateSnapshot",
    # Celery
    "CeleryTaskStatus",
]
