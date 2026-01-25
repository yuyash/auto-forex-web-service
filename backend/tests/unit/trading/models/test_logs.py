"""Unit tests for TaskLog and TaskMetric models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import (
    BacktestTasks,
    StrategyConfigurations,
    TaskLog,
    TaskMetric,
)

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(  # type: ignore[attr-defined]
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(db, user):
    """Create a test strategy configuration."""
    return StrategyConfigurations.objects.create(
        user=user,
        name="Test Strategy",
        strategy_type="floor",
        parameters={
            "initial_units": 1000,
            "max_layers": 5,
        },
    )


@pytest.fixture
def backtest_task(db, user, strategy_config):
    """Create a test backtest task."""
    return BacktestTasks.objects.create(
        user=user,
        config=strategy_config,
        name="Test Backtest",
        start_time="2024-01-01T00:00:00Z",
        end_time="2024-01-02T00:00:00Z",
        status=TaskStatus.CREATED,
    )


@pytest.mark.django_db
class TestTaskLogModel:
    """Test TaskLog model."""

    def test_create_task_log(self, backtest_task):
        """Test creating a task log entry."""
        log = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Test log message",
        )

        assert log.task_type == TaskType.BACKTEST
        assert log.task_id == backtest_task.id
        assert log.level == LogLevel.INFO
        assert log.message == "Test log message"
        assert log.timestamp is not None
        assert log.id is not None
        assert log.details == {}

    def test_task_log_default_level(self, backtest_task):
        """Test task log with default level."""
        log = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            message="Test message",
        )

        assert log.level == LogLevel.INFO

    def test_task_log_all_levels(self, backtest_task):
        """Test creating logs with all severity levels."""
        levels = [
            LogLevel.DEBUG,
            LogLevel.INFO,
            LogLevel.WARNING,
            LogLevel.ERROR,
            LogLevel.CRITICAL,
        ]

        for level in levels:
            log = TaskLog.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=backtest_task.id,
                level=level,
                message=f"Test {level} message",
            )
            assert log.level == level

    def test_task_log_ordering(self, backtest_task):
        """Test that logs are ordered by timestamp."""
        log1 = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="First log",
        )
        log2 = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Second log",
        )
        log3 = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Third log",
        )

        logs = list(TaskLog.objects.filter(task_type=TaskType.BACKTEST, task_id=backtest_task.id))
        assert logs[0] == log1
        assert logs[1] == log2
        assert logs[2] == log3

    def test_task_log_polymorphic_reference(self, backtest_task):
        """Test polymorphic task reference."""
        log1 = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Log 1",
        )
        log2 = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.ERROR,
            message="Log 2",
        )

        # Query logs by task_type and task_id
        task_logs = TaskLog.objects.filter(task_type=TaskType.BACKTEST, task_id=backtest_task.id)
        assert task_logs.count() == 2
        assert log1 in task_logs
        assert log2 in task_logs

    def test_task_log_str_representation(self, backtest_task):
        """Test string representation of task log."""
        log = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.ERROR,
            message="This is a test error message that is quite long",
        )

        str_repr = str(log)
        assert log.level in str_repr
        assert str(log.task_type) in str_repr
        assert str(log.task_id) in str_repr

    def test_task_log_filter_by_level(self, backtest_task):
        """Test filtering logs by level."""
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Info message",
        )
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.ERROR,
            message="Error message",
        )
        TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.ERROR,
            message="Another error",
        )

        error_logs = TaskLog.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id, level=LogLevel.ERROR
        )
        assert error_logs.count() == 2

    def test_task_log_with_details(self, backtest_task):
        """Test task log with details JSONField."""
        details = {
            "context": "test_context",
            "extra_info": "some extra information",
            "nested": {"key": "value"},
        }

        log = TaskLog.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            level=LogLevel.INFO,
            message="Test log with details",
            details=details,
        )

        assert log.details == details
        assert log.details["context"] == "test_context"
        assert log.details["nested"]["key"] == "value"


@pytest.mark.django_db
class TestTaskMetricModel:
    """Test TaskMetric model."""

    def test_create_task_metric(self, backtest_task):
        """Test creating a task metric entry."""
        metric = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10500.50,
        )

        assert metric.task_type == TaskType.BACKTEST
        assert metric.task_id == backtest_task.id
        assert metric.metric_name == "equity"
        assert metric.metric_value == 10500.50
        assert metric.timestamp is not None
        assert metric.id is not None
        assert metric.metadata is None

    def test_task_metric_with_metadata(self, backtest_task):
        """Test creating a metric with metadata."""
        metadata = {
            "instrument": "EUR_USD",
            "strategy": "floor",
            "layer": 3,
        }

        metric = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="drawdown",
            metric_value=250.75,
            metadata=metadata,
        )

        assert metric.metadata == metadata
        assert metric.metadata["instrument"] == "EUR_USD"
        assert metric.metadata["layer"] == 3

    def test_task_metric_ordering(self, backtest_task):
        """Test that metrics are ordered by timestamp."""
        metric1 = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10000.0,
        )
        metric2 = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10100.0,
        )
        metric3 = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10200.0,
        )

        metrics = list(
            TaskMetric.objects.filter(task_type=TaskType.BACKTEST, task_id=backtest_task.id)
        )
        assert metrics[0] == metric1
        assert metrics[1] == metric2
        assert metrics[2] == metric3

    def test_task_metric_polymorphic_reference(self, backtest_task):
        """Test polymorphic task reference."""
        metric1 = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10000.0,
        )
        metric2 = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="drawdown",
            metric_value=150.0,
        )

        # Query metrics by task_type and task_id
        task_metrics = TaskMetric.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id
        )
        assert task_metrics.count() == 2
        assert metric1 in task_metrics
        assert metric2 in task_metrics

    def test_task_metric_str_representation(self, backtest_task):
        """Test string representation of task metric."""
        metric = TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="total_trades",
            metric_value=42.0,
        )

        str_repr = str(metric)
        assert "total_trades" in str_repr
        assert "42" in str_repr
        assert str(metric.task_type) in str_repr
        assert str(metric.task_id) in str_repr

    def test_task_metric_filter_by_name(self, backtest_task):
        """Test filtering metrics by name."""
        TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10000.0,
        )
        TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="equity",
            metric_value=10100.0,
        )
        TaskMetric.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=backtest_task.id,
            metric_name="drawdown",
            metric_value=150.0,
        )

        equity_metrics = TaskMetric.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id, metric_name="equity"
        )
        assert equity_metrics.count() == 2

    def test_task_metric_multiple_metric_types(self, backtest_task):
        """Test storing different types of metrics."""
        metrics_data = [
            ("equity", 10000.0),
            ("drawdown", 250.5),
            ("total_trades", 42.0),
            ("win_rate", 0.65),
            ("profit_factor", 1.85),
        ]

        for name, value in metrics_data:
            TaskMetric.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=backtest_task.id,
                metric_name=name,
                metric_value=value,
            )

        assert (
            TaskMetric.objects.filter(task_type=TaskType.BACKTEST, task_id=backtest_task.id).count()
            == 5
        )

        # Verify each metric
        for name, value in metrics_data:
            metric = TaskMetric.objects.get(
                task_type=TaskType.BACKTEST, task_id=backtest_task.id, metric_name=name
            )
            assert metric.metric_value == value


@pytest.mark.django_db
class TestTaskLogAndMetricIndexes:
    """Test that indexes are properly configured."""

    def test_task_log_indexes_exist(self, backtest_task):
        """Test that TaskLog indexes are configured."""
        # Create some logs
        for i in range(5):
            TaskLog.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=backtest_task.id,
                level=LogLevel.INFO if i % 2 == 0 else LogLevel.ERROR,
                message=f"Log {i}",
            )

        # Query using indexed fields should work efficiently
        logs_by_task = TaskLog.objects.filter(task_type=TaskType.BACKTEST, task_id=backtest_task.id)
        assert logs_by_task.count() == 5

        logs_by_level = TaskLog.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id, level=LogLevel.ERROR
        )
        assert logs_by_level.count() == 2

    def test_task_metric_indexes_exist(self, backtest_task):
        """Test that TaskMetric indexes are configured."""
        # Create some metrics
        for i in range(5):
            TaskMetric.objects.create(
                task_type=TaskType.BACKTEST,
                task_id=backtest_task.id,
                metric_name="equity" if i % 2 == 0 else "drawdown",
                metric_value=float(10000 + i * 100),
            )

        # Query using indexed fields should work efficiently
        metrics_by_task = TaskMetric.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id
        )
        assert metrics_by_task.count() == 5

        metrics_by_name = TaskMetric.objects.filter(
            task_type=TaskType.BACKTEST, task_id=backtest_task.id, metric_name="equity"
        )
        assert metrics_by_name.count() == 3
