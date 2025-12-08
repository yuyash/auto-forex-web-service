"""
Integration tests for user registration endpoint.

Tests the POST /api/auth/register endpoint using live_server.
"""

from django.contrib.auth import get_user_model

import pytest
import requests

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestUserRegistration:
    """Integration tests for user registration endpoint."""

    def test_successful_registration(self, live_server):
        """Test successful user registration with valid data."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert "message" in json_data
        assert "user" in json_data
        assert json_data["user"]["email"] == "newuser@example.com"
        assert json_data["user"]["username"] == "newuser"
        assert json_data["user"]["email_verified"] is False

    def test_registration_missing_email(self, live_server):
        """Test registration fails without email."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "username": "newuser",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "email" in json_data

    def test_registration_without_username_succeeds(self, live_server):
        """Test registration succeeds without username (username is optional)."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "newuser_no_username@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        # Username is optional, so registration should succeed
        assert response.status_code == 201
        json_data = response.json()
        assert "user" in json_data
        assert json_data["user"]["email"] == "newuser_no_username@example.com"

    def test_registration_password_mismatch(self, live_server):
        """Test registration fails when passwords don't match."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "SecurePass123!",
            "password_confirm": "DifferentPass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "password_confirm" in json_data or "non_field_errors" in json_data

    def test_registration_weak_password(self, live_server):
        """Test registration fails with weak password."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "weak",
            "password_confirm": "weak",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400

    def test_registration_duplicate_email(self, live_server, test_user):
        """Test registration fails with existing email."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": test_user.email,
            "username": "anotheruser",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "email" in json_data

    def test_registration_duplicate_username(self, live_server, test_user):
        """Test registration fails with existing username."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "different@example.com",
            "username": test_user.username,
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "username" in json_data

    def test_registration_invalid_email_format(self, live_server):
        """Test registration fails with invalid email format."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "not-an-email",
            "username": "newuser",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "email" in json_data

    def test_registration_empty_request(self, live_server):
        """Test registration fails with empty request body."""
        url = f"{live_server.url}/api/auth/register"

        response = requests.post(url, json={}, timeout=10)

        assert response.status_code == 400

    def test_registration_with_first_and_last_name(self, live_server):
        """Test successful registration with first_name and last_name."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "nameduser@example.com",
            "username": "nameduser",
            "first_name": "John",
            "last_name": "Doe",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert json_data["user"]["first_name"] == "John"
        assert json_data["user"]["last_name"] == "Doe"

    def test_registration_with_first_name_only(self, live_server):
        """Test registration with only first_name provided."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "firstname@example.com",
            "username": "firstname",
            "first_name": "Jane",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert json_data["user"]["first_name"] == "Jane"
        assert json_data["user"]["last_name"] == ""

    def test_registration_without_names(self, live_server):
        """Test registration without first_name and last_name defaults to empty."""
        url = f"{live_server.url}/api/auth/register"
        data = {
            "email": "nonames@example.com",
            "username": "nonames",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 201
        json_data = response.json()
        assert json_data["user"]["first_name"] == ""
        assert json_data["user"]["last_name"] == ""
