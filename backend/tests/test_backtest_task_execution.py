"""
Unit tests for backtest task execution with integrated services.

Tests the execute_backtest_task function with:
- TaskLockManager integration
- ProgressReporter integration
- StateSynchronizer integration
- BacktestLogger integration
- Heartbeat updates
- Cancellation flag checks
- State transitions

Requirements: 1.1, 2.1, 2.2, 2.3, 5.2
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus
from trading.services.task_executor import execute_backtest_task

User = get_user_model()


@pytest.fixture
def user(db):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
    )


@pytest.fixture
def strategy_config(user, db):
    """Create a test strategy configuration."""
    from trading.models import StrategyConfig

    return StrategyConfig.objects.create(
        user=user,
        name="Test Floor Strategy",
        strategy_type="floor",
        parameters={
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
            "take_profit_pips": 50,
            "stop_loss_pips": 30,
            "max_positions": 5,
        },
    )


@pytest.fixture
def backtest_task(user, strategy_config, db):
    """Create a test backtest task."""
    return BacktestTask.objects.create(
        user=user,
        name="Test Backtest",
        config=strategy_config,
        instrument="EUR_USD",
        start_time=timezone.now() - timedelta(days=3),
        end_time=timezone.now() - timedelta(days=1),
        initial_balance=Decimal("10000.00"),
        commission_per_trade=Decimal("5.00"),
        data_source="postgresql",
        status=TaskStatus.CREATED,
    )


@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing."""
    from trading.historical_data_loader import TickDataPoint

    base_time = timezone.now() - timedelta(days=3)
    return [
        TickDataPoint(
            instrument="EUR_USD",
            timestamp=base_time + timedelta(hours=i),
            bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
            ask=Decimal("1.1002") + Decimal(str(i * 0.0001)),
            mid=Decimal("1.1001") + Decimal(str(i * 0.0001)),
            spread=Decimal("0.0002"),
        )
        for i in range(100)
    ]


@pytest.fixture
def mock_backtest_engine():
    """Create a mock BacktestEngine."""
    mock_engine = Mock()
    mock_engine.balance = Decimal("10150.00")
    mock_engine.trade_log = []
    mock_engine.equity_curve = []
    mock_engine.resource_monitor = Mock()
    mock_engine.resource_monitor.is_exceeded.return_value = False
    mock_engine.resource_monitor.stop = Mock()
    mock_engine.terminated = False
    mock_engine.config = Mock()
    mock_engine.config.memory_limit = 2147483648
    # Mock strategy with empty backtest events
    mock_engine.strategy = Mock()
    mock_engine.strategy._backtest_events = []
    mock_engine.strategy.finalize = Mock()
    mock_engine.calculate_performance_metrics.return_value = {
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "total_pnl": 0.0,
        "total_return": 0.0,
        "win_rate": 0.0,
        "max_drawdown": 0.0,
        "average_win": 0.0,
        "average_loss": 0.0,
        "sharpe_ratio": None,
        "profit_factor": None,
        "strategy_events": [],
    }
    return mock_engine


@pytest.mark.django_db
class TestBacktestTaskExecution:
    """Test execute_backtest_task with integrated services."""

    def test_lock_acquisition_and_release(
        self, backtest_task, sample_tick_data, mock_backtest_engine
    ):
        """Test that TaskLockManager acquires and releases locks properly."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer"),
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            result = execute_backtest_task(backtest_task.id)

            # Verify lock was acquired
            mock_lock_manager.acquire_lock.assert_called_once_with("backtest", backtest_task.id)

            # Verify lock was released
            mock_lock_manager.release_lock.assert_called_once_with("backtest", backtest_task.id)

            # Verify task completed successfully
            assert result["success"] is True

    def test_lock_acquisition_failure(self, backtest_task):
        """Test that task fails gracefully when lock cannot be acquired."""
        with patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class:
            # Mock lock manager to fail acquisition
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Execute task
            result = execute_backtest_task(backtest_task.id)

            # Verify task failed
            assert result["success"] is False
            assert "already running" in result["error"]

            # Verify lock was not released (since it wasn't acquired)
            mock_lock_manager.release_lock.assert_not_called()

    def test_heartbeat_updates_during_execution(
        self, backtest_task, sample_tick_data, mock_backtest_engine
    ):
        """Test that heartbeat is updated during task execution."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer"),
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock data loader to return data for 3 days
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            execute_backtest_task(backtest_task.id)

            # Verify heartbeat was updated (once per day = 3 times)
            assert mock_lock_manager.update_heartbeat.call_count == 3
            mock_lock_manager.update_heartbeat.assert_called_with("backtest", backtest_task.id)

    def test_cancellation_flag_check(self, backtest_task, sample_tick_data, mock_backtest_engine):
        """Test that task checks cancellation flag and stops when set."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer") as mock_state_sync_class,
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager to return cancellation after first day
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.side_effect = [False, True, False]
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock state synchronizer
            mock_state_sync = Mock()
            mock_state_sync_class.return_value = mock_state_sync

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            result = execute_backtest_task(backtest_task.id)

            # Verify task was cancelled
            assert result["success"] is False
            assert "cancelled" in result["error"]

            # Verify state was transitioned to stopped
            mock_state_sync.transition_to_stopped.assert_called_once()

            # Verify lock was released
            mock_lock_manager.release_lock.assert_called_once_with("backtest", backtest_task.id)

    def test_progress_reporting(self, backtest_task, sample_tick_data, mock_backtest_engine):
        """Test that progress is reported during execution."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter") as mock_progress_class,
            patch("trading.services.state_synchronizer.StateSynchronizer"),
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock progress reporter
            mock_progress = Mock()
            mock_progress_class.return_value = mock_progress

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            execute_backtest_task(backtest_task.id)

            # Verify progress reporter was initialized with correct parameters
            mock_progress_class.assert_called_once()
            call_kwargs = mock_progress_class.call_args[1]
            assert call_kwargs["task_id"] == backtest_task.id
            assert call_kwargs["user_id"] == backtest_task.user.id
            assert call_kwargs["total_days"] == 3

            # Verify progress was reported for each day
            assert mock_progress.report_day_start.call_count == 3
            assert mock_progress.report_day_complete.call_count == 3

    def test_state_transitions(self, backtest_task, sample_tick_data, mock_backtest_engine):
        """Test that state transitions are handled correctly."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer") as mock_state_sync_class,
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock state synchronizer
            mock_state_sync = Mock()
            mock_state_sync_class.return_value = mock_state_sync

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            execute_backtest_task(backtest_task.id)

            # Verify state was transitioned to completed
            mock_state_sync.transition_to_completed.assert_called_once()

    def test_error_handling_with_state_transition(self, backtest_task, sample_tick_data):
        """Test that errors trigger failed state transition."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer") as mock_state_sync_class,
            patch("trading.services.backtest_logger.BacktestLogger"),
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock state synchronizer
            mock_state_sync = Mock()
            mock_state_sync_class.return_value = mock_state_sync

            # Mock data loader to raise exception
            mock_loader = Mock()
            mock_loader.load_data.side_effect = Exception("Test error")
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine (won't be used due to data loader error)
            mock_engine = Mock()
            mock_engine.resource_monitor = Mock()
            mock_engine.resource_monitor.stop = Mock()
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = execute_backtest_task(backtest_task.id)

            # Verify task failed
            assert result["success"] is False
            assert "Test error" in result["error"]

            # Verify state was transitioned to failed
            mock_state_sync.transition_to_failed.assert_called_once()

            # Verify lock was released
            mock_lock_manager.release_lock.assert_called_once_with("backtest", backtest_task.id)

    def test_backtest_logger_integration(
        self, backtest_task, sample_tick_data, mock_backtest_engine
    ):
        """Test that BacktestLogger is used for structured logging."""
        with (
            patch("trading.services.task_executor.HistoricalDataLoader") as mock_loader_class,
            patch("trading.services.task_executor.BacktestEngine") as mock_engine_class,
            patch("trading.services.task_lock_manager.TaskLockManager") as mock_lock_manager_class,
            patch("trading.services.progress_reporter.ProgressReporter"),
            patch("trading.services.state_synchronizer.StateSynchronizer"),
            patch("trading.services.backtest_logger.BacktestLogger") as mock_logger_class,
        ):
            # Mock lock manager
            mock_lock_manager = Mock()
            mock_lock_manager.acquire_lock.return_value = True
            mock_lock_manager.check_cancellation_flag.return_value = False
            mock_lock_manager_class.return_value = mock_lock_manager

            # Mock backtest logger
            mock_logger = Mock()
            mock_logger_class.return_value = mock_logger

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            execute_backtest_task(backtest_task.id)

            # Verify logger was initialized
            mock_logger_class.assert_called_once()
            call_kwargs = mock_logger_class.call_args[1]
            assert call_kwargs["task_id"] == backtest_task.id

            # Verify logging methods were called
            assert mock_logger.log_execution_start.call_count == 1
            assert mock_logger.log_day_start.call_count == 3
            assert mock_logger.log_day_processing.call_count == 3
            assert mock_logger.log_day_complete.call_count == 3
            assert mock_logger.log_execution_complete.call_count == 1


class TestCeleryTaskTimeLimits:
    """Tests for Celery task time limit configuration."""

    def test_backtest_task_has_72_hour_time_limit(self):
        """Verify run_backtest_task has 72 hour time limits for long-running backtests."""
        from trading.tasks import run_backtest_task

        # Get the celery task's time limit settings
        # These are set via the @shared_task decorator
        assert hasattr(run_backtest_task, "time_limit")
        assert hasattr(run_backtest_task, "soft_time_limit")

        # 72 hours = 259200 seconds
        expected_time_limit = 72 * 60 * 60  # 259200
        expected_soft_limit = 71 * 60 * 60  # 255600

        assert run_backtest_task.time_limit == expected_time_limit, (
            f"Expected time_limit={expected_time_limit}, " f"got {run_backtest_task.time_limit}"
        )
        assert run_backtest_task.soft_time_limit == expected_soft_limit, (
            f"Expected soft_time_limit={expected_soft_limit}, "
            f"got {run_backtest_task.soft_time_limit}"
        )

    def test_trading_task_has_72_hour_time_limit(self):
        """Verify run_trading_task has 72 hour time limits for live trading."""
        from trading.tasks import run_trading_task

        assert hasattr(run_trading_task, "time_limit")
        assert hasattr(run_trading_task, "soft_time_limit")

        expected_time_limit = 72 * 60 * 60  # 259200
        expected_soft_limit = 71 * 60 * 60  # 255600

        assert run_trading_task.time_limit == expected_time_limit
        assert run_trading_task.soft_time_limit == expected_soft_limit
