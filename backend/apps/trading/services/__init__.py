"""Service layer for the trading app."""

from .controller import TaskController
from .executor import BacktestExecutor
from .registry import register_all_strategies, registry
from .state import StateManager

__all__ = [
    "registry",
    "register_all_strategies",
    "StateManager",
    "TaskController",
    "BacktestExecutor",
]
