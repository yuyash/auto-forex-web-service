"""Trading models package.

This package organizes trading models into logical modules:
- configs: StrategyConfig and related
- tasks: BacktestTask, TradingTask
- floor_state: FloorStrategyTaskState, FloorStrategyLayerState
- execution: TaskExecution, TaskExecutionResult
- metrics: ExecutionMetrics, ExecutionMetricsCheckpoint
- events: ExecutionStrategyEvent, ExecutionTradeLogEntry, ExecutionEquityPoint, TradingEvent
- state: ExecutionStateSnapshot
- celery: CeleryTaskStatus
"""

from apps.trading.models.celery import CeleryTaskStatus
from apps.trading.models.configs import StrategyConfig, StrategyConfigManager
from apps.trading.models.events import (
    ExecutionEquityPoint,
    ExecutionStrategyEvent,
    ExecutionTradeLogEntry,
    TradingEvent,
)
from apps.trading.models.execution import (
    TaskExecution,
    TaskExecutionManager,
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
)
from apps.trading.models.state import ExecutionStateSnapshot
from apps.trading.models.tasks import (
    BacktestTask,
    BacktestTaskManager,
    TradingTask,
    TradingTaskManager,
)

__all__ = [
    # Configs
    "StrategyConfig",
    "StrategyConfigManager",
    # Tasks
    "BacktestTask",
    "BacktestTaskManager",
    "TradingTask",
    "TradingTaskManager",
    # Floor State
    "FloorSide",
    "FloorStrategyTaskState",
    "FloorStrategyLayerState",
    # Execution
    "TaskExecution",
    "TaskExecutionManager",
    "TaskExecutionResult",
    # Metrics
    "ExecutionMetrics",
    "ExecutionMetricsManager",
    "ExecutionMetricsCheckpoint",
    # Events
    "ExecutionStrategyEvent",
    "ExecutionTradeLogEntry",
    "ExecutionEquityPoint",
    "TradingEvent",
    # State
    "ExecutionStateSnapshot",
    # Celery
    "CeleryTaskStatus",
]
