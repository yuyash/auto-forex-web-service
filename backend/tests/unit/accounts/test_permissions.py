"""
Unit tests for permission classes.

Tests cover:
- IsAdminUser permission
- IsAdminOrReadOnly permission
- Permission checks for authenticated/unauthenticated users
- Staff vs non-staff user access
"""

from unittest.mock import MagicMock

import pytest

from apps.accounts.permissions import IsAdminOrReadOnly, IsAdminUser, _get_request_user


class TestGetRequestUser:
    """Test cases for _get_request_user helper function."""

    def test_returns_user_when_authenticated(self) -> None:
        """Test returns user when authenticated User instance."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True

        request = MagicMock()
        request.user = mock_user

        result = _get_request_user(request)

        assert result == mock_user

    def test_returns_none_when_not_authenticated(self) -> None:
        """Test returns None when user is not authenticated."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = False

        request = MagicMock()
        request.user = mock_user

        result = _get_request_user(request)

        assert result is None

    def test_returns_none_when_no_user(self) -> None:
        """Test returns None when request has no user attribute."""
        request = MagicMock(spec=[])  # No attributes

        result = _get_request_user(request)

        assert result is None

    def test_returns_none_when_user_is_anonymous(self) -> None:
        """Test returns None when user is AnonymousUser."""
        from django.contrib.auth.models import AnonymousUser

        request = MagicMock()
        request.user = AnonymousUser()

        result = _get_request_user(request)

        assert result is None


class TestIsAdminUser:
    """Test cases for IsAdminUser permission class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.permission = IsAdminUser()

    def test_unauthenticated_user_denied(self) -> None:
        """Test that unauthenticated users are denied."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False

        result = self.permission.has_permission(request, None)

        assert result is False

    def test_inactive_user_denied(self) -> None:
        """Test that inactive users are denied."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = False
        mock_user.is_staff = True

        request = MagicMock()
        request.user = mock_user

        result = self.permission.has_permission(request, None)

        assert result is False

    def test_non_staff_user_denied(self) -> None:
        """Test that non-staff users are denied."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = False

        request = MagicMock()
        request.user = mock_user

        result = self.permission.has_permission(request, None)

        assert result is False

    def test_staff_user_allowed(self) -> None:
        """Test that staff users are allowed."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = True

        request = MagicMock()
        request.user = mock_user

        result = self.permission.has_permission(request, None)

        assert result is True

    def test_permission_message(self) -> None:
        """Test that permission has appropriate message."""
        assert "permission" in self.permission.message.lower()


class TestIsAdminOrReadOnly:
    """Test cases for IsAdminOrReadOnly permission class."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.permission = IsAdminOrReadOnly()

    def test_unauthenticated_user_denied(self) -> None:
        """Test that unauthenticated users are denied for any method."""
        request = MagicMock()
        request.user = MagicMock()
        request.user.is_authenticated = False
        request.method = "GET"

        result = self.permission.has_permission(request, None)

        assert result is False

    def test_inactive_user_denied(self) -> None:
        """Test that inactive users are denied even for GET."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = False
        mock_user.is_staff = False

        request = MagicMock()
        request.user = mock_user
        request.method = "GET"

        result = self.permission.has_permission(request, None)

        assert result is False

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_allowed_for_regular_user(self, method: str) -> None:
        """Test that safe methods are allowed for regular authenticated users."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = False

        request = MagicMock()
        request.user = mock_user
        request.method = method

        result = self.permission.has_permission(request, None)

        assert result is True

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_write_methods_denied_for_regular_user(self, method: str) -> None:
        """Test that write methods are denied for regular users."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = False

        request = MagicMock()
        request.user = mock_user
        request.method = method

        result = self.permission.has_permission(request, None)

        assert result is False

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_write_methods_allowed_for_admin(self, method: str) -> None:
        """Test that write methods are allowed for admin users."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = True

        request = MagicMock()
        request.user = mock_user
        request.method = method

        result = self.permission.has_permission(request, None)

        assert result is True

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_allowed_for_admin(self, method: str) -> None:
        """Test that safe methods are allowed for admin users."""
        from apps.accounts.models import User

        mock_user = MagicMock(spec=User)
        mock_user.is_authenticated = True
        mock_user.is_active = True
        mock_user.is_staff = True

        request = MagicMock()
        request.user = mock_user
        request.method = method

        result = self.permission.has_permission(request, None)

        assert result is True

    def test_permission_message(self) -> None:
        """Test that permission has appropriate message."""
        assert "permission" in self.permission.message.lower()


@pytest.mark.django_db
class TestPermissionsIntegration:
    """Integration tests for permissions with real database."""

    def test_is_admin_user_with_real_staff_user(self) -> None:
        """Test IsAdminUser with a real staff user."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            is_staff=True,
        )

        request = MagicMock()
        request.user = user

        permission = IsAdminUser()
        result = permission.has_permission(request, None)

        assert result is True

    def test_is_admin_user_with_real_regular_user(self) -> None:
        """Test IsAdminUser with a real regular user."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass",
            is_staff=False,
        )

        request = MagicMock()
        request.user = user

        permission = IsAdminUser()
        result = permission.has_permission(request, None)

        assert result is False

    def test_is_admin_or_read_only_post_regular_user(self) -> None:
        """Test IsAdminOrReadOnly POST with regular user."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass",
            is_staff=False,
        )

        request = MagicMock()
        request.user = user
        request.method = "POST"

        permission = IsAdminOrReadOnly()
        result = permission.has_permission(request, None)

        assert result is False

    def test_is_admin_or_read_only_get_regular_user(self) -> None:
        """Test IsAdminOrReadOnly GET with regular user."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regularpass",
            is_staff=False,
        )

        request = MagicMock()
        request.user = user
        request.method = "GET"

        permission = IsAdminOrReadOnly()
        result = permission.has_permission(request, None)

        assert result is True
