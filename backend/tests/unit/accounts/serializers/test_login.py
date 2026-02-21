"""Unit tests for UserLoginSerializer (validation logic only)."""

from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.serializers.login import UserLoginSerializer


class TestUserLoginSerializerValidation:
    """Unit tests for UserLoginSerializer validation methods."""

    def test_validate_missing_email(self) -> None:
        """Test validation with missing email."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"password": "TestPass123!"}

        with pytest.raises(ValidationError):
            serializer.validate(attrs)

    def test_validate_missing_password(self) -> None:
        """Test validation with missing password."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "test@example.com"}

        with pytest.raises(ValidationError):
            serializer.validate(attrs)

    def test_validate_empty_email(self) -> None:
        """Test validation with empty email."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "", "password": "TestPass123!"}

        with pytest.raises(ValidationError):
            serializer.validate(attrs)

    def test_validate_empty_password(self) -> None:
        """Test validation with empty password."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "test@example.com", "password": ""}

        with pytest.raises(ValidationError):
            serializer.validate(attrs)

    def test_validate_whitelist_check(self) -> None:
        """Test validation checks whitelist when enabled."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "test@example.com", "password": "TestPass123!"}

        with patch("apps.accounts.serializers.login.PublicAccountSettings") as mock_settings:
            mock_settings.get_settings.return_value.email_whitelist_enabled = True

            with patch("apps.accounts.serializers.login.WhitelistedEmail") as mock_whitelist:
                mock_whitelist.is_email_whitelisted.return_value = False

                with pytest.raises(ValidationError):
                    serializer.validate(attrs)

    def test_validate_inactive_user(self) -> None:
        """Test validation with inactive user."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "test@example.com", "password": "TestPass123!"}

        mock_user = MagicMock()
        mock_user.is_active = False

        with patch("apps.accounts.serializers.login.PublicAccountSettings") as mock_settings:
            mock_settings.get_settings.return_value.email_whitelist_enabled = False

            with patch("apps.accounts.serializers.login.authenticate") as mock_auth:
                mock_auth.return_value = mock_user

                with pytest.raises(ValidationError):
                    serializer.validate(attrs)

    def test_validate_locked_user(self) -> None:
        """Test validation with locked user."""
        from rest_framework.exceptions import ValidationError

        serializer = UserLoginSerializer()
        attrs = {"email": "test@example.com", "password": "TestPass123!"}

        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = True

        with patch("apps.accounts.serializers.login.PublicAccountSettings") as mock_settings:
            mock_settings.get_settings.return_value.email_whitelist_enabled = False

            with patch("apps.accounts.serializers.login.authenticate") as mock_auth:
                mock_auth.return_value = mock_user

                with pytest.raises(ValidationError):
                    serializer.validate(attrs)
