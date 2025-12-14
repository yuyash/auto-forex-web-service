"""Unit tests for accounts middleware.

Tests cover:
- SecurityMonitoringMiddleware
- TokenAuthMiddleware for WebSocket
- RateLimiter (moved into apps.accounts.middleware)
"""

from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory

import pytest

from apps.accounts.middleware import (
    RateLimiter,
    SecurityMonitoringMiddleware,
    _get_authenticated_user,
)


class TestRateLimiterCacheKey:
    """Test cases for cache key generation."""

    def test_get_cache_key_format(self) -> None:
        """Test cache key format is correct."""
        key = RateLimiter.get_cache_key("192.168.1.1")
        assert key == "login_attempts:192.168.1.1"

    def test_get_cache_key_ipv6(self) -> None:
        """Test cache key with IPv6 address."""
        key = RateLimiter.get_cache_key("::1")
        assert key == "login_attempts:::1"

    def test_get_cache_key_full_ipv6(self) -> None:
        """Test cache key with full IPv6 address."""
        key = RateLimiter.get_cache_key("2001:0db8:85a3:0000:0000:8a2e:0370:7334")
        assert "2001:0db8:85a3:0000:0000:8a2e:0370:7334" in key


class TestRateLimiterFailedAttempts:
    """Test cases for failed attempts tracking."""

    @patch("apps.accounts.middleware.cache")
    def test_get_failed_attempts_no_cache(self, mock_cache: MagicMock) -> None:
        """Test get_failed_attempts returns 0 when no cache entry."""
        mock_cache.get.return_value = 0

        result = RateLimiter.get_failed_attempts("192.168.1.1")

        assert result == 0
        mock_cache.get.assert_called_once()

    @patch("apps.accounts.middleware.cache")
    def test_get_failed_attempts_with_cache(self, mock_cache: MagicMock) -> None:
        """Test get_failed_attempts returns cached value."""
        mock_cache.get.return_value = 3

        result = RateLimiter.get_failed_attempts("192.168.1.1")

        assert result == 3

    @patch("apps.accounts.middleware.cache")
    def test_increment_failed_attempts(self, mock_cache: MagicMock) -> None:
        """Test increment_failed_attempts increases count."""
        mock_cache.get.return_value = 2

        result = RateLimiter.increment_failed_attempts("192.168.1.1")

        assert result == 3
        mock_cache.set.assert_called_once()
        # Verify timeout is set correctly (LOCKOUT_DURATION_MINUTES * 60)
        call_args = mock_cache.set.call_args
        assert call_args[0][1] == 3  # New count
        assert call_args[0][2] == RateLimiter.LOCKOUT_DURATION_MINUTES * 60

    @patch("apps.accounts.middleware.cache")
    def test_increment_failed_attempts_from_zero(self, mock_cache: MagicMock) -> None:
        """Test increment_failed_attempts from zero."""
        mock_cache.get.return_value = 0

        result = RateLimiter.increment_failed_attempts("192.168.1.1")

        assert result == 1

    @patch("apps.accounts.middleware.cache")
    def test_reset_failed_attempts(self, mock_cache: MagicMock) -> None:
        """Test reset_failed_attempts deletes cache entry."""
        RateLimiter.reset_failed_attempts("192.168.1.1")

        mock_cache.delete.assert_called_once_with("login_attempts:192.168.1.1")


class TestRateLimiterIPBlocking:
    """Test cases for IP blocking logic."""

    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_is_ip_blocked_by_attempts(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        """Test IP is blocked after max attempts exceeded."""
        mock_cache.get.return_value = RateLimiter.MAX_ATTEMPTS

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is True
        assert message is not None
        assert "Too many failed login attempts" in message
        assert str(RateLimiter.LOCKOUT_DURATION_MINUTES) in message

    @patch("apps.accounts.middleware.cache")
    @pytest.mark.django_db
    def test_is_ip_not_blocked_under_max(self, mock_cache: MagicMock) -> None:
        """Test IP is not blocked when under max attempts."""
        mock_cache.get.return_value = RateLimiter.MAX_ATTEMPTS - 1

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is False
        assert message is None

    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_is_ip_blocked_by_database_entry(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        """Test IP is blocked by database entry."""
        mock_cache.get.return_value = 0

        blocked_entry = MagicMock()
        blocked_entry.is_active.return_value = True
        blocked_entry.reason = "Manually blocked"
        mock_blocked_ip.objects.get.return_value = blocked_entry

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is True
        assert message == "Manually blocked"

    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_is_ip_not_blocked_when_db_entry_inactive(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
    ) -> None:
        """Test IP is not blocked when database entry is inactive."""
        mock_cache.get.return_value = 0

        blocked_entry = MagicMock()
        blocked_entry.is_active.return_value = False
        mock_blocked_ip.objects.get.return_value = blocked_entry

        is_blocked, message = RateLimiter.is_ip_blocked("192.168.1.1")

        assert is_blocked is False
        assert message is None


class TestRateLimiterBlockIPAddress:
    """Test cases for block_ip_address function."""

    @patch("apps.accounts.middleware.timezone")
    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_block_ip_creates_new_entry(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
        mock_tz: MagicMock,
    ) -> None:
        """Test block_ip_address creates new BlockedIP entry."""
        from django.utils import timezone

        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5
        mock_blocked_ip.objects.get_or_create.return_value = (MagicMock(), True)

        RateLimiter.block_ip_address("192.168.1.1", "Test reason")

        mock_blocked_ip.objects.get_or_create.assert_called_once()
        call_kwargs = mock_blocked_ip.objects.get_or_create.call_args[1]
        assert call_kwargs["defaults"]["reason"] == "Test reason"
        assert call_kwargs["defaults"]["is_permanent"] is False

    @patch("apps.accounts.middleware.timezone")
    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_block_ip_updates_existing_entry(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
        mock_tz: MagicMock,
    ) -> None:
        """Test block_ip_address updates existing BlockedIP entry."""
        from django.utils import timezone

        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5

        existing_entry = MagicMock()
        mock_blocked_ip.objects.get_or_create.return_value = (existing_entry, False)

        RateLimiter.block_ip_address("192.168.1.1", "Updated reason")

        assert existing_entry.reason == "Updated reason"
        existing_entry.save.assert_called_once()

    @patch("apps.accounts.middleware.timezone")
    @patch("apps.accounts.middleware.cache")
    @patch("apps.accounts.middleware.BlockedIP")
    def test_block_ip_uses_default_reason(
        self,
        mock_blocked_ip: MagicMock,
        mock_cache: MagicMock,
        mock_tz: MagicMock,
    ) -> None:
        """Test block_ip_address uses default reason."""
        from django.utils import timezone

        mock_tz.now.return_value = timezone.now()
        mock_cache.get.return_value = 5
        mock_blocked_ip.objects.get_or_create.return_value = (MagicMock(), True)

        RateLimiter.block_ip_address("192.168.1.1")

        call_kwargs = mock_blocked_ip.objects.get_or_create.call_args[1]
        assert "failed login attempts" in call_kwargs["defaults"]["reason"].lower()


class TestRateLimiterAccountLock:
    """Test cases for account locking logic."""

    def test_check_account_lock_when_locked(self) -> None:
        """Test check_account_lock returns True when account is locked."""
        mock_user = MagicMock()
        mock_user.is_locked = True

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        assert message is not None
        assert "locked" in message.lower()
        assert "contact support" in message.lower()

    def test_check_account_lock_exceeds_threshold(self) -> None:
        """Test check_account_lock locks account when threshold exceeded."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is True
        mock_user.lock_account.assert_called_once()
        assert message is not None
        assert "locked" in message.lower()

    def test_check_account_lock_not_locked(self) -> None:
        """Test check_account_lock returns False when not locked."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = RateLimiter.ACCOUNT_LOCK_THRESHOLD - 1

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is False
        assert message is None

    def test_check_account_lock_zero_attempts(self) -> None:
        """Test check_account_lock with zero failed attempts."""
        mock_user = MagicMock()
        mock_user.is_locked = False
        mock_user.failed_login_attempts = 0

        is_locked, message = RateLimiter.check_account_lock(mock_user)

        assert is_locked is False
        assert message is None


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
