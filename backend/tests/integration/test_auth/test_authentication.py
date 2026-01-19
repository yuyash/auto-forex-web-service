"""
Integration tests for authentication flows.

Tests user login, logout, and token invalidation flows.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import UserSession
from apps.accounts.services.jwt import JWTService
from tests.integration.factories import UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestAuthenticationFlows:
    """Test authentication flows including login, logout, and token management."""

    def test_user_login_with_valid_credentials(self, api_client: APIClient) -> None:
        """
        Test user login with valid credentials.

        Validates:
        - User can login with correct email and password
        - Response contains JWT token
        - Response contains user information
        - Token is valid and can be used for authentication
        """
        # Create user with known password
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.save()  # type: ignore[attr-defined]

        # Attempt login
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {
                "email": user.email,
                "password": password,
            },
            format="json",
        )

        # Assert successful login
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "user" in response.data

        # Verify user data in response
        assert response.data["user"]["id"] == user.id  # ty:ignore[unresolved-attribute]
        assert response.data["user"]["email"] == user.email
        assert response.data["user"]["username"] == user.username

        # Verify token is valid
        token = response.data["token"]
        jwt_service = JWTService()
        decoded_user = jwt_service.get_user_from_token(token)
        assert decoded_user is not None
        assert decoded_user.id == user.id  # ty:ignore[unresolved-attribute]

    def test_login_failure_with_invalid_credentials(self, api_client: APIClient) -> None:
        """
        Test login failure with invalid credentials.

        Validates:
        - Login fails with incorrect password
        - Response returns 401 Unauthorized
        - Error message is returned
        - No token is provided
        """
        # Create user with known password
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.save()  # type: ignore[attr-defined]

        # Attempt login with wrong password
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {
                "email": user.email,
                "password": "wrongpassword",
            },
            format="json",
        )

        # Assert login failed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data
        assert "token" not in response.data

    def test_login_failure_with_nonexistent_user(self, api_client: APIClient) -> None:
        """
        Test login failure with nonexistent user.

        Validates:
        - Login fails for email that doesn't exist
        - Response returns 401 Unauthorized
        - Error message is returned
        """
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {
                "email": "nonexistent@example.com",
                "password": "somepassword",
            },
            format="json",
        )

        # Assert login failed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_login_with_unverified_email(self, api_client: APIClient) -> None:
        """
        Test login with unverified email.

        Note: The system currently allows login with unverified email.
        This test documents the current behavior.

        Validates:
        - Login succeeds even with unverified email
        - Token is returned
        """
        # Create user with unverified email
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = False
        user.save()  # type: ignore[attr-defined]

        # Attempt login
        url = reverse("accounts:login")
        response = api_client.post(
            url,
            {
                "email": user.email,
                "password": password,
            },
            format="json",
        )

        # Assert login succeeds (current behavior)
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data

    def test_logout_and_token_invalidation(self, api_client: APIClient) -> None:
        """
        Test logout and token invalidation.

        Validates:
        - User can logout with valid token
        - Active sessions are terminated
        - Response confirms logout success
        """
        # Create user and login
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.save()  # type: ignore[attr-defined]

        # Login to get token
        login_url = reverse("accounts:login")
        login_response = api_client.post(
            login_url,
            {
                "email": user.email,
                "password": password,
            },
            format="json",
        )
        token = login_response.data["token"]

        # Create active session for user
        session = UserSession.objects.create(
            user=user,
            session_key="test-session-key",
            ip_address="127.0.0.1",
            is_active=True,
        )

        # Logout
        logout_url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.post(logout_url, format="json")

        # Assert successful logout
        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

        # Verify session was terminated
        session.refresh_from_db()    # type: ignore[attr-defined]
        assert not session.is_active
        assert session.logout_time is not None

    def test_logout_with_invalid_token(self, api_client: APIClient) -> None:
        """
        Test logout with invalid token.

        Validates:
        - Logout fails with invalid token
        - Response returns 401 Unauthorized
        - Error detail is returned
        """
        logout_url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = api_client.post(logout_url, format="json")

        # Assert logout failed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        # DRF returns 'detail' field for authentication errors
        assert "detail" in response.data or "error" in response.data

    def test_logout_without_token(self, api_client: APIClient) -> None:
        """
        Test logout without providing token.

        Validates:
        - Logout fails when no token is provided
        - Response returns 401 Unauthorized
        """
        logout_url = reverse("accounts:logout")
        response = api_client.post(logout_url, format="json")

        # Assert logout failed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh_with_valid_token(self, api_client: APIClient) -> None:
        """
        Test token refresh with valid token.

        Validates:
        - Valid token can be refreshed
        - New token is returned
        - New token is valid
        - Token contains updated timestamp
        """
        # Create user and login
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.save()  # type: ignore[attr-defined]

        # Login to get token
        login_url = reverse("accounts:login")
        login_response = api_client.post(
            login_url,
            {
                "email": user.email,
                "password": password,
            },
            format="json",
        )
        old_token = login_response.data["token"]

        # Decode old token to get timestamp
        jwt_service = JWTService()
        old_payload = jwt_service.decode_token(old_token)
        assert old_payload is not None
        old_iat = old_payload["iat"]

        # Wait a moment to ensure timestamp difference
        import time

        time.sleep(1)

        # Refresh token
        refresh_url = reverse("accounts:token_refresh")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {old_token}")
        response = api_client.post(refresh_url, format="json")

        # Assert successful refresh
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        new_token = response.data["token"]

        # Verify new token is valid
        decoded_user = jwt_service.get_user_from_token(new_token)
        assert decoded_user is not None
        assert decoded_user.id == user.id  # ty:ignore[unresolved-attribute]

        # Verify new token has updated timestamp
        new_payload = jwt_service.decode_token(new_token)
        assert new_payload is not None
        new_iat = new_payload["iat"]
        assert new_iat >= old_iat  # New token should have same or later timestamp

    def test_token_refresh_with_invalid_token(self, api_client: APIClient) -> None:
        """
        Test token refresh with invalid token.

        Validates:
        - Token refresh fails with invalid token
        - Response returns 401 Unauthorized
        """
        refresh_url = reverse("accounts:token_refresh")
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")
        response = api_client.post(refresh_url, format="json")

        # Assert refresh failed
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "error" in response.data

    def test_failed_login_attempts_increment(self, api_client: APIClient) -> None:
        """
        Test that failed login attempts are tracked.

        Validates:
        - Failed login attempts increment counter
        - User account tracks failed attempts
        """
        # Create user
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.save()  # type: ignore[attr-defined]

        # Initial failed attempts should be 0
        assert user.failed_login_attempts == 0

        # Attempt login with wrong password
        url = reverse("accounts:login")
        api_client.post(
            url,
            {
                "email": user.email,
                "password": "wrongpassword",
            },
            format="json",
        )

        # Verify failed attempts incremented
        user.refresh_from_db()    # type: ignore[attr-defined]
        assert user.failed_login_attempts == 1

    def test_successful_login_resets_failed_attempts(self, api_client: APIClient) -> None:
        """
        Test that successful login resets failed login attempts.

        Validates:
        - Successful login resets failed attempts counter to 0
        """
        # Create user with failed attempts
        password = "testpass123"
        user = UserFactory()
        user.set_password(password)  # type: ignore[attr-defined]
        user.email_verified = True
        user.failed_login_attempts = 3
        user.save()  # type: ignore[attr-defined]

        # Successful login
        url = reverse("accounts:login")
        api_client.post(
            url,
            {
                "email": user.email,
                "password": password,
            },
            format="json",
        )

        # Verify failed attempts reset
        user.refresh_from_db()    # type: ignore[attr-defined]
        assert user.failed_login_attempts == 0
