"""Unit tests for TokenRefreshView."""

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.services.jwt import JWTService
from apps.accounts.views.refresh import TokenRefreshView


@pytest.mark.django_db
class TestTokenRefreshView:
    """Tests for TokenRefreshView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.view = TokenRefreshView.as_view()

    def test_successful_token_refresh(self) -> None:
        """Test successful token refresh."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

        # Generate token
        token = JWTService().generate_token(user)

        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "user" in response.data

    def test_refresh_missing_token(self) -> None:
        """Test token refresh without token."""
        request = self.factory.post("/api/auth/refresh")
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_token(self) -> None:
        """Test token refresh with invalid token."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_header_format(self) -> None:
        """Test token refresh with invalid authorization header format."""
        request = self.factory.post("/api/auth/refresh")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
