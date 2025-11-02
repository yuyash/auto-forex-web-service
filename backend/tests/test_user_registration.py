"""
Unit tests for user registration API endpoint.

Requirements: 1.1, 1.2, 1.3, 1.5
"""

from django.contrib.auth import get_user_model
from django.urls import reverse

import pytest
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client() -> APIClient:
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def valid_user_data() -> dict:
    """Create valid user registration data."""
    return {
        "email": "testuser@example.com",
        "username": "testuser",
        "password": "SecurePass123!",
        "password_confirm": "SecurePass123!",
    }


@pytest.mark.django_db
class TestUserRegistration:
    """Test suite for user registration endpoint."""

    def test_successful_registration_with_valid_data(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test successful registration with valid data.

        Requirements: 1.1, 1.2
        """
        url = reverse("accounts:register")
        response = api_client.post(url, valid_user_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert "message" in response.data
        assert "user" in response.data
        assert response.data["user"]["email"] == valid_user_data["email"].lower()
        assert response.data["user"]["username"] == valid_user_data["username"]

        # Verify user was created in database
        user = User.objects.get(email=valid_user_data["email"].lower())
        assert user.email == valid_user_data["email"].lower()
        assert user.username == valid_user_data["username"]

    def test_email_validation_invalid_format(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test email validation with invalid format.

        Requirements: 1.2
        """
        url = reverse("accounts:register")

        # Test various invalid email formats
        invalid_emails = [
            "notanemail",
            "missing@domain",
            "@nodomain.com",
            "no@domain@double.com",
            "spaces in@email.com",
        ]

        for invalid_email in invalid_emails:
            data = valid_user_data.copy()
            data["email"] = invalid_email
            response = api_client.post(url, data, format="json")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "email" in response.data

    def test_email_validation_uniqueness(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test email validation for uniqueness.

        Requirements: 1.2, 1.5
        """
        url = reverse("accounts:register")

        # Create first user
        response = api_client.post(url, valid_user_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Try to create second user with same email
        data = valid_user_data.copy()
        data["username"] = "differentuser"
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data
        assert "already exists" in str(response.data["email"]).lower()

    def test_password_strength_validation(
        self, api_client: APIClient, valid_user_data: dict
    ) -> None:
        """
        Test password strength validation.

        Requirements: 1.2, 1.3
        """
        url = reverse("accounts:register")

        # Test weak passwords that should fail Django's validators
        weak_passwords = [
            ("short", "too short"),  # Too short (< 8 characters)
            ("12345678", "entirely numeric"),  # All numeric
            ("password", "too common"),  # Too common
        ]

        for weak_password, reason in weak_passwords:
            data = valid_user_data.copy()
            data["password"] = weak_password
            data["password_confirm"] = weak_password
            response = api_client.post(url, data, format="json")

            assert (
                response.status_code == status.HTTP_400_BAD_REQUEST
            ), f"Password '{weak_password}' should fail ({reason})"
            assert "password" in response.data

    def test_password_hashing(self, api_client: APIClient, valid_user_data: dict) -> None:
        """
        Test that passwords are properly hashed.

        Requirements: 1.3
        """
        url = reverse("accounts:register")
        response = api_client.post(url, valid_user_data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Retrieve user from database
        user = User.objects.get(email=valid_user_data["email"].lower())

        # Verify password is hashed (not stored in plain text)
        assert user.password != valid_user_data["password"]
        # Django uses different hashers (bcrypt, pbkdf2, argon2, md5 in tests)
        assert (
            user.password.startswith("bcrypt")
            or user.password.startswith("pbkdf2")
            or user.password.startswith("argon2")
            or user.password.startswith("md5")  # Used in test mode
        )

        # Verify password can be checked
        assert user.check_password(valid_user_data["password"])

    def test_duplicate_email_rejection(self, api_client: APIClient, valid_user_data: dict) -> None:
        """
        Test that duplicate emails are rejected.

        Requirements: 1.5
        """
        url = reverse("accounts:register")

        # Create first user
        response = api_client.post(url, valid_user_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

        # Try to register with same email (different case)
        data = valid_user_data.copy()
        data["email"] = valid_user_data["email"].upper()
        data["username"] = "differentuser"
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_password_mismatch(self, api_client: APIClient, valid_user_data: dict) -> None:
        """
        Test that password confirmation must match.

        Requirements: 1.2
        """
        url = reverse("accounts:register")
        data = valid_user_data.copy()
        data["password_confirm"] = "DifferentPassword123!"

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password_confirm" in response.data or "non_field_errors" in response.data

    def test_missing_required_fields(self, api_client: APIClient) -> None:
        """
        Test that required fields are validated.

        Requirements: 1.1, 1.2
        """
        url = reverse("accounts:register")

        # Test missing email
        response = api_client.post(
            url,
            {
                "username": "testuser",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

        # Test missing password
        response = api_client.post(
            url,
            {
                "email": "test@example.com",
                "username": "testuser",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data

    def test_username_auto_generation(self, api_client: APIClient) -> None:
        """
        Test that username is auto-generated from email if not provided.

        Requirements: 1.1
        """
        url = reverse("accounts:register")
        data = {
            "email": "autouser@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["username"] == "autouser"

        # Verify user was created with auto-generated username
        user = User.objects.get(email="autouser@example.com")
        assert user.username == "autouser"

    def test_username_uniqueness_handling(self, api_client: APIClient) -> None:
        """
        Test that duplicate usernames are handled by appending numbers.

        Requirements: 1.1
        """
        url = reverse("accounts:register")

        # Create first user
        data1 = {
            "email": "user1@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response1 = api_client.post(url, data1, format="json")
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.data["user"]["username"] == "user1"

        # Create second user with same email prefix
        data2 = {
            "email": "user1@different.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
        }
        response2 = api_client.post(url, data2, format="json")
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.data["user"]["username"] == "user11"

    def test_email_case_insensitivity(self, api_client: APIClient, valid_user_data: dict) -> None:
        """
        Test that email addresses are stored in lowercase.

        Requirements: 1.2
        """
        url = reverse("accounts:register")
        data = valid_user_data.copy()
        data["email"] = "TestUser@EXAMPLE.COM"

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["user"]["email"] == "testuser@example.com"

        # Verify in database
        user = User.objects.get(email="testuser@example.com")
        assert user.email == "testuser@example.com"
