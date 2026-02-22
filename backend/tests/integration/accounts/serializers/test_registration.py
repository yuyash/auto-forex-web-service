"""Unit tests for UserRegistrationSerializer."""

import pytest

from apps.accounts.models import PublicAccountSettings, User, WhitelistedEmail
from apps.accounts.serializers import UserRegistrationSerializer


@pytest.mark.django_db
class TestUserRegistrationSerializer:
    """Tests for UserRegistrationSerializer."""

    def test_valid_registration(self) -> None:
        """Test valid user registration."""
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()

        user = serializer.save()
        assert user.email == "test@example.com"
        assert user.username == "testuser"

    def test_password_mismatch(self) -> None:
        """Test registration with mismatched passwords."""
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "TestPass123!",
            "password_confirm": "DifferentPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "password_confirm" in serializer.errors

    def test_duplicate_email(self) -> None:
        """Test registration with duplicate email."""
        User.objects.create_user(
            email="test@example.com",
            username="existing",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "username": "newuser",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_invalid_username(self) -> None:
        """Test registration with invalid username."""
        data = {
            "email": "test@example.com",
            "username": "test user!",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "username" in serializer.errors

    def test_auto_generate_username(self) -> None:
        """Test auto-generating username from email."""
        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()

        user = serializer.save()
        assert user.username

    def test_whitelist_enabled_not_whitelisted(self) -> None:
        """Test registration when whitelist is enabled but email not whitelisted."""
        settings = PublicAccountSettings.get_settings()
        settings.email_whitelist_enabled = True
        settings.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

        # Cleanup
        settings.email_whitelist_enabled = False
        settings.save()

    def test_whitelist_enabled_whitelisted(self) -> None:
        """Test registration when whitelist is enabled and email is whitelisted."""
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
            "password_confirm": "TestPass123!",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()

        # Cleanup
        settings.email_whitelist_enabled = False
        settings.save()

    def test_weak_password(self) -> None:
        """Test registration with weak password."""
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "weak",
            "password_confirm": "weak",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "password" in serializer.errors
