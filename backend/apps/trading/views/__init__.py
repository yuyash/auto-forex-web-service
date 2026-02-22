"""Trading views package.

This package organizes trading views into logical modules:
- strategies: Strategy listing and defaults
- configs: StrategyConfig CRUD operations
- backtest: Backtest task ViewSet with full CRUD and lifecycle management
- trading: Trading task ViewSet with full CRUD and lifecycle management
"""

from .backtest import BacktestTaskViewSet
from .configs import (
    StrategyConfigDetailView,
    StrategyConfigView,
)
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
    # Tasks
    "BacktestTaskViewSet",
    "TradingTaskViewSet",
]
