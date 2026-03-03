"""Integration tests for TokenRefreshView (refresh token rotation)."""

import json

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
        self.jwt = JWTService()

    def _create_user(self) -> User:
        return User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

    def test_successful_token_refresh(self) -> None:
        """Test successful token refresh with rotation."""
        user = self._create_user()
        refresh_token = self.jwt.create_refresh_token(user)

        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            content_type="application/json",
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "refresh_token" in response.data
        assert "user" in response.data
        # New refresh token should differ (rotation)
        assert response.data["refresh_token"] != refresh_token

    def test_refresh_missing_token(self) -> None:
        """Test token refresh without refresh_token in body."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_token(self) -> None:
        """Test token refresh with invalid refresh token."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": "invalid_token"}),
            content_type="application/json",
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_header_format(self) -> None:
        """Test that old Bearer header approach no longer works."""
        user = self._create_user()
        token = self.jwt.generate_token(user)

        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
        )
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        response = self.view(request)

        # Should fail because refresh_token is missing from body
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_revoked_token_rejected(self) -> None:
        """Test that a revoked refresh token is rejected."""
        user = self._create_user()
        refresh_token = self.jwt.create_refresh_token(user)

        # Use it once (rotates — old is revoked)
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            content_type="application/json",
        )
        response = self.view(request)
        assert response.status_code == status.HTTP_200_OK

        # Try to reuse the old token (should fail + family revocation)
        request2 = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({"refresh_token": refresh_token}),
            content_type="application/json",
        )
        response2 = self.view(request2)
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED
