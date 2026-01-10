"""Unit tests for PerformanceTracker service.

Tests the PerformanceTracker class which tracks performance metrics
during task execution.
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import ExecutionMetricsCheckpoint, TaskExecution
from apps.trading.services.performance import PerformanceTracker


@pytest.fixture
def task_execution(db):
    """Create a test TaskExecution instance."""
    return TaskExecution.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=1,
        execution_number=1,
        status=TaskStatus.RUNNING,
        started_at=timezone.now(),
    )


@pytest.fixture
def tracker(task_execution):
    """Create a PerformanceTracker instance."""
    return PerformanceTracker(
        execution=task_execution,
        initial_balance=Decimal("10000.00"),
    )


class TestPerformanceTrackerInitialization:
    """Test PerformanceTracker initialization."""

    def test_initialization_with_valid_parameters(self, task_execution):
        """Test tracker initializes with correct values."""
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(task_execution, initial_balance)

        assert tracker.execution == task_execution
        assert tracker.initial_balance == initial_balance
        assert tracker.ticks_processed == 0
        assert tracker.trades_executed == 0
        assert tracker.current_balance == initial_balance
        assert tracker.realized_pnl == Decimal("0")
        assert tracker.unrealized_pnl == Decimal("0")
        assert tracker.open_positions_count == 0


class TestOnTickProcessed:
    """Test on_tick_processed method."""

    def test_increments_tick_counter(self, tracker):
        """Test that tick counter increments correctly."""
        assert tracker.ticks_processed == 0

        tracker.on_tick_processed()
        assert tracker.ticks_processed == 1

        tracker.on_tick_processed()
        assert tracker.ticks_processed == 2

    def test_multiple_ticks(self, tracker):
        """Test processing multiple ticks."""
        for _ in range(100):
            tracker.on_tick_processed()

        assert tracker.ticks_processed == 100


class TestOnTradeExecuted:
    """Test on_trade_executed method."""

    def test_opening_trade_increments_counters(self, tracker):
        """Test opening a trade increments counters."""
        tracker.on_trade_executed(is_opening=True)

        assert tracker.trades_executed == 1
        assert tracker.open_positions_count == 1

    def test_multiple_opening_trades(self, tracker):
        """Test opening multiple trades."""
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(is_opening=True)

        assert tracker.trades_executed == 3
        assert tracker.open_positions_count == 3

    def test_closing_trade_with_profit(self, tracker):
        """Test closing a trade with profit updates metrics."""
        # Open a position first
        tracker.on_trade_executed(is_opening=True)

        # Close with profit
        pnl = Decimal("100.50")
        tracker.on_trade_executed(pnl=pnl, is_opening=False)

        assert tracker.trades_executed == 2
        assert tracker.open_positions_count == 0
        assert tracker.realized_pnl == pnl
        assert tracker.current_balance == Decimal("10100.50")
        assert tracker._winning_trades == 1
        assert tracker._losing_trades == 0

    def test_closing_trade_with_loss(self, tracker):
        """Test closing a trade with loss updates metrics."""
        # Open a position first
        tracker.on_trade_executed(is_opening=True)

        # Close with loss
        pnl = Decimal("-50.25")
        tracker.on_trade_executed(pnl=pnl, is_opening=False)

        assert tracker.trades_executed == 2
        assert tracker.open_positions_count == 0
        assert tracker.realized_pnl == pnl
        assert tracker.current_balance == Decimal("9949.75")
        assert tracker._winning_trades == 0
        assert tracker._losing_trades == 1

    def test_multiple_trades_with_mixed_results(self, tracker):
        """Test multiple trades with wins and losses."""
        # Trade 1: Win
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)

        # Trade 2: Loss
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("-50"), is_opening=False)

        # Trade 3: Win
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("75"), is_opening=False)

        assert tracker.trades_executed == 6
        assert tracker.open_positions_count == 0
        assert tracker.realized_pnl == Decimal("125")
        assert tracker.current_balance == Decimal("10125")
        assert tracker._winning_trades == 2
        assert tracker._losing_trades == 1


class TestUpdateUnrealizedPnl:
    """Test update_unrealized_pnl method."""

    def test_updates_unrealized_pnl(self, tracker):
        """Test updating unrealized PnL."""
        unrealized = Decimal("50.75")
        tracker.update_unrealized_pnl(unrealized)

        assert tracker.unrealized_pnl == unrealized

    def test_updates_multiple_times(self, tracker):
        """Test updating unrealized PnL multiple times."""
        tracker.update_unrealized_pnl(Decimal("50"))
        assert tracker.unrealized_pnl == Decimal("50")

        tracker.update_unrealized_pnl(Decimal("75"))
        assert tracker.unrealized_pnl == Decimal("75")

        tracker.update_unrealized_pnl(Decimal("-25"))
        assert tracker.unrealized_pnl == Decimal("-25")


class TestSaveCheckpoint:
    """Test save_checkpoint method."""

    def test_creates_checkpoint_record(self, tracker):
        """Test that checkpoint is created in database."""
        checkpoint = tracker.save_checkpoint()

        assert checkpoint is not None
        assert checkpoint.execution == tracker.execution
        assert checkpoint.processed == 0
        assert checkpoint.total_pnl == Decimal("0")

    def test_checkpoint_with_metrics(self, tracker):
        """Test checkpoint includes current metrics."""
        # Process some ticks
        for _ in range(10):
            tracker.on_tick_processed()

        # Execute some trades
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)

        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("-50"), is_opening=False)

        # Update unrealized PnL
        tracker.update_unrealized_pnl(Decimal("25"))

        # Save checkpoint
        checkpoint = tracker.save_checkpoint()

        assert checkpoint.processed == 10
        assert checkpoint.total_trades == 2
        assert checkpoint.winning_trades == 1
        assert checkpoint.losing_trades == 1
        assert checkpoint.realized_pnl == Decimal("50")
        assert checkpoint.unrealized_pnl == Decimal("25")
        assert checkpoint.total_pnl == Decimal("75")
        assert checkpoint.average_win == Decimal("100")
        assert checkpoint.average_loss == Decimal("-50")

    def test_checkpoint_calculates_win_rate(self, tracker):
        """Test checkpoint calculates win rate correctly."""
        # 3 wins, 2 losses
        for _ in range(5):
            tracker.on_trade_executed(is_opening=True)

        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("50"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-25"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("75"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-30"), is_opening=False)

        checkpoint = tracker.save_checkpoint()

        # Win rate should be 60% (3 wins out of 5 trades)
        assert checkpoint.win_rate == Decimal("60.00")

    def test_checkpoint_calculates_profit_factor(self, tracker):
        """Test checkpoint calculates profit factor correctly."""
        # Gross profit: 100 + 50 = 150
        # Gross loss: 25 + 30 = 55
        # Profit factor: 150 / 55 ≈ 2.727
        for _ in range(4):
            tracker.on_trade_executed(is_opening=True)

        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("50"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-25"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-30"), is_opening=False)

        checkpoint = tracker.save_checkpoint()

        assert checkpoint.profit_factor is not None
        # Profit factor should be approximately 2.727
        assert abs(checkpoint.profit_factor - Decimal("2.7273")) < Decimal("0.01")

    def test_checkpoint_with_no_losses(self, tracker):
        """Test profit factor when there are no losses."""
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)

        checkpoint = tracker.save_checkpoint()

        # Profit factor should be None when there are no losses
        assert checkpoint.profit_factor is None

    def test_multiple_checkpoints(self, tracker):
        """Test creating multiple checkpoints."""
        tracker.save_checkpoint()

        # Process more data
        tracker.on_tick_processed()
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("50"), is_opening=False)

        checkpoint2 = tracker.save_checkpoint()

        # Both checkpoints should exist
        assert ExecutionMetricsCheckpoint.objects.filter(execution=tracker.execution).count() == 2

        # Second checkpoint should have updated metrics
        assert checkpoint2.processed == 1
        assert checkpoint2.total_trades == 1


class TestGetMetrics:
    """Test get_metrics method."""

    def test_returns_metrics_dictionary(self, tracker):
        """Test get_metrics returns correct dictionary."""
        metrics = tracker.get_metrics()

        assert isinstance(metrics, dict)
        assert "ticks_processed" in metrics
        assert "trades_executed" in metrics
        assert "current_balance" in metrics
        assert "current_pnl" in metrics
        assert "realized_pnl" in metrics
        assert "unrealized_pnl" in metrics
        assert "open_positions" in metrics
        assert "total_return" in metrics

    def test_metrics_with_data(self, tracker):
        """Test metrics reflect current state."""
        # Process some data
        for _ in range(5):
            tracker.on_tick_processed()

        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)
        tracker.update_unrealized_pnl(Decimal("25"))

        metrics = tracker.get_metrics()

        assert metrics["ticks_processed"] == 5
        assert metrics["trades_executed"] == 2
        assert metrics["current_balance"] == Decimal("10100")
        assert metrics["realized_pnl"] == Decimal("100")
        assert metrics["unrealized_pnl"] == Decimal("25")
        assert metrics["current_pnl"] == Decimal("125")
        assert metrics["open_positions"] == 0

    def test_total_return_calculation(self, tracker):
        """Test total return is calculated correctly."""
        # Make 10% profit
        tracker.on_trade_executed(is_opening=True)
        tracker.on_trade_executed(pnl=Decimal("1000"), is_opening=False)

        metrics = tracker.get_metrics()

        # Total return should be 10%
        assert metrics["total_return"] == Decimal("10.00")

    def test_win_rate_calculation(self, tracker):
        """Test win rate is calculated correctly."""
        # 2 wins, 1 loss
        for _ in range(3):
            tracker.on_trade_executed(is_opening=True)

        tracker.on_trade_executed(pnl=Decimal("100"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("50"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-25"), is_opening=False)

        metrics = tracker.get_metrics()

        # Win rate should be 66.67% (2 wins out of 3 trades)
        assert abs(metrics["win_rate"] - Decimal("66.67")) < Decimal("0.01")
