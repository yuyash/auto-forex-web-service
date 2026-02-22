"""Unit tests for settings models."""

import pytest

from apps.accounts.models import PublicAccountSettings, User, UserSettings


@pytest.mark.django_db
class TestUserSettings:
    """Tests for UserSettings model."""

    def test_create_user_settings(self) -> None:
        """Test creating user settings."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        settings, created = UserSettings.objects.get_or_create(
            user=user,
            defaults={
                "notification_enabled": True,
                "notification_email": True,
                "notification_browser": False,
            },
        )
        if not created:
            settings.notification_browser = False
            settings.save()

        assert settings.user == user
        assert settings.notification_enabled is True
        assert settings.notification_browser is False

    def test_user_settings_defaults(self) -> None:
        """Test user settings default values."""
        user = User.objects.create_user(
            email="test2@example.com",
            username="testuser2",
            password="testpass123",
        )
        settings, _ = UserSettings.objects.get_or_create(user=user)
        assert settings.notification_enabled is True
        assert settings.notification_email is True
        assert settings.notification_browser is True


@pytest.mark.django_db
class TestPublicAccountSettings:
    """Tests for PublicAccountSettings model."""

    def test_get_settings_creates_singleton(self) -> None:
        """Test get_settings creates singleton instance."""
        settings = PublicAccountSettings.get_settings()
        assert settings.pk == 1
        assert settings.registration_enabled is True
        assert settings.login_enabled is True

    def test_get_settings_returns_existing(self) -> None:
        """Test get_settings returns existing instance."""
        settings1 = PublicAccountSettings.get_settings()
        settings1.registration_enabled = False
        settings1.save()

        settings2 = PublicAccountSettings.get_settings()
        assert settings2.pk == settings1.pk
        assert settings2.registration_enabled is False

    def test_save_enforces_singleton(self) -> None:
        """Test save enforces singleton pattern."""
        settings = PublicAccountSettings()
        settings.registration_enabled = False
        settings.save()

        assert settings.pk == 1
        assert PublicAccountSettings.objects.count() == 1
