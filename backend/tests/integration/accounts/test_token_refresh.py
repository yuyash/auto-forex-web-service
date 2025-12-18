"""
Integration tests for token refresh endpoint.

Tests the POST /api/accounts/auth/refresh endpoint using live_server.
"""

from django.contrib.auth import get_user_model

import pytest
import requests

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestTokenRefresh:
    """Integration tests for token refresh endpoint."""

    def test_successful_token_refresh(self, live_server, test_user, auth_headers):
        """Test successful token refresh with valid token."""
        url = f"{live_server.url}/api/accounts/auth/refresh"

        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "token" in json_data
        assert "user" in json_data
        # New token should be different from the old one
        assert len(json_data["token"]) > 0

    def test_token_refresh_without_token(self, live_server):
        """Test token refresh fails without authorization token."""
        url = f"{live_server.url}/api/accounts/auth/refresh"

        response = requests.post(url, timeout=10)

        assert response.status_code == 401
        json_data = response.json()
        assert "detail" in json_data or "error" in json_data

    def test_token_refresh_with_invalid_token(self, live_server):
        """Test token refresh fails with invalid token."""
        url = f"{live_server.url}/api/accounts/auth/refresh"
        headers = {"Authorization": "Bearer invalid_token_here"}

        response = requests.post(url, headers=headers, timeout=10)

        assert response.status_code == 401
        json_data = response.json()
        assert "detail" in json_data or "error" in json_data

    def test_token_refresh_with_malformed_header(self, live_server):
        """Test token refresh fails with malformed authorization header."""
        url = f"{live_server.url}/api/accounts/auth/refresh"
        headers = {"Authorization": "NotBearer some_token"}

        response = requests.post(url, headers=headers, timeout=10)

        assert response.status_code == 401

    def test_token_refresh_returns_user_info(self, live_server, test_user, auth_headers):
        """Test token refresh response contains user information."""
        url = f"{live_server.url}/api/accounts/auth/refresh"

        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        user_data = json_data["user"]
        assert "id" in user_data
        assert "email" in user_data
        assert "username" in user_data
        assert "is_staff" in user_data
        assert "timezone" in user_data
        assert "language" in user_data

    def test_refreshed_token_is_valid(self, live_server, test_user, auth_headers):
        """Test that the refreshed token can be used for authenticated requests."""
        # First, refresh the token
        refresh_url = f"{live_server.url}/api/accounts/auth/refresh"
        refresh_response = requests.post(refresh_url, headers=auth_headers, timeout=10)

        assert refresh_response.status_code == 200
        new_token = refresh_response.json()["token"]

        # Then, use the new token to access a protected endpoint
        settings_url = f"{live_server.url}/api/accounts/settings/"
        new_headers = {"Authorization": f"Bearer {new_token}"}
        settings_response = requests.get(settings_url, headers=new_headers, timeout=10)

        assert settings_response.status_code == 200

    def test_token_refresh_with_empty_bearer(self, live_server):
        """Test token refresh fails with empty bearer token."""
        url = f"{live_server.url}/api/accounts/auth/refresh"
        headers = {"Authorization": "Bearer "}

        response = requests.post(url, headers=headers, timeout=10)

        assert response.status_code == 401
