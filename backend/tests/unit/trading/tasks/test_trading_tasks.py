"""Unit tests for trading Celery tasks."""

from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.market.models import OandaAccounts
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import (
    CeleryTaskStatus,
    Executions,
    StrategyConfigurations,
    TradingTasks,
)
from apps.trading.tasks.trading import TradingTaskRunner

User = get_user_model()


class TestTradingTaskRunner(TestCase):
    """Test suite for TradingTaskRunner.

    Tests:
    - Task runner initialization
    - Data source creation
    - Executor creation
    - Task execution with renamed models
    - Stop functionality
    """

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

        # Create OANDA account
        self.oanda_account = OandaAccounts.objects.create(
            user=self.user,
            account_id="001-001-1234567-001",
            api_token="test-api-token",
            currency="USD",
        )

        # Create strategy configuration
        self.config = StrategyConfigurations.objects.create(
            name="Test Strategy",
            strategy_type="floor",
            parameters={},
            user=self.user,
        )

        # Create trading task
        self.task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            config=self.config,
            user=self.user,
            oanda_account=self.oanda_account,
            instrument="EUR_USD",
        )

    def test_runner_initialization(self):
        """Test that TradingTaskRunner initializes correctly."""
        runner = TradingTaskRunner()
        assert runner is not None

    def test_create_data_source(self):
        """Test data source creation for trading."""
        runner = TradingTaskRunner()
        runner.task = self.task

        data_source = runner._create_data_source()

        assert data_source is not None
        assert hasattr(data_source, "channel")
        assert hasattr(data_source, "instrument")
        assert data_source.instrument == "EUR_USD"

    def test_create_executor(self):
        """Test executor creation for trading."""
        runner = TradingTaskRunner()
        runner.task = self.task

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=self.task.pk,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )
        runner.execution = execution

        # Create mock data source and strategy
        data_source = Mock()
        strategy = Mock()

        with patch("apps.market.services.oanda.OandaService"):
            executor = runner._create_executor(data_source, strategy)

        assert executor is not None
        assert executor.execution == execution
        assert executor.task == self.task

    def test_stop_updates_celery_task_status(self):
        """Test that stop() updates CeleryTaskStatus correctly."""
        # Create CeleryTaskStatus record
        task_name = "trading.tasks.run_trading_task"
        instance_key = str(self.task.pk)  # type: ignore[attr-defined]

        CeleryTaskStatus.objects.create(
            task_name=task_name,
            instance_key=instance_key,
            status=CeleryTaskStatus.Status.RUNNING,
        )

        runner = TradingTaskRunner()
        runner.stop(
            task_id=self.task.pk,  # type: ignore[attr-defined]
            mode="graceful",
        )

        # Verify status was updated
        status = CeleryTaskStatus.objects.get(
            task_name=task_name,
            instance_key=instance_key,
        )
        assert status.status == CeleryTaskStatus.Status.STOP_REQUESTED
        assert "graceful" in status.status_message

    def test_stop_with_different_modes(self):
        """Test stop() with different stop modes."""
        task_name = "trading.tasks.run_trading_task"
        instance_key = str(self.task.pk)  # type: ignore[attr-defined]

        for mode in ["immediate", "graceful", "graceful_close"]:
            # Create fresh status record
            CeleryTaskStatus.objects.filter(
                task_name=task_name,
                instance_key=instance_key,
            ).delete()

            CeleryTaskStatus.objects.create(
                task_name=task_name,
                instance_key=instance_key,
                status=CeleryTaskStatus.Status.RUNNING,
            )

            runner = TradingTaskRunner()
            runner.stop(
                task_id=self.task.pk,  # type: ignore[attr-defined]
                mode=mode,
            )

            # Verify status was updated with correct mode
            status = CeleryTaskStatus.objects.get(
                task_name=task_name,
                instance_key=instance_key,
            )
            assert status.status == CeleryTaskStatus.Status.STOP_REQUESTED
            assert mode in status.status_message

    def test_task_uses_renamed_models(self):
        """Test that task correctly uses renamed models."""
        _ = TradingTaskRunner()

        # Verify task can be loaded with new model name
        task = TradingTasks.objects.get(pk=self.task.pk)  # type: ignore[attr-defined]
        assert task is not None
        assert isinstance(task, TradingTasks)

        # Verify execution can be created with new model name
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,  # type: ignore[attr-defined]
            execution_number=1,
        )
        assert execution is not None
        assert isinstance(execution, Executions)

        # Verify config uses new model name
        assert isinstance(task.config, StrategyConfigurations)

    def test_run_method_is_shared_task(self):
        """Test that run() method is decorated as shared_task."""
        runner = TradingTaskRunner()

        # Verify the method has Celery task attributes
        assert hasattr(runner.run, "delay")
        assert hasattr(runner.run, "apply_async")

    def test_stop_method_is_shared_task(self):
        """Test that stop() method is decorated as shared_task."""
        runner = TradingTaskRunner()

        # Verify the method has Celery task attributes
        assert hasattr(runner.stop, "delay")
        assert hasattr(runner.stop, "apply_async")
