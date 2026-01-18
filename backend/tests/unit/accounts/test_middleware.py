"""Unit tests for accounts middleware."""

from apps.accounts.middleware import JWTAuthMiddleware, SecurityMonitoringMiddleware


class TestJWTAuthMiddleware:
    """Test JWTAuthMiddleware."""

    def test_middleware_class_exists(self):
        """Test middleware class exists."""
        assert JWTAuthMiddleware is not None

    def test_middleware_is_callable(self):
        """Test middleware is callable."""
        assert callable(JWTAuthMiddleware)


class TestSecurityMonitoringMiddleware:
    """Test SecurityMonitoringMiddleware."""

    def test_middleware_class_exists(self):
        """Test middleware class exists."""
        assert SecurityMonitoringMiddleware is not None

    def test_middleware_is_callable(self):
        """Test middleware is callable."""
        assert callable(SecurityMonitoringMiddleware)
