"""Unit tests for apps.accounts.services.events (SecurityEventService)."""

import pytest


@pytest.mark.django_db
def test_log_login_success_creates_event() -> None:
    from apps.accounts.models import AccountSecurityEvent, User
    from apps.accounts.services.events import SecurityEventService

    user = User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="TestPass123!",
    )

    security_events = SecurityEventService()
    security_events.log_login_success(user=user, ip_address="192.168.1.1")

    event = AccountSecurityEvent.objects.latest("created_at")
    assert event.event_type == "login_success"
    assert event.severity == "info"
    assert event.user == user
    assert event.ip_address == "192.168.1.1"


@pytest.mark.django_db
def test_log_login_failed_creates_event() -> None:
    from apps.accounts.models import AccountSecurityEvent
    from apps.accounts.services.events import SecurityEventService

    security_events = SecurityEventService()
    security_events.log_login_failed(
        username="someone",
        ip_address="10.0.0.1",
        reason="Invalid password",
        user_agent="ua",
    )

    event = AccountSecurityEvent.objects.latest("created_at")
    assert event.event_type == "login_failed"
    assert event.severity == "warning"
    assert event.user is None
    assert event.ip_address == "10.0.0.1"
    assert event.user_agent == "ua"
    assert event.details["username"] == "someone"
    assert event.details["reason"] == "Invalid password"


@pytest.mark.django_db
def test_log_security_event_creates_event() -> None:
    from apps.accounts.models import AccountSecurityEvent
    from apps.accounts.services.events import SecurityEventService

    security_events = SecurityEventService()
    security_events.log_security_event(
        event_type="custom_event",
        description="Something happened",
        severity="debug",
        ip_address="127.0.0.1",
        details={"k": "v"},
    )

    event = AccountSecurityEvent.objects.latest("created_at")
    assert event.event_type == "custom_event"
    assert event.severity == "debug"
    assert event.ip_address == "127.0.0.1"
    assert event.details == {"k": "v"}
