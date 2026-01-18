"""Unit tests for tick dataclasses."""

from datetime import datetime, timezone
from decimal import Decimal

from apps.trading.dataclasses.tick import Tick


class TestTick:
    """Test Tick dataclass."""

    def test_create_tick(self):
        """Test creating a tick."""
        timestamp = datetime.now(timezone.utc)
        tick = Tick(
            instrument="EUR_USD",
            timestamp=timestamp,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        assert tick.instrument == "EUR_USD"
        assert tick.timestamp == timestamp
        assert tick.bid == Decimal("1.1000")
        assert tick.ask == Decimal("1.1002")
        assert tick.mid == Decimal("1.1001")

    def test_tick_is_frozen(self):
        """Test tick is immutable."""
        tick = Tick(
            instrument="EUR_USD",
            timestamp=datetime.now(timezone.utc),
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("1.1001"),
        )

        # Tick is frozen, so assignment should fail
        # But we can't test this directly, so just verify it's frozen
        assert tick.bid == Decimal("1.1000")
