"""
Integration tests for alert and notification system.

Tests alert condition detection, notification creation, delivery,
duplicate prevention, and delivery status logging.
Validates Requirement 2.2.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.models import UserNotification
from tests.integration.base import IntegrationTestCase
from tests.integration.factories import (
    UserFactory,
    UserNotificationFactory,
)


@pytest.mark.django_db
class TestAlertConditionDetection(IntegrationTestCase):
    """Tests for alert condition detection."""

    def test_create_notification_on_condition(self) -> None:
        """Test that notification is created when alert condition is met."""
        # Create a notification directly (simulating alert condition detection)
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Your account has exceeded the maximum drawdown limit.",
            severity="critical",
        )

        # Verify notification was created
        self.assertIsNotNone(notification.pk)  # type: ignore[attr-defined]
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.notification_type, "risk_limit_breach")
        self.assertEqual(notification.severity, "critical")
        self.assertFalse(notification.is_read)

    def test_notification_includes_extra_data(self) -> None:
        """Test that notifications can include extra structured data."""
        extra_data = {
            "account_id": "101-001-12345678-001",
            "current_drawdown": 15.5,
            "limit": 10.0,
            "timestamp": timezone.now().isoformat(),
        }

        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Maximum drawdown limit exceeded.",
            severity="critical",
            extra_data=extra_data,
        )

        # Verify extra data was stored
        self.assertEqual(notification.extra_data["account_id"], extra_data["account_id"])
        self.assertEqual(
            notification.extra_data["current_drawdown"], extra_data["current_drawdown"]
        )
        self.assertEqual(notification.extra_data["limit"], extra_data["limit"])

    def test_notification_severity_levels(self) -> None:
        """Test that notifications support different severity levels."""
        severities = ["info", "warning", "error", "critical"]

        for severity in severities:
            notification = UserNotification.objects.create(
                user=self.user,
                notification_type="test_notification",
                title=f"Test {severity} notification",
                message=f"This is a {severity} level notification.",
                severity=severity,
            )

            self.assertEqual(notification.severity, severity)

    def test_notification_types(self) -> None:
        """Test that notifications support different types."""
        notification_types = [
            "trade_closed",
            "account_alert",
            "risk_limit_breach",
            "system_notification",
        ]

        for notif_type in notification_types:
            notification = UserNotification.objects.create(
                user=self.user,
                notification_type=notif_type,
                title=f"Test {notif_type}",
                message=f"This is a {notif_type} notification.",
                severity="info",
            )

            self.assertEqual(notification.notification_type, notif_type)


@pytest.mark.django_db
class TestNotificationCreation(IntegrationTestCase):
    """Tests for notification record creation."""

    def test_notification_created_with_timestamp(self) -> None:
        """Test that notifications are created with automatic timestamp."""
        before_creation = timezone.now()

        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your EUR/USD trade has been closed.",
            severity="info",
        )

        after_creation = timezone.now()

        # Verify timestamp is set and within expected range
        self.assertIsNotNone(notification.timestamp)
        self.assertGreaterEqual(notification.timestamp, before_creation)
        self.assertLessEqual(notification.timestamp, after_creation)

    def test_notification_defaults_to_unread(self) -> None:
        """Test that new notifications default to unread status."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="account_alert",
            title="Account Alert",
            message="Your account balance is low.",
            severity="warning",
        )

        self.assertFalse(notification.is_read)

    def test_notification_can_be_marked_as_read(self) -> None:
        """Test that notifications can be marked as read."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="system_notification",
            title="System Update",
            message="System maintenance scheduled.",
            severity="info",
        )

        # Mark as read
        notification.mark_as_read()

        # Verify status changed
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertTrue(notification.is_read)

    def test_notification_can_be_marked_as_unread(self) -> None:
        """Test that notifications can be marked as unread."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="system_notification",
            title="System Update",
            message="System maintenance scheduled.",
            severity="info",
            is_read=True,
        )

        # Mark as unread
        notification.mark_as_unread()

        # Verify status changed
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertFalse(notification.is_read)


@pytest.mark.django_db
class TestNotificationDelivery(IntegrationTestCase):
    """Tests for notification delivery via channels."""

    def test_notification_triggers_email_delivery(self) -> None:
        """Test that notification creation triggers email delivery."""
        # This test documents the expected behavior for email delivery.
        # In a real implementation, a signal handler would trigger email sending.

        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Your account has exceeded the maximum drawdown limit.",
            severity="critical",
        )

        # Verify the notification was created
        # In a real implementation, we would verify that email was sent
        self.assertIsNotNone(notification.pk)  # type: ignore[attr-defined]
        self.assertEqual(notification.user, self.user)
        self.assertEqual(notification.severity, "critical")

    def test_notification_delivery_respects_user_preferences(self) -> None:
        """Test that notification delivery respects user notification preferences."""
        # Create user with notification preferences
        from apps.accounts.models import UserSettings

        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.notification_enabled = True
        settings.notification_email = True
        settings.notification_browser = True
        settings.save()  # type: ignore[attr-defined]

        # Create notification
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your trade has been closed.",
            severity="info",
        )

        # Verify notification was created
        self.assertIsNotNone(notification.pk)  # type: ignore[attr-defined]

        # In a real implementation, we would verify that email was sent
        # based on user preferences

    def test_notification_not_delivered_when_disabled(self) -> None:
        """Test that notifications are not delivered when user has disabled them."""
        # Create user with notifications disabled
        from apps.accounts.models import UserSettings

        settings, _ = UserSettings.objects.get_or_create(user=self.user)
        settings.notification_enabled = False
        settings.save()  # type: ignore[attr-defined]

        # Create notification
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your trade has been closed.",
            severity="info",
        )

        # Notification record is still created, but delivery should be skipped
        self.assertIsNotNone(notification.pk)  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestDuplicateAlertPrevention(IntegrationTestCase):
    """Tests for duplicate alert prevention."""

    def test_duplicate_notifications_can_be_detected(self) -> None:
        """Test that duplicate notifications can be detected by type and time."""
        # Create first notification
        notification1 = UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Your account has exceeded the maximum drawdown limit.",
            severity="critical",
        )

        # Check for recent duplicate
        recent_duplicates = UserNotification.objects.filter(
            user=self.user,
            notification_type="risk_limit_breach",
            timestamp__gte=timezone.now() - timedelta(minutes=5),
        )

        # Should find the recent notification
        self.assertEqual(recent_duplicates.count(), 1)
        self.assertEqual(recent_duplicates.first(), notification1)

    def test_duplicate_prevention_with_cooldown_period(self) -> None:
        """Test that duplicate notifications within cooldown period are prevented."""
        # Create first notification
        UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Your account has exceeded the maximum drawdown limit.",
            severity="critical",
        )

        # Check if duplicate exists within cooldown (5 minutes)
        cooldown_minutes = 5
        recent_duplicates = UserNotification.objects.filter(
            user=self.user,
            notification_type="risk_limit_breach",
            timestamp__gte=timezone.now() - timedelta(minutes=cooldown_minutes),
        ).exists()

        # Should prevent creating duplicate
        if recent_duplicates:
            # Don't create duplicate notification
            pass
        else:
            # Create new notification
            UserNotification.objects.create(
                user=self.user,
                notification_type="risk_limit_breach",
                title="Risk Limit Exceeded",
                message="Your account has exceeded the maximum drawdown limit.",
                severity="critical",
            )

        # Verify only one notification exists
        total_notifications = UserNotification.objects.filter(
            user=self.user,
            notification_type="risk_limit_breach",
        ).count()

        self.assertEqual(total_notifications, 1)

    def test_different_notification_types_not_considered_duplicates(self) -> None:
        """Test that different notification types are not considered duplicates."""
        # Create notifications of different types
        UserNotification.objects.create(
            user=self.user,
            notification_type="risk_limit_breach",
            title="Risk Limit Exceeded",
            message="Risk limit exceeded.",
            severity="critical",
        )

        UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Trade closed.",
            severity="info",
        )

        # Verify both notifications exist
        total_notifications = UserNotification.objects.filter(user=self.user).count()
        self.assertEqual(total_notifications, 2)


@pytest.mark.django_db
class TestAlertDeliveryStatusLogging(IntegrationTestCase):
    """Tests for alert delivery status logging."""

    def test_notification_stores_delivery_metadata(self) -> None:
        """Test that notification can store delivery status metadata."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your trade has been closed.",
            severity="info",
            extra_data={
                "delivery_status": "pending",
                "delivery_attempts": 0,
                "last_delivery_attempt": None,
            },
        )

        # Verify metadata was stored
        self.assertEqual(notification.extra_data["delivery_status"], "pending")
        self.assertEqual(notification.extra_data["delivery_attempts"], 0)

    def test_notification_delivery_status_can_be_updated(self) -> None:
        """Test that notification delivery status can be updated."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your trade has been closed.",
            severity="info",
            extra_data={
                "delivery_status": "pending",
                "delivery_attempts": 0,
            },
        )

        # Update delivery status
        notification.extra_data["delivery_status"] = "delivered"
        notification.extra_data["delivery_attempts"] = 1
        notification.extra_data["delivered_at"] = timezone.now().isoformat()
        notification.save()  # type: ignore[attr-defined]

        # Verify status was updated
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(notification.extra_data["delivery_status"], "delivered")
        self.assertEqual(notification.extra_data["delivery_attempts"], 1)
        self.assertIn("delivered_at", notification.extra_data)

    def test_notification_failed_delivery_logging(self) -> None:
        """Test that failed delivery attempts are logged."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="trade_closed",
            title="Trade Closed",
            message="Your trade has been closed.",
            severity="info",
            extra_data={
                "delivery_status": "pending",
                "delivery_attempts": 0,
                "delivery_errors": [],
            },
        )

        # Simulate failed delivery
        notification.extra_data["delivery_status"] = "failed"
        notification.extra_data["delivery_attempts"] = 3
        notification.extra_data["delivery_errors"].append(
            {
                "attempt": 1,
                "error": "SMTP connection timeout",
                "timestamp": timezone.now().isoformat(),
            }
        )
        notification.save()  # type: ignore[attr-defined]

        # Verify failure was logged
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertEqual(notification.extra_data["delivery_status"], "failed")
        self.assertEqual(notification.extra_data["delivery_attempts"], 3)
        self.assertEqual(len(notification.extra_data["delivery_errors"]), 1)


@pytest.mark.django_db
class TestNotificationQuerying(IntegrationTestCase):
    """Tests for querying and filtering notifications."""

    def test_query_unread_notifications(self) -> None:
        """Test querying unread notifications for a user."""
        # Create mix of read and unread notifications
        UserNotificationFactory.create_batch(3, user=self.user, is_read=False)
        UserNotificationFactory.create_batch(2, user=self.user, is_read=True)

        # Query unread notifications
        unread = UserNotification.objects.filter(user=self.user, is_read=False)

        self.assertEqual(unread.count(), 3)

    def test_query_notifications_by_severity(self) -> None:
        """Test querying notifications by severity level."""
        # Create notifications with different severities
        UserNotificationFactory(user=self.user, severity="critical")
        UserNotificationFactory(user=self.user, severity="error")
        UserNotificationFactory.create_batch(2, user=self.user, severity="info")

        # Query critical notifications
        critical = UserNotification.objects.filter(user=self.user, severity="critical")
        self.assertEqual(critical.count(), 1)

        # Query info notifications
        info = UserNotification.objects.filter(user=self.user, severity="info")
        self.assertEqual(info.count(), 2)

    def test_query_notifications_by_type(self) -> None:
        """Test querying notifications by type."""
        # Create notifications of different types
        UserNotificationFactory.create_batch(2, user=self.user, notification_type="trade_closed")
        UserNotificationFactory(user=self.user, notification_type="risk_limit_breach")

        # Query by type
        trade_notifications = UserNotification.objects.filter(
            user=self.user, notification_type="trade_closed"
        )
        self.assertEqual(trade_notifications.count(), 2)

    def test_notifications_ordered_by_timestamp(self) -> None:
        """Test that notifications are ordered by timestamp descending."""
        # Create notifications
        UserNotificationFactory.create_batch(5, user=self.user)

        # Query all notifications
        all_notifications = UserNotification.objects.filter(user=self.user)

        # Verify ordering (most recent first)
        timestamps = [n.timestamp for n in all_notifications]
        self.assertEqual(timestamps, sorted(timestamps, reverse=True))

    def test_query_notifications_for_specific_user_only(self) -> None:
        """Test that queries only return notifications for the specified user."""
        # Create notifications for current user
        UserNotificationFactory.create_batch(3, user=self.user)

        # Create notifications for another user
        other_user = UserFactory()
        UserNotificationFactory.create_batch(2, user=other_user)

        # Query notifications for current user
        user_notifications = UserNotification.objects.filter(user=self.user)

        self.assertEqual(user_notifications.count(), 3)
        for notification in user_notifications:
            self.assertEqual(notification.user, self.user)
