"""
Unit tests for backtesting models.

Requirements: 12.1, 12.4
"""

# mypy: disable-error-code="attr-defined"

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.utils import timezone

import pytest

from trading.backtest_models import Backtest, BacktestResult
from trading.enums import TaskStatus

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
            "lot_size": 1.0,
            "scaling_mode": "additive",
            "retracement_pips": 30,
        },
        instrument="EUR_USD",
        start_date=timezone.now() - timedelta(days=30),
        end_date=timezone.now(),
        initial_balance=Decimal("10000.00"),
        commission_per_trade=Decimal("5.00"),
    )


@pytest.mark.django_db
class TestBacktestModel:
    """Test Backtest model."""

    def test_backtest_creation(self, user):
        """Test creating a backtest with valid data."""
        start_date = timezone.now() - timedelta(days=30)
        end_date = timezone.now()

        backtest = Backtest.objects.create(
            user=user,
            strategy_type="floor",
            config={"lot_size": 1.0},
            instrument="EUR_USD",
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal("10000.00"),
        )

        assert backtest.user == user
        assert backtest.strategy_type == "floor"
        assert backtest.config == {"lot_size": 1.0}
        assert backtest.instrument == "EUR_USD"
        assert backtest.start_date == start_date
        assert backtest.end_date == end_date
        assert backtest.initial_balance == Decimal("10000.00")
        assert backtest.status == TaskStatus.CREATED
        assert backtest.progress == 0

    def test_backtest_default_values(self, user):
        """Test backtest default field values."""
        backtest = Backtest.objects.create(
            user=user,
            strategy_type="floor",
            start_date=timezone.now(),
            end_date=timezone.now(),
        )

        assert backtest.config == {}
        assert backtest.instrument == "USD_JPY"
        assert backtest.initial_balance == Decimal("10000.00")
        assert backtest.commission_per_trade == Decimal("0")
        assert backtest.status == TaskStatus.CREATED
        assert backtest.progress == 0
        assert backtest.error_message is None

    def test_backtest_str_representation(self, backtest):
        """Test backtest string representation."""
        expected = f"floor backtest by {backtest.user.email} - created"
        assert str(backtest) == expected

    def test_backtest_start(self, backtest):
        """Test starting a backtest."""
        assert backtest.status == TaskStatus.CREATED
        assert backtest.started_at is None

        backtest.start()

        assert backtest.status == TaskStatus.RUNNING
        assert backtest.started_at is not None
        assert backtest.progress == 0

    def test_backtest_update_progress(self, backtest):
        """Test updating backtest progress."""
        backtest.start()

        backtest.update_progress(50)
        assert backtest.progress == 50

        backtest.update_progress(75)
        assert backtest.progress == 75

    def test_backtest_progress_bounds(self, backtest):
        """Test progress is bounded between 0 and 100."""
        backtest.update_progress(-10)
        assert backtest.progress == 0

        backtest.update_progress(150)
        assert backtest.progress == 100

    def test_backtest_complete(self, backtest):
        """Test completing a backtest."""
        backtest.start()
        assert backtest.status == TaskStatus.RUNNING
        assert backtest.completed_at is None

        backtest.complete()

        assert backtest.status == TaskStatus.COMPLETED
        assert backtest.completed_at is not None
        assert backtest.progress == 100

    def test_backtest_fail(self, backtest):
        """Test failing a backtest."""
        backtest.start()
        error_msg = "Connection timeout"

        backtest.fail(error_msg)

        assert backtest.status == TaskStatus.FAILED
        assert backtest.error_message == error_msg
        assert backtest.completed_at is not None

    def test_backtest_cancel(self, backtest):
        """Test cancelling a backtest."""
        backtest.start()

        backtest.cancel()

        assert backtest.status == TaskStatus.STOPPED
        assert backtest.completed_at is not None

    def test_backtest_status_transitions(self, backtest):
        """Test backtest status transitions."""
        # created -> running
        assert backtest.status == TaskStatus.CREATED
        backtest.start()
        assert backtest.status == TaskStatus.RUNNING

        # running -> completed
        backtest.complete()
        assert backtest.status == TaskStatus.COMPLETED

        # Test another backtest: running -> failed
        backtest2 = Backtest.objects.create(
            user=backtest.user,
            strategy_type="floor",
            start_date=timezone.now(),
            end_date=timezone.now(),
        )
        backtest2.start()
        backtest2.fail("Test error")
        assert backtest2.status == TaskStatus.FAILED

        # Test another backtest: running -> stopped
        backtest3 = Backtest.objects.create(
            user=backtest.user,
            strategy_type="floor",
            start_date=timezone.now(),
            end_date=timezone.now(),
        )
        backtest3.start()
        backtest3.cancel()
        assert backtest3.status == TaskStatus.STOPPED

    def test_backtest_duration_property(self, backtest):
        """Test backtest duration calculation."""
        # No duration when not started
        assert backtest.duration == "N/A"

        # Start and complete immediately
        backtest.start()
        backtest.complete()

        # Duration should be in seconds
        assert "s" in backtest.duration or "m" in backtest.duration

    def test_backtest_is_running_property(self, backtest):
        """Test is_running property."""
        assert not backtest.is_running

        backtest.start()
        assert backtest.is_running

        backtest.complete()
        assert not backtest.is_running

    def test_backtest_is_completed_property(self, backtest):
        """Test is_completed property."""
        assert not backtest.is_completed

        backtest.start()
        assert not backtest.is_completed

        backtest.complete()
        assert backtest.is_completed


@pytest.mark.django_db
class TestBacktestResultModel:
    """Test BacktestResult model."""

    def test_backtest_result_creation(self, backtest):
        """Test creating a backtest result."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("12000.00"),
            total_return=Decimal("20.0000"),
            total_pnl=Decimal("2000.00"),
            max_drawdown=Decimal("5.0000"),
            max_drawdown_amount=Decimal("500.00"),
            sharpe_ratio=Decimal("1.5000"),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("60.00"),
            average_win=Decimal("50.00"),
            average_loss=Decimal("-30.00"),
            largest_win=Decimal("200.00"),
            largest_loss=Decimal("-150.00"),
            profit_factor=Decimal("1.6667"),
        )

        assert result.backtest == backtest
        assert result.final_balance == Decimal("12000.00")
        assert result.total_return == Decimal("20.0000")
        assert result.total_pnl == Decimal("2000.00")
        assert result.max_drawdown == Decimal("5.0000")
        assert result.sharpe_ratio == Decimal("1.5000")
        assert result.total_trades == 100
        assert result.winning_trades == 60
        assert result.losing_trades == 40
        assert result.win_rate == Decimal("60.00")

    def test_backtest_result_str_representation(self, backtest):
        """Test backtest result string representation."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("12000.00"),
            total_return=Decimal("20.0000"),
            total_pnl=Decimal("2000.00"),
            max_drawdown=Decimal("5.0000"),
            max_drawdown_amount=Decimal("500.00"),
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            win_rate=Decimal("60.00"),
            average_win=Decimal("50.00"),
            average_loss=Decimal("-30.00"),
            largest_win=Decimal("200.00"),
            largest_loss=Decimal("-150.00"),
        )

        expected = "Results for floor - Return: 20.0000%"
        assert str(result) == expected

    def test_calculate_metrics_with_trades(self, backtest):
        """Test calculating metrics with trade data."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("10000.00"),
            total_return=Decimal("0"),
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_amount=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
        )

        trades = [
            {"pnl": 100.0, "instrument": "EUR_USD"},
            {"pnl": -50.0, "instrument": "EUR_USD"},
            {"pnl": 150.0, "instrument": "GBP_USD"},
            {"pnl": -30.0, "instrument": "GBP_USD"},
            {"pnl": 80.0, "instrument": "EUR_USD"},
        ]

        equity_curve = [
            {"timestamp": "2024-01-01", "balance": 10000.0},
            {"timestamp": "2024-01-02", "balance": 10100.0},
            {"timestamp": "2024-01-03", "balance": 10050.0},
            {"timestamp": "2024-01-04", "balance": 10200.0},
            {"timestamp": "2024-01-05", "balance": 10170.0},
            {"timestamp": "2024-01-06", "balance": 10250.0},
        ]

        result.calculate_metrics(trades, equity_curve, Decimal("10000.00"))

        assert result.total_trades == 5
        assert result.winning_trades == 3
        assert result.losing_trades == 2
        assert result.win_rate == Decimal("60.00")
        assert result.final_balance == Decimal("10250.0")
        assert result.total_pnl == Decimal("250.0")
        assert result.total_return == Decimal("2.5")

    def test_calculate_metrics_no_trades(self, backtest):
        """Test calculating metrics with no trades."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("10000.00"),
            total_return=Decimal("0"),
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_amount=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
        )

        result.calculate_metrics([], [], Decimal("10000.00"))

        assert result.total_trades == 0
        assert result.winning_trades == 0
        assert result.losing_trades == 0
        assert result.win_rate == Decimal("0")
        assert result.final_balance == Decimal("10000.00")
        assert result.total_pnl == Decimal("0")
        assert result.total_return == Decimal("0")

    def test_equity_curve_json_field(self, backtest):
        """Test equity curve JSON field storage."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("11000.00"),
            total_return=Decimal("10.0000"),
            total_pnl=Decimal("1000.00"),
            max_drawdown=Decimal("2.0000"),
            max_drawdown_amount=Decimal("200.00"),
            total_trades=10,
            winning_trades=6,
            losing_trades=4,
            win_rate=Decimal("60.00"),
            average_win=Decimal("200.00"),
            average_loss=Decimal("-100.00"),
            largest_win=Decimal("300.00"),
            largest_loss=Decimal("-150.00"),
            equity_curve=[
                {"timestamp": "2024-01-01T00:00:00Z", "balance": 10000.0},
                {"timestamp": "2024-01-02T00:00:00Z", "balance": 10500.0},
                {"timestamp": "2024-01-03T00:00:00Z", "balance": 11000.0},
            ],
        )

        assert isinstance(result.equity_curve, list)
        assert len(result.equity_curve) == 3
        assert result.equity_curve[0]["balance"] == 10000.0
        assert result.equity_curve[-1]["balance"] == 11000.0

    def test_max_drawdown_calculation(self, backtest):
        """Test maximum drawdown calculation."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("10000.00"),
            total_return=Decimal("0"),
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_amount=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
        )

        equity_curve = [
            {"timestamp": "2024-01-01", "balance": 10000.0},
            {"timestamp": "2024-01-02", "balance": 11000.0},  # Peak
            {"timestamp": "2024-01-03", "balance": 10500.0},  # Drawdown 500
            {"timestamp": "2024-01-04", "balance": 10200.0},  # Drawdown 800
            {"timestamp": "2024-01-05", "balance": 10800.0},  # Recovery
        ]

        result._calculate_max_drawdown(equity_curve, Decimal("10000.00"))

        # Max drawdown should be 800 from peak of 11000
        # That's 7.27% drawdown
        assert result.max_drawdown_amount == Decimal("800")
        assert result.max_drawdown > Decimal("7.0")
        assert result.max_drawdown < Decimal("8.0")

    def test_profit_factor_calculation(self, backtest):
        """Test profit factor calculation."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("10000.00"),
            total_return=Decimal("0"),
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_amount=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
        )

        # Gross profit: 300, Gross loss: 150
        # Profit factor: 300 / 150 = 2.0
        trades = [
            {"pnl": 100.0},
            {"pnl": 200.0},
            {"pnl": -50.0},
            {"pnl": -100.0},
        ]

        equity_curve = [
            {"timestamp": "2024-01-01", "balance": 10000.0},
            {"timestamp": "2024-01-02", "balance": 10150.0},
        ]

        result.calculate_metrics(trades, equity_curve, Decimal("10000.00"))

        assert result.profit_factor == Decimal("2.0")

    def test_profit_factor_no_losses(self, backtest):
        """Test profit factor when there are no losing trades."""
        result = BacktestResult.objects.create(
            backtest=backtest,
            final_balance=Decimal("10000.00"),
            total_return=Decimal("0"),
            total_pnl=Decimal("0"),
            max_drawdown=Decimal("0"),
            max_drawdown_amount=Decimal("0"),
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=Decimal("0"),
            average_win=Decimal("0"),
            average_loss=Decimal("0"),
            largest_win=Decimal("0"),
            largest_loss=Decimal("0"),
        )

        trades = [
            {"pnl": 100.0},
            {"pnl": 200.0},
        ]

        equity_curve = [
            {"timestamp": "2024-01-01", "balance": 10000.0},
            {"timestamp": "2024-01-02", "balance": 10300.0},
        ]

        result.calculate_metrics(trades, equity_curve, Decimal("10000.00"))

        # Profit factor should be None when there are no losses
        assert result.profit_factor is None
