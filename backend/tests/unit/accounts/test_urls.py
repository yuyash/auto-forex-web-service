"""Unit tests for urls.py."""

from django.urls import resolve, reverse

from apps.accounts.views import (
    EmailVerificationView,
    PublicAccountSettingsView,
    ResendVerificationEmailView,
    TokenRefreshView,
    UserLoginView,
    UserLogoutView,
    UserNotificationListView,
    UserNotificationMarkAllReadView,
    UserNotificationMarkReadView,
    UserRegistrationView,
    UserSettingsView,
)


class TestAccountsURLs:
    """Unit tests for accounts URL configuration."""

    def test_register_url_resolves(self) -> None:
        """Test register URL resolves to correct view."""
        url = reverse("accounts:register")
        resolved = resolve(url)
        assert resolved.func.view_class == UserRegistrationView  # type: ignore[attr-defined]

    def test_login_url_resolves(self) -> None:
        """Test login URL resolves to correct view."""
        url = reverse("accounts:login")
        resolved = resolve(url)
        assert resolved.func.view_class == UserLoginView  # type: ignore[attr-defined]

    def test_logout_url_resolves(self) -> None:
        """Test logout URL resolves to correct view."""
        url = reverse("accounts:logout")
        resolved = resolve(url)
        assert resolved.func.view_class == UserLogoutView  # type: ignore[attr-defined]

    def test_token_refresh_url_resolves(self) -> None:
        """Test token refresh URL resolves to correct view."""
        url = reverse("accounts:token_refresh")
        resolved = resolve(url)
        assert resolved.func.view_class == TokenRefreshView  # type: ignore[attr-defined]

    def test_verify_email_url_resolves(self) -> None:
        """Test verify email URL resolves to correct view."""
        url = reverse("accounts:verify_email")
        resolved = resolve(url)
        assert resolved.func.view_class == EmailVerificationView  # type: ignore[attr-defined]

    def test_resend_verification_url_resolves(self) -> None:
        """Test resend verification URL resolves to correct view."""
        url = reverse("accounts:resend_verification")
        resolved = resolve(url)
        assert resolved.func.view_class == ResendVerificationEmailView  # type: ignore[attr-defined]

    def test_user_settings_url_resolves(self) -> None:
        """Test user settings URL resolves to correct view."""
        url = reverse("accounts:user_settings")
        resolved = resolve(url)
        assert resolved.func.view_class == UserSettingsView  # type: ignore[attr-defined]

    def test_public_account_settings_url_resolves(self) -> None:
        """Test public account settings URL resolves to correct view."""
        url = reverse("accounts:public_account_settings")
        resolved = resolve(url)
        assert resolved.func.view_class == PublicAccountSettingsView  # type: ignore[attr-defined]

    def test_notifications_url_resolves(self) -> None:
        """Test notifications URL resolves to correct view."""
        url = reverse("accounts:notifications")
        resolved = resolve(url)
        assert resolved.func.view_class == UserNotificationListView  # type: ignore[attr-defined]

    def test_notification_read_url_resolves(self) -> None:
        """Test notification read URL resolves to correct view."""
        url = reverse("accounts:notification_read", kwargs={"notification_id": 1})
        resolved = resolve(url)
        assert resolved.func.view_class == UserNotificationMarkReadView  # type: ignore[attr-defined]

    def test_notifications_read_all_url_resolves(self) -> None:
        """Test notifications read all URL resolves to correct view."""
        url = reverse("accounts:notifications_read_all")
        resolved = resolve(url)
        assert resolved.func.view_class == UserNotificationMarkAllReadView  # type: ignore[attr-defined]
