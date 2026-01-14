"""Trading views package.

This package organizes trading views into logical modules:
- strategies: Strategy listing and defaults
- configs: StrategyConfig CRUD operations
- trading_tasks: TradingTask CRUD operations
- trading_actions: TradingTask lifecycle (start/stop/restart/status)
- trading_data: TradingTask data endpoints (equity/events/trades/logs)
- backtest_tasks: BacktestTask CRUD operations
- backtest_actions: BacktestTask lifecycle (start/stop/status)
- backtest_data: BacktestTask data endpoints (equity/events/trades/logs)
- executions: Execution-specific endpoints (Task 14)
"""

from .backtest_actions import (
    BacktestTaskExecutionsView,
    BacktestTaskExportView,
    BacktestTaskLogsView,
    BacktestTaskStartView,
    BacktestTaskStatusView,
    BacktestTaskStopView,
)
from .backtest_data import (
    BacktestTaskEquityCurveView,
    BacktestTaskMetricsCheckpointView,
    BacktestTaskResultsView,
    BacktestTaskStrategyEventsView,
    BacktestTaskTradeLogsView,
)
from .backtest_tasks import (
    BacktestTaskCopyView,
    BacktestTaskDetailView,
    BacktestTaskView,
)
from .configs import (
    StrategyConfigDetailView,
    StrategyConfigView,
)
from .executions import (
    ExecutionDetailView,
    ExecutionEquityView,
    ExecutionEventsView,
    ExecutionMetricsView,
    ExecutionStatusView,
    ExecutionTradesView,
)
from .strategies import (
    StrategyDefaultsView,
    StrategyView,
)
from .trading_actions import (
    TradingTaskExecutionsView,
    TradingTaskLogsView,
    TradingTaskRestartView,
    TradingTaskStartView,
    TradingTaskStatusView,
    TradingTaskStopView,
)
from .trading_data import (
    TradingTaskEquityCurveView,
    TradingTaskMetricsCheckpointView,
    TradingTaskResultsView,
    TradingTaskStrategyEventsView,
    TradingTaskTradeLogsView,
)
from .trading_tasks import (
    TradingTaskCopyView,
    TradingTaskDetailView,
    TradingTaskView,
)

__all__ = [
    # Strategies
    "StrategyView",
    "StrategyDefaultsView",
    # Strategy Configs
    "StrategyConfigView",
    "StrategyConfigDetailView",
    # Trading Tasks
    "TradingTaskView",
    "TradingTaskDetailView",
    "TradingTaskCopyView",
    # Trading Actions
    "TradingTaskStartView",
    "TradingTaskStopView",
    "TradingTaskRestartView",
    "TradingTaskExecutionsView",
    "TradingTaskLogsView",
    "TradingTaskStatusView",
    # Trading Data
    "TradingTaskResultsView",
    "TradingTaskEquityCurveView",
    "TradingTaskStrategyEventsView",
    "TradingTaskTradeLogsView",
    "TradingTaskMetricsCheckpointView",
    # Backtest Tasks
    "BacktestTaskView",
    "BacktestTaskDetailView",
    "BacktestTaskCopyView",
    # Backtest Actions
    "BacktestTaskStartView",
    "BacktestTaskStopView",
    "BacktestTaskStatusView",
    "BacktestTaskExecutionsView",
    "BacktestTaskExportView",
    "BacktestTaskLogsView",
    # Backtest Data
    "BacktestTaskResultsView",
    "BacktestTaskEquityCurveView",
    "BacktestTaskStrategyEventsView",
    "BacktestTaskTradeLogsView",
    "BacktestTaskMetricsCheckpointView",
    # Executions (Task 14)
    "ExecutionDetailView",
    "ExecutionStatusView",
    "ExecutionEventsView",
    "ExecutionTradesView",
    "ExecutionEquityView",
    "ExecutionMetricsView",
]
