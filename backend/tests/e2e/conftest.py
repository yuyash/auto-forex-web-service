"""Pytest fixtures for end-to-end integration tests."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfiguration

User = get_user_model()


@pytest.fixture
def api_client():
    """Create an API client for testing."""
    return APIClient()


@pytest.fixture
def test_user(db):
    """Create a test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        username="e2e_testuser",
        email="e2e_test@example.com",
        password="e2e_testpass123",
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Create an authenticated API client."""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def strategy_config(test_user):
    """Create a test strategy configuration."""
    return StrategyConfiguration.objects.create(
        user=test_user,
        name="E2E Test Strategy",
        strategy_type="floor",
        parameters={
            "entry_threshold": 0.5,
            "exit_threshold": 0.3,
            "max_position_size": 1000,
        },
    )


@pytest.fixture
def oanda_account(test_user):
    """Create a test OANDA account."""
    account = OandaAccounts.objects.create(
        user=test_user,
        account_id="E2E-TEST-001",
        api_type="practice",
        is_active=True,
    )
    account.set_api_token("e2e-test-api-key")
    account.save()
    return account
