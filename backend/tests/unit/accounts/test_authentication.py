"""
Unit tests for JWT authentication backend.

Tests cover:
- Token extraction from Authorization header
- Token validation
- User authentication from token
- Error handling for invalid/expired tokens
"""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.authentication import JWTAuthentication


class TestJWTAuthentication:
    """Test cases for JWTAuthentication class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.auth = JWTAuthentication()

    def test_authenticate_no_header(self) -> None:
        """Test authentication with no Authorization header."""
        request = MagicMock()
        request.META = {}

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_empty_header(self) -> None:
        """Test authentication with empty Authorization header."""
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": ""}

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_wrong_keyword(self) -> None:
        """Test authentication with wrong auth keyword."""
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Basic sometoken"}

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_malformed_header_single_part(self) -> None:
        """Test authentication with malformed header (single part)."""
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer"}

        result = self.auth.authenticate(request)

        assert result is None

    def test_authenticate_malformed_header_too_many_parts(self) -> None:
        """Test authentication with malformed header (too many parts)."""
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer token extra"}

        result = self.auth.authenticate(request)

        assert result is None

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_authenticate_valid_token(self, mock_get_user: MagicMock) -> None:
        """Test authentication with valid token."""
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False
        mock_get_user.return_value = mock_user

        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid_token"}

        result = self.auth.authenticate(request)

        assert result is not None
        assert result[0] == mock_user
        assert result[1] == "valid_token"
        mock_get_user.assert_called_once_with("valid_token")

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_authenticate_invalid_token(self, mock_get_user: MagicMock) -> None:
        """Test authentication with invalid token raises exception."""
        mock_get_user.return_value = None

        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer invalid_token"}

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "Invalid or expired token" in str(exc_info.value)

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_authenticate_inactive_user(self, mock_get_user: MagicMock) -> None:
        """Test authentication with inactive user raises exception."""
        mock_user = MagicMock()
        mock_user.is_active = False
        mock_user.is_locked = False
        mock_get_user.return_value = mock_user

        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid_token"}

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "disabled" in str(exc_info.value)

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_authenticate_locked_user(self, mock_get_user: MagicMock) -> None:
        """Test authentication with locked user raises exception."""
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = True
        mock_get_user.return_value = mock_user

        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid_token"}

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate(request)

        assert "locked" in str(exc_info.value)

    def test_authenticate_header_returns_keyword(self) -> None:
        """Test authenticate_header returns correct keyword."""
        request = MagicMock()
        result = self.auth.authenticate_header(request)

        assert result == "Bearer"

    def test_keyword_attribute(self) -> None:
        """Test keyword attribute is set correctly."""
        assert self.auth.keyword == "Bearer"


class TestAuthenticateCredentials:
    """Test cases for authenticate_credentials method."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.auth = JWTAuthentication()

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_credentials_valid(self, mock_get_user: MagicMock) -> None:
        """Test valid credentials return user and token."""
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False
        mock_get_user.return_value = mock_user

        user, token = self.auth.authenticate_credentials("test_token")

        assert user == mock_user
        assert token == "test_token"

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_credentials_invalid_token(self, mock_get_user: MagicMock) -> None:
        """Test invalid token raises AuthenticationFailed."""
        mock_get_user.return_value = None

        with pytest.raises(AuthenticationFailed):
            self.auth.authenticate_credentials("invalid_token")

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_credentials_inactive_user_raises(self, mock_get_user: MagicMock) -> None:
        """Test inactive user raises AuthenticationFailed."""
        mock_user = MagicMock()
        mock_user.is_active = False
        mock_get_user.return_value = mock_user

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate_credentials("test_token")

        assert "disabled" in str(exc_info.value)

    @patch("apps.accounts.authentication.get_user_from_token")
    def test_credentials_locked_user_raises(self, mock_get_user: MagicMock) -> None:
        """Test locked user raises AuthenticationFailed."""
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = True
        mock_get_user.return_value = mock_user

        with pytest.raises(AuthenticationFailed) as exc_info:
            self.auth.authenticate_credentials("test_token")

        assert "locked" in str(exc_info.value)


@pytest.mark.django_db
class TestJWTAuthenticationIntegration:
    """Integration tests for JWT authentication with real database."""

    def test_full_authentication_flow(self) -> None:
        """Test complete authentication flow with real user."""
        from apps.accounts.jwt_utils import generate_jwt_token
        from apps.accounts.models import User

        # Create a real user
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Generate a token
        token = generate_jwt_token(user)

        # Authenticate with the token
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        result = auth.authenticate(request)

        assert result is not None
        authenticated_user, returned_token = result
        assert authenticated_user.id == user.id
        assert authenticated_user.email == user.email
        assert returned_token == token

    def test_authentication_after_user_locked(self) -> None:
        """Test authentication fails after user is locked."""
        from apps.accounts.jwt_utils import generate_jwt_token
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = generate_jwt_token(user)

        # Lock the user
        user.is_locked = True
        user.save()

        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        with pytest.raises(AuthenticationFailed) as exc_info:
            auth.authenticate(request)

        assert "locked" in str(exc_info.value)

    def test_authentication_after_user_deactivated(self) -> None:
        """Test authentication fails after user is deactivated."""
        from apps.accounts.jwt_utils import generate_jwt_token
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        token = generate_jwt_token(user)

        # Deactivate the user
        user.is_active = False
        user.save()

        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": f"Bearer {token}"}

        with pytest.raises(AuthenticationFailed) as exc_info:
            auth.authenticate(request)

        assert "disabled" in str(exc_info.value)
