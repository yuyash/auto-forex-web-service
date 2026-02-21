"""Unit tests for UserRegistrationView (mocked dependencies)."""

from unittest.mock import patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.registration import UserRegistrationView


class TestUserRegistrationView:
    """Unit tests for UserRegistrationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_registration_view_initializes_security_events(self) -> None:
        """Test view initializes SecurityEventService."""
        with patch("apps.accounts.views.registration.SecurityEventService"):
            view = UserRegistrationView()
            assert hasattr(view, "security_events")

    def test_build_verification_url_with_frontend_url(self) -> None:
        """Test building verification URL with FRONTEND_URL setting."""
        request = self.factory.post("/api/auth/register")
        view = UserRegistrationView()

        with patch("apps.accounts.views.registration.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "https://example.com"
            url = view.build_verification_url(request, "test_token")

        assert url == "https://example.com/verify-email?token=test_token"

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        request = self.factory.post("/", HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1")
        view = UserRegistrationView()

        ip = view.get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        view = UserRegistrationView()

        ip = view.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_post_registration_disabled(self) -> None:
        """Test registration when disabled."""
        request = self.factory.post(
            "/api/auth/register", {"email": "test@example.com"}, format="json"
        )
        view = UserRegistrationView()

        with patch("apps.accounts.views.registration.PublicAccountSettings") as mock_settings:
            mock_settings.get_settings.return_value.registration_enabled = False

            response = view.post(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = UserRegistrationView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = UserRegistrationView()
        assert view.authentication_classes == []
