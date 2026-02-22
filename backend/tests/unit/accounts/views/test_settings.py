"""Unit tests for settings views (mocked dependencies)."""

from unittest.mock import MagicMock

from rest_framework import status
from rest_framework.test import APIRequestFactory

from apps.accounts.views.settings import PublicAccountSettingsView, UserSettingsView


class TestUserSettingsView:
    """Unit tests for UserSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_get_unauthenticated(self) -> None:
        """Test GET request without authentication."""
        request = self.factory.get("/api/settings")
        request.user = MagicMock()
        request.user.is_authenticated = False
        view = UserSettingsView()

        response = view.get(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_put_unauthenticated(self) -> None:
        """Test PUT request without authentication."""
        request = self.factory.put("/api/settings", {}, format="json")
        request.user = MagicMock()
        request.user.is_authenticated = False
        view = UserSettingsView()

        response = view.put(request)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_permission_classes(self) -> None:
        """Test view has IsAuthenticated permission."""
        from rest_framework.permissions import IsAuthenticated

        view = UserSettingsView()
        assert view.permission_classes == [IsAuthenticated]


class TestPublicAccountSettingsView:
    """Unit tests for PublicAccountSettingsView."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

    def test_permission_classes(self) -> None:
        """Test view has AllowAny permission."""
        from rest_framework.permissions import AllowAny

        view = PublicAccountSettingsView()
        assert view.permission_classes == [AllowAny]
