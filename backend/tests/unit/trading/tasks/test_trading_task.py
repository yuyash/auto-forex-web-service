"""Unit tests for trading task execution."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.tasks.trading import _execute_trading, run_trading_task, stop_trading_task


@pytest.fixture
def mock_trading_task():
    """Create a mock trading task."""
    task = Mock()
    task.pk = 1
    task.instrument = "USD_JPY"
    task._pip_size = Decimal("0.01")
    task.trading_mode = "netting"
    task.user = Mock()
    task.oanda_account = Mock()
    task.oanda_account.account_id = "test-account"
    task.oanda_account.balance = Decimal("10000")
    task.status = TaskStatus.CREATED
    task.celery_task_id = None
    task.started_at = None
    task.completed_at = None
    task.result_data = {}
    task.config = Mock()
    task.config.get_pip_size.return_value = Decimal("0.01")
    return task


class TestRunTradingTask:
    """Tests for run_trading_task."""

    @patch("apps.trading.tasks.trading._execute_trading")
    @patch("apps.trading.tasks.trading.TradingTasks")
    @patch("apps.trading.tasks.trading.TaskLog")
    def test_run_trading_task_success(
        self, mock_task_log, mock_trading_tasks, mock_execute, mock_trading_task
    ):
        """Test successful trading task execution."""
        # Setup
        mock_trading_tasks.objects.get.return_value = mock_trading_task
        mock_execute.return_value = None

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute
        run_trading_task(mock_request, task_id=1)

        # Verify task was loaded
        mock_trading_tasks.objects.get.assert_called_once_with(pk=1)

        # Verify task status was updated to RUNNING
        assert mock_trading_task.status == TaskStatus.RUNNING
        assert mock_trading_task.celery_task_id == "test-celery-id"
        assert mock_trading_task.started_at is not None

        # Verify execute was called
        mock_execute.assert_called_once_with(mock_trading_task)

        # Verify task status was updated to STOPPED
        assert mock_trading_task.status == TaskStatus.STOPPED
        assert mock_trading_task.completed_at is not None

        # Verify logs were created
        assert mock_task_log.objects.create.call_count == 2

    @patch("apps.trading.tasks.trading._execute_trading")
    @patch("apps.trading.tasks.trading.TradingTasks")
    @patch("apps.trading.tasks.trading.TaskLog")
    def test_run_trading_task_failure(
        self, mock_task_log, mock_trading_tasks, mock_execute, mock_trading_task
    ):
        """Test trading task execution failure."""
        # Setup
        mock_trading_tasks.objects.get.return_value = mock_trading_task
        mock_execute.side_effect = RuntimeError("Test error")

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute should raise exception
        with pytest.raises(RuntimeError, match="Test error"):
            run_trading_task(mock_request, task_id=1)

        # Verify task status was updated to FAILED
        assert mock_trading_task.status == TaskStatus.FAILED
        assert mock_trading_task.error_message == "Test error"
        assert mock_trading_task.error_traceback is not None

        # Verify error log was created
        error_log_calls = [
            call
            for call in mock_task_log.objects.create.call_args_list
            if call.kwargs.get("level") == LogLevel.ERROR
        ]
        assert len(error_log_calls) == 1

    @patch("apps.trading.tasks.trading.TradingTasks")
    def test_run_trading_task_not_found(self, mock_trading_tasks):
        """Test trading task not found."""
        # Setup
        from apps.trading.models import TradingTasks

        mock_trading_tasks.objects.get.side_effect = TradingTasks.DoesNotExist()

        # Create mock Celery request
        mock_request = Mock()
        mock_request.id = "test-celery-id"

        # Execute should raise exception
        with pytest.raises(TradingTasks.DoesNotExist):
            run_trading_task(mock_request, task_id=999)


class TestExecuteTrading:
    """Tests for _execute_trading."""

    @patch("apps.trading.tasks.trading.TradingExecutor")
    @patch("apps.trading.tasks.trading.TaskController")
    @patch("apps.trading.tasks.trading.LiveTickDataSource")
    @patch("apps.trading.tasks.trading.registry")
    @patch("apps.trading.tasks.trading.register_all_strategies")
    def test_execute_trading(
        self,
        mock_register,
        mock_registry,
        mock_data_source_cls,
        mock_controller_cls,
        mock_executor_cls,
        mock_trading_task,
    ):
        """Test _execute_trading creates and runs executor."""
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
        _execute_trading(mock_trading_task)

        # Verify strategies were registered
        mock_register.assert_called_once()

        # Verify strategy was created
        mock_registry.create.assert_called_once()

        # Verify data source was created
        mock_data_source_cls.assert_called_once()
        call_kwargs = mock_data_source_cls.call_args.kwargs
        assert call_kwargs["instrument"] == mock_trading_task.instrument

        # Verify controller was created
        mock_controller_cls.assert_called_once()

        # Verify executor was created
        mock_executor_cls.assert_called_once_with(
            task=mock_trading_task,
            strategy=mock_strategy,
            data_source=mock_data_source,
            controller=mock_controller,
        )

        # Verify executor was executed
        mock_executor.execute.assert_called_once()


class TestStopTradingTask:
    """Tests for stop_trading_task."""

    @patch("apps.trading.tasks.trading.CeleryTaskStatus")
    def test_stop_trading_task(self, mock_celery_status):
        """Test stop_trading_task updates status."""
        # Create mock Celery request
        mock_request = Mock()

        # Execute
        stop_trading_task(mock_request, task_id=1, mode="graceful")

        # Verify status was updated
        mock_celery_status.objects.filter.assert_called_once()
        filter_call = mock_celery_status.objects.filter.call_args
        assert filter_call.kwargs["task_name"] == "trading.tasks.run_trading_task"
        assert filter_call.kwargs["instance_key"] == "1"

        # Verify update was called
        mock_celery_status.objects.filter.return_value.update.assert_called_once()
        update_call = mock_celery_status.objects.filter.return_value.update.call_args
        assert update_call.kwargs["status"] == mock_celery_status.Status.STOP_REQUESTED
        assert "graceful" in update_call.kwargs["status_message"]
