"""Unit tests for TaskService."""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.trading.enums import LogLevel, TaskStatus, TaskType
from apps.trading.models import (
    BacktestTasks,
    StrategyConfigurations,
    TaskLog,
    TaskMetric,
    TradingTasks,
)
from apps.trading.services.service import TaskServiceImpl

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
def oanda_account(db, user):
    """Create a test OANDA account."""
    from apps.market.models import OandaAccounts

    return OandaAccounts.objects.create(
        user=user,
        account_id="001-001-1234567-001",
        api_type="practice",
        is_active=True,
    )


@pytest.fixture
def task_service():
    """Create a TaskService instance."""
    return TaskServiceImpl()


@pytest.mark.django_db
class TestTaskServiceCreate:
    """Test task creation."""

    def test_create_backtest_task(self, task_service, user, strategy_config):
        """Test creating a backtest task with valid configuration."""
        start_time = timezone.now()
        end_time = start_time + timedelta(days=1)

        task = task_service.create_task(
            task_type=TaskType.BACKTEST,
            user_id=user.id,
            name="Test Backtest",
            config_id=strategy_config.id,
            start_time=start_time,
            end_time=end_time,
            instrument="EUR_USD",
            initial_balance=Decimal("10000"),
        )

        assert isinstance(task, BacktestTasks)
        assert task.name == "Test Backtest"
        assert task.user == user
        assert task.config == strategy_config
        assert task.start_time == start_time
        assert task.end_time == end_time
        assert task.instrument == "EUR_USD"
        assert task.status == TaskStatus.CREATED

    def test_create_trading_task(self, task_service, user, strategy_config, oanda_account):
        """Test creating a trading task with valid configuration."""
        task = task_service.create_task(
            task_type=TaskType.TRADING,
            user_id=user.id,
            name="Test Trading",
            config_id=strategy_config.id,
            oanda_account_id=oanda_account.id,
            instrument="USD_JPY",
        )

        assert isinstance(task, TradingTasks)
        assert task.name == "Test Trading"
        assert task.user == user
        assert task.config == strategy_config
        assert task.oanda_account == oanda_account
        assert task.instrument == "USD_JPY"
        assert task.status == TaskStatus.CREATED

    def test_create_task_invalid_user(self, task_service, strategy_config):
        """Test creating a task with invalid user ID."""
        with pytest.raises(ValueError, match="User with id .* does not exist"):
            task_service.create_task(
                task_type=TaskType.BACKTEST,
                user_id=99999,
                name="Test Task",
                config_id=strategy_config.id,
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(days=1),
            )

    def test_create_task_invalid_config(self, task_service, user):
        """Test creating a task with invalid config ID."""
        with pytest.raises(ValueError, match="Strategy configuration with id .* does not exist"):
            task_service.create_task(
                task_type=TaskType.BACKTEST,
                user_id=user.id,
                name="Test Task",
                config_id=99999,
                start_time=timezone.now(),
                end_time=timezone.now() + timedelta(days=1),
            )

    def test_create_backtest_task_missing_time_range(self, task_service, user, strategy_config):
        """Test creating a backtest task without time range."""
        with pytest.raises(ValueError, match="start_time and end_time are required"):
            task_service.create_task(
                task_type=TaskType.BACKTEST,
                user_id=user.id,
                name="Test Task",
                config_id=strategy_config.id,
            )

    def test_create_trading_task_missing_account(self, task_service, user, strategy_config):
        """Test creating a trading task without OANDA account."""
        with pytest.raises(ValueError, match="oanda_account_id is required"):
            task_service.create_task(
                task_type=TaskType.TRADING,
                user_id=user.id,
                name="Test Task",
                config_id=strategy_config.id,
            )


@pytest.mark.django_db
class TestTaskServiceSubmit:
    """Test task submission."""

    @patch("apps.trading.tasks.run_backtest_task")
    def test_submit_backtest_task(self, mock_celery_task, task_service, user, strategy_config):
        """Test submitting a backtest task to Celery."""
        # Create a pending task
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.CREATED,
        )

        # Mock Celery task result
        mock_result = Mock()
        mock_result.id = str(uuid4())
        mock_celery_task.apply_async.return_value = mock_result

        # Submit task
        submitted_task = task_service.submit_task(task)

        # Verify Celery task was called
        mock_celery_task.apply_async.assert_called_once()
        call_args = mock_celery_task.apply_async.call_args
        assert call_args[1]["args"] == [task.pk]

        # Verify task was updated
        assert submitted_task.celery_task_id == mock_result.id
        assert submitted_task.status == TaskStatus.RUNNING
        assert submitted_task.started_at is not None

    @patch("apps.trading.tasks.run_trading_task")
    def test_submit_trading_task(
        self, mock_celery_task, task_service, user, strategy_config, oanda_account
    ):
        """Test submitting a trading task to Celery."""
        # Create a pending task
        task = TradingTasks.objects.create(
            user=user,
            config=strategy_config,
            oanda_account=oanda_account,
            name="Test Trading",
            status=TaskStatus.CREATED,
        )

        # Mock Celery task result
        mock_result = Mock()
        mock_result.id = str(uuid4())
        mock_celery_task.apply_async.return_value = mock_result

        # Submit task
        submitted_task = task_service.submit_task(task)

        # Verify Celery task was called
        mock_celery_task.apply_async.assert_called_once()

        # Verify task was updated
        assert submitted_task.celery_task_id == mock_result.id
        assert submitted_task.status == TaskStatus.RUNNING
        assert submitted_task.started_at is not None

    def test_submit_task_not_pending(self, task_service, user, strategy_config):
        """Test submitting a task that is not in PENDING status."""
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
        )

        with pytest.raises(ValueError, match="Task must be in PENDING status"):
            task_service.submit_task(task)


@pytest.mark.django_db
class TestTaskServiceCancel:
    """Test task cancellation."""

    def test_cancel_running_backtest_task(self, task_service, user, strategy_config):
        """Test cancelling a running backtest task."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        with patch.object(task, "get_celery_result") as mock_result:
            mock_result.return_value = Mock()
            success = task_service.cancel_task(task.id)  # type: ignore[attr-defined]

        assert success is True
        task.refresh_from_db()
        assert task.status == TaskStatus.STOPPED
        assert task.completed_at is not None

    def test_cancel_nonexistent_task(self, task_service):
        """Test cancelling a task that doesn't exist."""
        with pytest.raises(ValueError, match="Task with id .* does not exist"):
            task_service.cancel_task(uuid4())


@pytest.mark.django_db
class TestTaskServiceRestart:
    """Test task restart."""

    @patch("apps.trading.tasks.run_backtest_task")
    def test_restart_completed_task(self, mock_celery_task, task_service, user, strategy_config):
        """Test restarting a completed task."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.COMPLETED,
            celery_task_id=str(uuid4()),
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            result_data={"test": "data"},
        )

        # Mock Celery task result
        mock_result = Mock()
        mock_result.id = str(uuid4())
        mock_celery_task.apply_async.return_value = mock_result

        # Restart task
        restarted_task = task_service.restart_task(task.id)  # type: ignore[attr-defined]

        # Verify execution data was cleared
        assert restarted_task.status == TaskStatus.RUNNING
        assert restarted_task.retry_count == 1
        assert restarted_task.celery_task_id == mock_result.id
        assert restarted_task.started_at is not None

    def test_restart_task_exceeds_retry_limit(self, task_service, user, strategy_config):
        """Test restarting a task that has exceeded retry limit."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.FAILED,
            retry_count=3,
            max_retries=3,
        )

        with pytest.raises(ValueError, match="Task has reached maximum retry limit"):
            task_service.restart_task(task.id)  # type: ignore[attr-defined]

    def test_restart_running_task(self, task_service, user, strategy_config):
        """Test restarting a task that is currently running."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
        )

        with pytest.raises(ValueError, match="Cannot restart a task that is currently running"):
            task_service.restart_task(task.id)  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestTaskServiceResume:
    """Test task resume."""

    @patch("apps.trading.tasks.run_backtest_task")
    def test_resume_cancelled_task(self, mock_celery_task, task_service, user, strategy_config):
        """Test resuming a cancelled task."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.STOPPED,
            started_at=timezone.now() - timedelta(hours=1),
        )

        # Create some logs to verify they're preserved
        TaskLog.objects.create(
            task=task,
            level=LogLevel.INFO,
            message="Previous execution log",
        )

        # Mock Celery task result
        mock_result = Mock()
        mock_result.id = str(uuid4())
        mock_celery_task.apply_async.return_value = mock_result

        # Resume task
        resumed_task = task_service.resume_task(task.id)  # type: ignore[attr-defined]

        # Verify execution context was preserved
        assert resumed_task.status == TaskStatus.RUNNING
        assert resumed_task.started_at is not None  # Original started_at preserved
        assert resumed_task.logs.count() == 1  # Logs preserved

    def test_resume_non_cancelled_task(self, task_service, user, strategy_config):
        """Test resuming a task that is not cancelled."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.COMPLETED,
        )

        with pytest.raises(ValueError, match="Task cannot be resumed"):
            task_service.resume_task(task.id)  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestTaskServiceGetStatus:
    """Test task status retrieval."""

    def test_get_task_status(self, task_service, user, strategy_config):
        """Test getting task status."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
        )

        status = task_service.get_task_status(task.id)  # type: ignore[attr-defined]
        assert status == TaskStatus.RUNNING

    def test_get_status_nonexistent_task(self, task_service):
        """Test getting status of nonexistent task."""
        with pytest.raises(ValueError, match="Task with id .* does not exist"):
            task_service.get_task_status(uuid4())


@pytest.mark.django_db
class TestTaskServiceGetLogs:
    """Test task log retrieval."""

    def test_get_task_logs(self, task_service, user, strategy_config):
        """Test retrieving task logs."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create some logs
        for i in range(5):
            TaskLog.objects.create(
                task=task,
                level=LogLevel.INFO,
                message=f"Log message {i}",
            )

        logs = task_service.get_task_logs(task.id)  # type: ignore[attr-defined]
        assert len(logs) == 5

    def test_get_task_logs_with_level_filter(self, task_service, user, strategy_config):
        """Test retrieving logs with level filter."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create logs with different levels
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Info 1")
        TaskLog.objects.create(task=task, level=LogLevel.ERROR, message="Error 1")
        TaskLog.objects.create(task=task, level=LogLevel.INFO, message="Info 2")
        TaskLog.objects.create(task=task, level=LogLevel.ERROR, message="Error 2")

        error_logs = task_service.get_task_logs(task.id, level=LogLevel.ERROR)  # type: ignore[attr-defined]
        assert len(error_logs) == 2
        assert all(log.level == LogLevel.ERROR for log in error_logs)

    def test_get_task_logs_with_pagination(self, task_service, user, strategy_config):
        """Test retrieving logs with pagination."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create 10 logs
        for i in range(10):
            TaskLog.objects.create(
                task=task,
                level=LogLevel.INFO,
                message=f"Log {i}",
            )

        # Get first page
        page1 = task_service.get_task_logs(task.id, limit=5, offset=0)  # type: ignore[attr-defined]
        assert len(page1) == 5

        # Get second page
        page2 = task_service.get_task_logs(task.id, limit=5, offset=5)  # type: ignore[attr-defined]
        assert len(page2) == 5

        # Verify no overlap
        page1_ids = {log.id for log in page1}
        page2_ids = {log.id for log in page2}
        assert page1_ids.isdisjoint(page2_ids)


@pytest.mark.django_db
class TestTaskServiceGetMetrics:
    """Test task metric retrieval."""

    def test_get_task_metrics(self, task_service, user, strategy_config):
        """Test retrieving task metrics."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create some metrics
        for i in range(5):
            TaskMetric.objects.create(
                task=task,
                metric_name="equity",
                metric_value=10000.0 + i * 100,
            )

        metrics = task_service.get_task_metrics(task.id)  # type: ignore[attr-defined]
        assert len(metrics) == 5

    def test_get_task_metrics_with_name_filter(self, task_service, user, strategy_config):
        """Test retrieving metrics with name filter."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create metrics with different names
        TaskMetric.objects.create(task=task, metric_name="equity", metric_value=10000.0)
        TaskMetric.objects.create(task=task, metric_name="drawdown", metric_value=250.0)
        TaskMetric.objects.create(task=task, metric_name="equity", metric_value=10100.0)

        equity_metrics = task_service.get_task_metrics(task.id, metric_name="equity")  # type: ignore[attr-defined]
        assert len(equity_metrics) == 2
        assert all(m.metric_name == "equity" for m in equity_metrics)

    def test_get_task_metrics_with_time_range(self, task_service, user, strategy_config):
        """Test retrieving metrics with time range filter."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
        )

        # Create metrics at different times
        now = timezone.now()
        metric1 = TaskMetric.objects.create(
            task=task,
            metric_name="equity",
            metric_value=10000.0,
        )
        metric1.timestamp = now - timedelta(hours=2)
        metric1.save()

        metric2 = TaskMetric.objects.create(
            task=task,
            metric_name="equity",
            metric_value=10100.0,
        )
        metric2.timestamp = now - timedelta(hours=1)
        metric2.save()

        metric3 = TaskMetric.objects.create(
            task=task,
            metric_name="equity",
            metric_value=10200.0,
        )
        metric3.timestamp = now
        metric3.save()

        # Get metrics from last 90 minutes
        start_time = now - timedelta(minutes=90)
        recent_metrics = task_service.get_task_metrics(task.id, start_time=start_time)  # type: ignore[attr-defined]
        assert len(recent_metrics) == 2


@pytest.mark.django_db
class TestTaskServiceErrorHandling:
    """Test error handling in task service."""

    @patch("apps.trading.tasks.run_backtest_task")
    def test_submit_task_celery_connection_failure(
        self, mock_celery_task, task_service, user, strategy_config
    ):
        """Test handling of Celery connection failures during task submission."""
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.CREATED,
        )

        # Simulate Celery connection failure
        mock_celery_task.apply_async.side_effect = ConnectionError("Celery broker unavailable")

        with pytest.raises(RuntimeError, match="Failed to submit task to Celery"):
            task_service.submit_task(task)

        # Verify task status wasn't changed
        task.refresh_from_db()
        assert task.status == TaskStatus.CREATED
        assert task.celery_task_id is None

    def test_submit_task_invalid_configuration(self, task_service, user, strategy_config):
        """Test handling of invalid task configuration during submission."""
        # Create a task with valid configuration but set status to PENDING
        task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.CREATED,
        )

        # Mock validate_configuration to return invalid
        with patch.object(task, "validate_configuration", return_value=(False, "Invalid config")):
            with pytest.raises(ValueError, match="Task configuration is invalid"):
                task_service.submit_task(task)

    @patch("apps.trading.tasks.run_backtest_task")
    def test_restart_task_celery_failure(
        self, mock_celery_task, task_service, user, strategy_config
    ):
        """Test handling of Celery failures during task restart."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.FAILED,
        )

        # Simulate Celery failure during restart
        mock_celery_task.apply_async.side_effect = RuntimeError("Celery error")

        # The error gets wrapped in ValueError by restart_task
        with pytest.raises(ValueError, match="Failed to restart task"):
            task_service.restart_task(task.id)  # type: ignore[attr-defined]

    @patch("apps.trading.tasks.run_backtest_task")
    def test_resume_task_celery_failure(
        self, mock_celery_task, task_service, user, strategy_config
    ):
        """Test handling of Celery failures during task resume."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.STOPPED,
        )

        # Simulate Celery failure during resume
        mock_celery_task.apply_async.side_effect = RuntimeError("Celery error")

        # The error gets wrapped in ValueError by resume_task
        with pytest.raises(ValueError, match="Failed to resume task"):
            task_service.resume_task(task.id)  # type: ignore[attr-defined]

    def test_get_logs_nonexistent_task(self, task_service):
        """Test retrieving logs for nonexistent task."""
        with pytest.raises(ValueError, match="Task with id .* does not exist"):
            task_service.get_task_logs(uuid4())

    def test_get_metrics_nonexistent_task(self, task_service):
        """Test retrieving metrics for nonexistent task."""
        with pytest.raises(ValueError, match="Task with id .* does not exist"):
            task_service.get_task_metrics(uuid4())

    def test_cancel_task_without_celery_id(self, task_service, user, strategy_config):
        """Test cancelling a task without Celery task ID."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
            celery_task_id=None,  # No Celery task ID
        )

        # Should return False since there's no Celery task to cancel
        success = task_service.cancel_task(task.id)  # type: ignore[attr-defined]
        assert success is False

    def test_create_task_with_database_error(self, task_service, user, strategy_config):
        """Test handling of database errors during task creation."""
        # Simulate error by using invalid task type (not in TaskType enum)
        with pytest.raises(ValueError, match="Unknown task type"):
            task_service.create_task(
                task_type="INVALID_TYPE",  # Invalid task type
                user_id=user.id,
                name="Test Task",
                config_id=strategy_config.id,
            )

    @patch("apps.trading.models.BacktestTasks.objects.get")
    def test_get_status_with_celery_sync_failure(
        self, mock_get, task_service, user, strategy_config
    ):
        """Test handling of Celery synchronization failures during status retrieval."""
        task: BacktestTasks = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now() + timedelta(days=1),
            status=TaskStatus.RUNNING,
            celery_task_id=str(uuid4()),
        )

        # Mock the task retrieval to return our task
        mock_get.return_value = task

        # Mock update_from_celery_state to raise an exception
        with patch.object(task, "update_from_celery_state", side_effect=Exception("Celery error")):
            # Should still return current status despite sync failure
            status = task_service.get_task_status(task.id)  # type: ignore[attr-defined]
            assert status == TaskStatus.RUNNING
