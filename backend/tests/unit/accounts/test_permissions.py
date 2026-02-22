"""Unit tests for permissions.py."""

from unittest.mock import MagicMock

from apps.accounts.permissions import IsAdminOrReadOnly, IsAdminUser


class TestIsAdminUser:
    """Unit tests for IsAdminUser permission."""

    def test_has_permission_admin_user(self) -> None:
        """Test permission allows admin user."""
        permission = IsAdminUser()
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.is_staff = True

        result = permission.has_permission(request, None)

        assert result is True

    def test_has_permission_non_admin_user(self) -> None:
        """Test permission denies non-admin user."""
        permission = IsAdminUser()
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.is_staff = False

        result = permission.has_permission(request, None)

        assert result is False

    def test_has_permission_unauthenticated(self) -> None:
        """Test permission denies unauthenticated user."""
        permission = IsAdminUser()
        request = MagicMock()
        request.user = None

        result = permission.has_permission(request, None)

        assert result is False

    def test_has_permission_inactive_user(self) -> None:
        """Test permission denies inactive user."""
        permission = IsAdminUser()
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = False
        request.user.is_staff = True

        result = permission.has_permission(request, None)

        assert result is False


class TestIsAdminOrReadOnly:
    """Unit tests for IsAdminOrReadOnly permission."""

    def test_has_permission_read_only_authenticated(self) -> None:
        """Test permission allows read-only for authenticated user."""
        permission = IsAdminOrReadOnly()
        request = MagicMock()
        request.method = "GET"
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.is_staff = False

        result = permission.has_permission(request, None)

        assert result is True

    def test_has_permission_write_admin(self) -> None:
        """Test permission allows write for admin user."""
        permission = IsAdminOrReadOnly()
        request = MagicMock()
        request.method = "POST"
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.is_staff = True

        result = permission.has_permission(request, None)

        assert result is True

    def test_has_permission_write_non_admin(self) -> None:
        """Test permission denies write for non-admin user."""
        permission = IsAdminOrReadOnly()
        request = MagicMock()
        request.method = "POST"
        request.user = MagicMock()
        request.user.is_authenticated = True
        request.user.is_active = True
        request.user.is_staff = False

        result = permission.has_permission(request, None)

        assert result is False

    def test_has_permission_unauthenticated(self) -> None:
        """Test permission denies unauthenticated user."""
        permission = IsAdminOrReadOnly()
        request = MagicMock()
        request.user = None

        result = permission.has_permission(request, None)

        assert result is False
