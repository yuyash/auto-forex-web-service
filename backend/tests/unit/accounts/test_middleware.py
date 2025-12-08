"""
Unit tests for security monitoring middleware.

Tests cover:
- SecurityMonitoringMiddleware
- TokenAuthMiddleware for WebSocket
"""

from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory

import pytest

from apps.accounts.middleware import SecurityMonitoringMiddleware, _get_authenticated_user


class TestGetAuthenticatedUser:
    """Test cases for _get_authenticated_user helper function."""

    @pytest.mark.django_db
    def test_returns_user_when_authenticated(self) -> None:
        """Test returns user when authenticated."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        result = _get_authenticated_user(user)

        assert result == user

    def test_returns_none_for_anonymous_user(self) -> None:
        """Test returns None for anonymous user."""
        from django.contrib.auth.models import AnonymousUser

        user = AnonymousUser()

        result = _get_authenticated_user(user)

        assert result is None

    def test_returns_none_for_none(self) -> None:
        """Test returns None when user is None."""
        result = _get_authenticated_user(None)

        assert result is None


class TestSecurityMonitoringMiddleware:
    """Test cases for SecurityMonitoringMiddleware."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.mock_get_response = MagicMock(return_value=HttpResponse(status=200))
        self.middleware = SecurityMonitoringMiddleware(self.mock_get_response)

    def test_init_sets_get_response(self) -> None:
        """Test __init__ sets get_response."""
        mock_response = MagicMock()
        middleware = SecurityMonitoringMiddleware(mock_response)

        assert middleware.get_response == mock_response

    def test_get_client_ip_from_remote_addr(self) -> None:
        """Test _get_client_ip extracts from REMOTE_ADDR."""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        ip = self.middleware._get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_get_client_ip_from_x_forwarded_for(self) -> None:
        """Test _get_client_ip extracts from X-Forwarded-For header."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 192.168.1.1"
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        ip = self.middleware._get_client_ip(request)

        assert ip == "10.0.0.1"

    def test_get_client_ip_strips_whitespace(self) -> None:
        """Test _get_client_ip strips whitespace from IP."""
        request = self.factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "  10.0.0.1  , 192.168.1.1"

        ip = self.middleware._get_client_ip(request)

        assert ip == "10.0.0.1"

    @patch.object(SecurityMonitoringMiddleware, "_is_blocked_ip", return_value=False)
    def test_call_invokes_get_response(self, mock_blocked: MagicMock) -> None:
        """Test __call__ invokes get_response."""
        request = self.factory.get("/some/path")

        self.middleware(request)

        self.mock_get_response.assert_called_once_with(request)

    @patch.object(SecurityMonitoringMiddleware, "_is_blocked_ip", return_value=True)
    @patch.object(SecurityMonitoringMiddleware, "_log_authentication_event")
    def test_call_logs_blocked_ip_attempt(
        self,
        mock_log: MagicMock,
        mock_blocked: MagicMock,
    ) -> None:
        """Test __call__ logs blocked IP attempts."""
        request = self.factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.1"

        # Need to mock security_logger
        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_security_log:
            self.middleware(request)

            mock_security_log.assert_called_once()
            call_kwargs = mock_security_log.call_args.kwargs
            assert call_kwargs["event_type"] == "blocked_ip_attempt"
            assert call_kwargs["ip_address"] == "192.168.1.1"

    @patch("apps.accounts.middleware.RateLimiter")
    def test_is_blocked_ip_calls_rate_limiter(self, mock_rate_limiter: MagicMock) -> None:
        """Test _is_blocked_ip calls RateLimiter."""
        mock_rate_limiter.is_ip_blocked.return_value = (True, None)

        result = self.middleware._is_blocked_ip("192.168.1.1")

        mock_rate_limiter.is_ip_blocked.assert_called_once_with("192.168.1.1")
        assert result is True


class TestSecurityMonitoringMiddlewareLogging:
    """Test cases for SecurityMonitoringMiddleware logging methods."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.mock_get_response = MagicMock(return_value=HttpResponse(status=200))
        self.middleware = SecurityMonitoringMiddleware(self.mock_get_response)

    def test_log_registration_success(self) -> None:
        """Test logging successful registration."""
        request = self.factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=201)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "user_registration"
            assert call_kwargs["severity"] == "info"

    def test_log_registration_disabled(self) -> None:
        """Test logging registration disabled (503)."""
        request = self.factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=503)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "registration_blocked"
            assert call_kwargs["severity"] == "warning"

    def test_log_registration_failed(self) -> None:
        """Test logging failed registration."""
        request = self.factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=400)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "registration_failed"
            assert call_kwargs["severity"] == "warning"

    def test_log_login_disabled(self) -> None:
        """Test logging login disabled (503)."""
        request = self.factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=503)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "login_blocked"

    @patch("apps.accounts.middleware.RateLimiter")
    def test_log_login_rate_limited(self, mock_rate_limiter: MagicMock) -> None:
        """Test logging rate limited login (429)."""
        mock_rate_limiter.get_failed_attempts.return_value = 5

        request = self.factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=429)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "login_rate_limited"

    def test_log_account_locked(self) -> None:
        """Test logging account locked (403)."""
        request = self.factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=403)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_called_once()
            call_kwargs = mock_log.call_args.kwargs
            assert call_kwargs["event_type"] == "login_account_locked"
            assert call_kwargs["severity"] == "error"

    def test_no_log_for_non_auth_endpoints(self) -> None:
        """Test no logging for non-auth endpoints."""
        request = self.factory.get("/api/some/other/endpoint")
        request.META["REMOTE_ADDR"] = "192.168.1.1"
        response = HttpResponse(status=200)

        with patch.object(
            self.middleware.security_logger,
            "log_security_event",
        ) as mock_log:
            self.middleware._log_authentication_event(request, response, "192.168.1.1")

            mock_log.assert_not_called()
