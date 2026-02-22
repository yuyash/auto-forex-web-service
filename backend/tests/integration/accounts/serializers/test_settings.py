"""Integration tests for settings serializers (with database)."""

import pytest

from apps.accounts.models import PublicAccountSettings, User, UserSettings
from apps.accounts.serializers.settings import (
    PublicAccountSettingsSerializer,
    UserSettingsSerializer,
)


@pytest.mark.django_db
class TestUserSettingsSerializerIntegration:
    """Integration tests for UserSettingsSerializer."""

    def test_serialize_user_settings(self) -> None:
        """Test serializing user settings."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        settings, created = UserSettings.objects.get_or_create(user=user)
        if not created:
            # Signal already created it, update values
            settings.notification_enabled = True
            settings.notification_email = False
            settings.notification_browser = True
            settings.save()

        serializer = UserSettingsSerializer(settings)
        data = serializer.data

        assert data["notification_enabled"] is True
        assert data["notification_email"] is False
        assert data["notification_browser"] is True

    def test_update_user_settings(self) -> None:
        """Test updating user settings."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )
        settings, _ = UserSettings.objects.get_or_create(user=user)

        data = {
            "notification_enabled": False,
            "notification_email": False,
        }
        serializer = UserSettingsSerializer(settings, data=data, partial=True)
        assert serializer.is_valid()

        updated_settings = serializer.save()
        assert updated_settings.notification_enabled is False
        assert updated_settings.notification_email is False


@pytest.mark.django_db
class TestPublicAccountSettingsSerializerIntegration:
    """Integration tests for PublicAccountSettingsSerializer."""

    def test_serialize_public_settings(self) -> None:
        """Test serializing public account settings."""
        settings = PublicAccountSettings.get_settings()
        settings.registration_enabled = True
        settings.login_enabled = True
        settings.email_whitelist_enabled = False
        settings.save()

        serializer = PublicAccountSettingsSerializer(settings)
        data = serializer.data

        assert data["registration_enabled"] is True
        assert data["login_enabled"] is True
        assert data["email_whitelist_enabled"] is False
