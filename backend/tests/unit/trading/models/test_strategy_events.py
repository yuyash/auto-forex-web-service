"""Unit tests for StrategyEvents model."""

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, StrategyEvents


@pytest.mark.django_db
class TestStrategyEventsModel:
    """Test suite for StrategyEvents model."""

    @pytest.fixture
    def execution(self):
        """Create a test execution."""
        return Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

    def test_create_strategy_event_with_valid_data(self, execution):
        """Test creating StrategyEvents with valid fields."""
        timestamp = timezone.now()
        event_data = {
            "signal": "BUY",
            "price": 1.1234,
            "reason": "MA crossover",
        }

        event = StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            strategy_type="floor",
            timestamp=timestamp,
            event=event_data,
        )

        assert event.id is not None
        assert event.execution == execution
        assert event.sequence == 0
        assert event.event_type == "signal_generated"
        assert event.strategy_type == "floor"
        assert event.timestamp == timestamp
        assert event.event == event_data
        assert event.created_at is not None

    def test_unique_constraint_on_execution_sequence(self, execution):
        """Test that (execution, sequence) must be unique."""
        # Create first event
        StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            event={"signal": "BUY"},
        )

        # Attempt to create duplicate with same execution and sequence
        with pytest.raises(IntegrityError):
            StrategyEvents.objects.create(
                execution=execution,
                sequence=0,  # Same sequence
                event_type="position_opened",
                event={"signal": "SELL"},
            )

    def test_related_name_access_from_execution(self, execution):
        """Test accessing StrategyEvents from Execution via related_name."""
        # Create multiple events
        StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            event={"signal": "BUY"},
        )
        StrategyEvents.objects.create(
            execution=execution,
            sequence=1,
            event_type="position_opened",
            event={"units": 1000},
        )

        # Access via related_name
        events = list(execution.strategy_events.all())
        assert len(events) == 2
        assert events[0].sequence == 0
        assert events[1].sequence == 1

    def test_cascade_delete_on_execution_delete(self, execution):
        """Test that strategy events are deleted when execution is deleted."""
        StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            event={"signal": "BUY"},
        )

        assert StrategyEvents.objects.filter(execution=execution).count() == 1

        # Delete execution
        execution.delete()

        # Events should be deleted
        assert StrategyEvents.objects.count() == 0

    def test_optional_timestamp_field(self, execution):
        """Test that timestamp field is optional."""
        event = StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            event={"signal": "BUY"},
            # timestamp not provided
        )

        assert event.timestamp is None

    def test_strategy_type_filtering(self, execution):
        """Test filtering events by strategy_type."""
        StrategyEvents.objects.create(
            execution=execution,
            sequence=0,
            event_type="signal_generated",
            strategy_type="floor",
            event={"signal": "BUY"},
        )
        StrategyEvents.objects.create(
            execution=execution,
            sequence=1,
            event_type="signal_generated",
            strategy_type="momentum",
            event={"signal": "SELL"},
        )

        floor_events = StrategyEvents.objects.filter(strategy_type="floor")
        assert floor_events.count() == 1
        assert floor_events.first().sequence == 0
