"""Unit tests for UserLoginSerializer."""

import pytest

from apps.accounts.models import PublicAccountSettings, User, WhitelistedEmail
from apps.accounts.serializers import UserLoginSerializer


@pytest.mark.django_db
class TestUserLoginSerializer:
    """Tests for UserLoginSerializer."""

    def test_valid_login(self) -> None:
        """Test valid login credentials."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["user"] == user

    def test_invalid_credentials(self) -> None:
        """Test invalid login credentials."""
        User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "password": "WrongPassword",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()

    def test_locked_account(self) -> None:
        """Test login with locked account."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        user.is_locked = True
        user.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()

    def test_inactive_account(self) -> None:
        """Test login with inactive account."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        user.is_active = False
        user.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()

    def test_whitelist_enabled_not_whitelisted(self) -> None:
        """Test login when whitelist is enabled but email not whitelisted."""
        User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        settings = PublicAccountSettings.get_settings()
        settings.email_whitelist_enabled = True
        settings.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()

        # Cleanup
        settings.email_whitelist_enabled = False
        settings.save()

    def test_whitelist_enabled_whitelisted(self) -> None:
        """Test login when whitelist is enabled and email is whitelisted."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        settings = PublicAccountSettings.get_settings()
        settings.email_whitelist_enabled = True
        settings.save()

        WhitelistedEmail.objects.create(
            email_pattern="test@example.com",
            is_active=True,
        )

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data["user"] == user

        # Cleanup
        settings.email_whitelist_enabled = False
        settings.save()

    def test_missing_email(self) -> None:
        """Test login with missing email."""
        data = {
            "password": "TestPass123!",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_missing_password(self) -> None:
        """Test login with missing password."""
        data = {
            "email": "test@example.com",
        }
        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()
        assert "password" in serializer.errors
