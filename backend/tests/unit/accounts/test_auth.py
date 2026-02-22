"""Unit tests for accounts auth module."""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts.auth import JWTAuthentication


class TestJWTAuthentication:
    """Test JWTAuthentication class."""

    def test_keyword(self):
        auth = JWTAuthentication()
        assert auth.keyword == "Bearer"

    def test_authenticate_no_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_empty_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": ""}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_wrong_keyword(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Token abc123"}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_malformed_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer"}
        result = auth.authenticate(request)
        assert result is None

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_valid_token(self, mock_jwt_service_cls):
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = mock_user

        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer valid-token"}
        user, token = auth.authenticate(request)
        assert user is mock_user
        assert token == "valid-token"

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_invalid_token(self, mock_jwt_service_cls):
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = None

        auth = JWTAuthentication()
        with pytest.raises(AuthenticationFailed, match="Invalid or expired"):
            auth.authenticate_credentials("bad-token")

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_inactive_user(self, mock_jwt_service_cls):
        mock_user = MagicMock()
        mock_user.is_active = False
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = mock_user

        auth = JWTAuthentication()
        with pytest.raises(AuthenticationFailed, match="disabled"):
            auth.authenticate_credentials("some-token")

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_locked_user(self, mock_jwt_service_cls):
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = True
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = mock_user

        auth = JWTAuthentication()
        with pytest.raises(AuthenticationFailed, match="locked"):
            auth.authenticate_credentials("some-token")

    def test_authenticate_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        assert auth.authenticate_header(request) == "Bearer"
