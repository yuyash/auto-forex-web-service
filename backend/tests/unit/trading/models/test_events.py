"""Unit tests for trading event models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import (
    TradingEvent,
)

User = get_user_model()


@pytest.mark.django_db
class TestTradingEventModel:
    """Test TradingEvent model."""

    def test_create_trading_event(self):
        """Test creating a trading event."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        event = TradingEvent.objects.create(
            user=user,
            event_type="trade_opened",
            severity="info",
            description="Trade opened for EUR_USD",
        )

        assert event.user == user
        assert event.event_type == "trade_opened"
        assert event.severity == "info"

    def test_trading_event_with_details(self):
        """Test trading event with JSON details."""
        user = User.objects.create_user(    # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        details = {
            "instrument": "EUR_USD",
            "units": 1000,
            "price": "1.1000",
        }

        event = TradingEvent.objects.create(
            user=user,
            event_type="trade_opened",
            severity="info",
            description="Trade opened",
            details=details,
        )

        assert event.details == details
        assert event.details["instrument"] == "EUR_USD"
