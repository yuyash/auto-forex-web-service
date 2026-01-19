"""
Integration tests for audit logging and event tracking.

Tests structured log entry creation, log storage in database,
user/account identifier inclusion, log level filtering, and log retention policy.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import AccountSecurityEvent
from apps.market.models import MarketEvent
from apps.trading.models.events import TradingEvent
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import OandaAccountFactory, UserFactory


@pytest.mark.django_db
class TestAuditLogging(IntegrationTestCase):
    """Tests for audit logging and event tracking."""

    def test_structured_log_entry_creation(self):
        """Test that structured log entries are created with all required fields."""
        # Create user and account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Create a trading event with structured data
        event = TradingEvent.objects.create(
            event_type="trade_executed",
            severity="info",
            description="Trade executed successfully",
            user=user,
            account=account,
            instrument="EUR_USD",
            task_type="trading",
            task_id=123,
            details={
                "trade_id": "T12345",
                "direction": "BUY",
                "size": 1000,
                "price": 1.08950,
                "timestamp": "2024-01-15T10:30:00Z",
            },
        )

        # Verify all fields are populated
        assert event.event_type == "trade_executed"
        assert event.severity == "info"
        assert event.description == "Trade executed successfully"
        assert event.user == user
        assert event.account == account
        assert event.instrument == "EUR_USD"
        assert event.task_type == "trading"
        assert event.task_id == 123
        assert event.details["trade_id"] == "T12345"
        assert event.details["direction"] == "BUY"
        assert event.created_at is not None

    def test_log_storage_in_database(self):
        """Test that logs are correctly stored in the database."""
        user = UserFactory()

        # Create multiple events
        events_data = [
            {
                "event_type": "login_success",
                "severity": "info",
                "description": "User logged in successfully",
                "category": "security",
            },
            {
                "event_type": "login_failed",
                "severity": "warning",
                "description": "Failed login attempt",
                "category": "security",
            },
            {
                "event_type": "account_locked",
                "severity": "error",
                "description": "Account locked due to failed attempts",
                "category": "security",
            },
        ]

        for data in events_data:
            AccountSecurityEvent.objects.create(user=user, **data)

        # Verify all events are stored
        stored_events = AccountSecurityEvent.objects.filter(user=user)
        assert stored_events.count() == 3

        # Verify events can be queried by type
        login_events = AccountSecurityEvent.objects.filter(
            user=user, event_type__startswith="login"
        )
        assert login_events.count() == 2

    def test_user_account_identifier_inclusion(self):
        """Test that user and account identifiers are included in logs."""
        # Create user and account
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Create trading event
        trading_event = TradingEvent.objects.create(
            event_type="position_opened",
            severity="info",
            description="Position opened",
            user=user,
            account=account,
            instrument="GBP_USD",
            details={"position_id": "P123"},
        )

        # Verify user and account are linked
        assert trading_event.user.id == user.id  # ty:ignore[unresolved-attribute]
        assert trading_event.account.pk == account.pk  # ty:ignore[unresolved-attribute]

        # Create market event
        market_event = MarketEvent.objects.create(
            event_type="data_received",
            category="market",
            severity="info",
            description="Market data received",
            user=user,
            account=account,
            instrument="EUR_USD",
        )

        # Verify user and account are linked
        assert market_event.user.id == user.id  # ty:ignore[unresolved-attribute]
        assert market_event.account.pk == account.pk  # ty:ignore[unresolved-attribute]

        # Create security event
        security_event = AccountSecurityEvent.objects.create(
            event_type="password_changed",
            category="security",
            severity="info",
            description="User changed password",
            user=user,
            ip_address="192.168.1.1",
        )

        # Verify user is linked
        assert security_event.user.id == user.id  # ty:ignore[unresolved-attribute]

    def test_log_level_filtering(self):
        """Test that logs can be filtered by severity level."""
        user = UserFactory()

        # Create events with different severity levels
        severities = ["info", "warning", "error", "critical"]
        for severity in severities:
            AccountSecurityEvent.objects.create(
                event_type=f"test_{severity}",
                category="security",
                severity=severity,
                description=f"Test {severity} event",
                user=user,
            )

        # Test filtering by severity
        info_events = AccountSecurityEvent.objects.filter(user=user, severity="info")
        assert info_events.count() == 1

        warning_events = AccountSecurityEvent.objects.filter(user=user, severity="warning")
        assert warning_events.count() == 1

        error_events = AccountSecurityEvent.objects.filter(user=user, severity="error")
        assert error_events.count() == 1

        critical_events = AccountSecurityEvent.objects.filter(user=user, severity="critical")
        assert critical_events.count() == 1

        # Test filtering for high-severity events (error and critical)
        high_severity_events = AccountSecurityEvent.objects.filter(
            user=user, severity__in=["error", "critical"]
        )
        assert high_severity_events.count() == 2

    def test_log_retention_policy(self):
        """Test that old logs can be cleaned up based on retention policy."""
        user = UserFactory()

        # Create old events (older than retention period)
        old_timestamp = timezone.now() - timedelta(days=100)
        old_event = TradingEvent.objects.create(
            event_type="old_event",
            severity="info",
            description="Old event",
            user=user,
        )
        # Manually update created_at to simulate old event
        TradingEvent.objects.filter(id=old_event.id).update(created_at=old_timestamp)

        # Create recent events
        recent_event = TradingEvent.objects.create(
            event_type="recent_event",
            severity="info",
            description="Recent event",
            user=user,
        )

        # Verify both events exist
        assert TradingEvent.objects.filter(user=user).count() == 2

        # Simulate cleanup of events older than 90 days
        retention_cutoff = timezone.now() - timedelta(days=90)
        deleted_count, _ = TradingEvent.objects.filter(
            user=user, created_at__lt=retention_cutoff
        ).delete()

        # Verify old event was deleted
        assert deleted_count == 1
        assert TradingEvent.objects.filter(user=user).count() == 1
        assert TradingEvent.objects.filter(user=user, id=recent_event.id).exists()

    def test_event_category_filtering(self):
        """Test that events can be filtered by category."""
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Create events in different categories
        MarketEvent.objects.create(
            event_type="price_update",
            category="market",
            severity="info",
            description="Price updated",
            user=user,
            account=account,
        )

        AccountSecurityEvent.objects.create(
            event_type="login_attempt",
            category="security",
            severity="info",
            description="Login attempt",
            user=user,
        )

        # Filter by category
        market_events = MarketEvent.objects.filter(user=user, category="market")
        assert market_events.count() == 1

        security_events = AccountSecurityEvent.objects.filter(user=user, category="security")
        assert security_events.count() == 1

    def test_event_timestamp_ordering(self):
        """Test that events are ordered by timestamp."""
        user = UserFactory()

        # Create events at different times
        event1 = TradingEvent.objects.create(
            event_type="event1",
            severity="info",
            description="First event",
            user=user,
        )

        event2 = TradingEvent.objects.create(
            event_type="event2",
            severity="info",
            description="Second event",
            user=user,
        )

        event3 = TradingEvent.objects.create(
            event_type="event3",
            severity="info",
            description="Third event",
            user=user,
        )

        # Query events ordered by created_at (descending - newest first)
        events = TradingEvent.objects.filter(user=user).order_by("-created_at")
        event_list = list(events)

        # Verify ordering (newest first)
        assert event_list[0].id == event3.id
        assert event_list[1].id == event2.id
        assert event_list[2].id == event1.id

    def test_event_details_json_storage(self):
        """Test that event details are stored as JSON and can be queried."""
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Create event with complex details
        event = TradingEvent.objects.create(
            event_type="complex_event",
            severity="info",
            description="Event with complex details",
            user=user,
            account=account,
            details={
                "metadata": {
                    "source": "strategy_executor",
                    "version": "1.0.0",
                },
                "metrics": {
                    "execution_time_ms": 150,
                    "memory_usage_mb": 45.2,
                },
                "tags": ["production", "high-priority"],
            },
        )

        # Reload and verify JSON structure
        reloaded_event = TradingEvent.objects.get(id=event.id)
        assert reloaded_event.details["metadata"]["source"] == "strategy_executor"
        assert reloaded_event.details["metrics"]["execution_time_ms"] == 150
        assert "production" in reloaded_event.details["tags"]

    def test_event_creation_with_ip_and_user_agent(self):
        """Test that security events can store IP address and user agent."""
        user = UserFactory()

        # Create security event with IP and user agent
        event = AccountSecurityEvent.objects.create(
            event_type="login_success",
            category="security",
            severity="info",
            description="Successful login",
            user=user,
            ip_address="203.0.113.42",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        )

        # Verify IP and user agent are stored
        assert event.ip_address == "203.0.113.42"
        assert "Mozilla/5.0" in event.user_agent

    def test_multi_user_event_isolation(self):
        """Test that events are properly isolated between users."""
        # Create two users
        user1 = UserFactory()
        user2 = UserFactory()

        # Create events for each user
        TradingEvent.objects.create(
            event_type="user1_event",
            severity="info",
            description="User 1 event",
            user=user1,
        )

        TradingEvent.objects.create(
            event_type="user2_event",
            severity="info",
            description="User 2 event",
            user=user2,
        )

        # Verify each user only sees their own events
        user1_events = TradingEvent.objects.filter(user=user1)
        assert user1_events.count() == 1
        assert user1_events.first().event_type == "user1_event"  # ty:ignore[possibly-missing-attribute]

        user2_events = TradingEvent.objects.filter(user=user2)
        assert user2_events.count() == 1
        assert user2_events.first().event_type == "user2_event"  # ty:ignore[possibly-missing-attribute]
