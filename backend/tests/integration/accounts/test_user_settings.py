"""
Integration tests for user settings endpoint.

Tests the following endpoints using live_server:
- GET /api/accounts/settings/
- PUT /api/accounts/settings/
"""

from django.contrib.auth import get_user_model

import pytest
import requests

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestUserSettingsGet:
    """Integration tests for GET user settings endpoint."""

    def test_get_settings_authenticated(self, live_server, test_user, auth_headers):
        """Test getting user settings when authenticated."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "user" in json_data
        assert "settings" in json_data

    def test_get_settings_unauthenticated(self, live_server):
        """Test getting user settings fails when not authenticated."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.get(url, timeout=10)

        assert response.status_code == 401

    def test_get_settings_invalid_token(self, live_server):
        """Test getting user settings fails with invalid token."""
        url = f"{live_server.url}/api/accounts/settings/"
        headers = {"Authorization": "Bearer invalid_token"}

        response = requests.get(url, headers=headers, timeout=10)

        assert response.status_code == 401

    def test_get_settings_returns_user_profile(self, live_server, test_user, auth_headers):
        """Test settings response includes user profile data."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        user_data = json_data["user"]
        assert user_data["email"] == test_user.email
        assert user_data["username"] == test_user.username
        assert "timezone" in user_data
        assert "language" in user_data

    def test_get_settings_returns_settings_data(self, live_server, test_user, auth_headers):
        """Test settings response includes settings data."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        settings_data = json_data["settings"]
        assert "notification_enabled" in settings_data
        assert "notification_email" in settings_data
        assert "notification_browser" in settings_data


@pytest.mark.django_db(transaction=True)
class TestUserSettingsUpdate:
    """Integration tests for PUT user settings endpoint."""

    def test_update_settings_authenticated(self, live_server, test_user, auth_headers):
        """Test updating user settings when authenticated."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {
            "timezone": "America/New_York",
            "language": "ja",
        }

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["timezone"] == "America/New_York"
        assert json_data["user"]["language"] == "ja"

    def test_update_settings_unauthenticated(self, live_server):
        """Test updating user settings fails when not authenticated."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"timezone": "America/New_York"}

        response = requests.put(url, json=data, timeout=10)

        assert response.status_code == 401

    def test_update_notification_settings(self, live_server, test_user, auth_headers):
        """Test updating notification settings."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {
            "notification_enabled": True,
            "notification_email": True,
            "notification_browser": False,
        }

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        settings = json_data["settings"]
        assert settings["notification_enabled"] is True
        assert settings["notification_email"] is True
        assert settings["notification_browser"] is False

    def test_update_timezone_only(self, live_server, test_user, auth_headers):
        """Test partial update - timezone only."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"timezone": "Europe/London"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["timezone"] == "Europe/London"

    def test_update_language_only(self, live_server, test_user, auth_headers):
        """Test partial update - language only."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"language": "ja"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["language"] == "ja"

    def test_update_with_empty_body(self, live_server, test_user, auth_headers):
        """Test update with empty body (no changes)."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.put(url, json={}, headers=auth_headers, timeout=10)

        assert response.status_code == 200

    def test_update_settings_invalid_language(self, live_server, test_user, auth_headers):
        """Test update fails with invalid language code."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"language": "invalid_lang"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        # Should fail validation
        assert response.status_code == 400

    def test_settings_persist_after_update(self, live_server, test_user, auth_headers):
        """Test that settings changes persist."""
        url = f"{live_server.url}/api/accounts/settings/"

        # Update settings
        update_data = {"timezone": "Asia/Tokyo"}
        update_response = requests.put(url, json=update_data, headers=auth_headers, timeout=10)
        assert update_response.status_code == 200

        # Get settings and verify
        get_response = requests.get(url, headers=auth_headers, timeout=10)
        assert get_response.status_code == 200
        json_data = get_response.json()
        assert json_data["user"]["timezone"] == "Asia/Tokyo"

    def test_update_first_name(self, live_server, test_user, auth_headers):
        """Test updating user first_name."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"first_name": "UpdatedFirstName"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["first_name"] == "UpdatedFirstName"

    def test_update_last_name(self, live_server, test_user, auth_headers):
        """Test updating user last_name."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"last_name": "UpdatedLastName"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["last_name"] == "UpdatedLastName"

    def test_update_first_and_last_name(self, live_server, test_user, auth_headers):
        """Test updating both first_name and last_name."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {
            "first_name": "John",
            "last_name": "Doe",
        }

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["first_name"] == "John"
        assert json_data["user"]["last_name"] == "Doe"

    def test_update_username(self, live_server, test_user, auth_headers):
        """Test updating username."""
        url = f"{live_server.url}/api/accounts/settings/"
        data = {"username": "newusername123"}

        response = requests.put(url, json=data, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["username"] == "newusername123"

    def test_get_settings_returns_first_and_last_name(self, live_server, test_user, auth_headers):
        """Test settings response includes first_name and last_name."""
        url = f"{live_server.url}/api/accounts/settings/"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        user_data = json_data["user"]
        assert "first_name" in user_data
        assert "last_name" in user_data
