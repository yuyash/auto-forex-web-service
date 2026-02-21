"""Unit tests for MarketEvent model."""

from typing import Any


import pytest
from django.contrib.auth import get_user_model

from apps.market.enums import ApiType
from apps.market.models import MarketEvent, OandaAccounts

User = get_user_model()


@pytest.mark.django_db
class TestMarketEventModel:
    """Test MarketEvent model."""

    def test_create_market_event(self) -> None:
        """Test creating a market event."""
        event = MarketEvent.objects.create(
            event_type="tick_received",
            category="market",
            severity="info",
            description="Tick data received for EUR_USD",
        )

        assert event.event_type == "tick_received"
        assert event.category == "market"
        assert event.severity == "info"
        assert event.description == "Tick data received for EUR_USD"

    def test_market_event_with_user_and_account(self, user: Any) -> None:
        """Test market event with user and account."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        event = MarketEvent.objects.create(
            event_type="account_updated",
            category="account",
            severity="info",
            description="Account balance updated",
            user=user,
            account=account,
            instrument="EUR_USD",
            details={"balance": 10000.0},
        )

        assert event.user == user
        assert event.account == account
        assert event.instrument == "EUR_USD"
        assert event.details["balance"] == 10000.0

    def test_str_representation(self) -> None:
        """Test string representation."""
        event = MarketEvent.objects.create(
            event_type="test_event",
            category="test",
            severity="warning",
            description="Test event",
        )

        str_repr = str(event)
        assert "test" in str_repr
        assert "warning" in str_repr
        assert "test_event" in str_repr

    def test_ordering(self) -> None:
        """Test that events are ordered by created_at descending."""
        event1 = MarketEvent.objects.create(
            event_type="event1",
            description="First event",
        )

        event2 = MarketEvent.objects.create(
            event_type="event2",
            description="Second event",
        )

        events = list(MarketEvent.objects.all())
        assert events[0].id == event2.id
        assert events[1].id == event1.id
