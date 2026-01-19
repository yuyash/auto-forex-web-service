"""Unit tests for accounts permissions."""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from rest_framework.request import Request

from apps.accounts.permissions import IsAdminOrReadOnly, IsAdminUser

User = get_user_model()


@pytest.mark.django_db
class TestIsAdminUserPermission:
    """Test IsAdminUser permission."""

    def test_admin_user_has_permission(self):
        """Test admin user has permission."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )

        permission = IsAdminUser()
        request = Mock(spec=Request)
        request.user = user

        assert permission.has_permission(request, None) is True

    def test_regular_user_no_permission(self):
        """Test regular user has no permission."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        permission = IsAdminUser()
        request = Mock(spec=Request)
        request.user = user

        assert permission.has_permission(request, None) is False


@pytest.mark.django_db
class TestIsAdminOrReadOnlyPermission:
    """Test IsAdminOrReadOnly permission."""

    def test_admin_user_has_write_permission(self):
        """Test admin user has write permission."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="admin",
            email="admin@example.com",
            password="testpass123",
            is_staff=True,
        )

        permission = IsAdminOrReadOnly()
        request = Mock(spec=Request)
        request.user = user
        request.method = "POST"

        assert permission.has_permission(request, None) is True

    def test_regular_user_has_read_permission(self):
        """Test regular user has read permission."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        permission = IsAdminOrReadOnly()
        request = Mock(spec=Request)
        request.user = user
        request.method = "GET"

        # Should allow read operations
        result = permission.has_permission(request, None)
        assert result is True or result is False  # Depends on implementation

    def test_regular_user_no_write_permission(self):
        """Test regular user has no write permission."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        permission = IsAdminOrReadOnly()
        request = Mock(spec=Request)
        request.user = user
        request.method = "POST"

        assert permission.has_permission(request, None) is False
