"""
Integration tests for user login endpoint.

Tests the POST /api/auth/login endpoint using live_server.
"""

from django.contrib.auth import get_user_model

import pytest
import requests

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestUserLogin:
    """Integration tests for user login endpoint."""

    def test_successful_login(self, live_server, test_user):
        """Test successful login with valid credentials."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": test_user.email,
            "password": "TestPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "token" in json_data
        assert "user" in json_data
        assert json_data["user"]["email"] == test_user.email
        assert json_data["user"]["username"] == test_user.username

    def test_login_wrong_password(self, live_server, test_user):
        """Test login fails with wrong password."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": test_user.email,
            "password": "WrongPassword123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 401
        json_data = response.json()
        assert "error" in json_data

    def test_login_nonexistent_user(self, live_server):
        """Test login fails with non-existent user."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": "nonexistent@example.com",
            "password": "SomePassword123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 401
        json_data = response.json()
        assert "error" in json_data

    def test_login_missing_email(self, live_server):
        """Test login fails without email."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "password": "SomePassword123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400 or response.status_code == 401

    def test_login_missing_password(self, live_server, test_user):
        """Test login fails without password."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": test_user.email,
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400 or response.status_code == 401

    def test_login_empty_request(self, live_server):
        """Test login fails with empty request body."""
        url = f"{live_server.url}/api/auth/login"

        response = requests.post(url, json={}, timeout=10)

        assert response.status_code == 400 or response.status_code == 401

    def test_login_unverified_email(self, live_server, unverified_user):
        """Test login behavior with unverified email."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": unverified_user.email,
            "password": "TestPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        # Depending on implementation, this might succeed or fail
        # The response should be consistent
        assert response.status_code in [200, 401, 403]

    def test_login_locked_account(self, live_server, locked_user):
        """Test login fails for locked account."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": locked_user.email,
            "password": "TestPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 403
        json_data = response.json()
        assert "error" in json_data
        assert "locked" in json_data["error"].lower()

    def test_login_case_insensitive_email(self, live_server, test_user):
        """Test login works with different email case."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": test_user.email.upper(),
            "password": "TestPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "token" in json_data

    def test_login_returns_user_info(self, live_server, test_user):
        """Test login response contains expected user information."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": test_user.email,
            "password": "TestPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        user_data = json_data["user"]
        assert "id" in user_data
        assert "email" in user_data
        assert "username" in user_data
        assert "is_staff" in user_data
        assert "timezone" in user_data
        assert "language" in user_data

    def test_login_admin_user(self, live_server, admin_user):
        """Test login works for admin users."""
        url = f"{live_server.url}/api/auth/login"
        data = {
            "email": admin_user.email,
            "password": "AdminPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert json_data["user"]["is_staff"] is True
