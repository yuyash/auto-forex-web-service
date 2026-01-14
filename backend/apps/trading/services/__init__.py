"""Service layer for the trading app."""

from .controller import TaskController
from .errors import (
    BusinessLogicError,
    CriticalError,
    ErrorAction,
    ErrorCategory,
    ErrorContext,
    ErrorHandler,
    RetryConfig,
    TransientError,
    ValidationError,
    retry_with_backoff,
)
from .executor import BacktestExecutor
from .registry import register_all_strategies, registry
from .state import StateManager
from .validation import TaskValidator

__all__ = [
    "registry",
    "register_all_strategies",
    "StateManager",
    "TaskController",
    "BacktestExecutor",
    "ErrorHandler",
    "ErrorAction",
    "ErrorCategory",
    "ErrorContext",
    "ValidationError",
    "TransientError",
    "CriticalError",
    "BusinessLogicError",
    "RetryConfig",
    "retry_with_backoff",
    "TaskValidator",
]
