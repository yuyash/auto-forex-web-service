"""Unit tests for UserRegistrationSerializer (validation logic only)."""

import pytest

from apps.accounts.serializers.registration import UserRegistrationSerializer


class TestUserRegistrationSerializerValidation:
    """Unit tests for UserRegistrationSerializer validation methods."""

    def test_validate_username_valid(self) -> None:
        """Test username validation with valid username."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("valid_user.name-123")
        assert result == "valid_user.name-123"

    def test_validate_username_invalid_characters(self) -> None:
        """Test username validation with invalid characters."""
        from rest_framework.exceptions import ValidationError

        serializer = UserRegistrationSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_username("invalid user!")

    def test_validate_username_too_short(self) -> None:
        """Test username validation with too short username."""
        from rest_framework.exceptions import ValidationError

        serializer = UserRegistrationSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_username("ab")

    def test_validate_username_empty(self) -> None:
        """Test username validation with empty string."""
        serializer = UserRegistrationSerializer()
        result = serializer.validate_username("")
        assert result == ""

    def test_validate_email_invalid_format(self) -> None:
        """Test email validation with invalid format."""
        from rest_framework.exceptions import ValidationError

        serializer = UserRegistrationSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_email("invalid_email")

    def test_validate_password_weak(self) -> None:
        """Test password validation with weak password."""
        from rest_framework.exceptions import ValidationError

        serializer = UserRegistrationSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_password("weak")

    def test_validate_passwords_match(self) -> None:
        """Test validation when passwords match."""
        serializer = UserRegistrationSerializer()
        attrs = {
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        result = serializer.validate(attrs)
        assert result == attrs

    def test_validate_passwords_mismatch(self) -> None:
        """Test validation when passwords don't match."""
        from rest_framework.exceptions import ValidationError

        serializer = UserRegistrationSerializer()
        attrs = {
            "password": "TestPass123!",
            "password_confirm": "DifferentPass123!",
        }

        with pytest.raises(ValidationError):
            serializer.validate(attrs)
