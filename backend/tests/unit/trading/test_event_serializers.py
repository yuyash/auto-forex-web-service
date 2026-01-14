"""Unit tests for event and structured data serializers.

Tests cover:
- StrategyEventSerializer: Parsing event JSON into structured format
- StructuredLogSerializer: Transforming logs into structured format
- TaskExecutionWithStructuredDataSerializer: Enhanced execution serializer
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from apps.trading.models import (
    BacktestTask,
    ExecutionStrategyEvent,
    StrategyConfig,
    TaskExecution,
)
from apps.trading.serializers import (
    StrategyEventSerializer,
    StructuredLogSerializer,
    TaskExecutionWithStructuredDataSerializer,
)


@pytest.mark.django_db
class TestStrategyEventSerializer:
    """Test cases for StrategyEventSerializer."""

    def test_parse_floor_strategy_event(self, test_user):
        """Test parsing Floor strategy event with layer_number and retracement_count."""
        # Create task and execution
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
        )

        # Create event with Floor strategy data
        event_data = {
            "event_type": "layer_added",
            "timestamp": "2025-01-01T10:00:00Z",
            "price": "1.1000",
            "layer_number": 2,
            "retracement_count": 1,
            "direction": "long",
        }

        event = ExecutionStrategyEvent.objects.create(
            execution=execution,
            sequence=0,
            event_type="layer_added",
            strategy_type="floor",
            timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            event=event_data,
        )

        # Serialize
        serializer = StrategyEventSerializer(event)
        data = serializer.data

        # Verify structured fields
        assert data["parsed_event_type"] == "layer_added"
        assert data["parsed_timestamp"] == "2025-01-01T10:00:00Z"
        assert data["common_data"]["price"] == "1.1000"
        assert data["common_data"]["direction"] == "long"
        assert data["strategy_data"]["layer_number"] == 2
        assert data["strategy_data"]["retracement_count"] == 1

    def test_parse_event_without_strategy_data(self, test_user):
        """Test parsing event with only common data."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="momentum",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
        )

        # Create event with only common data
        event_data = {
            "event_type": "trade_executed",
            "timestamp": "2025-01-01T10:00:00Z",
            "price": "1.1000",
            "units": "1000",
            "direction": "long",
        }

        event = ExecutionStrategyEvent.objects.create(
            execution=execution,
            sequence=0,
            event_type="trade_executed",
            strategy_type="momentum",
            timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            event=event_data,
        )

        # Serialize
        serializer = StrategyEventSerializer(event)
        data = serializer.data

        # Verify common data extracted
        assert data["common_data"]["price"] == "1.1000"
        assert data["common_data"]["units"] == "1000"
        assert data["common_data"]["direction"] == "long"

        # Verify strategy_data is empty or minimal
        assert "layer_number" not in data["strategy_data"]

    def test_fallback_to_model_fields(self, test_user):
        """Test fallback to model fields when event JSON is missing data."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
        )

        # Create event without timestamp in JSON
        event_data = {
            "event_type": "layer_added",
            "price": "1.1000",
        }

        event = ExecutionStrategyEvent.objects.create(
            execution=execution,
            sequence=0,
            event_type="layer_added",
            strategy_type="floor",
            timestamp=datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
            event=event_data,
        )

        # Serialize
        serializer = StrategyEventSerializer(event)
        data = serializer.data

        # Verify fallback to model timestamp
        assert data["parsed_timestamp"] == "2025-01-01T10:00:00+00:00"
        assert data["parsed_event_type"] == "layer_added"


class TestStructuredLogSerializer:
    """Test cases for StructuredLogSerializer."""

    def test_categorize_error_log(self):
        """Test categorizing error logs."""
        log_entry = {
            "timestamp": "2025-01-01T10:00:00Z",
            "level": "error",
            "message": "Failed to execute trade: Connection timeout",
        }

        serializer = StructuredLogSerializer(log_entry)
        data = serializer.data

        assert data["log_type"] == "error"  # type: ignore[index]
        assert data["level"] == "error"  # type: ignore[index]
        assert data["message"] == "Failed to execute trade: Connection timeout"  # type: ignore[index]

    def test_categorize_trade_log(self):
        """Test categorizing trade logs."""
        log_entry = {
            "timestamp": "2025-01-01T10:00:00Z",
            "level": "info",
            "message": "Trade executed: EUR_USD long 1000 units at price 1.1000",
        }

        serializer = StructuredLogSerializer(log_entry)
        data = serializer.data

        assert data["log_type"] == "trade"  # type: ignore[index]
        assert data["level"] == "info"  # type: ignore[index]

        # Verify data extraction
        extracted_data = data["data"]  # type: ignore[index]
        assert extracted_data["instrument"] == "EUR_USD"
        assert extracted_data["direction"] == "long"
        assert extracted_data["units"] == "1000"
        assert extracted_data["price"] == "1.1000"

    def test_categorize_strategy_event_log(self):
        """Test categorizing strategy event logs."""
        log_entry = {
            "timestamp": "2025-01-01T10:00:00Z",
            "level": "info",
            "message": "Strategy signal: Adding layer 2 with retracement 1",
        }

        serializer = StructuredLogSerializer(log_entry)
        data = serializer.data

        assert data["log_type"] == "strategy_event"  # type: ignore[index]

        # Verify data extraction
        extracted_data = data["data"]  # type: ignore[index]
        assert extracted_data["layer_number"] == 2
        assert extracted_data["retracement_count"] == 1

    def test_categorize_system_log(self):
        """Test categorizing system logs."""
        log_entry = {
            "timestamp": "2025-01-01T10:00:00Z",
            "level": "info",
            "message": "Execution started",
        }

        serializer = StructuredLogSerializer(log_entry)
        data = serializer.data

        assert data["log_type"] == "system"  # type: ignore[index]
        assert data["level"] == "info"  # type: ignore[index]

    def test_extract_instrument_from_message(self):
        """Test extracting instrument from log message."""
        log_entry = {
            "timestamp": "2025-01-01T10:00:00Z",
            "level": "info",
            "message": "Processing tick for USD_JPY",
        }

        serializer = StructuredLogSerializer(log_entry)
        data = serializer.data

        assert data["data"]["instrument"] == "USD_JPY"  # type: ignore[index]


@pytest.mark.django_db
class TestTaskExecutionWithStructuredDataSerializer:
    """Test cases for TaskExecutionWithStructuredDataSerializer."""

    def test_includes_structured_events(self, test_user):
        """Test that serializer includes structured events."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
        )

        # Create some events
        ExecutionStrategyEvent.objects.create(
            execution=execution,
            sequence=0,
            event_type="layer_added",
            strategy_type="floor",
            event={"event_type": "layer_added", "layer_number": 1},
        )
        ExecutionStrategyEvent.objects.create(
            execution=execution,
            sequence=1,
            event_type="retracement",
            strategy_type="floor",
            event={"event_type": "retracement", "retracement_count": 1},
        )

        # Serialize
        serializer = TaskExecutionWithStructuredDataSerializer(execution)
        data = serializer.data

        # Verify structured events included
        assert "structured_events" in data
        assert len(data["structured_events"]) == 2
        assert data["structured_events"][0]["parsed_event_type"] == "layer_added"
        assert data["structured_events"][1]["parsed_event_type"] == "retracement"

    def test_includes_structured_logs(self, test_user):
        """Test that serializer includes structured logs."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
            logs=[
                {
                    "timestamp": "2025-01-01T10:00:00Z",
                    "level": "info",
                    "message": "Execution started",
                },
                {
                    "timestamp": "2025-01-01T10:01:00Z",
                    "level": "info",
                    "message": "Trade executed: EUR_USD long 1000 units",
                },
            ],
        )

        # Serialize
        serializer = TaskExecutionWithStructuredDataSerializer(execution)
        data = serializer.data

        # Verify structured logs included
        assert "structured_logs" in data
        assert len(data["structured_logs"]) == 2
        assert data["structured_logs"][0]["log_type"] == "system"
        assert data["structured_logs"][1]["log_type"] == "trade"

    def test_limits_events_to_100(self, test_user):
        """Test that serializer limits events to most recent 100."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )
        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
        )

        # Create 150 events
        for i in range(150):
            ExecutionStrategyEvent.objects.create(
                execution=execution,
                sequence=i,
                event_type="tick_received",
                strategy_type="floor",
                event={"event_type": "tick_received"},
            )

        # Serialize
        serializer = TaskExecutionWithStructuredDataSerializer(execution)
        data = serializer.data

        # Verify limited to 100 most recent
        assert len(data["structured_events"]) == 100
        # Should be sequences 50-149 (most recent 100)
        assert data["structured_events"][0]["sequence"] == 50

    def test_limits_logs_to_100(self, test_user):
        """Test that serializer limits logs to most recent 100."""
        config = StrategyConfig.objects.create(
            user=test_user,
            name="Test Config",
            strategy_type="floor",
            parameters={"instrument": "EUR_USD"},
            description="Test",
        )
        task = BacktestTask.objects.create(
            user=test_user,
            config=config,
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            initial_balance=10000,
        )

        # Create 150 log entries
        logs = []
        for i in range(150):
            logs.append(
                {
                    "timestamp": f"2025-01-01T10:{i:02d}:00Z",
                    "level": "info",
                    "message": f"Log entry {i}",
                }
            )

        execution = TaskExecution.objects.create(
            task_type="backtest",
            task_id=task.pk,
            execution_number=1,
            logs=logs,
        )

        # Serialize
        serializer = TaskExecutionWithStructuredDataSerializer(execution)
        data = serializer.data

        # Verify limited to 100 most recent
        assert len(data["structured_logs"]) == 100
        # Should be the last 100 logs
        assert "Log entry 50" in data["structured_logs"][0]["message"]
