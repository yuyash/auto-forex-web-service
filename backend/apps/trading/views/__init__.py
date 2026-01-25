"""Trading views package.

This package organizes trading views into logical modules:
- strategies: Strategy listing and defaults
- configs: StrategyConfig CRUD operations
- task: Task ViewSets with full CRUD and lifecycle management
"""

from .configs import (
    StrategyConfigDetailView,
    StrategyConfigView,
)
from .strategies import (
    StrategyDefaultsView,
    StrategyView,
)

__all__ = [
    # Strategies
    "StrategyView",
    "StrategyDefaultsView",
    # Strategy Configs
    "StrategyConfigView",
    "StrategyConfigDetailView",
]
