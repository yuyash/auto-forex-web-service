"""
Unit tests for account signals.

Tests cover:
- Auto-creation of UserSettings when User is created
- Signal handler behavior
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.signals import create_user_settings


class TestCreateUserSettingsSignal:
    """Test cases for create_user_settings signal handler."""

    @patch("apps.accounts.signals.UserSettings")
    def test_creates_settings_for_new_user(self, mock_settings: MagicMock) -> None:
        """Test that UserSettings is created for new user."""
        mock_user = MagicMock()

        create_user_settings(
            sender=MagicMock(),
            instance=mock_user,
            created=True,
        )

        mock_settings.objects.create.assert_called_once_with(user=mock_user)

    @patch("apps.accounts.signals.UserSettings")
    def test_does_not_create_settings_for_existing_user(self, mock_settings: MagicMock) -> None:
        """Test that UserSettings is not created for existing user update."""
        mock_user = MagicMock()

        create_user_settings(
            sender=MagicMock(),
            instance=mock_user,
            created=False,
        )

        mock_settings.objects.create.assert_not_called()

    @patch("apps.accounts.signals.UserSettings")
    def test_passes_correct_user_to_settings(self, mock_settings: MagicMock) -> None:
        """Test that correct user is passed to UserSettings.objects.create."""
        mock_user = MagicMock()
        mock_user.id = 123
        mock_user.email = "test@example.com"

        create_user_settings(
            sender=MagicMock(),
            instance=mock_user,
            created=True,
        )

        call_kwargs = mock_settings.objects.create.call_args[1]
        assert call_kwargs["user"] == mock_user


@pytest.mark.django_db
class TestCreateUserSettingsIntegration:
    """Integration tests for UserSettings auto-creation."""

    def test_user_settings_created_on_user_creation(self) -> None:
        """Test UserSettings is auto-created when User is created."""
        from apps.accounts.models import User, UserSettings

        user = User.objects.create_user(
            username="signaltest",
            email="signaltest@example.com",
            password="testpass123",
        )

        # UserSettings should be automatically created
        assert UserSettings.objects.filter(user=user).exists()

        settings = UserSettings.objects.get(user=user)
        assert settings.user == user

    def test_user_settings_has_defaults(self) -> None:
        """Test auto-created UserSettings has default values."""
        from apps.accounts.models import User, UserSettings

        user = User.objects.create_user(
            username="defaultstest",
            email="defaultstest@example.com",
            password="testpass123",
        )

        settings = UserSettings.objects.get(user=user)

        # Check defaults
        assert settings.notification_enabled is True
        assert settings.notification_email is True
        assert settings.notification_browser is True
        assert settings.settings_json == {}

    def test_user_settings_not_duplicated_on_save(self) -> None:
        """Test UserSettings is not duplicated when user is saved again."""
        from apps.accounts.models import User, UserSettings

        user = User.objects.create_user(
            username="nodupe",
            email="nodupe@example.com",
            password="testpass123",
        )

        # Save user again
        user.first_name = "Updated"
        user.save()

        # Should still only have one UserSettings
        assert UserSettings.objects.filter(user=user).count() == 1

    def test_user_accessible_via_related_name(self) -> None:
        """Test UserSettings is accessible via user.settings."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="relatedtest",
            email="relatedtest@example.com",
            password="testpass123",
        )

        # Access settings via related name
        settings = user.settings
        assert settings is not None
        assert settings.user == user

    def test_multiple_users_have_separate_settings(self) -> None:
        """Test each user has their own separate UserSettings."""
        from apps.accounts.models import User, UserSettings

        user1 = User.objects.create_user(
            username="user1",
            email="user1@example.com",
            password="testpass123",
        )
        user2 = User.objects.create_user(
            username="user2",
            email="user2@example.com",
            password="testpass123",
        )

        settings1 = UserSettings.objects.get(user=user1)
        settings2 = UserSettings.objects.get(user=user2)

        assert settings1.id != settings2.id
        assert settings1.user_id != settings2.user_id
