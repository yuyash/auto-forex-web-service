"""Unit tests for accounts authentication."""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.authentication import JWTAuthentication

User = get_user_model()


class TestJWTAuthentication:
    """Test JWTAuthentication class."""

    def test_authenticate_with_valid_token(self):
        """Test authentication with valid JWT token."""
        auth = JWTAuthentication()
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid_token"}

        mock_user = Mock(spec=User)
        with patch.object(auth, "authenticate_credentials") as mock_auth_creds:
            mock_auth_creds.return_value = (mock_user, "valid_token")
            result = auth.authenticate(request)

            assert result == (mock_user, "valid_token")
            mock_auth_creds.assert_called_once_with("valid_token")

    def test_authenticate_without_authorization_header(self):
        """Test authentication without Authorization header."""
        auth = JWTAuthentication()
        request = Mock()
        request.META = {}

        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_with_invalid_header_format(self):
        """Test authentication with invalid header format."""
        auth = JWTAuthentication()
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "InvalidFormat"}

        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_with_wrong_keyword(self):
        """Test authentication with wrong keyword (not Bearer)."""
        auth = JWTAuthentication()
        request = Mock()
        request.META = {"HTTP_AUTHORIZATION": "Token some_token"}

        result = auth.authenticate(request)
        assert result is None

    @pytest.mark.django_db
    def test_authenticate_credentials_with_valid_token(self):
        """Test authenticate_credentials with valid token."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        from apps.accounts.services.jwt import JWTService

        service = JWTService()
        token = service.generate_token(user)

        auth = JWTAuthentication()
        result = auth.authenticate_credentials(token)

        assert result[0].id == user.id
        assert result[1] == token

    def test_authenticate_credentials_with_invalid_token(self):
        """Test authenticate_credentials with invalid token."""
        auth = JWTAuthentication()

        with pytest.raises(AuthenticationFailed):
            auth.authenticate_credentials("invalid_token")

    @pytest.mark.django_db
    def test_authenticate_credentials_with_inactive_user(self):
        """Test authenticate_credentials with inactive user."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        user.is_active = False
        user.save()

        from apps.accounts.services.jwt import JWTService

        service = JWTService()
        token = service.generate_token(user)

        auth = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            auth.authenticate_credentials(token)

    @pytest.mark.django_db
    def test_authenticate_credentials_with_locked_user(self):
        """Test authenticate_credentials with locked user."""
        user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        user.is_locked = True
        user.save()

        from apps.accounts.services.jwt import JWTService

        service = JWTService()
        token = service.generate_token(user)

        auth = JWTAuthentication()
        with pytest.raises(AuthenticationFailed):
            auth.authenticate_credentials(token)
