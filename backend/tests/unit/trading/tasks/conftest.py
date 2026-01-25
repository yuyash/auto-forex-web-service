"""Fixtures for trading tasks tests."""

import pytest

from apps.accounts.models import User
from apps.market.models import OandaAccounts
from apps.trading.enums import StrategyType
from apps.trading.models import StrategyConfigurations


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create a test strategy configuration."""
    return StrategyConfigurations.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type=StrategyType.FLOOR,
        parameters={
            "instrument": "USD_JPY",
            "base_lot_size": 1.0,
            "retracement_pips": 30,
            "take_profit_pips": 25,
        },
    )


@pytest.fixture
def oanda_account(db, user):
    """Create a test OANDA account."""
    return OandaAccounts.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_token="test_api_token",
        api_type="practice",
        is_active=True,
    )
