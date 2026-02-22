"""Unit tests for floor strategy event factory."""

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.enums import EventType
from apps.trading.strategies.floor.enums import Direction
from apps.trading.strategies.floor.events import EventFactory


class TestEventFactory:
    def test_create_initial_entry(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_initial_entry(
            ts, 1, Direction.LONG, Decimal("150"), Decimal("1000")
        )
        assert event.event_type == EventType.INITIAL_ENTRY

    def test_create_retracement(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_retracement(ts, 1, 2, Decimal("149"), Decimal("500"))
        assert event.event_type == EventType.RETRACEMENT

    def test_create_take_profit(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_take_profit(
            ts, 1, Decimal("151"), Decimal("1000"), Decimal("10"), Decimal("100")
        )
        assert event.event_type == EventType.TAKE_PROFIT

    def test_create_margin_protection(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_margin_protection(ts, Decimal("0.85"), Decimal("500"))
        assert event.event_type == EventType.MARGIN_PROTECTION

    def test_create_layer_created(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_layer_created(ts, 2)
        assert event.event_type == EventType.ADD_LAYER

    def test_create_layer_closed(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = EventFactory.create_layer_closed(ts, 2)
        assert event.event_type == EventType.REMOVE_LAYER
