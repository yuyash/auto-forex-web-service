"""
Unit tests for role-based access control permissions.

Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
"""

# mypy: disable-error-code="attr-defined,valid-type,union-attr"

from django.contrib.auth import get_user_model

import pytest
from rest_framework.test import APIRequestFactory

from accounts.permissions import IsAdminOrReadOnly, IsAdminUser

User = get_user_model()


@pytest.fixture
def api_request_factory() -> APIRequestFactory:
    """Create an API request factory for testing."""
    return APIRequestFactory()


@pytest.fixture
def regular_user(db) -> User:
    """Create a regular (non-admin) test user."""
    user = User.objects.create_user(
        email="regular@example.com",
        username="regularuser",
        password="SecurePass123!",
        is_staff=False,
    )
    return user


@pytest.fixture
def admin_user(db) -> User:
    """Create an admin test user."""
    user = User.objects.create_user(
        email="admin@example.com",
        username="adminuser",
        password="SecurePass123!",
        is_staff=True,
    )
    return user


@pytest.mark.django_db
class TestIsAdminUserPermission:
    """Test suite for IsAdminUser permission class."""

    def test_admin_user_has_permission(
        self, api_request_factory: APIRequestFactory, admin_user: User
    ) -> None:
        """
        Test that admin users have permission.

        Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
        """
        permission = IsAdminUser()
        request = api_request_factory.get("/api/admin/dashboard")
        request.user = admin_user

        assert permission.has_permission(request, None) is True

    def test_regular_user_denied_permission(
        self, api_request_factory: APIRequestFactory, regular_user: User
    ) -> None:
        """
        Test that regular users are denied permission.

        Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
        """
        permission = IsAdminUser()
        request = api_request_factory.get("/api/admin/dashboard")
        request.user = regular_user

        assert permission.has_permission(request, None) is False

    def test_unauthenticated_user_denied_permission(
        self, api_request_factory: APIRequestFactory
    ) -> None:
        """
        Test that unauthenticated users are denied permission.

        Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
        """
        from django.contrib.auth.models import AnonymousUser

        permission = IsAdminUser()
        request = api_request_factory.get("/api/admin/dashboard")
        request.user = AnonymousUser()

        assert permission.has_permission(request, None) is False

    def test_permission_message(self) -> None:
        """
        Test that permission has appropriate error message.

        Requirements: 19.5
        """
        permission = IsAdminUser()
        assert hasattr(permission, "message")
        assert "permission" in permission.message.lower()

    def test_inactive_admin_user_denied_permission(
        self, api_request_factory: APIRequestFactory, admin_user: User
    ) -> None:
        """
        Test that inactive admin users are denied permission.

        Requirements: 19.5, 20.5
        """
        admin_user.is_active = False
        admin_user.save()

        permission = IsAdminUser()
        request = api_request_factory.get("/api/admin/dashboard")
        request.user = admin_user

        # Django's is_authenticated returns False for inactive users
        assert permission.has_permission(request, None) is False

    def test_permission_works_with_post_request(
        self, api_request_factory: APIRequestFactory, admin_user: User
    ) -> None:
        """
        Test that permission works with POST requests.

        Requirements: 22.5, 23.5
        """
        permission = IsAdminUser()
        request = api_request_factory.post("/api/admin/users/1/kickoff")
        request.user = admin_user

        assert permission.has_permission(request, None) is True

    def test_permission_works_with_delete_request(
        self, api_request_factory: APIRequestFactory, admin_user: User
    ) -> None:
        """
        Test that permission works with DELETE requests.

        Requirements: 22.5, 23.5
        """
        permission = IsAdminUser()
        request = api_request_factory.delete("/api/admin/strategies/1/stop")
        request.user = admin_user

        assert permission.has_permission(request, None) is True


@pytest.mark.django_db
class TestIsAdminOrReadOnlyPermission:
    """Test suite for IsAdminOrReadOnly permission class."""

    def test_admin_user_has_write_permission(
        self, api_request_factory: APIRequestFactory, admin_user: User
    ) -> None:
        """
        Test that admin users have write permission.

        Requirements: 19.5, 20.5, 21.5
        """
        permission = IsAdminOrReadOnly()
        request = api_request_factory.post("/api/admin/settings")
        request.user = admin_user

        assert permission.has_permission(request, None) is True

    def test_regular_user_has_read_permission(
        self, api_request_factory: APIRequestFactory, regular_user: User
    ) -> None:
        """
        Test that regular users have read permission.

        Requirements: 19.5, 20.5
        """
        permission = IsAdminOrReadOnly()
        request = api_request_factory.get("/api/admin/settings")
        request.user = regular_user

        assert permission.has_permission(request, None) is True

    def test_regular_user_denied_write_permission(
        self, api_request_factory: APIRequestFactory, regular_user: User
    ) -> None:
        """
        Test that regular users are denied write permission.

        Requirements: 19.5, 20.5, 21.5
        """
        permission = IsAdminOrReadOnly()
        request = api_request_factory.post("/api/admin/settings")
        request.user = regular_user

        assert permission.has_permission(request, None) is False

    def test_unauthenticated_user_denied_all_access(
        self, api_request_factory: APIRequestFactory
    ) -> None:
        """
        Test that unauthenticated users are denied all access.

        Requirements: 19.5
        """
        from django.contrib.auth.models import AnonymousUser

        permission = IsAdminOrReadOnly()

        # Test GET request
        request = api_request_factory.get("/api/admin/settings")
        request.user = AnonymousUser()
        assert permission.has_permission(request, None) is False

        # Test POST request
        request = api_request_factory.post("/api/admin/settings")
        request.user = AnonymousUser()
        assert permission.has_permission(request, None) is False

    def test_safe_methods_allowed_for_authenticated_users(
        self, api_request_factory: APIRequestFactory, regular_user: User
    ) -> None:
        """
        Test that safe HTTP methods are allowed for authenticated users.

        Requirements: 19.5, 20.5
        """
        permission = IsAdminOrReadOnly()

        # Test GET
        get_request = api_request_factory.get("/api/admin/settings")
        get_request.user = regular_user
        assert permission.has_permission(get_request, None) is True

        # Test HEAD
        head_request = api_request_factory.head("/api/admin/settings")
        head_request.user = regular_user
        assert permission.has_permission(head_request, None) is True  # type: ignore[arg-type]

        # Test OPTIONS
        options_request = api_request_factory.options("/api/admin/settings")
        options_request.user = regular_user
        assert permission.has_permission(options_request, None) is True

    def test_unsafe_methods_require_admin(
        self,
        api_request_factory: APIRequestFactory,
        regular_user: User,
        admin_user: User,
    ) -> None:
        """
        Test that unsafe HTTP methods require admin privileges.

        Requirements: 19.5, 20.5, 21.5, 22.5, 23.5
        """
        permission = IsAdminOrReadOnly()

        # Test POST - regular user denied
        request = api_request_factory.post("/api/admin/settings")
        request.user = regular_user
        assert permission.has_permission(request, None) is False

        # Test POST - admin user allowed
        request = api_request_factory.post("/api/admin/settings")
        request.user = admin_user
        assert permission.has_permission(request, None) is True

        # Test PUT - regular user denied
        request = api_request_factory.put("/api/admin/settings")
        request.user = regular_user
        assert permission.has_permission(request, None) is False

        # Test PUT - admin user allowed
        request = api_request_factory.put("/api/admin/settings")
        request.user = admin_user
        assert permission.has_permission(request, None) is True

        # Test DELETE - regular user denied
        request = api_request_factory.delete("/api/admin/settings")
        request.user = regular_user
        assert permission.has_permission(request, None) is False

        # Test DELETE - admin user allowed
        request = api_request_factory.delete("/api/admin/settings")
        request.user = admin_user
        assert permission.has_permission(request, None) is True

        # Test PATCH - regular user denied
        request = api_request_factory.patch("/api/admin/settings")
        request.user = regular_user
        assert permission.has_permission(request, None) is False

        # Test PATCH - admin user allowed
        request = api_request_factory.patch("/api/admin/settings")
        request.user = admin_user
        assert permission.has_permission(request, None) is True

    def test_permission_message(self) -> None:
        """
        Test that permission has appropriate error message.

        Requirements: 19.5
        """
        permission = IsAdminOrReadOnly()
        assert hasattr(permission, "message")
        assert "permission" in permission.message.lower()
        assert "modify" in permission.message.lower()
