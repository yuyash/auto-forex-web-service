"""Unit tests for ValidationResult dataclass."""

import pytest

from apps.trading.dataclasses import ValidationResult


class TestValidationResult:
    """Test suite for ValidationResult dataclass."""

    def test_create_validation_result_success(self):
        """Test creating a successful validation result."""
        result = ValidationResult(is_valid=True, error_message=None)

        assert result.is_valid is True
        assert result.error_message is None

    def test_create_validation_result_failure(self):
        """Test creating a failed validation result."""
        result = ValidationResult(is_valid=False, error_message="Balance cannot be negative")

        assert result.is_valid is False
        assert result.error_message == "Balance cannot be negative"

    def test_success_class_method(self):
        """Test ValidationResult.success() class method."""
        result = ValidationResult.success()

        assert result.is_valid is True
        assert result.error_message is None

    def test_failure_class_method(self):
        """Test ValidationResult.failure() class method."""
        error_msg = "Invalid configuration"
        result = ValidationResult.failure(error_msg)

        assert result.is_valid is False
        assert result.error_message == error_msg

    def test_validation_result_in_conditional(self):
        """Test using ValidationResult in conditional statements."""
        success_result = ValidationResult.success()
        failure_result = ValidationResult.failure("Error occurred")

        # Test truthy/falsy behavior based on is_valid
        if success_result.is_valid:
            assert True
        else:
            pytest.fail("Success result should be valid")

        if not failure_result.is_valid:
            assert True
        else:
            pytest.fail("Failure result should be invalid")

    def test_validation_result_error_message_access(self):
        """Test accessing error message from validation result."""
        result = ValidationResult.failure("State is corrupted")

        if not result.is_valid:
            error = result.error_message
            assert error == "State is corrupted"
            assert isinstance(error, str)

    def test_validation_result_with_empty_error_message(self):
        """Test validation result with empty error message."""
        result = ValidationResult(is_valid=False, error_message="")

        assert result.is_valid is False
        assert result.error_message == ""

    def test_validation_result_equality(self):
        """Test ValidationResult equality comparison."""
        result1 = ValidationResult.success()
        result2 = ValidationResult.success()
        result3 = ValidationResult.failure("Error")

        assert result1 == result2
        assert result1 != result3

    def test_validation_result_repr(self):
        """Test ValidationResult string representation."""
        success = ValidationResult.success()
        failure = ValidationResult.failure("Invalid data")

        assert "is_valid=True" in repr(success)
        assert "is_valid=False" in repr(failure)
        assert "Invalid data" in repr(failure)
