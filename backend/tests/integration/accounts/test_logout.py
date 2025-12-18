"""
Integration tests for user logout endpoint.

Tests the POST /api/accounts/auth/logout endpoint using live_server.
"""

from django.contrib.auth import get_user_model

import pytest
import requests

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestUserLogout:
    """Integration tests for user logout endpoint."""

    def test_successful_logout(self, live_server, test_user, auth_headers):
        """Test successful logout with valid token."""
        url = f"{live_server.url}/api/accounts/auth/logout"

        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data
        assert "logged out" in json_data["message"].lower()

    def test_logout_without_token(self, live_server):
        """Test logout fails without authorization token."""
        url = f"{live_server.url}/api/accounts/auth/logout"

        response = requests.post(url, timeout=10)

        assert response.status_code == 401

    def test_logout_with_invalid_token(self, live_server):
        """Test logout fails with invalid token."""
        url = f"{live_server.url}/api/accounts/auth/logout"
        headers = {"Authorization": "Bearer invalid_token_here"}

        response = requests.post(url, headers=headers, timeout=10)

        assert response.status_code == 401

    def test_logout_with_malformed_header(self, live_server):
        """Test logout fails with malformed authorization header."""
        url = f"{live_server.url}/api/accounts/auth/logout"
        headers = {"Authorization": "NotBearer some_token"}

        response = requests.post(url, headers=headers, timeout=10)

        assert response.status_code == 401

    def test_logout_terminates_sessions(self, live_server, test_user, auth_headers):
        """Test logout terminates user sessions."""
        from apps.accounts.models import UserSession

        # Create a session for the user
        UserSession.objects.create(
            user=test_user,
            session_key="test_session_key",
            ip_address="127.0.0.1",
            user_agent="test-agent",
        )

        url = f"{live_server.url}/api/accounts/auth/logout"
        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "sessions_terminated" in json_data

    def test_logout_response_structure(self, live_server, test_user, auth_headers):
        """Test logout response has expected structure."""
        url = f"{live_server.url}/api/accounts/auth/logout"

        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data
        assert "sessions_terminated" in json_data
        assert isinstance(json_data["sessions_terminated"], int)
