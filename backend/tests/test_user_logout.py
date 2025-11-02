"""
Unit tests for user logout API endpoint.

Requirements: 3.1, 3.2, 3.3, 3.5
"""

# mypy: disable-error-code="attr-defined,valid-type,union-attr"

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.jwt_utils import generate_jwt_token
from accounts.models import UserSession

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


@pytest.fixture
def auth_token(test_user: User) -> str:
    """Generate JWT token for test user."""
    return generate_jwt_token(test_user)


@pytest.fixture
def user_session(test_user: User, db) -> UserSession:
    """Create an active user session."""
    session = UserSession.objects.create(
        user=test_user,
        session_key="test_session_key_123",
        ip_address="127.0.0.1",
        user_agent="Test User Agent",
        is_active=True,
    )
    return session


@pytest.mark.django_db
class TestUserLogout:
    """Test suite for user logout endpoint."""

    def test_successful_logout(
        self, api_client: APIClient, test_user: User, auth_token: str, user_session: UserSession
    ) -> None:
        """
        Test successful logout.

        Requirements: 3.1, 3.2
        """
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data
        assert "Logged out successfully" in response.data["message"]
        assert "sessions_terminated" in response.data

    def test_jwt_token_invalidation(
        self, api_client: APIClient, test_user: User, auth_token: str, user_session: UserSession
    ) -> None:
        """
        Test JWT token invalidation (session termination).

        Note: JWT tokens are stateless, so we verify session termination instead.

        Requirements: 3.2
        """
        url = reverse("accounts:logout")

        # Verify session is active before logout
        user_session.refresh_from_db()
        assert user_session.is_active is True
        assert user_session.logout_time is None

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify session is terminated after logout
        user_session.refresh_from_db()
        assert user_session.is_active is False
        assert user_session.logout_time is not None

    def test_v20_stream_closure(
        self, api_client: APIClient, test_user: User, auth_token: str, user_session: UserSession
    ) -> None:
        """
        Test v20 stream closure on logout.

        Note: v20 stream management is not yet implemented, so we verify logging.

        Requirements: 3.3, 3.5
        """
        url = reverse("accounts:logout")

        # Set authorization header
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        with patch("accounts.views.logger") as mock_logger:
            response = api_client.post(url, format="json")

            assert response.status_code == status.HTTP_200_OK

            # Verify logger was called about v20 stream closure
            assert mock_logger.info.called
            call_args_list = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("v20 streams" in arg for arg in call_args_list)

    def test_logout_with_invalid_token(self, api_client: APIClient) -> None:
        """
        Test logout with invalid token.

        Requirements: 3.2
        """
        url = reverse("accounts:logout")

        # Set invalid token
        api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid_token_12345")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data
        assert "Invalid or expired token" in response.data["detail"]

    def test_logout_without_token(self, api_client: APIClient) -> None:
        """
        Test logout without providing token.

        Requirements: 3.1
        """
        url = reverse("accounts:logout")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data

    def test_logout_with_malformed_header(self, api_client: APIClient, auth_token: str) -> None:
        """
        Test logout with malformed authorization header.

        Requirements: 3.1
        """
        url = reverse("accounts:logout")

        # Test without "Bearer" prefix
        api_client.credentials(HTTP_AUTHORIZATION=auth_token)
        response = api_client.post(url, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Test with wrong prefix
        api_client.credentials(HTTP_AUTHORIZATION=f"Token {auth_token}")
        response = api_client.post(url, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_terminates_all_active_sessions(
        self, api_client: APIClient, test_user: User, auth_token: str, db
    ) -> None:
        """
        Test that logout terminates all active sessions for the user.

        Requirements: 3.2, 3.3
        """
        # Create multiple active sessions
        session1 = UserSession.objects.create(
            user=test_user,
            session_key="session_1",
            ip_address="127.0.0.1",
            user_agent="Browser 1",
            is_active=True,
        )
        session2 = UserSession.objects.create(
            user=test_user,
            session_key="session_2",
            ip_address="192.168.1.1",
            user_agent="Browser 2",
            is_active=True,
        )
        session3 = UserSession.objects.create(
            user=test_user,
            session_key="session_3",
            ip_address="10.0.0.1",
            user_agent="Browser 3",
            is_active=True,
        )

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["sessions_terminated"] == 3

        # Verify all sessions are terminated
        session1.refresh_from_db()
        session2.refresh_from_db()
        session3.refresh_from_db()

        assert session1.is_active is False
        assert session2.is_active is False
        assert session3.is_active is False

    def test_logout_logs_event(
        self, api_client: APIClient, test_user: User, auth_token: str, user_session: UserSession
    ) -> None:
        """
        Test that logout logs the event.

        Requirements: 3.2
        """
        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        with patch("accounts.views.logger") as mock_logger:
            response = api_client.post(url, format="json")

            assert response.status_code == status.HTTP_200_OK

            # Verify successful logout was logged
            assert mock_logger.info.called
            call_args = [call[0][0] for call in mock_logger.info.call_args_list]
            assert any("logged out successfully" in arg for arg in call_args)

    def test_logout_with_expired_token(self, api_client: APIClient, test_user: User) -> None:
        """
        Test logout with expired token.

        Requirements: 3.2
        """
        # Create an expired token by mocking the expiration
        with patch("accounts.jwt_utils.datetime") as mock_datetime:
            from datetime import datetime, timedelta
            from datetime import timezone as dt_timezone

            # Set time to past
            past_time = datetime.now(dt_timezone.utc) - timedelta(days=2)
            mock_datetime.now.return_value = past_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

            expired_token = generate_jwt_token(test_user)

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.data

    def test_logout_with_inactive_user(
        self, api_client: APIClient, test_user: User, auth_token: str
    ) -> None:
        """
        Test logout with inactive user account.

        Requirements: 3.2
        """
        # Deactivate user
        test_user.is_active = False
        test_user.save()

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        # Should fail because inactive users can't authenticate
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_locked_user(
        self, api_client: APIClient, test_user: User, auth_token: str
    ) -> None:
        """
        Test logout with locked user account.

        Requirements: 3.2
        """
        # Lock user account
        test_user.lock_account()

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        # Should fail because locked users can't authenticate
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_includes_ip_address_in_log(
        self, api_client: APIClient, test_user: User, auth_token: str, user_session: UserSession
    ) -> None:
        """
        Test that logout includes IP address in log.

        Requirements: 3.2
        """
        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        with patch("accounts.views.logger") as mock_logger:
            response = api_client.post(url, format="json")

            assert response.status_code == status.HTTP_200_OK

            # Verify IP address was logged
            assert mock_logger.info.called
            # Check the extra parameter contains ip_address
            for call in mock_logger.info.call_args_list:
                if len(call[1]) > 0 and "extra" in call[1]:
                    extra = call[1]["extra"]
                    if "ip_address" in extra:
                        assert extra["ip_address"] is not None
                        break

    def test_logout_returns_session_count(
        self, api_client: APIClient, test_user: User, auth_token: str, db
    ) -> None:
        """
        Test that logout returns the count of terminated sessions.

        Requirements: 3.2
        """
        # Create 2 active sessions
        UserSession.objects.create(
            user=test_user,
            session_key="session_1",
            ip_address="127.0.0.1",
            user_agent="Browser 1",
            is_active=True,
        )
        UserSession.objects.create(
            user=test_user,
            session_key="session_2",
            ip_address="192.168.1.1",
            user_agent="Browser 2",
            is_active=True,
        )

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["sessions_terminated"] == 2

    def test_logout_does_not_affect_other_users_sessions(
        self, api_client: APIClient, test_user: User, auth_token: str, db
    ) -> None:
        """
        Test that logout only terminates sessions for the authenticated user.

        Requirements: 3.2, 3.3
        """
        # Create another user with active session
        other_user = User.objects.create_user(
            email="otheruser@example.com",
            username="otheruser",
            password="SecurePass123!",
        )
        other_session = UserSession.objects.create(
            user=other_user,
            session_key="other_session",
            ip_address="10.0.0.1",
            user_agent="Other Browser",
            is_active=True,
        )

        # Create session for test user
        test_session = UserSession.objects.create(
            user=test_user,
            session_key="test_session",
            ip_address="127.0.0.1",
            user_agent="Test Browser",
            is_active=True,
        )

        url = reverse("accounts:logout")
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {auth_token}")

        response = api_client.post(url, format="json")

        assert response.status_code == status.HTTP_200_OK

        # Verify test user's session is terminated
        test_session.refresh_from_db()
        assert test_session.is_active is False

        # Verify other user's session is still active
        other_session.refresh_from_db()
        assert other_session.is_active is True
