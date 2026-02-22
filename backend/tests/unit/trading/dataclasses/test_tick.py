"""Unit tests for trading dataclasses tick."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from apps.trading.dataclasses.tick import Tick


class TestTick:
    """Test Tick dataclass."""

    def test_create_tick(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick(
            instrument="USD_JPY",
            timestamp=ts,
            bid=Decimal("150.25"),
            ask=Decimal("150.27"),
            mid=Decimal("150.26"),
        )
        assert tick.instrument == "USD_JPY"
        assert tick.bid == Decimal("150.25")
        assert tick.ask == Decimal("150.27")
        assert tick.mid == Decimal("150.26")

    def test_frozen(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick(
            instrument="USD_JPY",
            timestamp=ts,
            bid=Decimal("150"),
            ask=Decimal("151"),
            mid=Decimal("150.5"),
        )
        with pytest.raises(AttributeError):
            tick.bid = Decimal("999")

    def test_auto_mid_calculation(self):
        """Mid is recalculated when passed as 0."""
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick(
            instrument="EUR_USD",
            timestamp=ts,
            bid=Decimal("1.1000"),
            ask=Decimal("1.1002"),
            mid=Decimal("0"),
        )
        assert tick.mid == Decimal("1.1001")


class TestTickCreate:
    """Test Tick.create static method."""

    def test_create_with_mid(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick.create("EUR_USD", ts, Decimal("1.1"), Decimal("1.2"), Decimal("1.15"))
        assert tick.mid == Decimal("1.15")

    def test_create_without_mid(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick.create("EUR_USD", ts, Decimal("1.1000"), Decimal("1.1002"))
        assert tick.mid == Decimal("1.1001")


class TestTickFromDict:
    """Test Tick.from_dict static method."""

    def test_from_dict_valid(self):
        data = {
            "instrument": "USD_JPY",
            "timestamp": "2024-01-01T00:00:00Z",
            "bid": "150.25",
            "ask": "150.27",
            "mid": "150.26",
        }
        tick = Tick.from_dict(data)
        assert tick.instrument == "USD_JPY"
        assert tick.bid == Decimal("150.25")

    def test_from_dict_missing_instrument(self):
        with pytest.raises(ValueError, match="instrument"):
            Tick.from_dict(
                {"timestamp": "2024-01-01T00:00:00Z", "bid": "1", "ask": "2", "mid": "1.5"}
            )

    def test_from_dict_missing_timestamp(self):
        with pytest.raises(ValueError, match="timestamp"):
            Tick.from_dict({"instrument": "EUR_USD", "bid": "1", "ask": "2", "mid": "1.5"})

    def test_from_dict_missing_prices(self):
        with pytest.raises(ValueError, match="prices"):
            Tick.from_dict({"instrument": "EUR_USD", "timestamp": "2024-01-01T00:00:00Z"})

    def test_from_dict_datetime_object(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        data = {"instrument": "EUR_USD", "timestamp": ts, "bid": "1.1", "ask": "1.2", "mid": "1.15"}
        tick = Tick.from_dict(data)
        assert tick.timestamp == ts


class TestTickToDict:
    """Test Tick.to_dict method."""

    def test_to_dict(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        tick = Tick(
            instrument="EUR_USD",
            timestamp=ts,
            bid=Decimal("1.1"),
            ask=Decimal("1.2"),
            mid=Decimal("1.15"),
        )
        d = tick.to_dict()
        assert d["instrument"] == "EUR_USD"
        assert d["bid"] == "1.1"
        assert d["ask"] == "1.2"
        assert d["mid"] == "1.15"
        assert "timestamp" in d
