"""E2E tests for /api/accounts/notifications."""

import pytest

from apps.accounts.models import UserNotification


@pytest.mark.django_db
class TestNotifications:
    def test_list_notifications(self, authenticated_client):
        resp = authenticated_client.get("/api/accounts/notifications")
        assert resp.status_code == 200
        # Validate paginated response structure
        assert "count" in resp.data
        assert "results" in resp.data
        assert "next" in resp.data
        assert "previous" in resp.data

    def test_notifications_pagination(self, authenticated_client, test_user):
        """Create 3 notifications and verify page_size=2 paginates correctly."""
        for i in range(3):
            UserNotification.objects.create(
                user=test_user,
                notification_type="system_notification",
                title=f"Pagination Test {i}",
                message=f"Message {i}",
                severity="info",
            )
        resp = authenticated_client.get("/api/accounts/notifications", {"page_size": 2})
        assert resp.status_code == 200
        assert resp.data["count"] == 3
        assert len(resp.data["results"]) == 2
        assert resp.data["next"] is not None

    def test_notifications_unread_only_filter(self, authenticated_client, test_user):
        """Verify unread_only filter excludes read notifications."""
        UserNotification.objects.create(
            user=test_user,
            notification_type="system_notification",
            title="Unread Notif",
            message="I am unread",
            severity="info",
            is_read=False,
        )
        UserNotification.objects.create(
            user=test_user,
            notification_type="system_notification",
            title="Read Notif",
            message="I am read",
            severity="info",
            is_read=True,
        )
        resp = authenticated_client.get("/api/accounts/notifications", {"unread_only": "true"})
        assert resp.status_code == 200
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["title"] == "Unread Notif"

    def test_notification_result_structure(self, authenticated_client, test_user):
        """Verify each notification item has the expected fields."""
        UserNotification.objects.create(
            user=test_user,
            notification_type="system_notification",
            title="Structure Test",
            message="Check fields",
            severity="warning",
        )
        resp = authenticated_client.get("/api/accounts/notifications")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1
        item = resp.data["results"][0]
        assert "id" in item
        assert "title" in item
        assert "message" in item
        assert "severity" in item
        assert "timestamp" in item
        assert "read" in item
        assert "notification_type" in item

    def test_mark_notification_read(self, authenticated_client, test_user):
        notif = UserNotification.objects.create(
            user=test_user,
            notification_type="system_notification",
            title="Test",
            message="Hello",
            severity="info",
        )
        resp = authenticated_client.post(f"/api/accounts/notifications/{notif.id}/read")
        assert resp.status_code == 200

    def test_mark_all_read(self, authenticated_client, test_user):
        UserNotification.objects.create(
            user=test_user,
            notification_type="system_notification",
            title="Test",
            message="Hello",
            severity="info",
        )
        resp = authenticated_client.post("/api/accounts/notifications/read-all")
        assert resp.status_code == 200

    def test_notifications_unauthenticated(self, api_client):
        resp = api_client.get("/api/accounts/notifications")
        assert resp.status_code == 401
