"""
Unit tests for security monitoring middleware.

This module tests:
- Authentication event logging
- IP blocking after 5 failed attempts
- Account locking after 10 failed attempts
- Security event creation
- IP unblocking after timeout
- HTTP access logging
- SQL injection detection
- Path traversal detection

Requirements: 34.1, 34.2, 34.3, 34.4, 34.5, 35.1, 35.3, 35.4, 35.5
"""

from datetime import timedelta
from unittest.mock import Mock

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

import pytest

from accounts.middleware import HTTPAccessLoggingMiddleware, SecurityMonitoringMiddleware
from accounts.models import BlockedIP, UserSession
from accounts.rate_limiter import RateLimiter
from trading.event_models import Event

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="TestPass123!",
    )


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture
def get_response():
    """Create a mock get_response callable."""
    return Mock(return_value=HttpResponse(status=200))


@pytest.fixture
def security_middleware(get_response):
    """Create security monitoring middleware instance."""
    return SecurityMonitoringMiddleware(get_response)


@pytest.fixture
def http_middleware(get_response):
    """Create HTTP access logging middleware instance."""
    return HTTPAccessLoggingMiddleware(get_response)


class TestSecurityMonitoringMiddleware:
    """Test SecurityMonitoringMiddleware."""

    def test_get_client_ip_from_remote_addr(self, security_middleware, request_factory):
        """Test getting client IP from REMOTE_ADDR."""
        request = request_factory.get("/")
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        ip = security_middleware._get_client_ip(request)

        assert ip == "192.168.1.100"

    def test_get_client_ip_from_x_forwarded_for(self, security_middleware, request_factory):
        """Test getting client IP from X-Forwarded-For header."""
        request = request_factory.get("/")
        request.META["HTTP_X_FORWARDED_FOR"] = "10.0.0.1, 192.168.1.100"
        request.META["REMOTE_ADDR"] = "192.168.1.100"

        ip = security_middleware._get_client_ip(request)

        assert ip == "10.0.0.1"

    def test_is_blocked_ip_not_blocked(self, security_middleware, request_factory, db):
        """Test IP is not blocked when no blocks exist."""
        is_blocked = security_middleware._is_blocked_ip("192.168.1.100")

        assert is_blocked is False

    def test_is_blocked_ip_rate_limited(self, security_middleware, request_factory, db):
        """Test IP is blocked after rate limit exceeded."""
        ip_address = "192.168.1.100"

        # Simulate 5 failed attempts
        for _ in range(5):
            RateLimiter.increment_failed_attempts(ip_address)

        is_blocked = security_middleware._is_blocked_ip(ip_address)

        assert is_blocked is True

    def test_is_blocked_ip_database_block(self, security_middleware, request_factory, db):
        """Test IP is blocked when in database."""
        ip_address = "192.168.1.100"
        blocked_until = timezone.now() + timedelta(hours=1)

        BlockedIP.objects.create(
            ip_address=ip_address,
            reason="Test block",
            blocked_until=blocked_until,
            is_permanent=False,
        )

        is_blocked = security_middleware._is_blocked_ip(ip_address)

        assert is_blocked is True

    def test_log_successful_registration(self, security_middleware, request_factory, db):
        """Test logging successful registration event."""
        request = request_factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=201)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="user_registration")
        assert events.count() == 1
        assert events[0].severity == "info"
        assert events[0].ip_address == "192.168.1.100"

    def test_log_failed_registration(self, security_middleware, request_factory, db):
        """Test logging failed registration event."""
        request = request_factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=400)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="registration_failed")
        assert events.count() == 1
        assert events[0].severity == "warning"

    def test_log_registration_blocked(self, security_middleware, request_factory, db):
        """Test logging blocked registration event."""
        request = request_factory.post("/api/auth/register")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=503)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="registration_blocked")
        assert events.count() == 1
        assert events[0].severity == "warning"

    def test_log_successful_login(self, security_middleware, request_factory, user, db):
        """Test logging successful login event."""
        request = request_factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.user = user
        response = HttpResponse(status=200)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="login_success")
        assert events.count() == 1
        assert events[0].severity == "info"
        assert events[0].user == user

    def test_log_failed_login(self, security_middleware, request_factory, db):
        """Test logging failed login event."""
        request = request_factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=401)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="login_failed")
        assert events.count() == 1
        assert events[0].severity == "warning"

    def test_log_login_rate_limited(self, security_middleware, request_factory, db):
        """Test logging rate limited login event."""
        request = request_factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=429)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="login_rate_limited")
        assert events.count() == 1
        assert events[0].severity == "warning"

    def test_log_login_account_locked(self, security_middleware, request_factory, db):
        """Test logging account locked login event."""
        request = request_factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=403)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="login_account_locked")
        assert events.count() == 1
        assert events[0].severity == "error"

    def test_log_login_blocked(self, security_middleware, request_factory, db):
        """Test logging blocked login event."""
        request = request_factory.post("/api/auth/login")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=503)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="login_blocked")
        assert events.count() == 1
        assert events[0].severity == "warning"

    def test_log_successful_logout(self, security_middleware, request_factory, user, db):
        """Test logging successful logout event."""
        request = request_factory.post("/api/auth/logout")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.user = user
        response = HttpResponse(status=200)

        security_middleware._log_authentication_event(request, response, "192.168.1.100")

        events = Event.objects.filter(event_type="logout_success")
        assert events.count() == 1
        assert events[0].severity == "info"
        assert events[0].user == user

    def test_create_user_session(self, security_middleware, user, db):
        """Test creating user session."""
        ip_address = "192.168.1.100"
        user_agent = "TestAgent/1.0"

        security_middleware._create_user_session(user, ip_address, user_agent)

        sessions = UserSession.objects.filter(user=user)
        assert sessions.count() == 1
        assert sessions[0].ip_address == ip_address
        assert sessions[0].user_agent == user_agent
        assert sessions[0].is_active is True

    def test_blocked_ip_attempt_logged(self, security_middleware, request_factory, db):
        """Test blocked IP attempt is logged."""
        ip_address = "192.168.1.100"

        # Block the IP
        RateLimiter.block_ip_address(ip_address)

        # Create request
        request = request_factory.get("/")
        request.META["REMOTE_ADDR"] = ip_address
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"

        # Process request
        security_middleware(request)

        # Check event was logged
        events = Event.objects.filter(event_type="blocked_ip_attempt")
        assert events.count() == 1
        assert events[0].ip_address == ip_address


class TestHTTPAccessLoggingMiddleware:
    """Test HTTPAccessLoggingMiddleware."""

    def test_detect_sql_injection_in_path(self, http_middleware, request_factory, db):
        """Test SQL injection detection in path."""
        request = request_factory.get("/api/users?id=1' OR '1'='1")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"

        http_middleware._detect_suspicious_patterns(request, "192.168.1.100")

        events = Event.objects.filter(event_type="sql_injection_attempt")
        assert events.count() == 1
        assert events[0].severity == "critical"

    def test_detect_sql_injection_in_query_string(self, http_middleware, request_factory, db):
        """Test SQL injection detection in query string."""
        request = request_factory.get("/api/users")
        request.META["QUERY_STRING"] = "id=1 UNION SELECT * FROM users"
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"

        http_middleware._detect_suspicious_patterns(request, "192.168.1.100")

        events = Event.objects.filter(event_type="sql_injection_attempt")
        assert events.count() == 1

    def test_detect_path_traversal(self, http_middleware, request_factory, db):
        """Test path traversal detection."""
        request = request_factory.get("/api/../../../etc/passwd")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"

        http_middleware._detect_suspicious_patterns(request, "192.168.1.100")

        events = Event.objects.filter(event_type="path_traversal_attempt")
        assert events.count() == 1
        assert events[0].severity == "critical"

    def test_log_admin_endpoint_access_authenticated(
        self, http_middleware, request_factory, user, db
    ):
        """Test logging admin endpoint access by authenticated user."""
        user.is_staff = True
        user.save()

        request = request_factory.get("/api/admin/dashboard")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        request.user = user
        response = HttpResponse(status=200)

        http_middleware._log_http_access(request, response, "192.168.1.100", 50.0)

        events = Event.objects.filter(event_type="admin_endpoint_access")
        assert events.count() == 1
        assert events[0].severity == "info"
        assert events[0].user == user

    def test_log_admin_endpoint_access_unauthenticated(self, http_middleware, request_factory, db):
        """Test logging admin endpoint access by unauthenticated user."""
        request = request_factory.get("/api/admin/dashboard")
        request.META["REMOTE_ADDR"] = "192.168.1.100"
        request.META["HTTP_USER_AGENT"] = "TestAgent/1.0"
        response = HttpResponse(status=401)

        http_middleware._log_http_access(request, response, "192.168.1.100", 50.0)

        events = Event.objects.filter(event_type="admin_endpoint_access")
        assert events.count() == 1
        assert events[0].severity == "warning"


class TestIPBlocking:
    """Test IP blocking functionality."""

    def test_ip_blocked_after_5_failed_attempts(self, db):
        """Test IP is blocked after 5 failed login attempts."""
        ip_address = "192.168.1.101"  # Use unique IP

        # Reset cache first
        RateLimiter.reset_failed_attempts(ip_address)

        # Simulate 5 failed attempts
        for i in range(5):
            attempts = RateLimiter.increment_failed_attempts(ip_address)
            assert attempts == i + 1

        # Check if IP is blocked
        is_blocked, reason = RateLimiter.is_ip_blocked(ip_address)
        assert is_blocked is True
        assert reason is not None and "Too many failed login attempts" in reason

        # Cleanup
        RateLimiter.reset_failed_attempts(ip_address)

    def test_ip_not_blocked_before_threshold(self, db):
        """Test IP is not blocked before threshold."""
        ip_address = "192.168.1.102"  # Use unique IP

        # Reset cache first
        RateLimiter.reset_failed_attempts(ip_address)

        # Simulate 4 failed attempts
        for _ in range(4):
            RateLimiter.increment_failed_attempts(ip_address)

        # Check if IP is blocked
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        assert is_blocked is False

        # Cleanup
        RateLimiter.reset_failed_attempts(ip_address)

    def test_ip_unblocked_after_timeout(self, db):
        """Test IP is unblocked after timeout expires."""
        ip_address = "192.168.1.103"  # Use unique IP

        # Reset cache first
        RateLimiter.reset_failed_attempts(ip_address)

        blocked_until = timezone.now() - timedelta(minutes=1)

        # Create expired block
        BlockedIP.objects.create(
            ip_address=ip_address,
            reason="Test block",
            blocked_until=blocked_until,
            is_permanent=False,
        )

        # Check if IP is blocked
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        assert is_blocked is False

    def test_permanent_ip_block(self, db):
        """Test permanent IP block."""
        ip_address = "192.168.1.100"
        blocked_until = timezone.now() - timedelta(days=1)

        # Create permanent block
        BlockedIP.objects.create(
            ip_address=ip_address,
            reason="Permanent block",
            blocked_until=blocked_until,
            is_permanent=True,
        )

        # Check if IP is blocked
        is_blocked, _ = RateLimiter.is_ip_blocked(ip_address)
        assert is_blocked is True


class TestAccountLocking:
    """Test account locking functionality."""

    def test_account_locked_after_10_failed_attempts(self, user, db):
        """Test account is locked after 10 failed login attempts."""
        # Simulate 10 failed attempts
        for i in range(10):
            user.increment_failed_login()
            user.refresh_from_db()
            assert user.failed_login_attempts == i + 1

        # Check if account should be locked
        should_lock, reason = RateLimiter.check_account_lock(user)
        assert should_lock is True
        assert reason is not None and "locked" in reason.lower()
        assert user.is_locked is True

    def test_account_not_locked_before_threshold(self, user, db):
        """Test account is not locked before threshold."""
        # Simulate 9 failed attempts
        for _ in range(9):
            user.increment_failed_login()

        user.refresh_from_db()

        # Check if account should be locked
        should_lock, _ = RateLimiter.check_account_lock(user)
        assert should_lock is False
        assert user.is_locked is False

    def test_account_unlock(self, user, db):
        """Test account can be unlocked."""
        # Lock the account
        user.lock_account()
        user.refresh_from_db()
        assert user.is_locked is True

        # Unlock the account
        user.unlock_account()
        user.refresh_from_db()
        assert user.is_locked is False
        assert user.failed_login_attempts == 0

    def test_failed_login_reset_on_success(self, user, db):
        """Test failed login counter is reset on successful login."""
        # Simulate 5 failed attempts
        for _ in range(5):
            user.increment_failed_login()

        user.refresh_from_db()
        assert user.failed_login_attempts == 5

        # Reset on successful login
        user.reset_failed_login()
        user.refresh_from_db()
        assert user.failed_login_attempts == 0
        assert user.last_login_attempt is None


class TestSecurityEventCreation:
    """Test security event creation."""

    def test_create_security_event(self, user, db):
        """Test creating a security event."""
        event = Event.log_security_event(
            event_type="test_event",
            description="Test security event",
            severity="warning",
            user=user,
            ip_address="192.168.1.100",
            user_agent="TestAgent/1.0",
            details={"key": "value"},
        )

        assert event.category == "security"
        assert event.event_type == "test_event"
        assert event.severity == "warning"
        assert event.user == user
        assert event.ip_address == "192.168.1.100"
        assert event.details["key"] == "value"

    def test_security_events_indexed(self, db):
        """Test security events are properly indexed."""
        # Create multiple events
        for i in range(5):
            Event.log_security_event(
                event_type=f"test_event_{i}",
                description=f"Test event {i}",
                severity="info",
                ip_address="192.168.1.100",
            )

        # Query events
        events = Event.objects.filter(
            category="security",
            ip_address="192.168.1.100",
        )

        assert events.count() == 5

    def test_security_events_ordered_by_timestamp(self, db):
        """Test security events are ordered by timestamp."""
        # Create events with slight delays
        event1 = Event.log_security_event(
            event_type="event1",
            description="First event",
            severity="info",
        )

        event2 = Event.log_security_event(
            event_type="event2",
            description="Second event",
            severity="info",
        )

        # Query events
        events = Event.objects.filter(category="security")

        # Should be ordered newest first
        assert events[0].id == event2.id
        assert events[1].id == event1.id
