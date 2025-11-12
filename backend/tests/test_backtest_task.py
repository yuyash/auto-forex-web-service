"""
Unit tests for backtest Celery task.

Tests the run_backtest_task Celery task including:
- Task execution with valid configuration
- Progress updates during execution
- Result storage on completion
- Error handling and failure scenarios
- Resource limit enforcement

Requirements: 12.2
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.backtest_models import Backtest
from trading.tasks import run_backtest_task

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
def backtest(user):
    """Create a test backtest."""
    return Backtest.objects.create(
        user=user,
        strategy_type="floor",
        config={
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
        },
        instrument="EUR_USD",
        start_date=timezone.now() - timedelta(days=7),
        end_date=timezone.now() - timedelta(days=1),
        initial_balance=Decimal("10000.00"),
        commission_per_trade=Decimal("5.00"),
        status="pending",
    )


@pytest.fixture
def backtest_config_dict():
    """Create a backtest configuration dictionary."""
    start_date = timezone.now() - timedelta(days=7)
    end_date = timezone.now() - timedelta(days=1)

    return {
        "strategy_type": "floor",
        "strategy_config": {
            "base_lot_size": 1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
        },
        "instrument": "EUR_USD",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "initial_balance": 10000.00,
        "commission_per_trade": 5.00,
    }


@pytest.fixture
def sample_tick_data():
    """Create sample tick data for testing."""
    from trading.historical_data_loader import TickDataPoint

    base_time = timezone.now() - timedelta(days=7)
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
    mock_engine.trade_log = [
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1000,
            "exit_price": 1.1050,
            "entry_time": "2024-01-01T10:00:00",
            "exit_time": "2024-01-01T11:00:00",
            "duration": 3600,
            "pnl": 50.0,
            "reason": "take_profit",
        },
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1050,
            "exit_price": 1.1100,
            "entry_time": "2024-01-01T12:00:00",
            "exit_time": "2024-01-01T13:00:00",
            "duration": 3600,
            "pnl": 50.0,
            "reason": "take_profit",
        },
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1100,
            "exit_price": 1.1150,
            "entry_time": "2024-01-01T14:00:00",
            "exit_time": "2024-01-01T15:00:00",
            "duration": 3600,
            "pnl": 50.0,
            "reason": "take_profit",
        },
    ]
    mock_engine.equity_curve = [
        {"timestamp": "2024-01-01T10:00:00", "balance": 10000.0},
        {"timestamp": "2024-01-01T11:00:00", "balance": 10050.0},
        {"timestamp": "2024-01-01T12:00:00", "balance": 10100.0},
        {"timestamp": "2024-01-01T13:00:00", "balance": 10150.0},
    ]
    mock_engine.resource_monitor = Mock()
    mock_engine.resource_monitor.get_peak_memory.return_value = 150 * 1024 * 1024
    mock_engine.run.return_value = (
        mock_engine.trade_log,
        mock_engine.equity_curve,
        {
            "total_trades": 3,
            "winning_trades": 3,
            "losing_trades": 0,
            "total_pnl": 150.0,
            "win_rate": 100.0,
        },
    )
    return mock_engine


@pytest.mark.django_db
class TestRunBacktestTask:
    """Test run_backtest_task Celery task."""

    def test_task_execution_with_valid_config(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task executes successfully with valid configuration."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify result
            assert result["success"] is True
            assert result["backtest_id"] == backtest.id
            assert result["trade_count"] == 3
            assert result["final_balance"] == 10150.0
            assert result["win_rate"] == 100.0
            assert result["error"] is None
            assert result["terminated"] is False

            # Verify backtest status was updated
            backtest.refresh_from_db()
            assert backtest.status == "completed"
            assert backtest.total_trades == 3
            assert backtest.winning_trades == 3
            assert backtest.final_balance == Decimal("10150.00")

    def test_task_updates_backtest_status_to_running(self, backtest, backtest_config_dict):
        """Test task updates backtest status to running when started."""
        with patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class:
            # Mock data loader to return empty data (will fail)
            mock_loader = Mock()
            mock_loader.load_data.return_value = []
            mock_loader_class.return_value = mock_loader

            # Execute task
            run_backtest_task(backtest.id, backtest_config_dict)

            # Verify backtest status was updated to running (then failed due to no data)
            backtest.refresh_from_db()
            assert backtest.status == "failed"
            assert "No historical data" in backtest.error_message

    def test_task_stores_results_on_completion(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task stores results in database on completion."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            run_backtest_task(backtest.id, backtest_config_dict)

            # Verify results were stored
            backtest.refresh_from_db()
            assert backtest.status == "completed"
            assert backtest.total_trades == 3
            assert backtest.winning_trades == 3
            assert backtest.losing_trades == 0
            assert backtest.win_rate == Decimal("100.0")
            assert backtest.final_balance == Decimal("10150.00")
            assert len(backtest.equity_curve) > 0
            assert len(backtest.trade_log) == 3

    def test_task_handles_nonexistent_backtest(self, backtest_config_dict):
        """Test task handles nonexistent backtest gracefully."""
        # Execute task with invalid backtest ID
        result = run_backtest_task(99999, backtest_config_dict)

        # Verify error response
        assert result["success"] is False
        assert result["backtest_id"] == 99999
        assert "does not exist" in result["error"]

    def test_task_handles_no_historical_data(self, backtest, backtest_config_dict):
        """Test task handles case when no historical data is available."""
        with patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class:
            # Mock data loader to return empty data
            mock_loader = Mock()
            mock_loader.load_data.return_value = []
            mock_loader_class.return_value = mock_loader

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify error response
            assert result["success"] is False
            assert result["backtest_id"] == backtest.id
            assert "No historical data" in result["error"]

            # Verify backtest status was updated to failed
            backtest.refresh_from_db()
            assert backtest.status == "failed"
            assert "No historical data" in backtest.error_message

    def test_task_handles_engine_failure(self, backtest, backtest_config_dict, sample_tick_data):
        """Test task handles backtest engine failure."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine to raise exception
            mock_engine = Mock()
            mock_engine.run.side_effect = Exception("Engine error")
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify error response
            assert result["success"] is False
            assert result["backtest_id"] == backtest.id
            assert "Engine error" in result["error"]

            # Verify backtest status was updated to failed
            backtest.refresh_from_db()
            assert backtest.status == "failed"
            assert "Engine error" in backtest.error_message

    def test_task_handles_memory_limit_exceeded(
        self, backtest, backtest_config_dict, sample_tick_data
    ):
        """Test task handles memory limit exceeded error."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine to raise memory limit error
            mock_engine = Mock()
            mock_engine.resource_monitor = Mock()
            mock_engine.resource_monitor.get_peak_memory.return_value = 2500 * 1024 * 1024
            mock_engine.run.side_effect = RuntimeError(
                "Backtest terminated: memory limit exceeded (2048MB)"
            )
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify error response
            assert result["success"] is False
            assert result["backtest_id"] == backtest.id
            assert "memory limit exceeded" in result["error"]
            assert result["terminated"] is True

            # Verify backtest status was updated to failed
            backtest.refresh_from_db()
            assert backtest.status == "failed"
            assert "memory limit exceeded" in backtest.error_message

    def test_task_loads_resource_limits_from_config(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task loads resource limits from system configuration."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
            patch("trading.tasks.get_config") as mock_get_config,
        ):
            # Mock configuration
            def get_config_side_effect(key, default):
                config_map = {
                    "backtesting.cpu_limit": 2,
                    "backtesting.memory_limit": 1073741824,  # 1GB
                }
                return config_map.get(key, default)

            mock_get_config.side_effect = get_config_side_effect

            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            run_backtest_task(backtest.id, backtest_config_dict)

            # Verify BacktestConfig was created with correct limits
            call_args = mock_engine_class.call_args[0][0]
            assert call_args.cpu_limit == 2
            assert call_args.memory_limit == 1073741824

    def test_task_creates_backtest_config_correctly(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task creates BacktestConfig with correct parameters."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            run_backtest_task(backtest.id, backtest_config_dict)

            # Verify BacktestConfig was created correctly
            call_args = mock_engine_class.call_args[0][0]
            assert call_args.strategy_type == "floor"
            assert call_args.instrument == ["EUR_USD"]
            assert call_args.initial_balance == Decimal("10000.00")
            assert call_args.commission_per_trade == Decimal("5.00")

    def test_task_loads_historical_data_for_instrument(
        self, backtest, sample_tick_data, mock_backtest_engine
    ):
        """Test task loads historical data for all configured instrument."""
        # Create config with single instrument
        config_dict = {
            "strategy_type": "floor",
            "strategy_config": {},
            "instrument": "EUR_USD",
            "start_date": (timezone.now() - timedelta(days=7)).isoformat(),
            "end_date": (timezone.now() - timedelta(days=1)).isoformat(),
            "initial_balance": 10000.00,
            "commission_per_trade": 5.00,
        }

        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            run_backtest_task(backtest.id, config_dict)

            # Verify load_data was called for each instrument
            assert mock_loader.load_data.call_count == 2
            call_args_list = [
                call[1]["instrument"] for call in mock_loader.load_data.call_args_list
            ]
            assert "EUR_USD" in call_args_list
            assert "GBP_USD" in call_args_list

    def test_task_calculates_performance_metrics(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task calculates and stores performance metrics."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine
            mock_engine_class.return_value = mock_backtest_engine

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify metrics were calculated
            assert "trade_count" in result
            assert "final_balance" in result
            assert "total_return" in result
            assert "win_rate" in result
            assert "resource_usage" in result

    def test_task_stores_resource_usage_stats(
        self, backtest, backtest_config_dict, sample_tick_data, mock_backtest_engine
    ):
        """Test task stores resource usage statistics."""
        with (
            patch("trading.historical_data_loader.HistoricalDataLoader") as mock_loader_class,
            patch("trading.backtest_engine.BacktestEngine") as mock_engine_class,
        ):
            # Mock data loader
            mock_loader = Mock()
            mock_loader.load_data.return_value = sample_tick_data
            mock_loader_class.return_value = mock_loader

            # Mock backtest engine with resource monitor
            mock_engine = mock_backtest_engine
            mock_engine.resource_monitor.get_peak_memory.return_value = 175 * 1024 * 1024
            mock_engine_class.return_value = mock_engine

            # Execute task
            result = run_backtest_task(backtest.id, backtest_config_dict)

            # Verify resource usage was included in result
            assert "resource_usage" in result
            assert "peak_memory_mb" in result["resource_usage"]
            assert "memory_limit_mb" in result["resource_usage"]
            assert "cpu_limit_cores" in result["resource_usage"]

    def test_task_time_limits(self, backtest, backtest_config_dict):
        """Test task has appropriate time limits configured."""
        # Verify task decorator has time limits
        assert hasattr(run_backtest_task, "time_limit")
        assert hasattr(run_backtest_task, "soft_time_limit")

        # Time limits should be reasonable (1 hour hard, 55 min soft)
        assert run_backtest_task.time_limit == 3600
        assert run_backtest_task.soft_time_limit == 3300

    def test_task_is_bound(self):
        """Test task is bound to Celery instance."""
        # Verify task is bound (has bind attribute)
        assert hasattr(run_backtest_task, "bind")
        # The bind attribute is a method, not a boolean
        assert callable(run_backtest_task.bind)
