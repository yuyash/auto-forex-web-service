"""Unit tests for admin.py."""

from apps.accounts.admin import (
    BlockedIPAdmin,
    PublicAccountSettingsAdmin,
    UserAdmin,
    UserSessionAdmin,
    UserSettingsAdmin,
)


class TestAdminClasses:
    """Unit tests for admin class configurations."""

    def test_user_admin_list_display(self) -> None:
        """Test UserAdmin list_display configuration."""
        assert "email" in UserAdmin.list_display
        assert "username" in UserAdmin.list_display
        assert "is_locked" in UserAdmin.list_display

    def test_user_settings_admin_list_display(self) -> None:
        """Test UserSettingsAdmin list_display configuration."""
        assert "user" in UserSettingsAdmin.list_display
        assert "notification_enabled" in UserSettingsAdmin.list_display

    def test_user_session_admin_list_display(self) -> None:
        """Test UserSessionAdmin list_display configuration."""
        assert "user" in UserSessionAdmin.list_display
        assert "ip_address" in UserSessionAdmin.list_display
        assert "is_active" in UserSessionAdmin.list_display

    def test_blocked_ip_admin_list_display(self) -> None:
        """Test BlockedIPAdmin list_display configuration."""
        assert "ip_address" in BlockedIPAdmin.list_display
        assert "is_permanent" in BlockedIPAdmin.list_display

    def test_public_account_settings_admin_has_no_delete(self) -> None:
        """Test PublicAccountSettingsAdmin prevents deletion."""
        from django.contrib.admin import AdminSite

        from apps.accounts.models import PublicAccountSettings

        admin = PublicAccountSettingsAdmin(model=PublicAccountSettings, admin_site=AdminSite())
        assert admin.has_delete_permission(request=None) is False
