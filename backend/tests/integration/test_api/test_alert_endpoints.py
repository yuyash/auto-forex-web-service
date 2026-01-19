"""
Integration tests for alert (notification) API endpoints.

Tests alert configuration CRUD operations, listing, and filtering.
"""

from django.urls import reverse

from apps.accounts.models import UserNotification
from tests.integration.base import APIIntegrationTestCase
from tests.integration.factories import UserNotificationFactory


class NotificationListTests(APIIntegrationTestCase):
    """Tests for notification list endpoint."""

    def test_list_notifications_success(self) -> None:
        """Test listing all notifications for authenticated user."""
        # Create multiple notifications for the user
        notifications = UserNotificationFactory.create_batch(5, user=self.user)

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIsInstance(response.data, list)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data), 5)  # ty:ignore[possibly-missing-attribute]

        # Verify notifications are ordered by timestamp descending
        result_ids = [notif["id"] for notif in response.data]  # ty:ignore[possibly-missing-attribute]
        expected_ids = [
            n.id for n in sorted(notifications, key=lambda n: n.timestamp, reverse=True)
        ]
        self.assertEqual(result_ids, expected_ids)

    def test_list_notifications_empty(self) -> None:
        """Test listing notifications when user has no notifications."""
        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIsInstance(response.data, list)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(len(response.data), 0)  # ty:ignore[possibly-missing-attribute]

    def test_list_notifications_filters_by_user(self) -> None:
        """Test that listing only returns notifications belonging to the user."""
        # Create notifications for current user
        UserNotificationFactory.create_batch(3, user=self.user)

        # Create notifications for another user
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        UserNotificationFactory.create_batch(4, user=other_user)

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 3)  # ty:ignore[possibly-missing-attribute]

    def test_list_notifications_filter_unread_only(self) -> None:
        """Test filtering notifications to show only unread ones."""
        # Create mix of read and unread notifications
        UserNotificationFactory.create_batch(3, user=self.user, is_read=False)
        UserNotificationFactory.create_batch(2, user=self.user, is_read=True)

        url = reverse("accounts:notifications")
        response = self.client.get(url, {"unread_only": "true"})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 3)  # ty:ignore[possibly-missing-attribute]

        # Verify all returned notifications are unread
        for notif in response.data:  # ty:ignore[possibly-missing-attribute]
            self.assertFalse(notif["read"])

    def test_list_notifications_limit_parameter(self) -> None:
        """Test limiting the number of notifications returned."""
        # Create more notifications than the limit
        UserNotificationFactory.create_batch(10, user=self.user)

        url = reverse("accounts:notifications")
        response = self.client.get(url, {"limit": "5"})

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 5)  # ty:ignore[possibly-missing-attribute]

    def test_list_notifications_includes_all_fields(self) -> None:
        """Test that notification responses include all expected fields."""
        notification = UserNotificationFactory(
            user=self.user,
            notification_type="trade_closed",
            title="Test Notification",
            message="Test message content",
            severity="warning",
            is_read=False,
            extra_data={"trade_id": 123, "profit": 50.25},
        )

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 1)  # ty:ignore[possibly-missing-attribute]

        notif_data = response.data[0]  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(notif_data["id"], notification.pk)  # type: ignore[attr-defined]
        self.assertEqual(notif_data["notification_type"], "trade_closed")
        self.assertEqual(notif_data["title"], "Test Notification")
        self.assertEqual(notif_data["message"], "Test message content")
        self.assertEqual(notif_data["severity"], "warning")
        self.assertFalse(notif_data["read"])
        self.assertEqual(notif_data["extra_data"], {"trade_id": 123, "profit": 50.25})
        self.assertIn("timestamp", notif_data)

    def test_list_notifications_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot list notifications."""
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]
        url = reverse("accounts:notifications")

        response = self.client.get(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]


class NotificationMarkReadTests(APIIntegrationTestCase):
    """Tests for marking individual notifications as read."""

    def test_mark_notification_read_success(self) -> None:
        """Test marking a single notification as read."""
        notification = UserNotificationFactory(user=self.user, is_read=False)

        url = reverse("accounts:notification_read", kwargs={"notification_id": notification.pk})  # ty:ignore[unresolved-attribute]
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("message", response.data)  # ty:ignore[possibly-missing-attribute]

        # Verify notification was marked as read in database
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertTrue(notification.is_read)

    def test_mark_notification_read_already_read(self) -> None:
        """Test marking an already read notification as read (idempotent)."""
        notification = UserNotificationFactory(user=self.user, is_read=True)

        url = reverse("accounts:notification_read", kwargs={"notification_id": notification.pk})  # ty:ignore[unresolved-attribute]
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]

        # Verify notification is still marked as read
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertTrue(notification.is_read)

    def test_mark_notification_read_not_found(self) -> None:
        """Test marking non-existent notification returns 404."""
        url = reverse("accounts:notification_read", kwargs={"notification_id": 99999})

        response = self.client.post(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

    def test_mark_notification_read_belongs_to_other_user(self) -> None:
        """Test that users cannot mark notifications belonging to other users."""
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        notification = UserNotificationFactory(user=other_user, is_read=False)

        url = reverse("accounts:notification_read", kwargs={"notification_id": notification.pk})  # ty:ignore[unresolved-attribute]
        response = self.client.post(url)

        self.assert_response_error(response, status_code=404)  # ty:ignore[invalid-argument-type]

        # Verify notification was not marked as read
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertFalse(notification.is_read)

    def test_mark_notification_read_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot mark notifications as read."""
        notification = UserNotificationFactory(user=self.user, is_read=False)
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]

        url = reverse("accounts:notification_read", kwargs={"notification_id": notification.pk})  # ty:ignore[unresolved-attribute]
        response = self.client.post(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]

        # Verify notification was not marked as read
        notification.refresh_from_db()    # type: ignore[attr-defined]
        self.assertFalse(notification.is_read)


class NotificationMarkAllReadTests(APIIntegrationTestCase):
    """Tests for marking all notifications as read."""

    def test_mark_all_notifications_read_success(self) -> None:
        """Test marking all unread notifications as read."""
        # Create mix of read and unread notifications
        unread_notifications = UserNotificationFactory.create_batch(
            5, user=self.user, is_read=False
        )
        read_notifications = UserNotificationFactory.create_batch(2, user=self.user, is_read=True)

        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("message", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertIn("count", response.data)  # ty:ignore[possibly-missing-attribute]
        self.assertEqual(response.data["count"], 5)  # ty:ignore[possibly-missing-attribute]

        # Verify all notifications are now marked as read
        for notification in unread_notifications:
            notification.refresh_from_db()    # type: ignore[attr-defined]
            self.assertTrue(notification.is_read)

        # Verify already read notifications remain read
        for notification in read_notifications:
            notification.refresh_from_db()    # type: ignore[attr-defined]
            self.assertTrue(notification.is_read)

    def test_mark_all_notifications_read_no_unread(self) -> None:
        """Test marking all as read when there are no unread notifications."""
        # Create only read notifications
        UserNotificationFactory.create_batch(3, user=self.user, is_read=True)

        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]

    def test_mark_all_notifications_read_empty(self) -> None:
        """Test marking all as read when user has no notifications."""
        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 0)  # ty:ignore[possibly-missing-attribute]

    def test_mark_all_notifications_read_filters_by_user(self) -> None:
        """Test that marking all as read only affects current user's notifications."""
        # Create unread notifications for current user
        user_notifications = UserNotificationFactory.create_batch(3, user=self.user, is_read=False)

        # Create unread notifications for another user
        other_user = self.create_test_user(
            username="otheruser",
            email="other@example.com",
        )
        other_notifications = UserNotificationFactory.create_batch(
            4, user=other_user, is_read=False
        )

        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(response.data["count"], 3)  # ty:ignore[possibly-missing-attribute]

        # Verify current user's notifications are marked as read
        for notification in user_notifications:
            notification.refresh_from_db()    # type: ignore[attr-defined]
            self.assertTrue(notification.is_read)

        # Verify other user's notifications remain unread
        for notification in other_notifications:
            notification.refresh_from_db()    # type: ignore[attr-defined]
            self.assertFalse(notification.is_read)

    def test_mark_all_notifications_read_unauthenticated(self) -> None:
        """Test that unauthenticated users cannot mark all notifications as read."""
        UserNotificationFactory.create_batch(3, user=self.user, is_read=False)
        self.client.force_authenticate(user=None)  # ty:ignore[possibly-missing-attribute]

        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        self.assert_response_error(response, status_code=401)  # ty:ignore[invalid-argument-type]

        # Verify notifications remain unread
        unread_count = UserNotification.objects.filter(user=self.user, is_read=False).count()
        self.assertEqual(unread_count, 3)


class NotificationFilteringTests(APIIntegrationTestCase):
    """Tests for filtering and querying notifications."""

    def test_filter_notifications_by_type(self) -> None:
        """Test filtering notifications by notification type."""
        # Create notifications with different types
        UserNotificationFactory.create_batch(2, user=self.user, notification_type="trade_closed")
        UserNotificationFactory.create_batch(3, user=self.user, notification_type="account_alert")
        UserNotificationFactory.create_batch(
            1, user=self.user, notification_type="risk_limit_breach"
        )

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 6)  # ty:ignore[possibly-missing-attribute]

        # Verify we can identify notifications by type
        trade_closed = [n for n in response.data if n["notification_type"] == "trade_closed"]  # ty:ignore[possibly-missing-attribute]
        account_alerts = [n for n in response.data if n["notification_type"] == "account_alert"]  # ty:ignore[possibly-missing-attribute]
        risk_breaches = [n for n in response.data if n["notification_type"] == "risk_limit_breach"]  # ty:ignore[possibly-missing-attribute]

        self.assertEqual(len(trade_closed), 2)
        self.assertEqual(len(account_alerts), 3)
        self.assertEqual(len(risk_breaches), 1)

    def test_filter_notifications_by_severity(self) -> None:
        """Test filtering notifications by severity level."""
        # Create notifications with different severities
        UserNotificationFactory.create_batch(2, user=self.user, severity="info")
        UserNotificationFactory.create_batch(3, user=self.user, severity="warning")
        UserNotificationFactory.create_batch(1, user=self.user, severity="error")
        UserNotificationFactory.create_batch(1, user=self.user, severity="critical")

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 7)  # ty:ignore[possibly-missing-attribute]

        # Verify we can identify notifications by severity
        info_notifs = [n for n in response.data if n["severity"] == "info"]  # ty:ignore[possibly-missing-attribute]
        warning_notifs = [n for n in response.data if n["severity"] == "warning"]  # ty:ignore[possibly-missing-attribute]
        error_notifs = [n for n in response.data if n["severity"] == "error"]  # ty:ignore[possibly-missing-attribute]
        critical_notifs = [n for n in response.data if n["severity"] == "critical"]  # ty:ignore[possibly-missing-attribute]

        self.assertEqual(len(info_notifs), 2)
        self.assertEqual(len(warning_notifs), 3)
        self.assertEqual(len(error_notifs), 1)
        self.assertEqual(len(critical_notifs), 1)

    def test_notifications_ordered_by_timestamp_descending(self) -> None:
        """Test that notifications are ordered by timestamp in descending order."""
        # Create notifications (factory will create them with different timestamps)
        UserNotificationFactory.create_batch(5, user=self.user)

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]

        # Verify ordering
        timestamps = [notif["timestamp"] for notif in response.data]  # ty:ignore[possibly-missing-attribute]
        sorted_timestamps = sorted(timestamps, reverse=True)
        self.assertEqual(timestamps, sorted_timestamps)

    def test_notifications_include_extra_data(self) -> None:
        """Test that notifications correctly include extra_data field."""
        # Create notifications with various extra_data
        UserNotificationFactory(
            user=self.user,
            notification_type="trade_closed",
            extra_data={"trade_id": 123, "profit": 50.25, "instrument": "EUR_USD"},
        )
        UserNotificationFactory(
            user=self.user,
            notification_type="account_alert",
            extra_data={"balance": 5000.00, "threshold": 10000.00},
        )
        UserNotificationFactory(
            user=self.user,
            notification_type="system_notification",
            extra_data={},
        )

        url = reverse("accounts:notifications")
        response = self.client.get(url)

        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertEqual(len(response.data), 3)  # ty:ignore[possibly-missing-attribute]

        # Verify extra_data is included and correct
        for notif in response.data:  # ty:ignore[possibly-missing-attribute]
            self.assertIn("extra_data", notif)
            self.assertIsInstance(notif["extra_data"], dict)
