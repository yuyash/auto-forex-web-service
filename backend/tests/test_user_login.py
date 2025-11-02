"""
Unit tests for user login API endpoint.

Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 34.1, 34.2
"""

# mypy: disable-error-code="attr-defined,valid-type,union-attr"

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse

import jwt
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import BlockedIP
from accounts.rate_limiter import RateLimiter

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def test_user(db) -> User:
    """Create a test user."""
    user = User.objects.create_user(
        email="testuser@example.com",
        username="testuser",
        password="SecurePass123!",
    )
    return user


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear cache before each test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestUserLogin:
    """Test suite for user login endpoint."""

    def test_successful_login_with_valid_credentials(
        self, api_client: APIClient, test_user: User
    ) -> None:
        """
        Test successful login with valid credentials.

        Requirements: 2.1, 2.2
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == test_user.email
        assert response.data["user"]["username"] == test_user.username
        assert response.data["user"]["id"] == test_user.id

    def test_jwt_token_generation_and_structure(
        self, api_client: APIClient, test_user: User
    ) -> None:
        """
        Test JWT token generation and structure.

        Requirements: 2.3
        """
        from django.conf import settings

        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data

        # Decode and verify token structure
        token = response.data["token"]
        decoded = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        assert "user_id" in decoded
        assert "email" in decoded
        assert "username" in decoded
        assert "is_staff" in decoded
        assert "iat" in decoded
        assert "exp" in decoded
        assert decoded["user_id"] == test_user.id
        assert decoded["email"] == test_user.email
        assert decoded["username"] == test_user.username

    def test_invalid_credentials_rejection(self, api_client: APIClient, test_user: User) -> None:
        """
        Test invalid credentials rejection.

        Requirements: 2.2, 2.4
        """
        url = reverse("accounts:login")

        # Test wrong password
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "token" not in response.data

        # Test non-existent email
        data = {
            "email": "nonexistent@example.com",
            "password": "SecurePass123!",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_rate_limiting_after_5_failed_attempts(
        self, api_client: APIClient, test_user: User
    ) -> None:
        """
        Test rate limiting after 5 failed attempts.

        Requirements: 2.5, 34.1
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        # Make 5 failed attempts
        for _ in range(5):
            response = api_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # 6th attempt should be rate limited
        response = api_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert "error" in response.data

    def test_failed_login_logging(self, api_client: APIClient, test_user: User) -> None:
        """
        Test failed login logging.

        Requirements: 34.1, 34.2
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        with patch("accounts.views.logger") as mock_logger:
            response = api_client.post(url, data, format="json")

            assert response.status_code == status.HTTP_401_UNAUTHORIZED
            # Verify logger.warning was called for failed attempt
            assert mock_logger.warning.called
            call_args = mock_logger.warning.call_args
            assert "Failed login attempt" in call_args[0][0]

    def test_account_locking_after_10_failed_attempts(
        self, api_client: APIClient, test_user: User
    ) -> None:
        """
        Test account locking after 10 failed attempts.

        Requirements: 34.2
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        # Make 10 failed attempts
        for _ in range(10):
            # Clear IP rate limiting to focus on account locking
            cache.clear()
            response = api_client.post(url, data, format="json")
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Refresh user from database
        test_user.refresh_from_db()

        # Verify account is locked
        assert test_user.is_locked is True
        assert test_user.failed_login_attempts >= 10

        # Try to login with correct password - should fail due to lock
        cache.clear()
        data["password"] = "SecurePass123!"
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "locked" in response.data["error"].lower()

    def test_email_case_insensitivity(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that login works with different email cases.

        Requirements: 2.1
        """
        url = reverse("accounts:login")

        # Test with uppercase email
        data = {
            "email": "TESTUSER@EXAMPLE.COM",
            "password": "SecurePass123!",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data

    def test_successful_login_resets_failed_attempts(
        self, api_client: APIClient, test_user: User
    ) -> None:
        """
        Test that successful login resets failed attempt counters.

        Requirements: 2.2, 34.1
        """
        url = reverse("accounts:login")

        # Make 3 failed attempts
        for _ in range(3):
            data = {
                "email": "testuser@example.com",
                "password": "WrongPassword123!",
            }
            api_client.post(url, data, format="json")

        # Verify failed attempts were recorded
        test_user.refresh_from_db()
        assert test_user.failed_login_attempts == 3

        # Successful login
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify counters were reset
        test_user.refresh_from_db()
        assert test_user.failed_login_attempts == 0
        assert test_user.last_login_attempt is None

    def test_ip_blocking_persists_in_database(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that IP blocking is persisted in database.

        Requirements: 34.1, 34.2
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        # Make 5 failed attempts to trigger IP block
        for _ in range(5):
            api_client.post(url, data, format="json")

        # Verify BlockedIP record was created
        blocked_ips = BlockedIP.objects.filter(ip_address="127.0.0.1")
        assert blocked_ips.exists()

        blocked_ip = blocked_ips.first()
        assert blocked_ip.is_active()
        assert blocked_ip.failed_attempts >= 5

    def test_locked_account_cannot_login(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that locked accounts cannot login even with correct password.

        Requirements: 34.2
        """
        # Lock the account
        test_user.lock_account()

        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "locked" in response.data["error"].lower()

    def test_missing_credentials(self, api_client: APIClient) -> None:
        """
        Test that missing credentials are rejected.

        Requirements: 2.1
        """
        url = reverse("accounts:login")

        # Missing password
        response = api_client.post(url, {"email": "test@example.com"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Missing email
        response = api_client.post(url, {"password": "password"}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Missing both
        response = api_client.post(url, {}, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_inactive_user_cannot_login(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that inactive users cannot login.

        Requirements: 2.2
        """
        # Deactivate user
        test_user.is_active = False
        test_user.save()

        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_user_data_in_response(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that user data is included in successful login response.

        Requirements: 2.3
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "user" in response.data

        user_data = response.data["user"]
        assert user_data["id"] == test_user.id
        assert user_data["email"] == test_user.email
        assert user_data["username"] == test_user.username
        assert user_data["is_staff"] == test_user.is_staff
        assert user_data["timezone"] == test_user.timezone
        assert user_data["language"] == test_user.language

    def test_rate_limiter_cache_expiration(self, api_client: APIClient, test_user: User) -> None:
        """
        Test that rate limiter cache expires after timeout.

        Requirements: 2.5
        """
        url = reverse("accounts:login")
        data = {
            "email": "testuser@example.com",
            "password": "WrongPassword123!",
        }

        # Make 3 failed attempts
        for _ in range(3):
            api_client.post(url, data, format="json")

        # Verify attempts are cached
        ip_address = "127.0.0.1"
        attempts = RateLimiter.get_failed_attempts(ip_address)
        assert attempts == 3

        # Clear cache to simulate expiration
        cache.clear()

        # Verify attempts are reset
        attempts = RateLimiter.get_failed_attempts(ip_address)
        assert attempts == 0
