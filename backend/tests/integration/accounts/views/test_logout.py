"""Unit tests for UserLogoutView."""

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import User, UserSession
from apps.accounts.services.jwt import JWTService
from apps.accounts.views.logout import UserLogoutView


@pytest.mark.django_db
class TestUserLogoutView:
    """Tests for UserLogoutView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = UserLogoutView.as_view()

    def test_successful_logout(self) -> None:
        """Test successful logout."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        # Create active session
        UserSession.objects.create(
            user=user,
            session_key="test_session",
            ip_address="127.0.0.1",
        )

        # Generate token
        token = JWTService().generate_token(user)

        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        request.user = user

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "sessions_terminated" in response.data

    def test_logout_missing_token(self) -> None:
        """Test logout without token."""
        request = self.factory.post("/api/auth/logout")
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_token(self) -> None:
        """Test logout with invalid token."""
        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_header_format(self) -> None:
        """Test logout with invalid authorization header format."""
        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
