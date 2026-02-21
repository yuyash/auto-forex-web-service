"""Unit tests for UserLogoutView (mocked dependencies)."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.logout import UserLogoutView


class TestUserLogoutView:
    """Unit tests for UserLogoutView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_logout_view_initializes_security_events(self) -> None:
        """Test view initializes SecurityEventService."""
        with patch("apps.accounts.views.logout.SecurityEventService"):
            view = UserLogoutView()
            assert hasattr(view, "security_events")

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        request = self.factory.post("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1")
        view = UserLogoutView()

        ip = view.get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        view = UserLogoutView()

        ip = view.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_post_missing_authorization_header(self) -> None:
        """Test logout without authorization header."""
        request = self.factory.post("/api/auth/logout")
        view = UserLogoutView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_invalid_header_format(self) -> None:
        """Test logout with invalid authorization header format."""
        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "InvalidFormat token"
        view = UserLogoutView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_empty_token(self) -> None:
        """Test logout with empty token."""
        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "Bearer "
        view = UserLogoutView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_post_invalid_token(self) -> None:
        """Test logout with invalid token."""
        request = self.factory.post("/api/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid_token"
        view = UserLogoutView()

        with patch("apps.accounts.views.logout.JWTService") as mock_jwt:
            mock_jwt.return_value.get_user_from_token.return_value = None

            response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_classes(self) -> None:
        """Test view has IsAuthenticated permission."""
        from rest_framework.permissions import IsAuthenticated

        view = UserLogoutView()
        assert view.permission_classes == [IsAuthenticated]
