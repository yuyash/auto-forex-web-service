"""Validation result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation operation.

    This dataclass represents the outcome of validating data, providing
    a type-safe way to return validation results with optional error messages.
    """

    is_valid: bool
    error_message: str | None = None

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create a successful validation result.

        Returns:
            ValidationResult: Result indicating validation passed
        """
        return cls(is_valid=True, error_message=None)

    @classmethod
    def failure(cls, error_message: str) -> "ValidationResult":
        """Create a failed validation result.

        Args:
            error_message: Description of the validation error

        Returns:
            ValidationResult: Result indicating validation failed
        """
        return cls(is_valid=False, error_message=error_message)
