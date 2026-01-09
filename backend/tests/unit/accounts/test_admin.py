"""
Unit tests for accounts admin configuration.

Tests cover:
- UserAdmin
- UserSettingsAdmin
- UserSessionAdmin
- BlockedIPAdmin
"""

import pytest
from django.contrib.admin.sites import AdminSite

from apps.accounts.admin import BlockedIPAdmin, UserAdmin, UserSessionAdmin, UserSettingsAdmin
from apps.accounts.models import BlockedIP, User, UserSession, UserSettings


@pytest.mark.django_db
class TestUserAdmin:
    """Test cases for UserAdmin."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = UserAdmin(User, self.site)

    def test_list_display_fields(self) -> None:
        """Test list_display contains expected fields."""
        expected_fields = [
            "email",
            "username",
            "first_name",
            "last_name",
            "is_staff",
            "is_active",
            "is_locked",
            "failed_login_attempts",
            "created_at",
        ]
        assert self.admin.list_display == expected_fields

    def test_list_filter_fields(self) -> None:
        """Test list_filter contains expected fields."""
        expected_fields = [
            "is_staff",
            "is_active",
            "is_locked",
            "language",
            "created_at",
        ]
        assert self.admin.list_filter == expected_fields

    def test_search_fields(self) -> None:
        """Test search_fields contains expected fields."""
        assert self.admin.search_fields == ["email", "username", "first_name", "last_name"]

    def test_ordering(self) -> None:
        """Test ordering is by created_at descending."""
        assert self.admin.ordering == ["-created_at"]

    def test_fieldsets_includes_additional_info(self) -> None:
        """Test fieldsets includes Additional Info section."""
        fieldset_names = [fs[0] for fs in self.admin.fieldsets]
        assert "Additional Info" in fieldset_names

    def test_additional_info_fields(self) -> None:
        """Test Additional Info fieldset contains expected fields."""
        additional_info = None
        for name, options in self.admin.fieldsets:
            if name == "Additional Info":
                additional_info = options
                break

        assert additional_info is not None
        expected_fields = (
            "timezone",
            "language",
            "is_locked",
            "failed_login_attempts",
            "last_login_attempt",
        )
        assert additional_info["fields"] == expected_fields


@pytest.mark.django_db
class TestUserSettingsAdmin:
    """Test cases for UserSettingsAdmin."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = UserSettingsAdmin(UserSettings, self.site)

    def test_list_display_fields(self) -> None:
        """Test list_display contains expected fields."""
        expected_fields = [
            "user",
            "notification_enabled",
            "updated_at",
        ]
        assert self.admin.list_display == expected_fields

    def test_list_filter_fields(self) -> None:
        """Test list_filter contains expected fields."""
        assert self.admin.list_filter == ["notification_enabled"]

    def test_search_fields(self) -> None:
        """Test search_fields contains expected fields."""
        assert self.admin.search_fields == ["user__email", "user__username"]

    def test_readonly_fields(self) -> None:
        """Test readonly_fields contains timestamp fields."""
        assert self.admin.readonly_fields == ["created_at", "updated_at"]


@pytest.mark.django_db
class TestUserSessionAdmin:
    """Test cases for UserSessionAdmin."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = UserSessionAdmin(UserSession, self.site)

    def test_list_display_fields(self) -> None:
        """Test list_display contains expected fields."""
        expected_fields = [
            "user",
            "ip_address",
            "login_time",
            "last_activity",
            "is_active",
        ]
        assert self.admin.list_display == expected_fields

    def test_list_filter_fields(self) -> None:
        """Test list_filter contains expected fields."""
        assert self.admin.list_filter == ["is_active", "login_time"]

    def test_search_fields(self) -> None:
        """Test search_fields contains expected fields."""
        assert self.admin.search_fields == ["user__email", "ip_address", "session_key"]

    def test_readonly_fields(self) -> None:
        """Test readonly_fields contains timestamp fields."""
        expected_fields = ["login_time", "last_activity", "logout_time"]
        assert self.admin.readonly_fields == expected_fields

    def test_ordering(self) -> None:
        """Test ordering is by login_time descending."""
        assert self.admin.ordering == ["-login_time"]


@pytest.mark.django_db
class TestBlockedIPAdmin:
    """Test cases for BlockedIPAdmin."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = BlockedIPAdmin(BlockedIP, self.site)

    def test_list_display_fields(self) -> None:
        """Test list_display contains expected fields."""
        expected_fields = [
            "ip_address",
            "reason",
            "failed_attempts",
            "blocked_at",
            "blocked_until",
            "is_permanent",
        ]
        assert self.admin.list_display == expected_fields

    def test_list_filter_fields(self) -> None:
        """Test list_filter contains expected fields."""
        assert self.admin.list_filter == ["is_permanent", "blocked_at"]
