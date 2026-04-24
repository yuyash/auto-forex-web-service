"""Trading views package.

This package organizes trading views into logical modules:
- strategies: Strategy listing and defaults
- configs: StrategyConfig CRUD operations
- backtest: Backtest task ViewSet with full CRUD and lifecycle management
- trading: Trading task ViewSet with full CRUD and lifecycle management
"""

from .backtest import BacktestTaskViewSet
from .configs import (
    StrategyConfigCopyView,
    StrategyConfigDetailView,
    StrategyConfigTasksView,
    StrategyConfigView,
)
from .recovery import RecoveryAttemptListView
from .strategies import (
    StrategyDefaultsView,
    StrategyView,
)
from .trading import TradingTaskViewSet

__all__ = [
    # Strategies
    "StrategyView",
    "StrategyDefaultsView",
    # Strategy Configs
    "StrategyConfigView",
    "StrategyConfigDetailView",
    "StrategyConfigTasksView",
    "StrategyConfigCopyView",
    # Tasks
    "BacktestTaskViewSet",
    "TradingTaskViewSet",
    "RecoveryAttemptListView",
]
