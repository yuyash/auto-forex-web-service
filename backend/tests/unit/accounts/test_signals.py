"""Unit tests for signals.py."""

from unittest.mock import MagicMock, patch

from apps.accounts.models import User
from apps.accounts.signals import create_user_settings


class TestCreateUserSettingsSignal:
    """Unit tests for create_user_settings signal handler."""

    def test_creates_settings_for_new_user(self) -> None:
        """Test signal creates UserSettings for new user."""
        mock_user = MagicMock()
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.pk = 1

        with patch("apps.accounts.signals.UserSettings.objects.create") as mock_create:
            create_user_settings(
                sender=User,
                instance=mock_user,
                created=True,
            )

        mock_create.assert_called_once_with(user=mock_user)

    def test_does_not_create_settings_for_existing_user(self) -> None:
        """Test signal does not create UserSettings for existing user."""
        mock_user = MagicMock()

        with patch("apps.accounts.signals.UserSettings.objects.create") as mock_create:
            create_user_settings(
                sender=User,
                instance=mock_user,
                created=False,
            )

        mock_create.assert_not_called()
