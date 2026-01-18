"""Trading views package.

This package organizes trading views into logical modules:
- strategies: Strategy listing and defaults
- configs: StrategyConfig CRUD operations
- trading_tasks: TradingTask CRUD operations
- trading_actions: TradingTask lifecycle (start/stop/restart/status)
- backtest_tasks: BacktestTask CRUD operations
- backtest_actions: BacktestTask lifecycle (start/stop/status)
- executions: Execution-specific endpoints
"""

from .backtest_actions import (
    BacktestTaskExecutionsView,
    BacktestTaskRestartView,
    BacktestTaskResumeView,
    BacktestTaskStartView,
    BacktestTaskStatusView,
    BacktestTaskStopView,
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
    ExecutionLatestMetricsView,
    ExecutionLogsView,
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
    TradingTaskRestartView,
    TradingTaskResumeView,
    TradingTaskStartView,
    TradingTaskStatusView,
    TradingTaskStopView,
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
    "TradingTaskResumeView",
    "TradingTaskRestartView",
    "TradingTaskExecutionsView",
    "TradingTaskStatusView",
    # Backtest Tasks
    "BacktestTaskView",
    "BacktestTaskDetailView",
    "BacktestTaskCopyView",
    # Backtest Actions
    "BacktestTaskStartView",
    "BacktestTaskStopView",
    "BacktestTaskResumeView",
    "BacktestTaskRestartView",
    "BacktestTaskStatusView",
    "BacktestTaskExecutionsView",
    # Executions (Task 14)
    "ExecutionDetailView",
    "ExecutionLogsView",
    "ExecutionStatusView",
    "ExecutionEventsView",
    "ExecutionTradesView",
    "ExecutionEquityView",
    "ExecutionMetricsView",
    "ExecutionLatestMetricsView",
]
