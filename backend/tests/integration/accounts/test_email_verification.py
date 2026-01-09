"""
Integration tests for email verification endpoints.

Tests the following endpoints using live_server:
- POST /api/accounts/auth/verify-email
- POST /api/accounts/auth/resend-verification
"""

import pytest
import requests
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class TestEmailVerification:
    """Integration tests for email verification endpoint."""

    def test_verify_email_with_valid_token(self, live_server, unverified_user):
        """Test email verification with valid token."""
        # Generate verification token
        token = unverified_user.generate_verification_token()

        url = f"{live_server.url}/api/accounts/auth/verify-email"
        data = {"token": token}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data
        assert "verified" in json_data["message"].lower()
        assert json_data["user"]["email_verified"] is True

    def test_verify_email_with_invalid_token(self, live_server):
        """Test email verification fails with invalid token."""
        url = f"{live_server.url}/api/accounts/auth/verify-email"
        data = {"token": "invalid_token_12345"}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "error" in json_data

    def test_verify_email_without_token(self, live_server):
        """Test email verification fails without token."""
        url = f"{live_server.url}/api/accounts/auth/verify-email"
        data = {}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "error" in json_data

    def test_verify_email_empty_token(self, live_server):
        """Test email verification fails with empty token."""
        url = f"{live_server.url}/api/accounts/auth/verify-email"
        data = {"token": ""}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400

    def test_verify_email_returns_user_info(self, live_server, unverified_user):
        """Test verification response contains user information."""
        token = unverified_user.generate_verification_token()

        url = f"{live_server.url}/api/accounts/auth/verify-email"
        data = {"token": token}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "user" in json_data
        user_data = json_data["user"]
        assert "id" in user_data
        assert "email" in user_data
        assert "username" in user_data
        assert "email_verified" in user_data


@pytest.mark.django_db(transaction=True)
class TestResendVerification:
    """Integration tests for resend verification email endpoint."""

    def test_resend_verification_for_unverified_user(self, live_server, unverified_user):
        """Test resend verification email for unverified user."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {"email": unverified_user.email}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data

    def test_resend_verification_for_verified_user(self, live_server, test_user):
        """Test resend verification fails for already verified user."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {"email": test_user.email}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "error" in json_data
        assert "already verified" in json_data["error"].lower()

    def test_resend_verification_for_nonexistent_email(self, live_server):
        """Test resend verification for non-existent email (should not reveal existence)."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {"email": "nonexistent@example.com"}

        response = requests.post(url, json=data, timeout=10)

        # Should return 200 to not reveal whether email exists
        assert response.status_code == 200
        json_data = response.json()
        assert "message" in json_data

    def test_resend_verification_without_email(self, live_server):
        """Test resend verification fails without email."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400
        json_data = response.json()
        assert "error" in json_data

    def test_resend_verification_empty_email(self, live_server):
        """Test resend verification fails with empty email."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {"email": ""}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 400

    def test_resend_verification_case_insensitive(self, live_server, unverified_user):
        """Test resend verification works with different email case."""
        url = f"{live_server.url}/api/accounts/auth/resend-verification"
        data = {"email": unverified_user.email.upper()}

        response = requests.post(url, json=data, timeout=10)

        assert response.status_code == 200
