"""Unit tests for settings serializers (validation logic only)."""

from apps.accounts.serializers.settings import (
    PublicAccountSettingsSerializer,
    UserSettingsSerializer,
)


class TestUserSettingsSerializer:
    """Unit tests for UserSettingsSerializer."""

    def test_meta_fields(self) -> None:
        """Test serializer meta fields."""
        assert "notification_enabled" in UserSettingsSerializer.Meta.fields
        assert "notification_email" in UserSettingsSerializer.Meta.fields
        assert "notification_browser" in UserSettingsSerializer.Meta.fields
        assert "settings_json" in UserSettingsSerializer.Meta.fields

    def test_read_only_fields(self) -> None:
        """Test read-only fields."""
        assert "id" in UserSettingsSerializer.Meta.read_only_fields
        assert "created_at" in UserSettingsSerializer.Meta.read_only_fields
        assert "updated_at" in UserSettingsSerializer.Meta.read_only_fields


class TestPublicAccountSettingsSerializer:
    """Unit tests for PublicAccountSettingsSerializer."""

    def test_meta_fields(self) -> None:
        """Test serializer meta fields."""
        assert "registration_enabled" in PublicAccountSettingsSerializer.Meta.fields
        assert "login_enabled" in PublicAccountSettingsSerializer.Meta.fields
        assert "email_whitelist_enabled" in PublicAccountSettingsSerializer.Meta.fields
