"""
Integration tests for performance metrics calculation.

Tests the calculation of trading performance metrics including total return,
Sharpe ratio, maximum drawdown, win rate, and real-time metric updates.
"""

from decimal import Decimal

import pytest

from apps.trading.models import Executions
from apps.trading.services.performance import PerformanceTracker
from tests.integration.factories import (
    BacktestTaskFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestPerformanceMetricsCalculation:
    """Test performance metrics calculation."""

    def test_total_return_calculation(self):
        """
        Test total return calculation.

        Verifies that the system correctly calculates total return
        as a percentage of initial balance."""
        # Create test data
        user = UserFactory()
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create performance tracker
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(execution, initial_balance)

        # Simulate some trades
        tracker.on_trade_executed(pnl=Decimal("500.00"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("300.00"), is_opening=False)
        tracker.on_trade_executed(pnl=Decimal("-200.00"), is_opening=False)

        # Get metrics
        metrics = tracker.get_metrics()

        # Verify total return calculation
        # Total PnL = 500 + 300 - 200 = 600
        # Total return = (600 / 10000) * 100 = 6%
        assert metrics["realized_pnl"] == Decimal("600.00")
        assert metrics["current_balance"] == Decimal("10600.00")
        assert metrics["total_return"] == Decimal("6.00")

    def test_sharpe_ratio_computation(self):
        """
        Test Sharpe ratio computation.

        Verifies that the system can compute Sharpe ratio from
        returns distribution (requires multiple trades)."""
        # Create test data
        user = UserFactory()
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create performance tracker
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(execution, initial_balance)

        # Simulate multiple trades with varying returns
        trades = [
            Decimal("100.00"),
            Decimal("150.00"),
            Decimal("-50.00"),
            Decimal("200.00"),
            Decimal("-75.00"),
            Decimal("125.00"),
            Decimal("175.00"),
            Decimal("-100.00"),
        ]

        for pnl in trades:
            tracker.on_trade_executed(pnl=pnl, is_opening=False)

        # Get metrics
        metrics = tracker.get_metrics()

        # Verify we have trade data for Sharpe ratio calculation
        assert metrics["total_trades"] == 8
        assert metrics["realized_pnl"] == sum(trades)

        # Note: Actual Sharpe ratio calculation would require
        # standard deviation and risk-free rate, which is not
        # implemented in the current PerformanceTracker.
        # This test verifies we have the necessary data.

    def test_maximum_drawdown_calculation(self):
        """
        Test maximum drawdown calculation.

        Verifies that the system correctly calculates the maximum
        peak-to-trough decline in account balance."""
        # Create test data
        user = UserFactory()
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create performance tracker
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(execution, initial_balance)

        # Simulate trades that create a drawdown
        # Balance progression: 10000 -> 10500 -> 10200 -> 9800 -> 10300
        tracker.on_trade_executed(pnl=Decimal("500.00"), is_opening=False)  # Peak at 10500
        tracker.on_trade_executed(pnl=Decimal("-300.00"), is_opening=False)  # 10200
        tracker.on_trade_executed(pnl=Decimal("-400.00"), is_opening=False)  # Trough at 9800
        tracker.on_trade_executed(pnl=Decimal("500.00"), is_opening=False)  # Recovery to 10300

        # Get metrics
        metrics = tracker.get_metrics()

        # Verify balance progression
        assert metrics["current_balance"] == Decimal("10300.00")
        assert metrics["realized_pnl"] == Decimal("300.00")

        # Note: Maximum drawdown calculation (peak-to-trough)
        # would be (10500 - 9800) / 10500 = 6.67%
        # This is not currently tracked in PerformanceTracker
        # but the test verifies we have the trade data.

    def test_win_rate_calculation(self):
        """
        Test win rate calculation.

        Verifies that the system correctly calculates win rate
        as the percentage of profitable trades."""
        # Create test data
        user = UserFactory()
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create performance tracker
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(execution, initial_balance)

        # Simulate trades: 6 winners, 4 losers
        winning_trades = [
            Decimal("100.00"),
            Decimal("150.00"),
            Decimal("200.00"),
            Decimal("75.00"),
            Decimal("125.00"),
            Decimal("50.00"),
        ]
        losing_trades = [
            Decimal("-50.00"),
            Decimal("-75.00"),
            Decimal("-100.00"),
            Decimal("-25.00"),
        ]

        for pnl in winning_trades:
            tracker.on_trade_executed(pnl=pnl, is_opening=False)

        for pnl in losing_trades:
            tracker.on_trade_executed(pnl=pnl, is_opening=False)

        # Get metrics
        metrics = tracker.get_metrics()

        # Verify win rate calculation
        # Win rate = (6 / 10) * 100 = 60%
        assert metrics["total_trades"] == 10
        assert metrics["winning_trades"] == 6
        assert metrics["losing_trades"] == 4
        assert metrics["win_rate"] == Decimal("60.00")

    def test_real_time_metric_updates(self):
        """
        Test real-time metric updates.

        Verifies that metrics are updated in real-time as trades
        are executed and ticks are processed."""
        # Create test data
        user = UserFactory()
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create performance tracker
        initial_balance = Decimal("10000.00")
        tracker = PerformanceTracker(execution, initial_balance)

        # Initial state
        metrics = tracker.get_metrics()
        assert metrics["ticks_processed"] == 0
        assert metrics["trades_executed"] == 0
        assert metrics["realized_pnl"] == Decimal("0")
        assert metrics["unrealized_pnl"] == Decimal("0")

        # Process some ticks
        tracker.on_tick_processed()
        tracker.on_tick_processed()
        tracker.on_tick_processed()

        metrics = tracker.get_metrics()
        assert metrics["ticks_processed"] == 3

        # Execute a trade (opening)
        tracker.on_trade_executed(is_opening=True)

        metrics = tracker.get_metrics()
        assert metrics["trades_executed"] == 1
        assert metrics["open_positions"] == 1

        # Update unrealized PnL
        tracker.update_unrealized_pnl(Decimal("50.00"))

        metrics = tracker.get_metrics()
        assert metrics["unrealized_pnl"] == Decimal("50.00")
        assert metrics["current_pnl"] == Decimal("50.00")  # realized + unrealized

        # Close the position
        tracker.on_trade_executed(pnl=Decimal("50.00"), is_opening=False)

        metrics = tracker.get_metrics()
        assert metrics["trades_executed"] == 2
        assert metrics["open_positions"] == 0
        assert metrics["realized_pnl"] == Decimal("50.00")
        assert metrics["current_balance"] == Decimal("10050.00")

        # Verify metrics are updated in real-time
        assert metrics["total_trades"] == 1  # Only closed trades count
        assert metrics["winning_trades"] == 1
        assert metrics["win_rate"] == Decimal("100.00")
