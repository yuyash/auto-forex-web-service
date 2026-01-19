"""
Test the integration test infrastructure setup.

This module verifies that the base test classes, factories, and fixtures
are working correctly.
"""

import pytest
from django.contrib.auth import get_user_model

from tests.integration.base import APIIntegrationTestCase, IntegrationTestCase
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    UserFactory,
)

User = get_user_model()


class TestIntegrationTestCase(IntegrationTestCase):
    """Test the IntegrationTestCase base class."""

    def test_user_creation(self):
        """Test that test user is created correctly."""
        self.assertIsNotNone(self.user)
        self.assertIsInstance(self.user, User)
        self.assertTrue(self.user.is_active)

    def test_client_authentication(self):
        """Test that client is authenticated."""
        response = self.client.get("/api/health/")
        # Should not get 401/403 for authenticated requests
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)

    def test_create_test_account(self):
        """Test creating a test OANDA account."""
        account = self.create_test_account()
        self.assertIsNotNone(account)
        self.assertEqual(account.user, self.user)
        self.assertTrue(account.is_active)


class TestAPIIntegrationTestCase(APIIntegrationTestCase):
    """Test the APIIntegrationTestCase base class."""

    def test_api_client_authentication(self):
        """Test that API client is authenticated."""
        response = self.client.get("/api/health/")
        # Should not get 401/403 for authenticated requests
        self.assertNotEqual(response.status_code, 401)
        self.assertNotEqual(response.status_code, 403)

    def test_assert_response_success(self):
        """Test assert_response_success helper."""
        response = self.client.get("/api/health/")
        # This should not raise an exception
        self.assert_response_success(response, status_code=response.status_code)  # ty:ignore[invalid-argument-type]


@pytest.mark.django_db
class TestFactories:
    """Test the factory classes."""

    def test_user_factory(self):
        """Test UserFactory creates valid users."""
        user = UserFactory()
        assert user.pk is not None  # ty:ignore[unresolved-attribute]
        assert user.email
        assert user.username
        assert user.is_active

    def test_oanda_account_factory(self):
        """Test OandaAccountFactory creates valid accounts."""
        account = OandaAccountFactory()
        assert account.pk is not None  # ty:ignore[unresolved-attribute]
        assert account.user is not None
        assert account.account_id
        assert account.balance > 0  # ty:ignore[unsupported-operator]

    def test_strategy_configuration_factory(self):
        """Test StrategyConfigurationFactory creates valid configs."""
        config = StrategyConfigurationFactory()
        assert config.pk is not None  # ty:ignore[unresolved-attribute]
        assert config.user is not None
        assert config.name
        assert config.strategy_type == "floor"
        assert config.parameters


@pytest.mark.django_db
class TestFixtures:
    """Test the pytest fixtures."""

    def test_test_user_fixture(self, test_user):
        """Test test_user fixture."""
        assert test_user.pk is not None
        assert test_user.is_active

    def test_authenticated_client_fixture(self, authenticated_client, test_user):
        """Test authenticated_client fixture."""
        response = authenticated_client.get("/api/health/")
        # Should not get 401/403 for authenticated requests
        assert response.status_code not in [401, 403]

    def test_test_account_fixture(self, test_account, test_user):
        """Test test_account fixture."""
        assert test_account.pk is not None
        assert test_account.user == test_user

    def test_multiple_accounts_fixture(self, multiple_accounts, test_user):
        """Test multiple_accounts fixture."""
        assert len(multiple_accounts) == 3
        for account in multiple_accounts:
            assert account.user == test_user

    def test_mock_market_data_fixture(self, mock_market_data):
        """Test mock_market_data fixture."""
        assert "instrument" in mock_market_data
        assert "bid" in mock_market_data
        assert "ask" in mock_market_data
