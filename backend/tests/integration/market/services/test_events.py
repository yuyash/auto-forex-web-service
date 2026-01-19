"""Integration tests for EventService."""

from typing import Any

import pytest

from apps.market.enums import (
    ApiType,
    MarketEventCategory,
    MarketEventSeverity,
    MarketEventType,
)
from apps.market.models import MarketEvent, OandaAccounts
from apps.market.services.events import MarketEventService


@pytest.mark.django_db
class TestMarketEventServiceIntegration:
    """Integration tests for MarketEventService."""

    def test_log_event_creates_market_event(self, user: Any) -> None:
        """Test that log_event() creates MarketEvent record."""
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
        )

        service = MarketEventService()

        service.log_event(
            event_type=MarketEventType.ORDER_SUBMITTED,  # type: ignore[arg-type]
            description="Test event description",
            severity=MarketEventSeverity.INFO,
            category=MarketEventCategory.MARKET,
            user=user,
            account=account,
            instrument="EUR_USD",
            details={"key": "value"},
        )

        # Verify event was created
        event = MarketEvent.objects.filter(event_type=str(MarketEventType.ORDER_SUBMITTED)).first()

        assert event is not None
        assert event.category == str(MarketEventCategory.MARKET)
        assert event.severity == str(MarketEventSeverity.INFO)
        assert event.user == user
        assert event.account == account
        assert event.instrument == "EUR_USD"
        assert event.details["key"] == "value"

    def test_log_event_without_optional_fields(self) -> None:
        """Test logging event without optional fields."""
        service = MarketEventService()

        service.log_event(
            event_type=MarketEventType.ORDER_FAILED,  # type: ignore[arg-type]
            description="Simple event",
            severity=MarketEventSeverity.WARNING,
            category=MarketEventCategory.MARKET,
        )

        # Verify event was created
        event = MarketEvent.objects.filter(event_type=str(MarketEventType.ORDER_FAILED)).first()

        assert event is not None
        assert event.user is None
        assert event.account is None
        assert event.instrument == ""

    def test_log_trading_event(self, user: Any) -> None:
        """Test logging trading event."""
        service = MarketEventService()

        service.log_trading_event(
            event_type=MarketEventType.ORDER_SUBMITTED,  # type: ignore[arg-type]
            description="Trade executed",
            user=user,
        )

        # Verify event was created with trading category
        event = MarketEvent.objects.filter(event_type=str(MarketEventType.ORDER_SUBMITTED)).first()

        assert event is not None
        assert event.category == str(MarketEventCategory.TRADING)
