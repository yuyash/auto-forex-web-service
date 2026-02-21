"""Integration tests for settings views (with database)."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User


@pytest.mark.django_db
class TestUserSettingsViewIntegration:
    """Integration tests for UserSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

    def test_get_user_settings(self) -> None:
        """Test getting user settings."""
        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:user_settings")

        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "user" in response.data
        assert "settings" in response.data

    def test_update_user_settings(self) -> None:
        """Test updating user settings."""
        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:user_settings")

        data = {
            "timezone": "Asia/Tokyo",
            "language": "ja",
            "notification_enabled": False,
        }
        response = self.client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        self.user.refresh_from_db()
        assert self.user.timezone == "Asia/Tokyo"
        assert self.user.language == "ja"

    def test_get_settings_unauthenticated(self) -> None:
        """Test getting settings without authentication."""
        url = reverse("accounts:user_settings")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestPublicAccountSettingsViewIntegration:
    """Integration tests for PublicAccountSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = APIClient()

    def test_get_public_settings(self) -> None:
        """Test getting public account settings."""
        url = reverse("accounts:public_account_settings")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "registration_enabled" in response.data
        assert "login_enabled" in response.data
        assert "email_whitelist_enabled" in response.data

    def test_get_public_settings_no_auth_required(self) -> None:
        """Test public settings endpoint doesn't require authentication."""
        url = reverse("accounts:public_account_settings")
        # Explicitly unauthenticated
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
