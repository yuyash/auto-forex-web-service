"""Unit tests for UserLoginView."""

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.middlewares import RateLimiter
from apps.accounts.models import PublicAccountSettings, User
from apps.accounts.views.login import UserLoginView


@pytest.mark.django_db
class TestUserLoginView:
    """Tests for UserLoginView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = UserLoginView.as_view()
        cache.clear()

    def test_successful_login(self) -> None:
        """Test successful login."""
        User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["authenticated"] is True
        assert "token" not in response.data
        assert response.data["user"]["email"] == "test@example.com"
        assert response.cookies["access_token"].value
        assert response.cookies["refresh_token"].value

    def test_login_invalid_credentials(self) -> None:
        """Test login with invalid credentials."""
        User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        data = {
            "email": "test@example.com",
            "password": "WrongPassword",
        }
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_admin_invalid_credentials_are_rate_limited(self) -> None:
        """Test admin accounts do not bypass failed-attempt tracking."""
        user = User.objects.create_user(
            email="admin@example.com",
            username="adminuser",
            password="TestPass123!",
            is_staff=True,
        )

        data = {
            "email": "admin@example.com",
            "password": "WrongPassword",
        }
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert RateLimiter.get_failed_attempts("127.0.0.1") == 1
        user.refresh_from_db()
        assert user.failed_login_attempts == 1

    def test_login_locked_account(self) -> None:
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
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_disabled(self) -> None:
        """Test login when disabled."""
        settings = PublicAccountSettings.get_settings()
        settings.login_enabled = False
        settings.save()

        data = {
            "email": "test@example.com",
            "password": "TestPass123!",
        }
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

        # Cleanup
        settings.login_enabled = True
        settings.save()

    def test_login_missing_credentials(self) -> None:
        """Test login with missing credentials."""
        data = {"email": "test@example.com"}
        request = self.factory.post(
            "/api/accounts/auth/login", data, content_type="application/json"
        )
        response = self.view(request)

        # Serializer validation fails, returns 401 for invalid credentials
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
