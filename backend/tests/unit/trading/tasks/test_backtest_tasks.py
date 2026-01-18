"""Unit tests for backtest Celery tasks."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTasks, CeleryTaskStatus, Executions, StrategyConfigurations
from apps.trading.tasks.backtest import BacktestTaskRunner, _run_backtest_task_wrapper

User = get_user_model()


class TestBacktestTaskRunner(TestCase):
    """Test suite for BacktestTaskRunner.

    Tests:
    - Task runner initialization
    - Data source creation
    - Executor creation
    - Task execution with renamed models
    """

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create strategy configuration
        self.config = StrategyConfigurations.objects.create(
            name="Test Strategy",
            strategy_type="floor",
            parameters={},
            user=self.user,
        )

        # Create backtest task
        self.task = BacktestTasks.objects.create(
            name="Test Backtest",
            description="Test backtest task",
            config=self.config,
            user=self.user,
            instrument="EUR_USD",
            start_time=datetime(2024, 1, 1, tzinfo=UTC),
            end_time=datetime(2024, 1, 2, tzinfo=UTC),
            initial_balance=Decimal("10000"),
        )

    def test_runner_initialization(self):
        """Test that BacktestTaskRunner initializes correctly."""
        runner = BacktestTaskRunner()
        assert runner is not None

    def test_create_data_source(self):
        """Test data source creation for backtest."""
        runner = BacktestTaskRunner()
        runner.task = self.task

        data_source = runner._create_data_source()

        assert data_source is not None
        assert hasattr(data_source, "channel")
        assert "backtest" in data_source.channel

    def test_create_executor(self):
        """Test executor creation for backtest."""
        runner = BacktestTaskRunner()
        runner.task = self.task

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=self.task.pk,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )
        runner.execution = execution

        # Create mock data source and strategy
        data_source = Mock()
        strategy = Mock()

        executor = runner._create_executor(data_source, strategy)

        assert executor is not None
        assert executor.execution == execution
        assert executor.task == self.task

    @patch("apps.trading.tasks.backtest.ExecutionLifecycle")
    @patch("apps.trading.services.lifecycle.StrategyCreationContext")
    def test_run_creates_execution(
        self,
        mock_strategy_ctx,
        mock_lifecycle,
    ):
        """Test that run() creates an execution with correct task type."""
        # Setup mocks
        mock_strategy = Mock()
        mock_strategy_ctx.return_value.__enter__.return_value.create_strategy.return_value = (
            mock_strategy
        )

        # Mock lifecycle to prevent save issues
        mock_lifecycle_instance = Mock()
        mock_lifecycle.return_value.__enter__.return_value = mock_lifecycle_instance
        mock_lifecycle.return_value.__exit__.return_value = None

        runner = BacktestTaskRunner()

        # Mock task service
        runner.task_service = Mock()
        runner.task_service.start = Mock()
        runner.task_service.mark_stopped = Mock()

        with patch.object(runner, "_initialize_task_service"):
            with patch.object(runner, "_create_data_source"):
                with patch.object(runner, "_create_executor"):
                    runner.run(task_id=self.task.pk)

        # Verify execution was created
        execution = Executions.objects.filter(
            task_type=TaskType.BACKTEST,
            task_id=self.task.pk,
        ).first()

        assert execution is not None
        assert execution.task_type == TaskType.BACKTEST
        assert execution.task_id == self.task.pk

    def test_run_handles_missing_task(self):
        """Test that run() handles missing task gracefully."""
        runner = BacktestTaskRunner()

        # Mock task service
        runner.task_service = Mock()
        runner.task_service.start = Mock()
        runner.task_service.mark_stopped = Mock()

        with patch.object(runner, "_initialize_task_service"):
            runner.run(task_id=99999)  # Non-existent task

        # Verify task service was marked as failed
        runner.task_service.mark_stopped.assert_called_once()
        call_args = runner.task_service.mark_stopped.call_args
        assert call_args[1]["status"] == CeleryTaskStatus.Status.FAILED

    def test_wrapper_function_exists(self):
        """Test that the Celery wrapper function exists and is callable."""
        assert callable(_run_backtest_task_wrapper)

    @patch("apps.trading.tasks.backtest.BacktestTaskRunner")
    def test_wrapper_function_calls_runner(self, mock_runner_class):
        """Test that wrapper function creates runner and calls run()."""
        mock_runner = Mock()
        mock_runner.run = Mock()
        mock_runner_class.return_value = mock_runner

        # Import the actual function
        from apps.trading.tasks.backtest import _run_backtest_task_wrapper

        # Get the underlying function (not the Celery task wrapper)
        actual_function = _run_backtest_task_wrapper.__wrapped__

        # Call the actual function (no self parameter for the unwrapped function)
        actual_function(1, None)

        # Verify runner was created and run() was called
        mock_runner_class.assert_called_once()
        mock_runner.run.assert_called_once_with(1, None)

    def test_backtest_channel_for_request(self):
        """Test that backtest channel name is generated correctly."""
        runner = BacktestTaskRunner()
        request_id = "test-request-123"

        channel = runner._backtest_channel_for_request(request_id)

        assert "backtest" in channel
        assert request_id in channel

    def test_task_uses_renamed_models(self):
        """Test that task correctly uses renamed models."""
        _ = BacktestTaskRunner()

        # Verify task can be loaded with new model name
        task = BacktestTasks.objects.get(pk=self.task.pk)
        assert task is not None
        assert isinstance(task, BacktestTasks)

        # Verify execution can be created with new model name
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk,
            execution_number=1,
        )
        assert execution is not None
        assert isinstance(execution, Executions)

        # Verify config uses new model name
        assert isinstance(task.config, StrategyConfigurations)
