"""
Unit tests for event logging models.

Tests cover:
- Event model field validation
- Event model indexes
- Notification model creation
- Event category and severity choices

Requirements: 24.1, 24.5, 27.1
"""

import pytest

from accounts.models import OandaAccount, User
from trading.event_models import Event, Notification


@pytest.mark.django_db
class TestEventModel:
    """Test Event model functionality."""

    def test_event_creation_with_all_fields(self) -> None:
        """Test creating an event with all fields populated."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        event = Event.objects.create(
            category="trading",
            event_type="order_submitted",
            severity="info",
            user=user,
            account=account,
            description="Market order submitted for EUR_USD",
            details={
                "order_id": "ORDER-001",
                "instrument": "EUR_USD",
                "units": 10000,
                "direction": "long",
            },
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert event.category == "trading"
        assert event.event_type == "order_submitted"
        assert event.severity == "info"
        assert event.user == user
        assert event.account == account
        assert event.description == "Market order submitted for EUR_USD"
        assert event.details["order_id"] == "ORDER-001"
        assert event.ip_address == "192.168.1.100"
        assert event.user_agent == "Mozilla/5.0"
        assert event.timestamp is not None

    def test_event_category_choices(self) -> None:
        """Test event category choices validation."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        # Test all valid categories
        categories = ["trading", "system", "security", "admin"]
        for category in categories:
            event = Event.objects.create(
                category=category,
                event_type="test_event",
                severity="info",
                user=user,
                description=f"Test {category} event",
            )
            assert event.category == category

    def test_event_severity_choices(self) -> None:
        """Test event severity choices validation."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        # Test all valid severity levels
        severities = ["debug", "info", "warning", "error", "critical"]
        for severity in severities:
            event = Event.objects.create(
                category="system",
                event_type="test_event",
                severity=severity,
                user=user,
                description=f"Test {severity} event",
            )
            assert event.severity == severity

    def test_event_indexes_exist(self) -> None:
        """Test that required indexes are created on Event model."""
        # Verify indexes are defined in model Meta
        indexes = Event._meta.indexes

        # Check that we have the expected number of indexes
        assert len(indexes) >= 5

        # Verify index field combinations
        index_fields = [tuple(idx.fields) for idx in indexes]

        # Check for required index field combinations
        assert ("timestamp", "category") in index_fields
        assert ("timestamp", "severity") in index_fields
        assert ("user", "timestamp") in index_fields
        assert ("category", "event_type") in index_fields
        assert ("severity", "timestamp") in index_fields

    def test_event_without_user_or_account(self) -> None:
        """Test creating an event without user or account (system events)."""
        event = Event.objects.create(
            category="system",
            event_type="database_connection",
            severity="info",
            description="Database connection established",
            details={"database": "postgres", "host": "localhost"},
        )

        assert event.user is None
        assert event.account is None
        assert event.category == "system"

    def test_event_log_trading_event_classmethod(self) -> None:
        """Test log_trading_event class method."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        event = Event.log_trading_event(
            event_type="position_opened",
            description="Long position opened on EUR_USD",
            severity="info",
            user=user,
            account=account,
            details={"position_id": "POS-001", "units": 10000},
        )

        assert event.category == "trading"
        assert event.event_type == "position_opened"
        assert event.severity == "info"
        assert event.user == user
        assert event.account == account
        assert event.details["position_id"] == "POS-001"

    def test_event_log_system_event_classmethod(self) -> None:
        """Test log_system_event class method."""
        event = Event.log_system_event(
            event_type="celery_worker_started",
            description="Celery worker started successfully",
            severity="info",
            details={"worker_id": "worker-1", "queue": "default"},
        )

        assert event.category == "system"
        assert event.event_type == "celery_worker_started"
        assert event.severity == "info"
        assert event.user is None
        assert event.details["worker_id"] == "worker-1"

    def test_event_log_security_event_classmethod(self) -> None:
        """Test log_security_event class method."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        event = Event.log_security_event(
            event_type="failed_login",
            description="Failed login attempt",
            severity="warning",
            user=user,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
            details={"attempt_count": 3},
        )

        assert event.category == "security"
        assert event.event_type == "failed_login"
        assert event.severity == "warning"
        assert event.user == user
        assert event.ip_address == "192.168.1.100"
        assert event.user_agent == "Mozilla/5.0"

    def test_event_log_admin_event_classmethod(self) -> None:
        """Test log_admin_event class method."""
        admin_user = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            password="adminpass123",
            is_staff=True,
        )

        event = Event.log_admin_event(
            event_type="user_kicked_off",
            description="User kicked off by admin",
            severity="warning",
            user=admin_user,
            details={"target_user": "testuser", "reason": "security"},
        )

        assert event.category == "admin"
        assert event.event_type == "user_kicked_off"
        assert event.severity == "warning"
        assert event.user == admin_user
        assert event.details["target_user"] == "testuser"

    def test_event_ordering(self) -> None:
        """Test that events are ordered by timestamp descending."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        # Create multiple events
        event1 = Event.objects.create(
            category="system",
            event_type="test_event_1",
            severity="info",
            user=user,
            description="First event",
        )

        event2 = Event.objects.create(
            category="system",
            event_type="test_event_2",
            severity="info",
            user=user,
            description="Second event",
        )

        event3 = Event.objects.create(
            category="system",
            event_type="test_event_3",
            severity="info",
            user=user,
            description="Third event",
        )

        # Query all events
        events = list(Event.objects.all())

        # Most recent should be first
        assert events[0].id == event3.id
        assert events[1].id == event2.id
        assert events[2].id == event1.id

    def test_event_str_representation(self) -> None:
        """Test Event string representation."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        event = Event.objects.create(
            category="trading",
            event_type="order_submitted",
            severity="info",
            user=user,
            description="Test event",
        )

        str_repr = str(event)
        assert "INFO" in str_repr
        assert "trading" in str_repr
        assert "order_submitted" in str_repr


@pytest.mark.django_db
class TestNotificationModel:
    """Test Notification model functionality."""

    def test_notification_creation(self) -> None:
        """Test creating a notification."""
        notification = Notification.objects.create(
            notification_type="margin_warning",
            title="Margin Warning",
            message="Margin-liquidation ratio reached 100%",
            severity="critical",
        )

        assert notification.notification_type == "margin_warning"
        assert notification.title == "Margin Warning"
        assert notification.message == "Margin-liquidation ratio reached 100%"
        assert notification.severity == "critical"
        assert notification.is_read is False
        assert notification.timestamp is not None

    def test_notification_severity_choices(self) -> None:
        """Test notification severity choices validation."""
        severities = ["info", "warning", "error", "critical"]
        for severity in severities:
            notification = Notification.objects.create(
                notification_type="test_notification",
                title=f"Test {severity}",
                message=f"Test {severity} notification",
                severity=severity,
            )
            assert notification.severity == severity

    def test_notification_with_related_event(self) -> None:
        """Test creating a notification with a related event."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )

        event = Event.objects.create(
            category="system",
            event_type="connection_failure",
            severity="error",
            user=user,
            description="Failed to connect to OANDA API",
        )

        notification = Notification.objects.create(
            notification_type="connection_failure",
            title="Connection Failure",
            message="Failed to connect to OANDA API",
            severity="error",
            related_event=event,
        )

        assert notification.related_event == event
        assert notification.related_event.event_type == "connection_failure"

    def test_notification_mark_as_read(self) -> None:
        """Test marking a notification as read."""
        notification = Notification.objects.create(
            notification_type="test_notification",
            title="Test Notification",
            message="Test message",
            severity="info",
        )

        assert notification.is_read is False

        notification.mark_as_read()

        notification.refresh_from_db()
        assert notification.is_read is True

    def test_notification_mark_as_unread(self) -> None:
        """Test marking a notification as unread."""
        notification = Notification.objects.create(
            notification_type="test_notification",
            title="Test Notification",
            message="Test message",
            severity="info",
            is_read=True,
        )

        assert notification.is_read is True

        notification.mark_as_unread()

        notification.refresh_from_db()
        assert notification.is_read is False

    def test_notification_create_margin_warning_classmethod(self) -> None:
        """Test create_margin_warning class method."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        notification = Notification.create_margin_warning(
            account=account,
            ratio=1.05,
        )

        assert notification.notification_type == "margin_warning"
        assert "Margin Warning" in notification.title
        assert account.account_id in notification.title
        # Check for percentage format (105.00% or 105%)
        assert "105" in notification.message
        assert "%" in notification.message
        assert notification.severity == "critical"

    def test_notification_create_connection_failure_classmethod(self) -> None:
        """Test create_connection_failure class method."""
        user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        account = OandaAccount.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )
        account.set_api_token("test_token_12345")
        account.save()

        notification = Notification.create_connection_failure(
            account=account,
            error_message="Connection timeout",
        )

        assert notification.notification_type == "connection_failure"
        assert "Connection Failure" in notification.title
        assert account.account_id in notification.title
        assert "Connection timeout" in notification.message
        assert notification.severity == "error"

    def test_notification_create_system_health_alert_classmethod(self) -> None:
        """Test create_system_health_alert class method."""
        notification = Notification.create_system_health_alert(
            title="High CPU Usage",
            message="CPU usage exceeded 90%",
            severity="warning",
        )

        assert notification.notification_type == "system_health"
        assert notification.title == "High CPU Usage"
        assert notification.message == "CPU usage exceeded 90%"
        assert notification.severity == "warning"

    def test_notification_indexes_exist(self) -> None:
        """Test that required indexes are created on Notification model."""
        # Verify indexes are defined in model Meta
        indexes = Notification._meta.indexes

        # Check that we have the expected number of indexes
        assert len(indexes) >= 3

        # Verify index field combinations
        index_fields = [tuple(idx.fields) for idx in indexes]

        # Check for required index field combinations
        assert ("timestamp", "is_read") in index_fields
        assert ("severity", "is_read") in index_fields
        assert ("notification_type",) in index_fields

    def test_notification_ordering(self) -> None:
        """Test that notifications are ordered by timestamp descending."""
        # Create multiple notifications
        notif1 = Notification.objects.create(
            notification_type="test",
            title="First",
            message="First notification",
            severity="info",
        )

        notif2 = Notification.objects.create(
            notification_type="test",
            title="Second",
            message="Second notification",
            severity="info",
        )

        notif3 = Notification.objects.create(
            notification_type="test",
            title="Third",
            message="Third notification",
            severity="info",
        )

        # Query all notifications
        notifications = list(Notification.objects.all())

        # Most recent should be first
        assert notifications[0].id == notif3.id
        assert notifications[1].id == notif2.id
        assert notifications[2].id == notif1.id

    def test_notification_str_representation(self) -> None:
        """Test Notification string representation."""
        notification = Notification.objects.create(
            notification_type="test_notification",
            title="Test Notification",
            message="Test message",
            severity="warning",
        )

        str_repr = str(notification)
        assert "WARNING" in str_repr
        assert "Test Notification" in str_repr
        assert "Unread" in str_repr

        notification.mark_as_read()
        str_repr = str(notification)
        assert "Read" in str_repr
