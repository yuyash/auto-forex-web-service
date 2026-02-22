"""Unit tests for email verification views (mocked dependencies)."""

from unittest.mock import patch

from rest_framework.test import APIRequestFactory

from apps.accounts.views.verification import EmailVerificationView, ResendVerificationEmailView


class TestEmailVerificationView:
    """Unit tests for EmailVerificationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = EmailVerificationView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = EmailVerificationView()
        assert view.authentication_classes == []


class TestResendVerificationEmailView:
    """Unit tests for ResendVerificationEmailView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_build_verification_url_with_frontend_url(self) -> None:
        """Test building verification URL with FRONTEND_URL setting."""
        request = self.factory.post("/api/auth/resend-verification")
        view = ResendVerificationEmailView()

        with patch("apps.accounts.views.verification.settings") as mock_settings:
            mock_settings.FRONTEND_URL = "https://example.com"
            url = view.build_verification_url(request, "test_token")

        assert url == "https://example.com/verify-email?token=test_token"

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = ResendVerificationEmailView()
        assert view.permission_classes == [AllowAny]

    def test_authentication_classes(self) -> None:
        """Test view has no authentication classes."""
        view = ResendVerificationEmailView()
        assert view.authentication_classes == []
