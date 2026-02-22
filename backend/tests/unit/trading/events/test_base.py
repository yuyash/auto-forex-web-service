"""Unit tests for trading events base module."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

from apps.trading.enums import EventType
from apps.trading.events.base import (
    GenericStrategyEvent,
    StrategyEvent,
)


class TestStrategyEventFromDict:
    """Test StrategyEvent.from_dict factory method."""

    def test_from_dict_initial_entry(self):
        data = {
            "event_type": EventType.INITIAL_ENTRY.value,
            "direction": "long",
            "units": 1000,
            "layer_index": 0,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.INITIAL_ENTRY

    def test_from_dict_retracement(self):
        data = {
            "event_type": EventType.RETRACEMENT.value,
            "direction": "long",
            "units": 500,
            "layer_index": 0,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.RETRACEMENT

    def test_from_dict_take_profit(self):
        data = {
            "event_type": EventType.TAKE_PROFIT.value,
            "direction": "long",
            "units": 500,
            "layer_index": 0,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.TAKE_PROFIT

    def test_from_dict_unknown_type_returns_generic(self):
        data = {"event_type": "completely_unknown_type"}
        event = StrategyEvent.from_dict(data)
        assert isinstance(event, GenericStrategyEvent)

    def test_from_dict_generic_lifecycle_event(self):
        data = {"event_type": EventType.STRATEGY_STARTED.value}
        event = StrategyEvent.from_dict(data)
        assert isinstance(event, GenericStrategyEvent)

    def test_from_dict_add_layer(self):
        data = {
            "event_type": EventType.ADD_LAYER.value,
            "layer_index": 1,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.ADD_LAYER

    def test_from_dict_remove_layer(self):
        data = {
            "event_type": EventType.REMOVE_LAYER.value,
            "layer_index": 1,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.REMOVE_LAYER

    def test_from_dict_volatility_lock(self):
        data = {
            "event_type": EventType.VOLATILITY_LOCK.value,
            "direction": "short",
            "units": 1000,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.VOLATILITY_LOCK

    def test_from_dict_margin_protection(self):
        data = {
            "event_type": EventType.MARGIN_PROTECTION.value,
            "units": 500,
        }
        event = StrategyEvent.from_dict(data)
        assert event.event_type == EventType.MARGIN_PROTECTION


class TestGenericStrategyEvent:
    """Test GenericStrategyEvent class."""

    def test_to_dict(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_SIGNAL,
            timestamp=ts,
            data={"signal": "buy"},
        )
        d = event.to_dict()
        assert d["event_type"] == "strategy_signal"
        assert d["signal"] == "buy"
        assert "timestamp" in d

    def test_from_dict(self):
        data = {
            "event_type": "strategy_signal",
            "signal": "buy",
            "confidence": 0.85,
        }
        event = GenericStrategyEvent.from_dict(data)
        assert event.event_type == EventType.STRATEGY_SIGNAL
        assert event.data["signal"] == "buy"
        assert event.data["confidence"] == 0.85

    def test_from_dict_with_timestamp(self):
        ts = datetime(2024, 1, 1, tzinfo=UTC)
        data = {
            "event_type": "strategy_signal",
            "timestamp": ts,
        }
        event = GenericStrategyEvent.from_dict(data)
        assert event.timestamp == ts

    def test_activate_logs_event(self):
        event = GenericStrategyEvent(
            event_type=EventType.STRATEGY_STARTED,
            data={},
        )
        context = MagicMock()
        context.task_id = "test-id"
        context.task_type.value = "trading"
        context.instrument = "USD_JPY"
        # Should not raise
        event.activate(context)

    def test_activate_tick_received_debug_level(self):
        event = GenericStrategyEvent(
            event_type=EventType.TICK_RECEIVED,
            data={},
        )
        context = MagicMock()
        context.task_id = "test-id"
        context.task_type.value = "trading"
        context.instrument = "USD_JPY"
        event.activate(context)

    def test_activate_error_occurred_error_level(self):
        event = GenericStrategyEvent(
            event_type=EventType.ERROR_OCCURRED,
            data={},
        )
        context = MagicMock()
        context.task_id = "test-id"
        context.task_type.value = "trading"
        context.instrument = "USD_JPY"
        event.activate(context)
