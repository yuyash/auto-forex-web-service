"""Pytest fixtures for serializer tests."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import StrategyConfigurations

User = get_user_model()


@pytest.fixture
def user(db):  # type: ignore[misc]
    """Create test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]  # type: ignore[attr-defined]
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):  # type: ignore[misc]
    """Create test strategy configuration."""
    return StrategyConfigurations.objects.create(
        user=user,
        name="Test Floor Strategy",
        strategy_type="floor",
        parameters={
            "instrument": "EUR_USD",
            "lot_size": 1000,
            "max_layers": 5,
            "layer_spacing_pips": 10,
            "take_profit_pips": 50,
            "max_retracements": 3,
            "retracement_trigger_progression": "additive",
            "retracement_trigger_increment": 5,
            "lot_size_progression": "additive",
            "lot_size_increment": 500,
            "atr_period": 14,
            "atr_multiplier": 1.5,  # Use float instead of Decimal for JSON serialization
        },
        description="Test strategy configuration",
    )
