"""
Pytest fixtures for integration tests.

This module provides shared fixtures for integration tests including:
- Database fixtures (test users, accounts, etc.)
- Mock fixtures (OANDA API, market data, etc.)
- Client fixtures (authenticated clients)
"""

import pytest
import responses
from django.contrib.auth import get_user_model
from django.test import Client
from rest_framework.test import APIClient

from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    UserFactory,
)

User = get_user_model()


# =============================================================================
# Database Fixtures
# =============================================================================


@pytest.fixture
def test_user(db):
    """
    Create a test user.

    Returns:
        User: Test user instance
    """
    return UserFactory()


@pytest.fixture
def test_user_with_password(db):
    """
    Create a test user with a known password.

    Returns:
        tuple: (User instance, password string)
    """
    password = "testpass123"
    user = UserFactory()
    user.set_password(password)  # type: ignore[attr-defined]
    user.save()  # type: ignore[attr-defined]
    return user, password


@pytest.fixture
def authenticated_client(test_user):
    """
    Create an authenticated Django test client.

    Args:
        test_user: Test user fixture

    Returns:
        Client: Authenticated Django test client
    """
    client = Client()
    client.force_login(test_user)
    return client


@pytest.fixture
def api_client():
    """
    Create a DRF API client.

    Returns:
        APIClient: DRF API client
    """
    return APIClient()


@pytest.fixture
def authenticated_api_client(test_user, api_client):
    """
    Create an authenticated DRF API client.

    Args:
        test_user: Test user fixture
        api_client: API client fixture

    Returns:
        APIClient: Authenticated DRF API client
    """
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def test_account(test_user):
    """
    Create a test OANDA account.

    Args:
        test_user: Test user fixture

    Returns:
        OandaAccount: Test OANDA account instance
    """
    return OandaAccountFactory(user=test_user)


@pytest.fixture
def multiple_accounts(test_user):
    """
    Create multiple test accounts for the same user.

    Args:
        test_user: Test user fixture

    Returns:
        list: List of OandaAccount instances
    """
    return OandaAccountFactory.create_batch(3, user=test_user)


@pytest.fixture
def test_strategy_config(test_user):
    """
    Create a test strategy configuration.

    Args:
        test_user: Test user fixture

    Returns:
        StrategyConfiguration: Test strategy configuration instance
    """
    return StrategyConfigurationFactory(user=test_user)


@pytest.fixture
def multiple_users(db):
    """
    Create multiple test users.

    Returns:
        list: List of User instances
    """
    return UserFactory.create_batch(3)


# =============================================================================
# Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_oanda_api():
    """
    Mock OANDA API responses.

    Yields:
        responses.RequestsMock: Mock responses context manager
    """
    with responses.RequestsMock() as rsps:
        # Mock common OANDA API endpoints
        rsps.add(
            responses.GET,
            "https://api-fxpractice.oanda.com/v3/accounts",
            json={"accounts": []},
            status=200,
        )
        rsps.add(
            responses.GET,
            "https://api-fxpractice.oanda.com/v3/instruments",
            json={"instruments": []},
            status=200,
        )
        yield rsps


@pytest.fixture
def mock_market_data():
    """
    Provide mock market data for testing.

    Returns:
        dict: Mock market data dictionary
    """
    return {
        "instrument": "EUR_USD",
        "time": "2024-01-15T10:30:00.000000Z",
        "bid": 1.08950,
        "ask": 1.08955,
        "mid": 1.089525,
    }


@pytest.fixture
def mock_tick_data():
    """
    Provide mock tick data for testing.

    Returns:
        list: List of mock tick data dictionaries
    """
    return [
        {
            "instrument": "EUR_USD",
            "timestamp": "2024-01-15T10:30:00.000000Z",
            "bid": 1.08950,
            "ask": 1.08955,
            "mid": 1.089525,
        },
        {
            "instrument": "EUR_USD",
            "timestamp": "2024-01-15T10:30:01.000000Z",
            "bid": 1.08951,
            "ask": 1.08956,
            "mid": 1.089535,
        },
        {
            "instrument": "EUR_USD",
            "timestamp": "2024-01-15T10:30:02.000000Z",
            "bid": 1.08952,
            "ask": 1.08957,
            "mid": 1.089545,
        },
    ]


@pytest.fixture
def mock_oanda_account_response():
    """
    Provide mock OANDA account response data.

    Returns:
        dict: Mock OANDA account response
    """
    return {
        "account": {
            "id": "101-001-12345678-001",
            "currency": "USD",
            "balance": "10000.00",
            "marginUsed": "500.00",
            "marginAvailable": "9500.00",
            "unrealizedPL": "50.00",
            "openPositionCount": 2,
            "openTradeCount": 2,
        }
    }


@pytest.fixture
def mock_oanda_position_response():
    """
    Provide mock OANDA position response data.

    Returns:
        dict: Mock OANDA position response
    """
    return {
        "position": {
            "instrument": "EUR_USD",
            "long": {
                "units": "1000",
                "averagePrice": "1.08950",
                "unrealizedPL": "25.00",
            },
            "short": {
                "units": "0",
                "averagePrice": "0",
                "unrealizedPL": "0",
            },
        }
    }


# =============================================================================
# Time Control Fixtures
# =============================================================================


@pytest.fixture
def freeze_time():
    """
    Provide freezegun time control.

    Returns:
        function: Function to freeze time at a specific datetime
    """
    from freezegun import freeze_time as _freeze_time

    return _freeze_time


# =============================================================================
# Redis Mock Fixtures
# =============================================================================


@pytest.fixture
def mock_redis():
    """
    Provide a fake Redis instance for testing.

    Returns:
        FakeRedis: Fake Redis instance
    """
    import fakeredis

    return fakeredis.FakeRedis()


@pytest.fixture
def mock_redis_client(mock_redis):
    """
    Provide a fake Redis client for testing.

    Args:
        mock_redis: Mock Redis fixture

    Returns:
        FakeRedis: Fake Redis client
    """
    return mock_redis
