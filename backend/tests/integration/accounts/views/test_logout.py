"""Integration tests for UserLogoutView."""

import pytest
from django.test import RequestFactory
from rest_framework import status

from apps.accounts.models import RefreshToken, User, UserSession
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

        request = self.factory.post("/api/accounts/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        request.user = user
        request.session = type("Session", (), {"session_key": "test_session"})()

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "sessions_terminated" in response.data
        assert response.data["sessions_terminated"] == 1

    def test_logout_missing_token(self) -> None:
        """Test logout without token."""
        request = self.factory.post("/api/accounts/auth/logout")
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_token(self) -> None:
        """Test logout with invalid token."""
        request = self.factory.post("/api/accounts/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_invalid_header_format(self) -> None:
        """Test logout with invalid authorization header format."""
        request = self.factory.post("/api/accounts/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token"
        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_only_revokes_current_session_tokens(self) -> None:
        """Logging out one client should leave another client's refresh token valid."""
        user = User.objects.create_user(
            email="test2@example.com",
            username="testuser2",
            password="TestPass123!",
        )
        session_a = UserSession.objects.create(
            user=user,
            session_key="session-a",
            ip_address="127.0.0.1",
        )
        session_b = UserSession.objects.create(
            user=user,
            session_key="session-b",
            ip_address="127.0.0.2",
        )
        jwt_service = JWTService()
        refresh_a = jwt_service.create_refresh_token(user, session=session_a)
        refresh_b = jwt_service.create_refresh_token(user, session=session_b)
        token = jwt_service.generate_token(user)

        request = self.factory.post(
            "/api/accounts/auth/logout", HTTP_COOKIE=f"refresh_token={refresh_a}"
        )
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"
        request.user = user
        request.session = type("Session", (), {"session_key": "session-a"})()

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        session_a.refresh_from_db()
        session_b.refresh_from_db()
        assert session_a.is_active is False
        assert session_b.is_active is True

        token_a = RefreshToken.objects.get(token=JWTService.hash_refresh_token(refresh_a))
        token_b = RefreshToken.objects.get(token=JWTService.hash_refresh_token(refresh_b))
        assert token_a.revoked_at is not None
        assert token_b.revoked_at is None
