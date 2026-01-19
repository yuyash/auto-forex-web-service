"""Unit tests for accounts signals."""

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.models import UserSettings

User = get_user_model()


@pytest.mark.django_db
class TestUserSignals:
    """Test signals for User model."""

    def test_user_settings_created_on_user_creation(self):
        """Test UserSettings is created when user is created."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # UserSettings should be created automatically
        assert hasattr(user, "settings")
        assert isinstance(user.settings, UserSettings)

    def test_user_settings_not_duplicated(self):
        """Test UserSettings is not duplicated on user save."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        settings_id = user.settings.id

        # Save user again
        user.first_name = "Updated"
        user.save()

        # Settings should still be the same instance
        user.refresh_from_db()  # type: ignore[attr-defined]
        assert user.settings.id == settings_id
