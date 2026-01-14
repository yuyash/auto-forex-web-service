"""Unit tests for StrategyEvent dataclass."""

from datetime import datetime

from apps.trading.enums import EventType
from apps.trading.events import GenericStrategyEvent as StrategyEvent


class TestStrategyEvent:
    """Test suite for StrategyEvent dataclass."""

    def test_create_strategy_event(self):
        """Test creating a StrategyEvent with basic data."""
        event = StrategyEvent(
            event_type=EventType.INITIAL_ENTRY,  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat("2024-01-10T12:00:00+00:00"),
            data={
                "layer_number": 1,
                "direction": "long",
                "price": "150.25",
                "units": 1000,
            },
        )

        assert event.event_type == EventType.INITIAL_ENTRY
        assert isinstance(event.timestamp, datetime)
        assert event.data["layer_number"] == 1
        assert event.data["direction"] == "long"
        assert event.data["price"] == "150.25"
        assert event.data["units"] == 1000

    def test_create_strategy_event_without_timestamp(self):
        """Test creating a StrategyEvent without timestamp."""
        event = StrategyEvent(
            event_type=EventType.ADD_LAYER,  # type: ignore[arg-type]
            data={"layer_number": 2},
        )

        assert event.event_type == EventType.ADD_LAYER
        assert event.timestamp is None
        assert event.data["layer_number"] == 2

    def test_strategy_event_to_dict(self):
        """Test converting StrategyEvent to dictionary."""
        event = StrategyEvent(
            event_type=EventType.TAKE_PROFIT,  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat("2024-01-10T12:05:00+00:00"),
            data={
                "layer_number": 1,
                "pnl": 100.50,
                "pips": 10,
                "direction": "long",
            },
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == EventType.TAKE_PROFIT.value
        assert "timestamp" in event_dict
        assert event_dict["layer_number"] == 1
        assert event_dict["pnl"] == 100.50
        assert event_dict["pips"] == 10
        assert event_dict["direction"] == "long"

    def test_strategy_event_to_dict_without_timestamp(self):
        """Test converting StrategyEvent to dictionary when timestamp is None."""
        event = StrategyEvent(
            event_type=EventType.REMOVE_LAYER,  # type: ignore[arg-type]
            data={"layer_number": 3},
        )

        event_dict = event.to_dict()

        assert event_dict["event_type"] == EventType.REMOVE_LAYER.value
        assert event_dict["layer_number"] == 3

    def test_strategy_event_from_dict(self):
        """Test creating StrategyEvent from dictionary."""
        event_dict = {
            "event_type": "retracement",
            "timestamp": "2024-01-10T12:03:00Z",
            "layer_number": 1,
            "direction": "short",
            "price": "149.75",
            "units": 500,
            "retracement_count": 2,
        }

        event = StrategyEvent.from_dict(event_dict)

        assert isinstance(event.timestamp, datetime)
        assert event.data["layer_number"] == 1
        assert event.data["direction"] == "short"
        assert event.data["price"] == "149.75"
        assert event.data["units"] == 500
        assert event.data["retracement_count"] == 2

    def test_strategy_event_from_dict_with_legacy_type_field(self):
        """Test creating StrategyEvent from dictionary with legacy 'type' field."""
        event_dict = {
            "type": "volatility_lock",  # Legacy field name
            "timestamp": "2024-01-10T12:10:00Z",
            "reason": "ATR exceeded threshold",
        }

        event = StrategyEvent.from_dict(event_dict)

        assert isinstance(event.timestamp, datetime)
        assert event.data["reason"] == "ATR exceeded threshold"

    def test_strategy_event_round_trip(self):
        """Test round-trip conversion: StrategyEvent -> dict -> StrategyEvent."""
        original = StrategyEvent(
            event_type=EventType.TAKE_PROFIT,  # type: ignore[arg-type]
            timestamp=datetime.fromisoformat("2024-01-10T12:05:00+00:00"),
            data={
                "layer_number": 1,
                "pnl": 100.50,
                "pips": 10,
            },
        )

        # Convert to dict
        event_dict = original.to_dict()

        # Convert back to StrategyEvent
        reconstructed = StrategyEvent.from_dict(event_dict)

        assert reconstructed.event_type == original.event_type
        assert isinstance(reconstructed.timestamp, datetime)
        assert reconstructed.data == original.data

    def test_strategy_event_empty_data(self):
        """Test creating StrategyEvent with empty data."""
        event = StrategyEvent(event_type=EventType.STRATEGY_STARTED)  # type: ignore[arg-type]

        assert event.event_type == EventType.STRATEGY_STARTED
        assert event.timestamp is None
        assert event.data == {}

    def test_strategy_event_from_dict_empty(self):
        """Test creating StrategyEvent from minimal dictionary."""
        event_dict = {"event_type": "strategy_stopped"}

        event = StrategyEvent.from_dict(event_dict)

        assert event.timestamp is None
        assert event.data == {}

    def test_strategy_event_with_nested_data(self):
        """Test StrategyEvent with nested data structures."""
        event = StrategyEvent(
            event_type=EventType.MARGIN_PROTECTION,  # type: ignore[arg-type]
            data={
                "reason": "margin_threshold_exceeded",
                "details": {
                    "current_margin": 0.05,
                    "threshold": 0.10,
                    "positions_closed": 2,
                },
            },
        )

        assert event.event_type == EventType.MARGIN_PROTECTION
        assert event.data["reason"] == "margin_threshold_exceeded"
        assert event.data["details"]["current_margin"] == 0.05
        assert event.data["details"]["positions_closed"] == 2

        # Test round-trip with nested data
        event_dict = event.to_dict()
        reconstructed = StrategyEvent.from_dict(event_dict)

        assert reconstructed.data["details"]["current_margin"] == 0.05
