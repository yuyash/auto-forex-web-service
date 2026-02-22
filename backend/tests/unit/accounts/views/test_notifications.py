"""Unit tests for notification views (mocked dependencies)."""

from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.notifications import (
    UserNotificationListView,
    UserNotificationMarkAllReadView,
    UserNotificationMarkReadView,
)


class TestUserNotificationListView:
    """Unit tests for UserNotificationListView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_get_unauthenticated(self) -> None:
        """Test GET request without user ID."""
        request = self.factory.get("/api/notifications")
        request.user = MagicMock()
        request.user.id = None
        view = UserNotificationListView()

        response = view.get(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_classes(self) -> None:
        """Test view has IsAuthenticated permission."""
        from rest_framework.permissions import IsAuthenticated

        view = UserNotificationListView()
        assert view.permission_classes == [IsAuthenticated]


class TestUserNotificationMarkReadView:
    """Unit tests for UserNotificationMarkReadView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_post_unauthenticated(self) -> None:
        """Test POST request without user ID."""
        request = self.factory.post("/api/notifications/1/read")
        request.user = MagicMock()
        request.user.id = None
        view = UserNotificationMarkReadView()

        response = view.post(request, notification_id=1)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_classes(self) -> None:
        """Test view has IsAuthenticated permission."""
        from rest_framework.permissions import IsAuthenticated

        view = UserNotificationMarkReadView()
        assert view.permission_classes == [IsAuthenticated]


class TestUserNotificationMarkAllReadView:
    """Unit tests for UserNotificationMarkAllReadView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_post_unauthenticated(self) -> None:
        """Test POST request without user ID."""
        request = self.factory.post("/api/notifications/read-all")
        request.user = MagicMock()
        request.user.id = None
        view = UserNotificationMarkAllReadView()

        response = view.post(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_classes(self) -> None:
        """Test view has IsAuthenticated permission."""
        from rest_framework.permissions import IsAuthenticated

        view = UserNotificationMarkAllReadView()
        assert view.permission_classes == [IsAuthenticated]
