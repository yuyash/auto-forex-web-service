"""Integration tests for user notification endpoints.

Covers:
- GET  /api/accounts/notifications
- POST /api/accounts/notifications/<id>/read
- POST /api/accounts/notifications/read-all
"""

import pytest
import requests


@pytest.fixture
def user_notification(db, test_user):
    from apps.accounts.models import UserNotification

    return UserNotification.objects.create(
        user=test_user,
        notification_type="account_alert",
        title="Test notification",
        message="Hello",
        severity="info",
        is_read=False,
        extra_data={"k": "v"},
    )


@pytest.mark.django_db(transaction=True)
class TestUserNotificationsList:
    def test_list_requires_auth(self, live_server):
        url = f"{live_server.url}/api/accounts/notifications"
        response = requests.get(url, timeout=10)
        assert response.status_code == 401

    def test_list_returns_notifications(self, live_server, auth_headers, user_notification):
        url = f"{live_server.url}/api/accounts/notifications"
        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        first = data[0]
        assert "id" in first
        assert "title" in first
        assert "message" in first
        assert "severity" in first
        assert "timestamp" in first
        assert "read" in first
        assert "notification_type" in first
        assert "extra_data" in first

    def test_list_unread_only_filters(self, live_server, auth_headers, test_user):
        from apps.accounts.models import UserNotification

        UserNotification.objects.create(
            user=test_user,
            notification_type="account_alert",
            title="Unread",
            message="U",
            severity="info",
            is_read=False,
        )
        UserNotification.objects.create(
            user=test_user,
            notification_type="account_alert",
            title="Read",
            message="R",
            severity="info",
            is_read=True,
        )

        url = f"{live_server.url}/api/accounts/notifications?unread_only=true"
        response = requests.get(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert all(item["read"] is False for item in data)


@pytest.mark.django_db(transaction=True)
class TestUserNotificationsMarkRead:
    def test_mark_read_sets_flag(self, live_server, auth_headers, user_notification):
        url = f"{live_server.url}/api/accounts/notifications/{user_notification.id}/read"
        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        assert "message" in response.json()

        user_notification.refresh_from_db()
        assert user_notification.is_read is True

    def test_mark_read_not_found(self, live_server, auth_headers):
        url = f"{live_server.url}/api/accounts/notifications/999999/read"
        response = requests.post(url, headers=auth_headers, timeout=10)
        assert response.status_code == 404

    def test_mark_read_cannot_access_other_users_notification(self, live_server, auth_headers, db):
        from django.contrib.auth import get_user_model

        from apps.accounts.models import UserNotification

        User = get_user_model()
        other_user = User.objects.create_user(  # type: ignore[attr-defined]
            username="other",
            email="other@example.com",
            password="TestPass123!",
        )

        other_notification = UserNotification.objects.create(
            user=other_user,
            notification_type="account_alert",
            title="Other",
            message="Other",
            severity="info",
            is_read=False,
        )

        url = f"{live_server.url}/api/accounts/notifications/{other_notification.id}/read"
        response = requests.post(url, headers=auth_headers, timeout=10)
        assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
class TestUserNotificationsMarkAllRead:
    def test_mark_all_read_marks_only_unread_and_returns_count(
        self, live_server, auth_headers, test_user
    ):
        from apps.accounts.models import UserNotification

        UserNotification.objects.create(
            user=test_user,
            notification_type="account_alert",
            title="Unread1",
            message="U1",
            severity="info",
            is_read=False,
        )
        UserNotification.objects.create(
            user=test_user,
            notification_type="account_alert",
            title="Unread2",
            message="U2",
            severity="info",
            is_read=False,
        )
        UserNotification.objects.create(
            user=test_user,
            notification_type="account_alert",
            title="Read",
            message="R",
            severity="info",
            is_read=True,
        )

        url = f"{live_server.url}/api/accounts/notifications/read-all"
        response = requests.post(url, headers=auth_headers, timeout=10)

        assert response.status_code == 200
        data = response.json()
        assert "count" in data
        assert data["count"] >= 2

        assert UserNotification.objects.filter(user=test_user, is_read=False).count() == 0

    def test_mark_all_read_requires_auth(self, live_server):
        url = f"{live_server.url}/api/accounts/notifications/read-all"
        response = requests.post(url, timeout=10)
        assert response.status_code == 401
