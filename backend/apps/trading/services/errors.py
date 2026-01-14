"""
Error handling service for trading system.

This module provides centralized error handling with categorization,
retry logic, and appropriate error actions.
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ErrorCategory(str, Enum):
    """Categories of errors in the trading system."""

    VALIDATION = "validation"
    TRANSIENT = "transient"
    CRITICAL = "critical"
    BUSINESS_LOGIC = "business_logic"


class ErrorAction(str, Enum):
    """Actions to take when an error occurs."""

    REJECT = "reject"  # Reject the operation and return error to user
    RETRY = "retry"  # Retry the operation with backoff
    FAIL_TASK = "fail_task"  # Mark task as failed and stop
    LOG_AND_CONTINUE = "log_and_continue"  # Log error but continue execution


# Custom exception classes for different error categories
class ValidationError(Exception):
    """Raised when validation fails."""

    pass


class TransientError(Exception):
    """Raised when a transient/temporary error occurs."""

    pass


class CriticalError(Exception):
    """Raised when a critical/unrecoverable error occurs."""

    pass


class BusinessLogicError(Exception):
    """Raised when a business logic error occurs."""

    pass


@dataclass
class ErrorContext:
    """Context information about an error."""

    error: Exception
    execution_id: Optional[int] = None
    task_id: Optional[int] = None
    tick_data: Optional[Dict[str, Any]] = None
    strategy_state: Optional[Dict[str, Any]] = None
    additional_info: Optional[Dict[str, Any]] = None


class ErrorHandler:
    """
    Centralized error handling for the trading system.

    Categorizes errors and determines appropriate actions based on
    error type and context.
    """

    def __init__(self):
        """Initialize the error handler."""
        self.logger = logger

    def handle_error(self, error: Exception, context: Optional[ErrorContext] = None) -> ErrorAction:
        """
        Determine how to handle an error based on its type and context.

        Args:
            error: The exception that occurred
            context: Optional context information about the error

        Returns:
            ErrorAction indicating how to handle the error
        """
        # Categorize the error
        category = self._categorize_error(error)

        # Log the error with context
        self._log_error(error, category, context)

        # Determine action based on category
        if category == ErrorCategory.VALIDATION:
            return ErrorAction.REJECT
        elif category == ErrorCategory.TRANSIENT:
            return ErrorAction.RETRY
        elif category == ErrorCategory.CRITICAL:
            return ErrorAction.FAIL_TASK
        elif category == ErrorCategory.BUSINESS_LOGIC:
            return ErrorAction.LOG_AND_CONTINUE
        else:
            # Default to logging and continuing for unknown errors
            return ErrorAction.LOG_AND_CONTINUE

    def _categorize_error(self, error: Exception) -> ErrorCategory:
        """
        Categorize an error based on its type.

        Args:
            error: The exception to categorize

        Returns:
            ErrorCategory for the error
        """
        # Check custom exception types first
        if isinstance(error, ValidationError):
            return ErrorCategory.VALIDATION
        elif isinstance(error, TransientError):
            return ErrorCategory.TRANSIENT
        elif isinstance(error, CriticalError):
            return ErrorCategory.CRITICAL
        elif isinstance(error, BusinessLogicError):
            return ErrorCategory.BUSINESS_LOGIC

        # Check standard exception types
        error_type = type(error).__name__
        error_message = str(error).lower()

        # Validation errors
        if (
            error_type
            in [
                "ValueError",
                "TypeError",
                "KeyError",
                "AttributeError",
            ]
            or "invalid" in error_message
        ):
            return ErrorCategory.VALIDATION

        # Transient errors (network, timeout, temporary failures)
        if (
            error_type
            in [
                "ConnectionError",
                "TimeoutError",
                "RequestException",
                "HTTPError",
            ]
            or "timeout" in error_message
            or "connection" in error_message
            or "temporary" in error_message
        ):
            return ErrorCategory.TRANSIENT

        # Critical errors (data corruption, system failures)
        if (
            error_type
            in [
                "MemoryError",
                "SystemError",
                "RuntimeError",
            ]
            or "corrupt" in error_message
            or "fatal" in error_message
        ):
            return ErrorCategory.CRITICAL

        # Default to business logic error
        return ErrorCategory.BUSINESS_LOGIC

    def _log_error(
        self,
        error: Exception,
        category: ErrorCategory,
        context: Optional[ErrorContext] = None,
    ) -> None:
        """
        Log an error with appropriate level and context.

        Args:
            error: The exception that occurred
            category: The error category
            context: Optional context information
        """
        error_info = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "category": category.value,
        }

        if context:
            if context.execution_id:
                error_info["execution_id"] = context.execution_id
            if context.task_id:
                error_info["task_id"] = context.task_id
            if context.additional_info:
                error_info.update(context.additional_info)

        # Log at appropriate level based on category
        if category == ErrorCategory.CRITICAL:
            self.logger.critical(
                f"Critical error occurred: {error}", extra=error_info, exc_info=True
            )
        elif category == ErrorCategory.VALIDATION:
            self.logger.warning(f"Validation error occurred: {error}", extra=error_info)
        elif category == ErrorCategory.TRANSIENT:
            self.logger.warning(f"Transient error occurred: {error}", extra=error_info)
        else:
            self.logger.error(
                f"Business logic error occurred: {error}",
                extra=error_info,
                exc_info=True,
            )


@dataclass
class RetryConfig:
    """
    Configuration for retry logic with exponential backoff.

    Attributes:
        max_attempts: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        exponential_base: Base for exponential backoff calculation
    """

    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0


def retry_with_backoff(
    func: Callable[[], T],
    config: Optional[RetryConfig] = None,
    error_handler: Optional[ErrorHandler] = None,
) -> T:
    """
    Retry a function with exponential backoff.

    This function will retry the given function up to max_attempts times,
    with exponentially increasing delays between attempts. Only transient
    errors will trigger retries.

    Args:
        func: The function to retry (should take no arguments)
        config: Optional retry configuration (uses defaults if not provided)
        error_handler: Optional error handler for logging

    Returns:
        The result of the function call

    Raises:
        The last exception if all retry attempts fail
    """
    if config is None:
        config = RetryConfig()

    if error_handler is None:
        error_handler = ErrorHandler()

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            return func()
        except Exception as e:
            last_exception = e

            # Check if this is a transient error worth retrying
            action = error_handler.handle_error(e)

            if action != ErrorAction.RETRY:
                # Not a transient error, don't retry
                raise

            # If this was the last attempt, raise the exception
            if attempt == config.max_attempts - 1:
                func_name = getattr(func, "__name__", repr(func))
                logger.error(
                    f"All {config.max_attempts} retry attempts failed for function {func_name}"
                )
                raise

            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base**attempt),
                config.max_delay,
            )

            func_name = getattr(func, "__name__", repr(func))
            logger.info(
                f"Retry attempt {attempt + 1}/{config.max_attempts} "
                f"for {func_name} after {delay:.2f}s delay"
            )

            time.sleep(delay)

    # This should never be reached, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic failed unexpectedly")
