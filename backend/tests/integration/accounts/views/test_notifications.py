"""Integration tests for notification views (with database)."""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User, UserNotification


@pytest.mark.django_db
class TestUserNotificationListViewIntegration:
    """Integration tests for UserNotificationListView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

    def test_list_notifications(self) -> None:
        """Test listing user notifications."""
        UserNotification.objects.create(
            user=self.user,
            notification_type="test",
            title="Test Notification",
            message="Test message",
            severity="info",
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notifications")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Test Notification"

    def test_list_notifications_with_limit(self) -> None:
        """Test listing notifications with limit parameter."""
        for i in range(5):
            UserNotification.objects.create(
                user=self.user,
                notification_type="test",
                title=f"Notification {i}",
                message="Test",
                severity="info",
            )

        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notifications")
        response = self.client.get(url, {"page_size": 3})

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 3

    def test_list_notifications_unread_only(self) -> None:
        """Test listing only unread notifications."""
        UserNotification.objects.create(
            user=self.user,
            notification_type="test",
            title="Unread",
            message="Test",
            severity="info",
            is_read=False,
        )
        UserNotification.objects.create(
            user=self.user,
            notification_type="test",
            title="Read",
            message="Test",
            severity="info",
            is_read=True,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notifications")
        response = self.client.get(url, {"unread_only": "true"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Unread"


@pytest.mark.django_db
class TestUserNotificationMarkReadViewIntegration:
    """Integration tests for UserNotificationMarkReadView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

    def test_mark_notification_as_read(self) -> None:
        """Test marking a notification as read."""
        notification = UserNotification.objects.create(
            user=self.user,
            notification_type="test",
            title="Test",
            message="Test",
            severity="info",
            is_read=False,
        )

        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notification_read", kwargs={"notification_id": notification.id})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        notification.refresh_from_db()
        assert notification.is_read is True

    def test_mark_nonexistent_notification(self) -> None:
        """Test marking nonexistent notification."""
        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notification_read", kwargs={"notification_id": 99999})
        response = self.client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestUserNotificationMarkAllReadViewIntegration:
    """Integration tests for UserNotificationMarkAllReadView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="TestPass123!",
        )

    def test_mark_all_notifications_as_read(self) -> None:
        """Test marking all notifications as read."""
        for i in range(3):
            UserNotification.objects.create(
                user=self.user,
                notification_type="test",
                title=f"Test {i}",
                message="Test",
                severity="info",
                is_read=False,
            )

        self.client.force_authenticate(user=self.user)
        url = reverse("accounts:notifications_read_all")
        response = self.client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3

        unread_count = UserNotification.objects.filter(user=self.user, is_read=False).count()
        assert unread_count == 0
