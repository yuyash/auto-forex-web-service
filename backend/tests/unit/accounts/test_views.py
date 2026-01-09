"""
Unit tests for account views.

Tests cover:
- UserRegistrationView
- EmailVerificationView
- ResendVerificationEmailView
- UserLoginView
- UserLogoutView
- TokenRefreshView
- UserSettingsView
- PublicAccountSettingsView
"""

from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views import (
    EmailVerificationView,
    PublicAccountSettingsView,
    ResendVerificationEmailView,
    TokenRefreshView,
    UserLoginView,
    UserLogoutView,
    UserRegistrationView,
    UserSettingsView,
)


class TestUserRegistrationView:
    """Test cases for UserRegistrationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = UserRegistrationView.as_view()

    def test_get_client_ip_from_remote_addr(self) -> None:
        """Test get_client_ip extracts from REMOTE_ADDR."""
        view_instance = UserRegistrationView()
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        ip = view_instance.get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_from_x_forwarded_for(self) -> None:
        """Test get_client_ip extracts from X-Forwarded-For header."""
        view_instance = UserRegistrationView()
        request = MagicMock()
        request.META = {
            "HTTP_X_FORWARDED_FOR": "10.0.0.1, 192.168.1.1",
            "REMOTE_ADDR": "127.0.0.1",
        }

        ip = view_instance.get_client_ip(request)

        assert ip == "10.0.0.1"

    @override_settings(FRONTEND_URL="https://example.com")
    def test_build_verification_url_uses_frontend_url(self) -> None:
        """Test build_verification_url uses FRONTEND_URL setting."""
        view_instance = UserRegistrationView()
        request = MagicMock()

        url = view_instance.build_verification_url(request, "test-token")

        assert url == "https://example.com/verify-email?token=test-token"

    @pytest.mark.django_db
    def test_registration_disabled_returns_503(self) -> None:
        """Test registration returns 503 when disabled."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        settings.registration_enabled = False
        settings.save()

        request = self.factory.post(
            "/api/accounts/auth/register",
            {
                "email": "new@example.com",
                "password": "TestPass123!",
                "password_confirm": "TestPass123!",
            },
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "disabled" in response.data["error"].lower()

    @pytest.mark.django_db
    @patch("apps.accounts.services.email.boto3.client")
    def test_registration_success(self, mock_boto3_client: MagicMock) -> None:
        """Test successful registration."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        settings.registration_enabled = True
        settings.save()

        mock_boto3_client.return_value.send_email.return_value = {"MessageId": "test"}

        request = self.factory.post(
            "/api/accounts/auth/register",
            {
                "email": "newuser@example.com",
                "password": "TestPass123!",
                "password_confirm": "TestPass123!",
            },
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["email"] == "newuser@example.com"
        assert response.data["message"] is not None

    @pytest.mark.django_db
    def test_registration_invalid_data(self) -> None:
        """Test registration with invalid data."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        settings.registration_enabled = True
        settings.save()

        request = self.factory.post(
            "/api/accounts/auth/register",
            {
                "email": "invalid-email",
                "password": "short",
                "password_confirm": "short",
            },
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestEmailVerificationView:
    """Test cases for EmailVerificationView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = EmailVerificationView.as_view()

    def test_missing_token_returns_400(self) -> None:
        """Test missing token returns 400."""
        request = self.factory.post(
            "/api/accounts/auth/verify-email",
            {},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "token" in response.data["error"].lower()

    def test_invalid_token_returns_400(self) -> None:
        """Test invalid token returns 400."""
        request = self.factory.post(
            "/api/accounts/auth/verify-email",
            {"token": "invalid-token"},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "invalid" in response.data["error"].lower()

    @patch("apps.accounts.services.email.boto3.client")
    def test_valid_token_verifies_email(self, mock_boto3_client: MagicMock) -> None:
        """Test valid token verifies user email."""
        from apps.accounts.models import User

        mock_boto3_client.return_value.send_email.return_value = {"MessageId": "test"}

        user = User.objects.create_user(
            username="verifyuser",
            email="verify@example.com",
            password="testpass123",
        )
        token = user.generate_verification_token()

        request = self.factory.post(
            "/api/accounts/auth/verify-email",
            {"token": token},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["user"]["email_verified"] is True

        user.refresh_from_db()
        assert user.email_verified is True


@pytest.mark.django_db
class TestResendVerificationEmailView:
    """Test cases for ResendVerificationEmailView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = ResendVerificationEmailView.as_view()

    def test_missing_email_returns_400(self) -> None:
        """Test missing email returns 400."""
        request = self.factory.post(
            "/api/accounts/auth/resend-verification",
            {},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_nonexistent_email_returns_200(self) -> None:
        """Test nonexistent email returns 200 (security - don't reveal existence)."""
        request = self.factory.post(
            "/api/accounts/auth/resend-verification",
            {"email": "nonexistent@example.com"},
            format="json",
        )

        response = self.view(request)

        # Should return 200 to not reveal if email exists
        assert response.status_code == status.HTTP_200_OK

    def test_already_verified_returns_400(self) -> None:
        """Test already verified email returns 400."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="verified",
            email="verified@example.com",
            password="testpass123",
        )
        user.email_verified = True
        user.save()

        request = self.factory.post(
            "/api/accounts/auth/resend-verification",
            {"email": "verified@example.com"},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already verified" in response.data["error"].lower()


@pytest.mark.django_db
class TestUserLoginView:
    """Test cases for UserLoginView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = UserLoginView.as_view()

    def test_get_client_ip(self) -> None:
        """Test get_client_ip method."""
        view_instance = UserLoginView()
        request = MagicMock()
        request.META = {"REMOTE_ADDR": "192.168.1.100"}

        ip = view_instance.get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_login_disabled_returns_503(self) -> None:
        """Test login returns 503 when disabled."""
        from apps.accounts.models import PublicAccountSettings

        settings = PublicAccountSettings.get_settings()
        settings.login_enabled = False
        settings.save()

        request = self.factory.post(
            "/api/accounts/auth/login",
            {"email": "test@example.com", "password": "testpass"},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "disabled" in response.data["error"].lower()

    def test_login_success(self) -> None:
        """Test successful login."""
        from apps.accounts.models import PublicAccountSettings, User

        settings = PublicAccountSettings.get_settings()
        settings.login_enabled = True
        settings.save()

        User.objects.create_user(
            username="logintest",
            email="login@example.com",
            password="TestPass123!",
        )

        request = self.factory.post(
            "/api/accounts/auth/login",
            {"email": "login@example.com", "password": "TestPass123!"},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        # The response uses "token" key, not "access_token"
        assert "token" in response.data

    def test_login_invalid_credentials(self) -> None:
        """Test login with invalid credentials."""
        from apps.accounts.models import PublicAccountSettings, User

        settings = PublicAccountSettings.get_settings()
        settings.login_enabled = True
        settings.save()

        User.objects.create_user(
            username="logintest",
            email="login@example.com",
            password="TestPass123!",
        )

        request = self.factory.post(
            "/api/accounts/auth/login",
            {"email": "login@example.com", "password": "WrongPassword!"},
            format="json",
        )

        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_login_whitelist_blocks_logs_when_credentials_valid(self, caplog) -> None:
        """Test whitelist block logs a clear message even when password is correct."""
        import logging

        from apps.accounts.models import PublicAccountSettings, User

        settings = PublicAccountSettings.get_settings()
        settings.login_enabled = True
        settings.email_whitelist_enabled = True
        settings.save()

        User.objects.create_user(
            username="logintest",
            email="login@example.com",
            password="TestPass123!",
            is_staff=True,
            is_superuser=True,
        )

        with caplog.at_level(logging.WARNING):
            request = self.factory.post(
                "/api/accounts/auth/login",
                {"email": "login@example.com", "password": "TestPass123!"},
                format="json",
            )

            response = self.view(request)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "Authentication blocked - email not whitelisted" in caplog.text
        assert "credentials_valid=True" in caplog.text


@pytest.mark.django_db
class TestUserLogoutView:
    """Test cases for UserLogoutView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = UserLogoutView.as_view()

    def test_logout_requires_authentication(self) -> None:
        """Test logout requires authentication."""
        request = self.factory.post("/api/accounts/auth/logout")

        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_success_with_jwt_header(self) -> None:
        """Test successful logout with JWT in header."""
        from apps.accounts.models import User
        from apps.accounts.services.jwt import JWTService

        user = User.objects.create_user(
            username="logoutuser",
            email="logout@example.com",
            password="testpass123",
        )

        token = JWTService().generate_token(user)
        request = self.factory.post("/api/accounts/auth/logout")
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTokenRefreshView:
    """Test cases for TokenRefreshView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = TokenRefreshView.as_view()

    def test_refresh_missing_token_returns_401(self) -> None:
        """Test refresh with missing token returns 401 (unauthorized)."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            {},
            format="json",
        )

        response = self.view(request)

        # The view requires authentication, so missing token = 401
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_invalid_token_returns_401(self) -> None:
        """Test refresh with invalid token returns 401."""
        request = self.factory.post(
            "/api/accounts/auth/refresh",
            {"refresh_token": "invalid-token"},
            format="json",
        )
        # Add invalid token in header
        request.META["HTTP_AUTHORIZATION"] = "Bearer invalid-token"

        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_refresh_valid_token(self) -> None:
        """Test refresh with valid token."""
        from apps.accounts.models import User
        from apps.accounts.services.jwt import JWTService

        user = User.objects.create_user(
            username="refreshuser",
            email="refresh@example.com",
            password="testpass123",
        )

        token = JWTService().generate_token(user)

        request = self.factory.post(
            "/api/accounts/auth/refresh",
            {"refresh_token": token},
            format="json",
        )
        # Add token in header for authentication
        request.META["HTTP_AUTHORIZATION"] = f"Bearer {token}"

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data


@pytest.mark.django_db
class TestUserSettingsView:
    """Test cases for UserSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = UserSettingsView.as_view()

    def test_get_settings_requires_authentication(self) -> None:
        """Test get settings requires authentication."""
        request = self.factory.get("/api/accounts/settings")

        response = self.view(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_get_settings_success(self) -> None:
        """Test successful get settings."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="settingsuser",
            email="settings@example.com",
            password="testpass123",
        )

        request = self.factory.get("/api/accounts/settings")
        from rest_framework.test import force_authenticate

        force_authenticate(request, user=user)

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        # The response has nested structure: {"settings": {...}, "user": {...}}
        assert "settings" in response.data
        assert "notification_enabled" in response.data["settings"]

    def test_update_settings_success(self) -> None:
        """Test successful settings update."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="updateuser",
            email="update@example.com",
            password="testpass123",
        )

        request = self.factory.put(
            "/api/accounts/settings",
            {"notification_enabled": False},
            format="json",
        )
        from rest_framework.test import force_authenticate

        force_authenticate(request, user=user)

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK
        # The response has nested structure: {"settings": {...}, "user": {...}}
        assert response.data["settings"]["notification_enabled"] is False


@pytest.mark.django_db
class TestPublicAccountSettingsView:
    """Test cases for PublicAccountSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()
        self.view = PublicAccountSettingsView.as_view()

    def test_get_public_settings_no_auth_required(self) -> None:
        """Test get public settings doesn't require authentication."""
        request = self.factory.get("/api/accounts/settings/public")

        response = self.view(request)

        assert response.status_code == status.HTTP_200_OK

    def test_get_public_settings_returns_expected_fields(self) -> None:
        """Test get public settings returns expected fields."""
        request = self.factory.get("/api/accounts/settings/public")

        response = self.view(request)

        assert "registration_enabled" in response.data
        assert "login_enabled" in response.data
        assert "email_whitelist_enabled" in response.data

    def test_get_public_settings_only_has_3_fields(self) -> None:
        """Test public settings only exposes 3 fields."""
        request = self.factory.get("/api/accounts/settings/public")

        response = self.view(request)

        assert len(response.data) == 3
