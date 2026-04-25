"""Unit tests for accounts auth module."""

from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.test import APIRequestFactory

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
        request.COOKIES = {}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_empty_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": ""}
        request.COOKIES = {}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_wrong_keyword(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Token abc123"}
        request.COOKIES = {}
        result = auth.authenticate(request)
        assert result is None

    def test_authenticate_malformed_header(self):
        auth = JWTAuthentication()
        request = MagicMock()
        request.META = {"HTTP_AUTHORIZATION": "Bearer"}
        request.COOKIES = {}
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
        request.COOKIES = {}
        user, token = auth.authenticate(request)
        assert user is mock_user
        assert token == "valid-token"

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_cookie_token_for_safe_request(self, mock_jwt_service_cls):
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = mock_user

        auth = JWTAuthentication()
        request = MagicMock()
        request.method = "GET"
        request.META = {}
        request.COOKIES = {settings.AUTH_ACCESS_COOKIE_NAME: "cookie-token"}

        user, token = auth.authenticate(request)

        assert user is mock_user
        assert token == "cookie-token"

    @patch("apps.accounts.auth.JWTService")
    def test_authenticate_cookie_token_requires_csrf_for_unsafe_request(self, mock_jwt_service_cls):
        mock_user = MagicMock()
        mock_user.is_active = True
        mock_user.is_locked = False
        mock_jwt_service_cls.return_value.get_user_from_token.return_value = mock_user

        auth = JWTAuthentication()
        request = APIRequestFactory(enforce_csrf_checks=True).post(
            "/api/protected/", {}, format="json"
        )
        request.COOKIES = {settings.AUTH_ACCESS_COOKIE_NAME: "cookie-token"}

        with pytest.raises(PermissionDenied, match="CSRF"):
            auth.authenticate(request)

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
