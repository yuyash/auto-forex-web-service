"""
Unit tests for JWT authentication middleware.

Requirements: 2.3, 2.4
"""

# mypy: disable-error-code="attr-defined,valid-type,union-attr"

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse

import jwt
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.authentication import JWTAuthentication
from accounts.jwt_utils import decode_jwt_token, generate_jwt_token, refresh_jwt_token

User = get_user_model()


def _token_to_str(token: Any) -> str:
    """Coerce PyJWT token return type to a plain string for mypy and headers."""
    if isinstance(token, memoryview):
        token = token.tobytes()
    if isinstance(token, (bytes, bytearray)):
        return token.decode("utf-8")
    return str(token)


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


@pytest.fixture
def valid_token(test_user: User) -> str:
    """Generate a valid JWT token for testing."""
    return generate_jwt_token(test_user)


@pytest.fixture
def expired_token(test_user: User) -> str:
    """Generate an expired JWT token for testing."""
    now = datetime.now(timezone.utc)
    expiration = now - timedelta(hours=1)  # Expired 1 hour ago

    payload = {
        "user_id": test_user.id,
        "email": test_user.email,
        "username": test_user.username,
        "is_staff": test_user.is_staff,
        "iat": int(now.timestamp()),
        "exp": int(expiration.timestamp()),
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return _token_to_str(token)


@pytest.mark.django_db
class TestJWTAuthentication:
    """Test suite for JWT authentication middleware."""

    def test_valid_jwt_token_authentication(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test valid JWT token authentication.

        Requirements: 2.3, 2.4
        """
        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should succeed (200 OK) because token is valid
        assert response.status_code == status.HTTP_200_OK

    def test_expired_jwt_token_rejection(
        self, api_client: APIClient, test_user: User, expired_token: str
    ) -> None:
        """
        Test expired JWT token rejection.

        Requirements: 2.4
        """
        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header with expired token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_token}")

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because token is expired
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_invalid_jwt_token_rejection(self, api_client: APIClient) -> None:
        """
        Test invalid JWT token rejection.

        Requirements: 2.4
        """
        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header with invalid token
        invalid_token = "invalid.token.string"
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {invalid_token}")

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because token is invalid
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_missing_authorization_header(self, api_client: APIClient) -> None:
        """
        Test that missing authorization header is rejected.

        Requirements: 2.4
        """
        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Don't set authorization header
        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because no token provided
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_malformed_authorization_header(self, api_client: APIClient, valid_token: str) -> None:
        """
        Test that malformed authorization header is rejected.

        Requirements: 2.4
        """
        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set malformed authorization header (missing "Bearer" keyword)
        api_client.credentials(HTTP_AUTHORIZATION=valid_token)

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because header is malformed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_with_inactive_user(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test that token for inactive user is rejected.

        Requirements: 2.4
        """
        # Deactivate user
        test_user.is_active = False
        test_user.save()

        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because user is inactive
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_with_locked_user(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test that token for locked user is rejected.

        Requirements: 2.4
        """
        # Lock user account
        test_user.lock_account()

        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because user is locked
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_with_nonexistent_user(self, api_client: APIClient) -> None:
        """
        Test that token for nonexistent user is rejected.

        Requirements: 2.4
        """
        # Create token with nonexistent user ID
        now = datetime.now(timezone.utc)
        expiration = now + timedelta(seconds=settings.JWT_EXPIRATION_DELTA)

        payload = {
            "user_id": 99999,  # Nonexistent user ID
            "email": "nonexistent@example.com",
            "username": "nonexistent",
            "is_staff": False,
            "iat": int(now.timestamp()),
            "exp": int(expiration.timestamp()),
        }

        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

        # Use logout endpoint as it requires authentication
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {_token_to_str(token)}")

        response = api_client.post(url, format="json")

        # Should fail (401 Unauthorized) because user doesn't exist
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_jwt_authentication_backend_authenticate_method(
        self, test_user: User, valid_token: str
    ) -> None:
        """
        Test JWTAuthentication.authenticate() method directly.

        Requirements: 2.3, 2.4
        """
        auth_backend = JWTAuthentication()

        # Create mock request with valid token
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": f"Bearer {valid_token}"}

        # Authenticate
        result = auth_backend.authenticate(request)

        # Should return (user, token) tuple
        assert result is not None
        user, token = result
        assert user.id == test_user.id
        assert token == valid_token

    def test_jwt_authentication_backend_with_no_header(self) -> None:
        """
        Test JWTAuthentication.authenticate() with no authorization header.

        Requirements: 2.4
        """
        auth_backend = JWTAuthentication()

        # Create mock request without authorization header
        request = Mock()
        request.META = {}

        # Authenticate
        result = auth_backend.authenticate(request)

        # Should return None (not authenticated)
        assert result is None

    def test_jwt_authentication_backend_with_invalid_format(self, valid_token: str) -> None:
        """
        Test JWTAuthentication.authenticate() with invalid header format.

        Requirements: 2.4
        """
        auth_backend = JWTAuthentication()

        # Create mock request with invalid format (missing Bearer keyword)
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": valid_token}

        # Authenticate
        result = auth_backend.authenticate(request)

        # Should return None (not authenticated)
        assert result is None

    def test_decode_jwt_token_with_valid_token(self, valid_token: str, test_user: User) -> None:
        """
        Test decode_jwt_token() with valid token.

        Requirements: 2.4
        """
        payload = decode_jwt_token(valid_token)

        assert payload is not None
        assert payload["user_id"] == test_user.id
        assert payload["email"] == test_user.email
        assert payload["username"] == test_user.username
        assert "iat" in payload
        assert "exp" in payload

    def test_decode_jwt_token_with_expired_token(self, expired_token: str) -> None:
        """
        Test decode_jwt_token() with expired token.

        Requirements: 2.4
        """
        payload = decode_jwt_token(expired_token)

        # Should return None for expired token
        assert payload is None

    def test_decode_jwt_token_with_invalid_token(self) -> None:
        """
        Test decode_jwt_token() with invalid token.

        Requirements: 2.4
        """
        payload = decode_jwt_token("invalid.token.string")

        # Should return None for invalid token
        assert payload is None


@pytest.mark.django_db
class TestTokenRefresh:
    """Test suite for token refresh functionality."""

    def test_token_refresh_functionality(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test token refresh functionality.

        Requirements: 2.3, 2.4
        """
        import time

        url = reverse("accounts:token_refresh")

        # Set authorization header with valid token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        # Wait a moment to ensure different timestamp
        time.sleep(1)

        response = api_client.post(url, format="json")

        # Should succeed and return new token
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "user" in response.data

        # New token should be different from old token
        new_token = response.data["token"]
        assert new_token != valid_token

        # New token should be valid
        payload = decode_jwt_token(new_token)
        assert payload is not None
        assert payload["user_id"] == test_user.id

    def test_token_refresh_with_expired_token(
        self, api_client: APIClient, expired_token: str
    ) -> None:
        """
        Test token refresh with expired token.

        Requirements: 2.4
        """
        url = reverse("accounts:token_refresh")

        # Set authorization header with expired token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_token}")

        response = api_client.post(url, format="json")

        # Should fail because token is expired
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data or "error" in response.data

    def test_token_refresh_with_invalid_token(self, api_client: APIClient) -> None:
        """
        Test token refresh with invalid token.

        Requirements: 2.4
        """
        url = reverse("accounts:token_refresh")

        # Set authorization header with invalid token
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid.token.string")

        response = api_client.post(url, format="json")

        # Should fail because token is invalid
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data or "error" in response.data

    def test_token_refresh_without_authorization_header(self, api_client: APIClient) -> None:
        """
        Test token refresh without authorization header.

        Requirements: 2.4
        """
        url = reverse("accounts:token_refresh")

        # Don't set authorization header
        response = api_client.post(url, format="json")

        # Should fail because no token provided
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_token_refresh_with_inactive_user(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test token refresh with inactive user.

        Requirements: 2.4
        """
        # Deactivate user
        test_user.is_active = False
        test_user.save()

        url = reverse("accounts:token_refresh")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should fail because user is inactive
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data or "error" in response.data

    def test_token_refresh_with_locked_user(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test token refresh with locked user.

        Requirements: 2.4
        """
        # Lock user account
        test_user.lock_account()

        url = reverse("accounts:token_refresh")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should fail because user is locked
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data or "error" in response.data

    def test_refresh_jwt_token_utility_function(self, test_user: User, valid_token: str) -> None:
        """
        Test refresh_jwt_token() utility function.

        Requirements: 2.3, 2.4
        """
        import time

        # Wait a moment to ensure different timestamp
        time.sleep(1)

        new_token = refresh_jwt_token(valid_token)

        # Should return a new token
        assert new_token is not None
        assert new_token != valid_token

        # New token should be valid
        payload = decode_jwt_token(new_token)
        assert payload is not None
        assert payload["user_id"] == test_user.id

    def test_refresh_jwt_token_with_invalid_token(self) -> None:
        """
        Test refresh_jwt_token() with invalid token.

        Requirements: 2.4
        """
        new_token = refresh_jwt_token("invalid.token.string")

        # Should return None for invalid token
        assert new_token is None

    def test_token_refresh_returns_user_data(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test that token refresh returns user data.

        Requirements: 2.3
        """
        url = reverse("accounts:token_refresh")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        response = api_client.post(url, format="json")

        # Should succeed and return user data
        assert response.status_code == status.HTTP_200_OK
        assert "user" in response.data

        user_data = response.data["user"]
        assert user_data["id"] == test_user.id
        assert user_data["email"] == test_user.email
        assert user_data["username"] == test_user.username
        assert user_data["is_staff"] == test_user.is_staff
        assert user_data["timezone"] == test_user.timezone
        assert user_data["language"] == test_user.language

    def test_refreshed_token_has_extended_expiration(
        self, api_client: APIClient, test_user: User, valid_token: str
    ) -> None:
        """
        Test that refreshed token has extended expiration.

        Requirements: 2.3
        """
        import time

        # Decode original token
        original_payload = decode_jwt_token(valid_token)
        assert original_payload is not None
        original_exp = original_payload["exp"]

        url = reverse("accounts:token_refresh")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {valid_token}")

        # Wait a moment to ensure different timestamp
        time.sleep(1)

        response = api_client.post(url, format="json")

        # Should succeed
        assert response.status_code == status.HTTP_200_OK

        # Decode new token
        new_token = response.data["token"]
        new_payload = decode_jwt_token(new_token)
        assert new_payload is not None
        new_exp = new_payload["exp"]

        # New expiration should be later than original
        assert new_exp > original_exp

    def test_token_refresh_with_malformed_header(
        self, api_client: APIClient, valid_token: str
    ) -> None:
        """
        Test token refresh with malformed authorization header.

        Requirements: 2.4
        """
        url = reverse("accounts:token_refresh")

        # Set malformed authorization header (missing "Bearer" keyword)
        api_client.credentials(HTTP_AUTHORIZATION=valid_token)

        response = api_client.post(url, format="json")

        # Should fail because header is malformed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
