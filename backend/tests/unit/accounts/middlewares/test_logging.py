"""Unit tests for HTTPAccessLoggingMiddleware (mocked dependencies)."""

from unittest.mock import MagicMock, patch

from apps.accounts.middlewares.logging import HTTPAccessLoggingMiddleware


class TestHTTPAccessLoggingMiddleware:
    """Unit tests for HTTPAccessLoggingMiddleware."""

    def test_init_creates_security_events(self) -> None:
        """Test middleware initializes SecurityEventService."""
        get_response = MagicMock()

        with patch("apps.accounts.middlewares.logging.SecurityEventService"):
            middleware = HTTPAccessLoggingMiddleware(get_response)

        assert hasattr(middleware, "security_events")
        assert middleware.get_response == get_response

    def test_get_client_ip_with_x_forwarded_for(self) -> None:
        """Test extracting client IP from X-Forwarded-For header."""
        get_response = MagicMock()
        middleware = HTTPAccessLoggingMiddleware(get_response)

        request = MagicMock()
        request.META = {"HTTP_X_FORWARDED_FOR": "203.0.113.1, 198.51.100.1"}

        ip = middleware._get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_get_client_ip_without_x_forwarded_for(self) -> None:
        """Test extracting client IP from REMOTE_ADDR."""
        get_response = MagicMock()
        middleware = HTTPAccessLoggingMiddleware(get_response)

        request = MagicMock()
        request.META = {"REMOTE_ADDR": "192.168.1.1"}

        ip = middleware._get_client_ip(request)

        assert ip == "192.168.1.1"

    def test_detect_suspicious_patterns_sql_injection(self) -> None:
        """Test detecting SQL injection patterns."""
        get_response = MagicMock()
        middleware = HTTPAccessLoggingMiddleware(get_response)

        request = MagicMock()
        request.path = "/api/test?id=1' OR '1'='1"
        request.META = {"QUERY_STRING": "", "HTTP_USER_AGENT": "Test"}

        with patch.object(middleware.security_events, "log_security_event") as mock_log:
            middleware._detect_suspicious_patterns(request, "127.0.0.1")

        mock_log.assert_called_once()
        assert "sql_injection_attempt" in str(mock_log.call_args)

    def test_detect_suspicious_patterns_path_traversal(self) -> None:
        """Test detecting path traversal patterns."""
        get_response = MagicMock()
        middleware = HTTPAccessLoggingMiddleware(get_response)

        request = MagicMock()
        request.path = "/api/test/../../../etc/passwd"
        request.META = {"QUERY_STRING": "", "HTTP_USER_AGENT": "Test"}

        with patch.object(middleware.security_events, "log_security_event") as mock_log:
            middleware._detect_suspicious_patterns(request, "127.0.0.1")

        mock_log.assert_called_once()
        assert "path_traversal_attempt" in str(mock_log.call_args)
