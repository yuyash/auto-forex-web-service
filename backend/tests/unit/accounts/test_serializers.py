"""Unit tests for accounts serializers."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.serializers import (
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
)

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistrationSerializer:
    """Test UserRegistrationSerializer."""

    def test_valid_registration_data(self):
        """Test serializer with valid registration data."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()

    def test_password_mismatch(self):
        """Test validation fails when passwords don't match."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "DifferentPass123!",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "password_confirm" in serializer.errors or "non_field_errors" in serializer.errors

    def test_weak_password(self):
        """Test validation fails with weak password."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "weak",
            "password_confirm": "weak",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()

    def test_invalid_email(self):
        """Test validation fails with invalid email."""
        data = {
            "username": "testuser",
            "email": "invalid-email",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_create_user(self):
        """Test user creation through serializer."""
        data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Test",
            "last_name": "User",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid()
        user = serializer.save()
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.check_password("TestPass123!")


@pytest.mark.django_db
class TestUserLoginSerializer:
    """Test UserLoginSerializer."""

    def test_valid_login_data(self):
        """Test serializer with valid login credentials."""
        # Create a test user
        User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }

        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid()
        assert "user" in serializer.validated_data

    def test_invalid_credentials(self):
        """Test validation fails with invalid credentials."""
        data = {
            "email": "test@example.com",
            "password": "WrongPassword",
        }

        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()


@pytest.mark.django_db
class TestUserProfileSerializer:
    """Test UserProfileSerializer."""

    def test_serialize_user_profile(self):
        """Test serializing user profile."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
            first_name="Test",
            last_name="User",
        )

        serializer = UserProfileSerializer(user)
        data = serializer.data

        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert "password" not in data

    def test_update_user_profile(self):
        """Test updating user profile."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="TestPass123!",
        )

        data = {
            "first_name": "Updated",
            "last_name": "Name",
        }

        serializer = UserProfileSerializer(user, data=data, partial=True)
        assert serializer.is_valid()
        updated_user = serializer.save()

        assert updated_user.first_name == "Updated"
        assert updated_user.last_name == "Name"
