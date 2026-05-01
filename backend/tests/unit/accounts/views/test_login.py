"""Unit tests for UserLoginView (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.middlewares.utils import get_client_ip
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

        ip = get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        request = self.factory.post("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        ip = get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_post_login_disabled(self) -> None:
        """Test login when disabled."""
        request = self.factory.post(
            "/api/accounts/auth/login", {"email": "test@example.com"}, format="json"
        )
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

    def test_successful_login_sets_refresh_cookie(self) -> None:
        """Test successful login sets auth cookies without exposing tokens in JSON."""
        request = self.factory.post(
            "/api/accounts/auth/login",
            {"email": "test@example.com", "password": "secret"},
            format="json",
        )
        view = UserLoginView()

        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.username = "testuser"
        mock_user.is_staff = False
        mock_user.timezone = "UTC"
        mock_user.language = "en"
        mock_user.reset_failed_login = MagicMock()

        serializer_instance = MagicMock()
        serializer_instance.is_valid.return_value = True
        serializer_instance.validated_data = {"user": mock_user}
        view.serializer_class = MagicMock(return_value=serializer_instance)

        with (
            patch("apps.accounts.views.login.PublicAccountSettings") as mock_settings,
            patch("apps.accounts.views.login.RateLimiter") as mock_rate_limiter,
            patch("apps.accounts.views.login.User") as mock_user_model,
            patch("apps.accounts.views.login.JWTService") as mock_jwt,
        ):
            mock_settings.get_settings.return_value.login_enabled = True
            mock_rate_limiter.is_ip_blocked.return_value = (False, None)
            mock_user_model.DoesNotExist = Exception
            mock_user_model.objects.get.side_effect = mock_user_model.DoesNotExist
            mock_jwt.return_value.generate_token.return_value = "access-token"
            mock_jwt.return_value.create_refresh_token.return_value = "refresh-token"

            response = view.post(view.initialize_request(request))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["authenticated"] is True  # type: ignore[index]
        assert "token" not in response.data  # type: ignore[operator]
        assert "refresh_token" not in response.data  # type: ignore[operator]
        assert response.cookies["refresh_token"].value == "refresh-token"
        assert response.cookies["access_token"].value == "access-token"
