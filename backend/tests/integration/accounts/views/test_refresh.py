"""Integration tests for TokenRefreshView (refresh token rotation)."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import RefreshToken, User
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
        stored_token = RefreshToken.objects.get(user=user)

        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE=f"refresh_token={refresh_token}",
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "refresh_token" not in response.data
        assert "user" in response.data
        assert response.cookies["refresh_token"].value != refresh_token
        assert stored_token.token == JWTService.hash_refresh_token(refresh_token)
        assert stored_token.token != refresh_token

        stored_token.refresh_from_db()
        assert stored_token.revoked_at is not None
        assert RefreshToken.objects.filter(user=user).count() == 2

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

        # Should fail because refresh-token cookie is missing.
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_revoked_token_rejected(self) -> None:
        """Test that a revoked refresh token is rejected."""
        user = self._create_user()
        refresh_token = self.jwt.create_refresh_token(user)

        # Use it once (rotates — old is revoked)
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE=f"refresh_token={refresh_token}",
        )
        response = self.view(request)
        assert response.status_code == status.HTTP_200_OK

        # Try to reuse the old token (should fail + family revocation)
        request2 = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE=f"refresh_token={refresh_token}",
        )
        response2 = self.view(request2)
        assert response2.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_accepts_legacy_plaintext_refresh_token(self) -> None:
        """Test rollout compatibility for legacy plaintext DB rows."""
        user = self._create_user()
        refresh_token = "legacy_plaintext_refresh_token"
        legacy_row = RefreshToken.objects.create(
            user=user,
            token=refresh_token,
            expires_at=datetime.now(UTC) + timedelta(days=7),
        )

        request = self.factory.post(
            "/api/accounts/auth/refresh",
            data=json.dumps({}),
            content_type="application/json",
            HTTP_COOKIE=f"refresh_token={refresh_token}",
        )
        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        legacy_row.refresh_from_db()
        assert legacy_row.revoked_at is not None
        assert RefreshToken.objects.filter(user=user).count() == 2
