"""Unit tests for SecurityMonitoringMiddleware (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from apps.accounts.middlewares.security import SecurityMonitoringMiddleware


class TestSecurityMonitoringMiddleware:
    """Unit tests for SecurityMonitoringMiddleware."""

    def test_init_creates_security_events(self) -> None:
        """Test middleware initializes SecurityEventService."""
        get_response = MagicMock()

        with patch("apps.accounts.middlewares.security.SecurityEventService"):
            middleware = SecurityMonitoringMiddleware(get_response)

        assert hasattr(middleware, "security_events")
        assert middleware.get_response == get_response

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        get_response = MagicMock()
        middleware = SecurityMonitoringMiddleware(get_response)

        request = MagicMock()
        request.META = {"HTTP_X_FORWARDED_FOR": "203.0.113.1, 198.51.100.1"}

        ip = middleware._get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        get_response = MagicMock()
        middleware = SecurityMonitoringMiddleware(get_response)

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        ip = middleware._get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_is_blocked_ip(self) -> None:
        """Test checking if IP is blocked."""
        get_response = MagicMock()
        middleware = SecurityMonitoringMiddleware(get_response)

        with patch("apps.accounts.middlewares.security.RateLimiter") as mock_limiter:
            mock_limiter.is_ip_blocked.return_value = (True, "Blocked")

            result = middleware._is_blocked_ip("192.168.1.1")

        assert result is True
