"""
Base test classes for integration tests.

This module provides base classes with common setup and utility methods
for integration tests across the Auto Forex backend.
"""

from typing import Any

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from rest_framework.response import Response
from rest_framework.test import APIClient

User = get_user_model()


class IntegrationTestCase(TestCase):
    """
    Base class for all integration tests with common setup.

    Provides:
    - Test user creation
    - Client authentication
    - Test account creation helpers
    - Common assertions
    """

    @classmethod
    def setUpTestData(cls) -> None:
        """Create test data shared across all test methods."""
        super().setUpTestData()
        # Subclasses can override to create shared test data

    def setUp(self) -> None:
        """Set up test client and authentication for each test."""
        super().setUp()
        self.client = Client()
        self.user = self.create_test_user()
        self.authenticate_client()

    def create_test_user(
        self,
        username: str = "testuser",
        email: str = "test@example.com",
        password: str = "testpass123",
        **kwargs: Any,
    ) -> User:  # ty:ignore[invalid-type-form]
        """
        Create a test user with appropriate permissions.

        Args:
            username: Username for the test user
            email: Email for the test user
            password: Password for the test user
            **kwargs: Additional user fields

        Returns:
            Created User instance
        """
        return User.objects.create_user(  # type: ignore[attr-defined]
            username=username,
            email=email,
            password=password,
            **kwargs,
        )

    def authenticate_client(self) -> None:
        """Authenticate the test client with test user credentials."""
        self.client.force_login(self.user)

    def create_test_account(self, **kwargs: Any) -> Any:
        """
        Create a test OANDA account with default or custom parameters.

        Args:
            **kwargs: Account fields to override defaults

        Returns:
            Created Account instance
        """
        from apps.market.models import OandaAccounts

        defaults = {
            "user": self.user,
            "account_id": f"TEST-{self.user.id:06d}",
            "api_type": "practice",
            "is_active": True,
        }
        defaults.update(kwargs)
        account = OandaAccounts.objects.create(**defaults)
        account.set_api_token("test-api-key")
        account.save()
        return account


class APIIntegrationTestCase(IntegrationTestCase):
    """
    Base class for API endpoint integration tests.

    Extends IntegrationTestCase with API-specific utilities:
    - DRF APIClient instead of Django test client
    - Response assertion helpers
    - JSON structure validation
    """

    def setUp(self) -> None:
        """Set up API client and authentication for each test."""
        # Don't call super().setUp() to avoid creating Django test client
        TestCase.setUp(self)
        self.client = APIClient()
        self.user = self.create_test_user()
        self.authenticate_api_client()

    def authenticate_api_client(self) -> None:
        """Authenticate the API client with test user credentials."""
        self.client.force_authenticate(user=self.user)  # ty:ignore[possibly-missing-attribute]

    def assert_response_success(
        self,
        response: Response,  # type: ignore[type-arg]
        status_code: int = 200,
    ) -> None:
        """
        Assert response is successful with expected status code.

        Args:
            response: DRF Response object
            status_code: Expected HTTP status code (default: 200)
        """
        self.assertEqual(
            response.status_code,
            status_code,
            f"Expected status {status_code}, got {response.status_code}. "
            f"Response data: {response.data}",
        )

    def assert_response_error(
        self,
        response: Response,  # type: ignore[type-arg]
        status_code: int,
        error_code: str | None = None,
    ) -> None:
        """
        Assert response is an error with expected status and error code.

        Args:
            response: DRF Response object
            status_code: Expected HTTP status code
            error_code: Optional expected error code in response
        """
        self.assertEqual(
            response.status_code,
            status_code,
            f"Expected status {status_code}, got {response.status_code}. "
            f"Response data: {response.data}",
        )

        if error_code is not None:
            self.assertIn(  # type: ignore[arg-type]
                "error",
                response.data,  # ty:ignore[invalid-argument-type]
                "Expected 'error' field in error response",
            )
            if isinstance(response.data["error"], dict):  # ty:ignore[not-subscriptable]
                self.assertEqual(
                    response.data["error"].get("code"),  # ty:ignore[not-subscriptable]
                    error_code,
                    f"Expected error code '{error_code}', got '{response.data['error'].get('code')}'",  # ty:ignore[not-subscriptable]
                )

    def assert_json_structure(
        self,
        data: dict[str, Any],
        expected_structure: dict[str, type],
    ) -> None:
        """
        Assert JSON response matches expected structure.

        Args:
            data: Response data dictionary
            expected_structure: Dictionary mapping field names to expected types

        Example:
            self.assert_json_structure(
                response.data,
                {
                    "id": int,
                    "name": str,
                    "is_active": bool,
                }
            )
        """
        for field, expected_type in expected_structure.items():
            self.assertIn(  # type: ignore[arg-type]
                field,
                data,
                f"Expected field '{field}' in response data",
            )
            self.assertIsInstance(
                data[field],
                expected_type,
                f"Expected field '{field}' to be {expected_type.__name__}, "
                f"got {type(data[field]).__name__}",
            )

    def assert_paginated_response(
        self,
        response: Response,  # type: ignore[type-arg]
        expected_count: int | None = None,
    ) -> None:
        """
        Assert response is a paginated response with expected structure.

        Args:
            response: DRF Response object
            expected_count: Optional expected count of results
        """
        self.assert_response_success(response)  # type: ignore[arg-type]
        self.assertIn("results", response.data)  # type: ignore[arg-type]
        self.assertIsInstance(response.data["results"], list)  # ty:ignore[not-subscriptable]

        if expected_count is not None:
            self.assertEqual(
                len(response.data["results"]),  # ty:ignore[not-subscriptable]
                expected_count,
                f"Expected {expected_count} results, got {len(response.data['results'])}",  # ty:ignore[not-subscriptable]
            )
