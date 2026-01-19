"""Unit tests for renamed serializers.

Tests for serializers that were renamed as part of the refactoring:
- StrategyEventsSerializer (formerly StrategyEventSerializer)
- ExecutionsSerializer (formerly TaskExecutionSerializer)
- ExecutionsListSerializer (formerly TaskExecutionListSerializer)
- ExecutionsDetailSerializer (formerly TaskExecutionDetailSerializer)
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.trading.models import BacktestTasks, Executions, StrategyEvents
from apps.trading.serializers import (
    ExecutionsDetailSerializer,
    ExecutionsListSerializer,
    ExecutionsSerializer,
    StrategyEventsSerializer,
)


@pytest.mark.django_db
class TestStrategyEventsSerializer:
    """Test suite for StrategyEventsSerializer."""

    @pytest.fixture
    def execution(self, user, strategy_config):
        """Create a test execution."""
        backtest_task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            data_source="athena",
            start_time=timezone.now(),
            end_time=timezone.now(),
            initial_balance=Decimal("10000.00"),
            instrument="EUR_USD",
        )
        return Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

    @pytest.fixture
    def strategy_event(self, execution):
        """Create a test StrategyEvents instance."""
        return StrategyEvents.objects.create(
            execution=execution,
            sequence=1,
            event_type="initial_entry",
            strategy_type="floor",
            timestamp=timezone.now(),
            event={
                "event_type": "initial_entry",
                "layer_number": 1,
                "price": "1.1000",
                "instrument": "EUR_USD",
                "direction": "long",
            },
        )

    def test_serialization(self, strategy_event):
        """Test serialization of StrategyEvents instance."""
        serializer = StrategyEventsSerializer(strategy_event)
        data = serializer.data

        assert "sequence" in data
        assert "event_type" in data
        assert "strategy_type" in data
        assert "timestamp" in data
        assert "event" in data
        assert "created_at" in data

    def test_parsed_fields(self, strategy_event):
        """Test parsed fields from event JSON."""
        serializer = StrategyEventsSerializer(strategy_event)
        data = serializer.data

        assert "parsed_event_type" in data
        assert "parsed_timestamp" in data
        assert "common_data" in data
        assert "strategy_data" in data

        # Check parsed values
        assert data["parsed_event_type"] == "initial_entry"
        assert "price" in data["common_data"]
        assert "layer_number" in data["strategy_data"]


@pytest.mark.django_db
class TestExecutionsSerializers:
    """Test suite for Executions serializers."""

    @pytest.fixture
    def execution(self, user, strategy_config):
        """Create a test execution."""
        backtest_task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            data_source="athena",
            start_time=timezone.now(),
            end_time=timezone.now(),
            initial_balance=Decimal("10000.00"),
            instrument="EUR_USD",
        )
        return Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="completed",
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )

    def test_executions_serializer(self, execution):
        """Test ExecutionsSerializer."""
        serializer = ExecutionsSerializer(execution)
        data = serializer.data

        assert "id" in data
        assert "task_type" in data
        assert "task_id" in data
        assert "execution_number" in data
        assert "status" in data
        assert "duration" in data

    def test_executions_list_serializer(self, execution):
        """Test ExecutionsListSerializer."""
        serializer = ExecutionsListSerializer(execution)
        data = serializer.data

        assert "id" in data
        assert "task_type" in data
        assert "status" in data
        # Should not include logs
        assert "logs" not in data

    def test_executions_detail_serializer(self, execution):
        """Test ExecutionsDetailSerializer."""
        serializer = ExecutionsDetailSerializer(execution)
        data = serializer.data

        assert "id" in data
        assert "task_type" in data
        assert "status" in data
        assert "logs" in data
        assert "has_metrics" in data
        assert "error_traceback" in data

    def test_has_metrics_field(self, execution):
        """Test has_metrics field returns correct value."""
        serializer = ExecutionsDetailSerializer(execution)
        data = serializer.data

        # Should be False when no metrics exist
        assert data["has_metrics"] is False
