"""Unit tests for error handling service."""

import pytest

from apps.trading.services.errors import (
    BusinessLogicError,
    CriticalError,
    ErrorAction,
    ErrorContext,
    ErrorHandler,
    RetryConfig,
    TransientError,
    ValidationError,
    retry_with_backoff,
)


class TestErrorHandler:
    """Test ErrorHandler class."""

    def test_handle_validation_error(self):
        """Test handling of validation errors."""
        handler = ErrorHandler()
        error = ValidationError("Invalid configuration")
        action = handler.handle_error(error)
        assert action == ErrorAction.REJECT

    def test_handle_transient_error(self):
        """Test handling of transient errors."""
        handler = ErrorHandler()
        error = TransientError("Connection timeout")
        action = handler.handle_error(error)
        assert action == ErrorAction.RETRY

    def test_handle_critical_error(self):
        """Test handling of critical errors."""
        handler = ErrorHandler()
        error = CriticalError("Data corruption detected")
        action = handler.handle_error(error)
        assert action == ErrorAction.FAIL_TASK

    def test_handle_business_logic_error(self):
        """Test handling of business logic errors."""
        handler = ErrorHandler()
        error = BusinessLogicError("Strategy signal invalid")
        action = handler.handle_error(error)
        assert action == ErrorAction.LOG_AND_CONTINUE

    def test_categorize_value_error_as_validation(self):
        """Test that ValueError is categorized as validation error."""
        handler = ErrorHandler()
        error = ValueError("Invalid value")
        action = handler.handle_error(error)
        assert action == ErrorAction.REJECT

    def test_categorize_connection_error_as_transient(self):
        """Test that ConnectionError is categorized as transient."""
        handler = ErrorHandler()
        error = ConnectionError("Connection failed")
        action = handler.handle_error(error)
        assert action == ErrorAction.RETRY

    def test_categorize_memory_error_as_critical(self):
        """Test that MemoryError is categorized as critical."""
        handler = ErrorHandler()
        error = MemoryError("Out of memory")
        action = handler.handle_error(error)
        assert action == ErrorAction.FAIL_TASK

    def test_handle_error_with_context(self):
        """Test error handling with context information."""
        handler = ErrorHandler()
        error = ValidationError("Invalid parameter")
        context = ErrorContext(
            error=error,
            execution_id=123,
            task_id=456,
            additional_info={"parameter": "initial_units"},
        )
        action = handler.handle_error(error, context)
        assert action == ErrorAction.REJECT


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_with_backoff(func)
        assert result == "success"
        assert call_count == 1

    def test_retry_success_after_failures(self):
        """Test successful execution after transient failures."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TransientError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=3, initial_delay=0.01, max_delay=0.1)
        result = retry_with_backoff(func, config)
        assert result == "success"
        assert call_count == 3

    def test_retry_exhausted_attempts(self):
        """Test that all retry attempts are exhausted."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise TransientError("Always fails")

        config = RetryConfig(max_attempts=3, initial_delay=0.01, max_delay=0.1)
        with pytest.raises(TransientError):
            retry_with_backoff(func, config)
        assert call_count == 3

    def test_retry_non_transient_error_no_retry(self):
        """Test that non-transient errors are not retried."""
        call_count = 0

        def func():
            nonlocal call_count
            call_count += 1
            raise ValidationError("Invalid input")

        config = RetryConfig(max_attempts=3, initial_delay=0.01, max_delay=0.1)
        with pytest.raises(ValidationError):
            retry_with_backoff(func, config)
        assert call_count == 1  # Should not retry

    def test_retry_exponential_backoff(self):
        """Test that delays increase exponentially."""
        import time

        call_times = []

        def func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise TransientError("Temporary failure")
            return "success"

        config = RetryConfig(max_attempts=3, initial_delay=0.1, max_delay=1.0, exponential_base=2.0)
        retry_with_backoff(func, config)

        # Check that delays are increasing
        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        # Second delay should be roughly 2x the first delay
        assert delay2 > delay1


class TestRetryConfig:
    """Test RetryConfig dataclass."""

    def test_default_config(self):
        """Test default retry configuration."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0

    def test_custom_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5, initial_delay=0.5, max_delay=30.0, exponential_base=3.0
        )
        assert config.max_attempts == 5
        assert config.initial_delay == 0.5
        assert config.max_delay == 30.0
        assert config.exponential_base == 3.0
