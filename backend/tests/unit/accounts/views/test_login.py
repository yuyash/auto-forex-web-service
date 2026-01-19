"""Unit tests for UserLoginView (mocked dependencies)."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.login import UserLoginView


class TestUserLoginView:
    """Unit tests for UserLoginView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_login_view_initializes_security_events(self) -> None:
        """Test view initializes SecurityEventService."""
        with patch("apps.accounts.views.login.SecurityEventService"):
            view = UserLoginView()
            assert hasattr(view, "security_events")

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        request = self.factory.post("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1")
        view = UserLoginView()

        ip = view.get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        view = UserLoginView()

        ip = view.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_post_login_disabled(self) -> None:
        """Test login when disabled."""
        request = self.factory.post("/api/auth/login", {"email": "test@example.com"}, format="json")
        view = UserLoginView()

        with patch("apps.accounts.views.login.PublicAccountSettings") as mock_settings:
            mock_settings.get_settings.return_value.login_enabled = False

            response = view.post(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = UserLoginView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = UserLoginView()
        assert view.authentication_classes == []
