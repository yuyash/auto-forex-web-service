"""Unit tests for EventEmitter service."""

import pytest

from apps.trading.dataclasses import EventContext, Tick
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import ExecutionStrategyEvent, TaskExecution
from apps.trading.services.events import EventEmitter


@pytest.fixture
def execution(db):
    """Create a test execution."""
    return TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=1,
        execution_number=1,
        status=TaskStatus.RUNNING,
    )


@pytest.fixture
def event_context(execution, test_user):
    """Create a test event context."""
    return EventContext(
        execution=execution,
        user=test_user,
        account=None,
        instrument="USD_JPY",
    )


@pytest.fixture
def event_emitter(event_context):
    """Create an EventEmitter instance."""
    return EventEmitter(event_context)


@pytest.mark.django_db
class TestEventEmitter:
    """Test suite for EventEmitter class."""

    def test_initialization(self, event_context):
        """Test EventEmitter initialization."""
        emitter = EventEmitter(event_context)
        assert emitter.context == event_context

    def test_emit_tick_received(self, event_emitter, execution):
        """Test emitting a tick_received event."""
        tick = Tick(
            instrument="USD_JPY",
            timestamp="2024-01-01T12:00:00Z",
            bid="150.123",
            ask="150.125",
            mid="150.124",
        )

        event = event_emitter.emit_tick_received(tick)

        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "tick_received"
        assert event.event["type"] == "tick_received"
        assert event.event["instrument"] == "USD_JPY"
        assert event.event["bid"] == "150.123"
        assert event.event["ask"] == "150.125"
        assert event.event["mid"] == "150.124"

    def test_emit_strategy_event(self, event_emitter, execution):
        """Test emitting a strategy event."""
        event_data = {
            "signal": "buy",
            "confidence": 0.85,
            "layer_number": 1,
        }

        event = event_emitter.emit_strategy_event(
            event_type="signal",
            strategy_type="floor",
            event_data=event_data,
        )

        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "signal"
        assert event.strategy_type == "floor"
        assert event.event["type"] == "signal"
        assert event.event["signal"] == "buy"
        assert event.event["confidence"] == 0.85
        assert event.event["layer_number"] == 1

    def test_emit_trade_executed(self, event_emitter, execution):
        """Test emitting a trade_executed event."""
        trade_data = {
            "direction": "long",
            "units": 1000,
            "price": "150.123",
            "order_id": "12345",
        }

        event = event_emitter.emit_trade_executed(trade_data)

        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "trade_executed"
        assert event.event["type"] == "trade_executed"
        assert event.event["instrument"] == "USD_JPY"
        assert event.event["direction"] == "long"
        assert event.event["units"] == 1000
        assert event.event["price"] == "150.123"
        assert event.event["order_id"] == "12345"

    def test_emit_status_changed(self, event_emitter, execution):
        """Test emitting a status_changed event."""
        event = event_emitter.emit_status_changed(
            from_status="RUNNING",
            to_status="PAUSED",
            reason="User requested pause",
        )

        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "status_changed"
        assert event.event["type"] == "status_changed"
        assert event.event["from_status"] == "RUNNING"
        assert event.event["to_status"] == "PAUSED"
        assert event.event["reason"] == "User requested pause"

    def test_emit_error(self, event_emitter, execution):
        """Test emitting an error event."""
        error = ValueError("Invalid configuration")
        error_context = {"config_key": "max_layers", "value": -1}

        event = event_emitter.emit_error(error, error_context)

        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "error_occurred"
        assert event.event["type"] == "error_occurred"
        assert event.event["error_type"] == "ValueError"
        assert event.event["error_message"] == "Invalid configuration"
        assert event.event["context"]["config_key"] == "max_layers"
        assert event.event["context"]["value"] == -1

    def test_sequence_numbers_are_monotonic(self, event_emitter, execution):
        """Test that sequence numbers increase monotonically."""
        tick = Tick(
            instrument="USD_JPY",
            timestamp="2024-01-01T12:00:00Z",
            bid="150.123",
            ask="150.125",
            mid="150.124",
        )

        # Emit multiple events
        event1 = event_emitter.emit_tick_received(tick)
        event2 = event_emitter.emit_status_changed("RUNNING", "PAUSED")
        event3 = event_emitter.emit_tick_received(tick)

        assert event1.sequence == 0
        assert event2.sequence == 1
        assert event3.sequence == 2

    def test_events_are_persisted(self, event_emitter, execution):
        """Test that events are persisted to the database."""
        tick = Tick(
            instrument="USD_JPY",
            timestamp="2024-01-01T12:00:00Z",
            bid="150.123",
            ask="150.125",
            mid="150.124",
        )

        event_emitter.emit_tick_received(tick)

        # Query the database
        events = ExecutionStrategyEvent.objects.filter(execution=execution)
        assert events.count() == 1
        first_event = events.first()
        assert first_event is not None
        assert first_event.event_type == "tick_received"

    def test_timestamp_parsing(self, event_emitter):
        """Test timestamp parsing from ISO format."""
        # Test with Z suffix
        dt1 = event_emitter._parse_timestamp("2024-01-01T12:00:00Z")
        assert dt1.year == 2024
        assert dt1.month == 1
        assert dt1.day == 1

        # Test with timezone offset
        dt2 = event_emitter._parse_timestamp("2024-01-01T12:00:00+00:00")
        assert dt2.year == 2024

    def test_emit_error_without_context(self, event_emitter, execution):
        """Test emitting an error without context."""
        error = RuntimeError("Something went wrong")

        event = event_emitter.emit_error(error)

        assert event.event["error_type"] == "RuntimeError"
        assert event.event["error_message"] == "Something went wrong"
        assert event.event["context"] == {}
