"""Unit tests for backtest task execution."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.tasks.backtest import (
    _execute_backtest,
    _trigger_backtest_publisher,
    run_backtest_task,
)


@pytest.fixture
def mock_backtest_task():
    """Create a mock backtest task."""
    task = Mock()
    task.pk = 1
    task.instrument = "USD_JPY"
    task._pip_size = Decimal("0.01")
    task.trading_mode = "netting"
    task.user = Mock()
    task.initial_balance = Decimal("10000")
    task.start_time = timezone.now()
    task.end_time = timezone.now()
    task.data_source = "postgresql"
    task.status = TaskStatus.CREATED
    task.celery_task_id = None
    task.started_at = None
    task.completed_at = None
    task.result_data = {}
    task.config = Mock()
    task.config.get_pip_size.return_value = Decimal("0.01")
    return task


class TestRunBacktestTask:
    """Tests for run_backtest_task."""

    @patch("apps.trading.tasks.backtest._execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTasks")
    @patch("apps.trading.tasks.backtest.TaskLog")
    def test_run_backtest_task_success(
        self, mock_task_log, mock_backtest_tasks, mock_execute, mock_backtest_task
    ):
        """Test successful backtest task execution."""
        # Setup
        mock_backtest_tasks.objects.get.return_value = mock_backtest_task
        mock_execute.return_value = None

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute
        run_backtest_task(mock_request, task_id=1)

        # Verify task was loaded
        mock_backtest_tasks.objects.get.assert_called_once_with(pk=1)

        # Verify task status was updated to RUNNING
        assert mock_backtest_task.status == TaskStatus.RUNNING
        assert mock_backtest_task.celery_task_id == "test-celery-id"
        assert mock_backtest_task.started_at is not None

        # Verify execute was called
        mock_execute.assert_called_once_with(mock_backtest_task)

        # Verify task status was updated to COMPLETED
        assert mock_backtest_task.status == TaskStatus.COMPLETED
        assert mock_backtest_task.completed_at is not None

        # Verify logs were created
        assert mock_task_log.objects.create.call_count == 2

    @patch("apps.trading.tasks.backtest._execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTasks")
    @patch("apps.trading.tasks.backtest.TaskLog")
    def test_run_backtest_task_failure(
        self, mock_task_log, mock_backtest_tasks, mock_execute, mock_backtest_task
    ):
        """Test backtest task execution failure."""
        # Setup
        mock_backtest_tasks.objects.get.return_value = mock_backtest_task
        mock_execute.side_effect = RuntimeError("Test error")

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute should raise exception
        with pytest.raises(RuntimeError, match="Test error"):
            run_backtest_task(mock_request, task_id=1)

        # Verify task status was updated to FAILED
        assert mock_backtest_task.status == TaskStatus.FAILED
        assert mock_backtest_task.error_message == "Test error"
        assert mock_backtest_task.error_traceback is not None

        # Verify error log was created
        error_log_calls = [
            call
            for call in mock_task_log.objects.create.call_args_list
            if call.kwargs.get("level") == LogLevel.ERROR
        ]
        assert len(error_log_calls) == 1

    @patch("apps.trading.tasks.backtest.BacktestTasks")
    def test_run_backtest_task_not_found(self, mock_backtest_tasks):
        """Test backtest task not found."""
        # Setup
        from apps.trading.models import BacktestTasks

        mock_backtest_tasks.objects.get.side_effect = BacktestTasks.DoesNotExist()

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute should raise exception
        with pytest.raises(BacktestTasks.DoesNotExist):
            run_backtest_task(mock_request, task_id=999)


class TestExecuteBacktest:
    """Tests for _execute_backtest."""

    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.TaskController")
    @patch("apps.trading.tasks.backtest.RedisTickDataSource")
    @patch("apps.trading.tasks.backtest.registry")
    @patch("apps.trading.tasks.backtest.register_all_strategies")
    def test_execute_backtest(
        self,
        mock_register,
        mock_registry,
        mock_data_source_cls,
        mock_controller_cls,
        mock_executor_cls,
        mock_backtest_task,
    ):
        """Test _execute_backtest creates and runs executor."""
        # Setup mocks
        mock_strategy = Mock()
        mock_registry.create.return_value = mock_strategy

        mock_data_source = Mock()
        mock_data_source_cls.return_value = mock_data_source

        mock_controller = Mock()
        mock_controller_cls.return_value = mock_controller

        mock_executor = Mock()
        mock_executor_cls.return_value = mock_executor

        # Execute
        _execute_backtest(mock_backtest_task)

        # Verify strategies were registered
        mock_register.assert_called_once()

        # Verify strategy was created
        mock_registry.create.assert_called_once()

        # Verify data source was created
        mock_data_source_cls.assert_called_once()

        # Verify controller was created
        mock_controller_cls.assert_called_once()

        # Verify executor was created
        mock_executor_cls.assert_called_once_with(
            task=mock_backtest_task,
            strategy=mock_strategy,
            data_source=mock_data_source,
            controller=mock_controller,
        )

        # Verify executor was executed
        mock_executor.execute.assert_called_once()


class TestTriggerBacktestPublisher:
    """Tests for _trigger_backtest_publisher."""

    @patch("apps.trading.tasks.backtest.publish_backtest_ticks")
    def test_trigger_backtest_publisher(self, mock_publish, mock_backtest_task):
        """Test _trigger_backtest_publisher triggers async task."""
        # Execute
        _trigger_backtest_publisher(mock_backtest_task)

        # Verify publish task was called
        mock_publish.delay.assert_called_once()

        # Verify correct parameters
        call_kwargs = mock_publish.delay.call_args.kwargs
        assert call_kwargs["channel"] == f"backtest:{mock_backtest_task.pk}"
        assert call_kwargs["instrument"] == mock_backtest_task.instrument
        assert call_kwargs["data_source"] == mock_backtest_task.data_source
