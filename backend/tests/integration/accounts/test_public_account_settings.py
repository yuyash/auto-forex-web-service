"""
Integration tests for public account settings endpoint.

Tests the following endpoints using live_server:
- GET /api/accounts/settings/public
"""

import pytest
import requests


@pytest.mark.django_db(transaction=True)
class TestPublicAccountSettingsGet:
    """Integration tests for GET public account settings endpoint."""

    def test_get_public_settings_no_auth_required(self, live_server):
        """Test getting public settings works without authentication."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "registration_enabled" in json_data
        assert "login_enabled" in json_data
        assert "email_whitelist_enabled" in json_data

    def test_get_public_settings_returns_boolean_values(self, live_server):
        """Test public settings returns boolean values."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert isinstance(json_data["registration_enabled"], bool)
        assert isinstance(json_data["login_enabled"], bool)
        assert isinstance(json_data["email_whitelist_enabled"], bool)

    def test_get_public_settings_default_values(self, live_server):
        """Test public settings returns expected default values."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        # Default values as defined in the model
        assert json_data["registration_enabled"] is True
        assert json_data["login_enabled"] is True
        assert json_data["email_whitelist_enabled"] is False

    def test_get_public_settings_authenticated_also_works(self, live_server, auth_headers):
        """Test public settings also works when authenticated."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "registration_enabled" in json_data
        assert "login_enabled" in json_data
        assert "email_whitelist_enabled" in json_data

    def test_get_public_settings_does_not_expose_extra_fields(self, live_server):
        """Test public settings only exposes the 3 public fields."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.get(url, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        # Should only have these 3 fields
        expected_fields = {"registration_enabled", "login_enabled", "email_whitelist_enabled"}
        assert set(json_data.keys()) == expected_fields


@pytest.mark.django_db(transaction=True)
class TestPublicAccountSettingsModification:
    """Integration tests to verify public settings cannot be modified via this endpoint."""

    def test_post_not_allowed(self, live_server):
        """Test POST method is not allowed on public settings."""
        url = f"{live_server.url}/api/accounts/settings/public"
        data = {"registration_enabled": False}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 405  # Method Not Allowed

    def test_put_not_allowed(self, live_server):
        """Test PUT method is not allowed on public settings."""
        url = f"{live_server.url}/api/accounts/settings/public"
        data = {"registration_enabled": False}

        response = requests.put(url, json=data, timeout=10)

        assert response.status_code == 405  # Method Not Allowed

    def test_patch_not_allowed(self, live_server):
        """Test PATCH method is not allowed on public settings."""
        url = f"{live_server.url}/api/accounts/settings/public"
        data = {"registration_enabled": False}

        response = requests.patch(url, json=data, timeout=10)

        assert response.status_code == 405  # Method Not Allowed

    def test_delete_not_allowed(self, live_server):
        """Test DELETE method is not allowed on public settings."""
        url = f"{live_server.url}/api/accounts/settings/public"

        response = requests.delete(url, timeout=10)

        assert response.status_code == 405  # Method Not Allowed
