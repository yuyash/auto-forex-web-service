"""
Unit tests for system settings functionality.

Requirements: 1.1, 2.1, 19.5
"""

from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import SystemSettings

if TYPE_CHECKING:
    from accounts.models import User as UserType
else:
    UserType = get_user_model()

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def regular_user(db) -> "UserType":
    """Create a regular user for testing."""
    return User.objects.create_user(
        email="user@example.com",
        username="regularuser",
        password="TestPass123!",
        is_staff=False,
    )


@pytest.fixture
def admin_user(db) -> "UserType":
    """Create an admin user for testing."""
    return User.objects.create_user(
        email="admin@example.com",
        username="adminuser",
        password="AdminPass123!",
        is_staff=True,
    )


@pytest.fixture
def valid_user_data() -> dict:
    """Create valid user registration data."""
    return {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }


@pytest.fixture
def valid_login_data() -> dict:
    """Create valid login data."""
    return {
        "email": "user@example.com",
        "password": "TestPass123!",
    }


@pytest.mark.django_db
class TestSystemSettingsSingleton:
    """Test suite for SystemSettings singleton pattern."""

    def test_singleton_pattern(self) -> None:
        """
        Test that only one SystemSettings instance exists.

        Requirements: 1.1, 2.1
        """
        # Get settings multiple times
        settings1 = SystemSettings.get_settings()
        settings2 = SystemSettings.get_settings()

        # Should be the same instance
        assert settings1.pk == settings2.pk
        assert settings1.pk == 1

        # Should only be one instance in database
        assert SystemSettings.objects.count() == 1

    def test_default_values(self) -> None:
        """
        Test that default values are set correctly.

        Requirements: 1.1, 2.1
        """
        settings = SystemSettings.get_settings()

        assert settings.registration_enabled is True
        assert settings.login_enabled is True
        assert settings.updated_by is None


@pytest.mark.django_db
class TestRegistrationWithSystemSettings:
    """Test suite for registration endpoint with system settings."""

    def test_registration_allowed_when_enabled(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test registration is allowed when registration_enabled=True.

        Requirements: 1.1
        """
        # Ensure registration is enabled
        settings = SystemSettings.get_settings()
        settings.registration_enabled = True
        settings.save()

        url = reverse("accounts:register")
        response = api_client.post(url, valid_user_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        assert response.data["user"]["email"] == valid_user_data["email"].lower()

    def test_registration_blocked_when_disabled(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test registration is blocked when registration_enabled=False.

        Requirements: 1.1
        """
        # Disable registration
        settings = SystemSettings.get_settings()
        settings.registration_enabled = False
        settings.save()

        url = reverse("accounts:register")
        response = api_client.post(url, valid_user_data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "error" in response.data
        assert "disabled" in response.data["error"].lower()

        # Verify user was not created
        assert not User.objects.filter(email=valid_user_data["email"].lower()).exists()


@pytest.mark.django_db
class TestLoginWithSystemSettings:
    """Test suite for login endpoint with system settings."""

    def test_login_allowed_when_enabled(
        self, api_client: APIClient, regular_user: "UserType", valid_login_data: dict
    ) -> None:
        """
        Test login is allowed when login_enabled=True.

        Requirements: 2.1
        """
        # Ensure login is enabled
        settings = SystemSettings.get_settings()
        settings.login_enabled = True
        settings.save()

        url = reverse("accounts:login")
        response = api_client.post(url, valid_login_data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "user" in response.data

    def test_login_blocked_when_disabled(
        self, api_client: APIClient, regular_user: "UserType", valid_login_data: dict
    ) -> None:
        """
        Test login is blocked when login_enabled=False.

        Requirements: 2.1
        """
        # Disable login
        settings = SystemSettings.get_settings()
        settings.login_enabled = False
        settings.save()

        url = reverse("accounts:login")
        response = api_client.post(url, valid_login_data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "error" in response.data
        assert "disabled" in response.data["error"].lower()


@pytest.mark.django_db
class TestPublicSystemSettingsEndpoint:
    """Test suite for public system settings endpoint."""

    def test_public_settings_returns_correct_flags(self, api_client: APIClient) -> None:
        """
        Test public settings endpoint returns correct flags.

        Requirements: 1.1, 2.1
        """
        # Set specific values
        settings = SystemSettings.get_settings()
        settings.registration_enabled = True
        settings.login_enabled = False
        settings.save()

        url = reverse("accounts:public_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["registration_enabled"] is True
        assert response.data["login_enabled"] is False

    def test_public_settings_no_auth_required(self, api_client: APIClient) -> None:
        """
        Test public settings endpoint does not require authentication.

        Requirements: 1.1, 2.1
        """
        url = reverse("accounts:public_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "registration_enabled" in response.data
        assert "login_enabled" in response.data

    def test_public_settings_does_not_expose_sensitive_data(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test public settings endpoint does not expose sensitive data.

        Requirements: 1.1, 2.1
        """
        # Update settings with admin user
        settings = SystemSettings.get_settings()
        settings.updated_by = admin_user
        settings.save()

        url = reverse("accounts:public_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Should only have the three boolean flags
        assert len(response.data) == 3
        assert "registration_enabled" in response.data
        assert "login_enabled" in response.data
        assert "email_whitelist_enabled" in response.data
        assert "updated_by" not in response.data
        assert "updated_at" not in response.data


@pytest.mark.django_db
class TestAdminSystemSettingsEndpoint:
    """Test suite for admin system settings endpoint."""

    def test_admin_can_retrieve_settings(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test admin can retrieve system settings.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=admin_user)

        url = reverse("accounts:admin_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert "registration_enabled" in response.data
        assert "login_enabled" in response.data
        assert "updated_at" in response.data

    def test_admin_can_update_settings(self, api_client: APIClient, admin_user: "UserType") -> None:
        """
        Test admin can update system settings.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=admin_user)

        url = reverse("accounts:admin_system_settings")
        data = {
            "registration_enabled": False,
            "login_enabled": True,
        }
        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["registration_enabled"] is False
        assert response.data["login_enabled"] is True

        # Verify in database
        settings = SystemSettings.get_settings()
        assert settings.registration_enabled is False
        assert settings.login_enabled is True
        assert settings.updated_by == admin_user

    def test_admin_can_partially_update_settings(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test admin can partially update system settings.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=admin_user)

        # Set initial state
        settings = SystemSettings.get_settings()
        settings.registration_enabled = True
        settings.login_enabled = True
        settings.save()

        # Update only registration_enabled
        url = reverse("accounts:admin_system_settings")
        data = {"registration_enabled": False}
        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["registration_enabled"] is False
        assert response.data["login_enabled"] is True  # Should remain unchanged

    def test_regular_user_cannot_retrieve_settings(
        self, api_client: APIClient, regular_user: "UserType"
    ) -> None:
        """
        Test regular user cannot retrieve system settings.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=regular_user)

        url = reverse("accounts:admin_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_cannot_update_settings(
        self, api_client: APIClient, regular_user: "UserType"
    ) -> None:
        """
        Test regular user cannot update system settings.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=regular_user)

        url = reverse("accounts:admin_system_settings")
        data = {
            "registration_enabled": False,
            "login_enabled": False,
        }
        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

        # Verify settings were not changed
        settings = SystemSettings.get_settings()
        assert settings.registration_enabled is True
        assert settings.login_enabled is True

    def test_unauthenticated_user_cannot_access_admin_settings(self, api_client: APIClient) -> None:
        """
        Test unauthenticated user cannot access admin settings.

        Requirements: 19.5
        """
        url = reverse("accounts:admin_system_settings")

        # Try GET
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

        # Try PUT
        data = {"registration_enabled": False}
        response = api_client.put(url, data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestSystemSettingsHTTPStatusCodes:
    """Test suite for appropriate HTTP status codes."""

    def test_registration_returns_503_when_disabled(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test registration returns 503 Service Unavailable when disabled.

        Requirements: 1.1
        """
        settings = SystemSettings.get_settings()
        settings.registration_enabled = False
        settings.save()

        url = reverse("accounts:register")
        response = api_client.post(url, valid_user_data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_login_returns_503_when_disabled(
        self, api_client: APIClient, regular_user: "UserType", valid_login_data: dict
    ) -> None:
        """
        Test login returns 503 Service Unavailable when disabled.

        Requirements: 2.1
        """
        settings = SystemSettings.get_settings()
        settings.login_enabled = False
        settings.save()

        url = reverse("accounts:login")
        response = api_client.post(url, valid_login_data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_public_settings_returns_200(self, api_client: APIClient) -> None:
        """
        Test public settings endpoint returns 200 OK.

        Requirements: 1.1, 2.1
        """
        url = reverse("accounts:public_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_admin_settings_get_returns_200_for_admin(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test admin settings GET returns 200 OK for admin.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=admin_user)

        url = reverse("accounts:admin_system_settings")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

    def test_admin_settings_put_returns_200_for_admin(
        self, api_client: APIClient, admin_user: "UserType"
    ) -> None:
        """
        Test admin settings PUT returns 200 OK for admin.

        Requirements: 19.5
        """
        api_client.force_authenticate(user=admin_user)

        url = reverse("accounts:admin_system_settings")
        data = {"registration_enabled": False}
        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
