"""
Unit tests for security dashboard endpoint.

This module tests:
- Security dashboard endpoint access
- Failed login data retrieval
- Blocked IP data retrieval
- Locked account data retrieval
- HTTP access patterns
- Suspicious patterns
- Filtering by event type, severity, IP, date range

Requirements: 37.1, 37.2, 37.3, 37.4
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

import pytest

from accounts.models import BlockedIP
from trading.event_models import Event

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_user(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a regular user."""
    return User.objects.create_user(
        username="regular",
        email="regular@example.com",
        password="RegularPass123!",
    )


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


@pytest.fixture
def authenticated_admin_client(client, admin_user):
    """Create an authenticated admin client."""
    client.force_login(admin_user)
    return client


@pytest.fixture
def authenticated_regular_client(client, regular_user):
    """Create an authenticated regular client."""
    client.force_login(regular_user)
    return client


@pytest.fixture
def security_events(db, regular_user):
    """Create sample security events."""
    one_day_ago = timezone.now() - timedelta(days=1)

    # Create failed login events
    Event.objects.create(
        category="security",
        event_type="login_failed",
        severity="warning",
        description="Failed login attempt",
        ip_address="192.168.1.100",
        user_agent="Mozilla/5.0",
        details={"email": "test@example.com"},
        timestamp=one_day_ago,
    )

    # Create suspicious activity event
    Event.objects.create(
        category="security",
        event_type="suspicious_activity",
        severity="error",
        description="Suspicious activity detected",
        ip_address="192.168.1.101",
        timestamp=one_day_ago,
    )

    # Create HTTP request event
    Event.objects.create(
        category="security",
        event_type="http_request",
        severity="info",
        description="HTTP request",
        ip_address="192.168.1.100",
        timestamp=timezone.now() - timedelta(minutes=30),
    )


@pytest.fixture
def blocked_ip(db):
    """Create a blocked IP."""
    return BlockedIP.objects.create(
        ip_address="192.168.1.100",
        reason="Too many failed login attempts",
        failed_attempts=5,
        blocked_until=timezone.now() + timedelta(hours=1),
    )


@pytest.fixture
def locked_user(db):
    """Create a locked user."""
    user = User.objects.create_user(
        username="locked",
        email="locked@example.com",
        password="LockedPass123!",
    )
    user.is_locked = True
    user.failed_login_attempts = 10
    user.last_login_attempt = timezone.now()
    user.save()
    return user


@pytest.mark.django_db
class TestSecurityDashboard:
    """Test security dashboard endpoint."""

    def test_security_dashboard_requires_authentication(self, client):
        """Test that security dashboard requires authentication."""
        response = client.get("/api/admin/security/")

        assert response.status_code == 401

    def test_security_dashboard_requires_admin_permission(self, authenticated_regular_client):
        """Test that security dashboard requires admin permission."""
        response = authenticated_regular_client.get("/api/admin/security/")

        assert response.status_code == 403

    def test_security_dashboard_success(
        self, authenticated_admin_client, security_events, blocked_ip, locked_user
    ):
        """Test successful security dashboard retrieval."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "timestamp" in data
        assert "summary" in data
        assert "failed_logins" in data
        assert "blocked_ips" in data
        assert "locked_accounts" in data
        assert "http_access_patterns" in data
        assert "suspicious_patterns" in data
        assert "filtered_events" in data
        assert "filters_applied" in data

        # Check summary
        assert data["summary"]["failed_logins_24h"] >= 1
        assert data["summary"]["blocked_ips_active"] >= 1
        assert data["summary"]["locked_accounts"] >= 1
        assert data["summary"]["suspicious_events_24h"] >= 1

    def test_security_dashboard_filter_by_event_type(
        self, authenticated_admin_client, security_events
    ):
        """Test filtering security dashboard by event type."""
        response = authenticated_admin_client.get(
            "/api/admin/security/", {"event_type": "login_failed"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check that filters were applied
        assert data["filters_applied"]["event_type"] == "login_failed"

        # Check that filtered events contain only login_failed events
        for event in data["filtered_events"]:
            assert event["event_type"] == "login_failed"

    def test_security_dashboard_filter_by_severity(
        self, authenticated_admin_client, security_events
    ):
        """Test filtering security dashboard by severity."""
        response = authenticated_admin_client.get("/api/admin/security/", {"severity": "error"})

        assert response.status_code == 200
        data = response.json()

        # Check that filters were applied
        assert data["filters_applied"]["severity"] == "error"

        # Check that filtered events contain only error severity events
        for event in data["filtered_events"]:
            assert event["severity"] == "error"

    def test_security_dashboard_filter_by_ip_address(
        self, authenticated_admin_client, security_events
    ):
        """Test filtering security dashboard by IP address."""
        response = authenticated_admin_client.get(
            "/api/admin/security/", {"ip_address": "192.168.1.100"}
        )

        assert response.status_code == 200
        data = response.json()

        # Check that filters were applied
        assert data["filters_applied"]["ip_address"] == "192.168.1.100"

        # Check that filtered events contain only events from specified IP
        for event in data["filtered_events"]:
            assert event["ip_address"] == "192.168.1.100"

    def test_security_dashboard_filter_by_date_range(
        self, authenticated_admin_client, security_events
    ):
        """Test filtering security dashboard by date range."""
        start_date = (timezone.now() - timedelta(days=2)).isoformat()
        end_date = timezone.now().isoformat()

        response = authenticated_admin_client.get(
            "/api/admin/security/", {"start_date": start_date, "end_date": end_date}
        )

        assert response.status_code == 200
        data = response.json()

        # Check that filters were applied
        assert data["filters_applied"]["start_date"] == start_date
        assert data["filters_applied"]["end_date"] == end_date

    def test_security_dashboard_failed_logins_data(
        self, authenticated_admin_client, security_events
    ):
        """Test that failed logins data is returned correctly."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check failed logins structure
        assert len(data["failed_logins"]) >= 1
        failed_login = data["failed_logins"][0]
        assert "id" in failed_login
        assert "timestamp" in failed_login
        assert "ip_address" in failed_login
        assert "user_email" in failed_login
        assert "user_agent" in failed_login
        assert "description" in failed_login

    def test_security_dashboard_blocked_ips_data(self, authenticated_admin_client, blocked_ip):
        """Test that blocked IPs data is returned correctly."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check blocked IPs structure
        assert len(data["blocked_ips"]) >= 1
        blocked = data["blocked_ips"][0]
        assert "id" in blocked
        assert "ip_address" in blocked
        assert "reason" in blocked
        assert "failed_attempts" in blocked
        assert "blocked_at" in blocked
        assert "blocked_until" in blocked
        assert "is_permanent" in blocked

    def test_security_dashboard_locked_accounts_data(self, authenticated_admin_client, locked_user):
        """Test that locked accounts data is returned correctly."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check locked accounts structure
        assert len(data["locked_accounts"]) >= 1
        locked = data["locked_accounts"][0]
        assert "id" in locked
        assert "email" in locked
        assert "username" in locked
        assert "failed_attempts" in locked
        assert "last_login_attempt" in locked
        assert "locked_since" in locked

    def test_security_dashboard_http_access_patterns(
        self, authenticated_admin_client, security_events
    ):
        """Test that HTTP access patterns are returned correctly."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check HTTP access patterns structure
        assert isinstance(data["http_access_patterns"], list)
        if len(data["http_access_patterns"]) > 0:
            pattern = data["http_access_patterns"][0]
            assert "ip_address" in pattern
            assert "request_count" in pattern

    def test_security_dashboard_suspicious_patterns(
        self, authenticated_admin_client, security_events
    ):
        """Test that suspicious patterns are returned correctly."""
        response = authenticated_admin_client.get("/api/admin/security/")

        assert response.status_code == 200
        data = response.json()

        # Check suspicious patterns structure
        assert len(data["suspicious_patterns"]) >= 1
        pattern = data["suspicious_patterns"][0]
        assert "id" in pattern
        assert "timestamp" in pattern
        assert "event_type" in pattern
        assert "ip_address" in pattern
        assert "severity" in pattern
        assert "description" in pattern
        assert "details" in pattern
