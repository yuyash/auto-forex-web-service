"""Unit tests for UserRegistrationView."""

from unittest.mock import patch

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import PublicAccountSettings, User
from apps.accounts.views.registration import UserRegistrationView


@pytest.mark.django_db
class TestUserRegistrationView:
    """Tests for UserRegistrationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = UserRegistrationView.as_view()

    def test_successful_registration(self) -> None:
        """Test successful user registration."""
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        request = self.factory.post("/api/auth/register", data, content_type="application/json")

        with patch("apps.accounts.views.registration.AccountEmailService") as mock_email:
            mock_email.return_value.send_verification_email.return_value = True
            response = self.view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        assert response.data["user"]["email"] == "newuser@example.com"

    def test_registration_disabled(self) -> None:
        """Test registration when disabled."""
        settings = PublicAccountSettings.get_settings()
        settings.registration_enabled = False
        settings.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        request = self.factory.post("/api/auth/register", data, content_type="application/json")
        response = self.view(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # Cleanup
        settings.registration_enabled = True
        settings.save()

    def test_registration_duplicate_email(self) -> None:
        """Test registration with duplicate email."""
        User.objects.create_user(
            email="existing@example.com",
            username="existing",
            password="TestPass123!",
        )

        data = {
            "email": "existing@example.com",
            "username": "newuser",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
        }
        request = self.factory.post("/api/auth/register", data, content_type="application/json")
        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_registration_password_mismatch(self) -> None:
        """Test registration with mismatched passwords."""
        data = {
            "email": "test@example.com",
            "username": "testuser",
            "password": "TestPass123!",
            "password_confirm": "DifferentPass123!",
        }
        request = self.factory.post("/api/auth/register", data, content_type="application/json")
        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
