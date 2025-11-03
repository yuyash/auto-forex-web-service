"""
Unit tests for backtest performance calculation.

This module tests the performance metrics calculation functionality
of the BacktestEngine including:
- Total return calculation
- Maximum drawdown calculation
- Sharpe ratio calculation
- Win rate calculation
- Profit factor calculation
- Equity curve generation

Requirements: 12.4
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from trading.backtest_engine import BacktestConfig, BacktestEngine


@pytest.fixture
def backtest_config():
    """Create a test backtest configuration."""
    return BacktestConfig(
        strategy_type="test_strategy",
        strategy_config={},
        instruments=["EUR_USD"],
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        initial_balance=Decimal("10000.00"),
        slippage_pips=Decimal("0"),
        commission_per_trade=Decimal("0"),
    )


@pytest.fixture
def backtest_engine(backtest_config):
    """Create a BacktestEngine instance."""
    return BacktestEngine(backtest_config)


@pytest.fixture
def sample_trades_winning():
    """Create sample winning trades."""
    return [
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


@pytest.fixture
def sample_trades_mixed():
    """Create sample mixed (winning and losing) trades."""
    return [
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
            "exit_price": 1.1020,
            "entry_time": "2024-01-01T12:00:00",
            "exit_time": "2024-01-01T13:00:00",
            "duration": 3600,
            "pnl": -30.0,
            "reason": "stop_loss",
        },
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1020,
            "exit_price": 1.1080,
            "entry_time": "2024-01-01T14:00:00",
            "exit_time": "2024-01-01T15:00:00",
            "duration": 3600,
            "pnl": 60.0,
            "reason": "take_profit",
        },
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1080,
            "exit_price": 1.1050,
            "entry_time": "2024-01-01T16:00:00",
            "exit_time": "2024-01-01T17:00:00",
            "duration": 3600,
            "pnl": -30.0,
            "reason": "stop_loss",
        },
        {
            "instrument": "EUR_USD",
            "direction": "long",
            "units": 10000,
            "entry_price": 1.1050,
            "exit_price": 1.1100,
            "entry_time": "2024-01-01T18:00:00",
            "exit_time": "2024-01-01T19:00:00",
            "duration": 3600,
            "pnl": 50.0,
            "reason": "take_profit",
        },
    ]


@pytest.fixture
def sample_equity_curve_upward():
    """Create sample equity curve with upward trend."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    return [
        {"timestamp": base_time.isoformat(), "balance": 10000.0},
        {"timestamp": (base_time + timedelta(hours=1)).isoformat(), "balance": 10050.0},
        {"timestamp": (base_time + timedelta(hours=2)).isoformat(), "balance": 10100.0},
        {"timestamp": (base_time + timedelta(hours=3)).isoformat(), "balance": 10150.0},
    ]


@pytest.fixture
def sample_equity_curve_with_drawdown():
    """Create sample equity curve with drawdown."""
    base_time = datetime(2024, 1, 1, 10, 0, 0)
    return [
        {"timestamp": base_time.isoformat(), "balance": 10000.0},
        {"timestamp": (base_time + timedelta(hours=1)).isoformat(), "balance": 10050.0},
        {"timestamp": (base_time + timedelta(hours=2)).isoformat(), "balance": 10020.0},  # Drawdown
        {"timestamp": (base_time + timedelta(hours=3)).isoformat(), "balance": 10080.0},
        {"timestamp": (base_time + timedelta(hours=4)).isoformat(), "balance": 10050.0},  # Drawdown
        {"timestamp": (base_time + timedelta(hours=5)).isoformat(), "balance": 10100.0},
    ]


class TestTotalReturnCalculation:
    """Test total return calculation."""

    def test_total_return_with_profit(self, backtest_engine, sample_trades_winning):
        """Test total return calculation with profitable trades."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_winning
        backtest_engine.balance = Decimal("10150.00")  # Initial 10000 + 150 profit
        backtest_engine.equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000.0},
            {"timestamp": "2024-01-01T15:00:00", "balance": 10150.0},
        ]

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify total return
        assert metrics["total_pnl"] == 150.0
        assert metrics["total_return"] == 1.5  # 150 / 10000 * 100 = 1.5%
        assert metrics["final_balance"] == 10150.0
        assert metrics["initial_balance"] == 10000.0

    def test_total_return_with_loss(self, backtest_engine):
        """Test total return calculation with losing trades."""
        # Set up engine state with losses
        backtest_engine.trade_log = [
            {
                "instrument": "EUR_USD",
                "direction": "long",
                "units": 10000,
                "entry_price": 1.1000,
                "exit_price": 1.0950,
                "entry_time": "2024-01-01T10:00:00",
                "exit_time": "2024-01-01T11:00:00",
                "duration": 3600,
                "pnl": -50.0,
                "reason": "stop_loss",
            }
        ]
        backtest_engine.balance = Decimal("9950.00")
        backtest_engine.equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000.0},
            {"timestamp": "2024-01-01T11:00:00", "balance": 9950.0},
        ]

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify total return
        assert metrics["total_pnl"] == -50.0
        assert metrics["total_return"] == -0.5  # -50 / 10000 * 100 = -0.5%

    def test_total_return_with_no_trades(self, backtest_engine):
        """Test total return calculation with no trades."""
        # Set up engine state with no trades
        backtest_engine.trade_log = []
        backtest_engine.balance = Decimal("10000.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify zero return
        assert metrics["total_pnl"] == 0.0
        assert metrics["total_return"] == 0.0
        assert metrics["total_trades"] == 0


class TestMaxDrawdownCalculation:
    """Test maximum drawdown calculation."""

    def test_max_drawdown_with_decline(self, backtest_engine, sample_equity_curve_with_drawdown):
        """Test max drawdown calculation with equity decline."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_with_drawdown

        # Calculate max drawdown
        dd_metrics = backtest_engine._calculate_max_drawdown()

        # Peak was 10080, trough was 10050, drawdown = 30
        # Percentage: (30 / 10080) * 100 = 0.2976%
        assert dd_metrics["max_drawdown_amount"] == 30.0
        assert abs(dd_metrics["max_drawdown"] - 0.2976) < 0.01  # Allow small rounding error

    def test_max_drawdown_with_no_decline(self, backtest_engine, sample_equity_curve_upward):
        """Test max drawdown calculation with no decline."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_upward

        # Calculate max drawdown
        dd_metrics = backtest_engine._calculate_max_drawdown()

        # No drawdown in upward trend
        assert dd_metrics["max_drawdown"] == 0.0
        assert dd_metrics["max_drawdown_amount"] == 0.0

    def test_max_drawdown_with_empty_curve(self, backtest_engine):
        """Test max drawdown calculation with empty equity curve."""
        # Set up engine state
        backtest_engine.equity_curve = []

        # Calculate max drawdown
        dd_metrics = backtest_engine._calculate_max_drawdown()

        # No drawdown with empty curve
        assert dd_metrics["max_drawdown"] == 0.0
        assert dd_metrics["max_drawdown_amount"] == 0.0


class TestSharpeRatioCalculation:
    """Test Sharpe ratio calculation."""

    def test_sharpe_ratio_with_positive_returns(self, backtest_engine, sample_equity_curve_upward):
        """Test Sharpe ratio calculation with positive returns."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_upward

        # Calculate Sharpe ratio
        sharpe = backtest_engine._calculate_sharpe_ratio()

        # Should have positive Sharpe ratio with consistent positive returns
        assert sharpe is not None
        assert sharpe > 0

    def test_sharpe_ratio_with_volatile_returns(
        self, backtest_engine, sample_equity_curve_with_drawdown
    ):
        """Test Sharpe ratio calculation with volatile returns."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_with_drawdown

        # Calculate Sharpe ratio
        sharpe = backtest_engine._calculate_sharpe_ratio()

        # Should have lower Sharpe ratio with volatile returns
        assert sharpe is not None
        # Sharpe will be lower due to volatility

    def test_sharpe_ratio_with_insufficient_data(self, backtest_engine):
        """Test Sharpe ratio calculation with insufficient data."""
        # Set up engine state with only one point
        backtest_engine.equity_curve = [{"timestamp": "2024-01-01T10:00:00", "balance": 10000.0}]

        # Calculate Sharpe ratio
        sharpe = backtest_engine._calculate_sharpe_ratio()

        # Should return None with insufficient data
        assert sharpe is None

    def test_sharpe_ratio_with_zero_volatility(self, backtest_engine):
        """Test Sharpe ratio calculation with zero volatility."""
        # Set up engine state with constant balance (no volatility)
        backtest_engine.equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000.0},
            {"timestamp": "2024-01-01T11:00:00", "balance": 10000.0},
            {"timestamp": "2024-01-01T12:00:00", "balance": 10000.0},
        ]

        # Calculate Sharpe ratio
        sharpe = backtest_engine._calculate_sharpe_ratio()

        # Should return None with zero volatility
        assert sharpe is None


class TestWinRateCalculation:
    """Test win rate calculation."""

    def test_win_rate_with_all_winning_trades(self, backtest_engine, sample_trades_winning):
        """Test win rate calculation with all winning trades."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_winning
        backtest_engine.balance = Decimal("10150.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify win rate
        assert metrics["total_trades"] == 3
        assert metrics["winning_trades"] == 3
        assert metrics["losing_trades"] == 0
        assert metrics["win_rate"] == 100.0

    def test_win_rate_with_mixed_trades(self, backtest_engine, sample_trades_mixed):
        """Test win rate calculation with mixed trades."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_mixed
        backtest_engine.balance = Decimal("10100.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify win rate: 3 wins out of 5 trades = 60%
        assert metrics["total_trades"] == 5
        assert metrics["winning_trades"] == 3
        assert metrics["losing_trades"] == 2
        assert metrics["win_rate"] == 60.0

    def test_win_rate_with_no_trades(self, backtest_engine):
        """Test win rate calculation with no trades."""
        # Set up engine state
        backtest_engine.trade_log = []
        backtest_engine.balance = Decimal("10000.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify zero win rate
        assert metrics["win_rate"] == 0.0


class TestProfitFactorCalculation:
    """Test profit factor calculation."""

    def test_profit_factor_with_mixed_trades(self, backtest_engine, sample_trades_mixed):
        """Test profit factor calculation with mixed trades."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_mixed
        backtest_engine.balance = Decimal("10100.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify profit factor
        # Gross profit: 50 + 60 + 50 = 160
        # Gross loss: 30 + 30 = 60
        # Profit factor: 160 / 60 = 2.6667
        assert metrics["profit_factor"] is not None
        assert abs(metrics["profit_factor"] - 2.6667) < 0.01

    def test_profit_factor_with_only_winning_trades(self, backtest_engine, sample_trades_winning):
        """Test profit factor calculation with only winning trades."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_winning
        backtest_engine.balance = Decimal("10150.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify profit factor is None (no losses to divide by)
        assert metrics["profit_factor"] is None

    def test_profit_factor_with_only_losing_trades(self, backtest_engine):
        """Test profit factor calculation with only losing trades."""
        # Set up engine state
        backtest_engine.trade_log = [
            {
                "instrument": "EUR_USD",
                "direction": "long",
                "units": 10000,
                "entry_price": 1.1000,
                "exit_price": 1.0950,
                "entry_time": "2024-01-01T10:00:00",
                "exit_time": "2024-01-01T11:00:00",
                "duration": 3600,
                "pnl": -50.0,
                "reason": "stop_loss",
            }
        ]
        backtest_engine.balance = Decimal("9950.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify profit factor is 0 (no profits)
        assert metrics["profit_factor"] == 0.0


class TestAverageWinLossCalculation:
    """Test average win/loss calculation."""

    def test_average_win_and_loss(self, backtest_engine, sample_trades_mixed):
        """Test average win and loss calculation."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_mixed
        backtest_engine.balance = Decimal("10100.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify average win: (50 + 60 + 50) / 3 = 53.33
        assert abs(metrics["average_win"] - 53.33) < 0.01

        # Verify average loss: (-30 + -30) / 2 = -30
        assert metrics["average_loss"] == -30.0

        # Verify largest win and loss
        assert metrics["largest_win"] == 60.0
        assert metrics["largest_loss"] == -30.0

    def test_average_win_with_no_losses(self, backtest_engine, sample_trades_winning):
        """Test average win calculation with no losses."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_winning
        backtest_engine.balance = Decimal("10150.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify average win: (50 + 50 + 50) / 3 = 50
        assert metrics["average_win"] == 50.0

        # Verify no losses
        assert metrics["average_loss"] == 0.0
        assert metrics["largest_loss"] == 0.0


class TestEquityCurveGeneration:
    """Test equity curve generation."""

    def test_equity_curve_populated(self, backtest_engine, sample_equity_curve_upward):
        """Test that equity curve is properly populated."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_upward

        # Verify equity curve structure
        assert len(backtest_engine.equity_curve) == 4
        assert all("timestamp" in point for point in backtest_engine.equity_curve)
        assert all("balance" in point for point in backtest_engine.equity_curve)

        # Verify balance progression
        assert backtest_engine.equity_curve[0]["balance"] == 10000.0
        assert backtest_engine.equity_curve[-1]["balance"] == 10150.0

    def test_equity_curve_used_in_calculations(
        self, backtest_engine, sample_equity_curve_with_drawdown, sample_trades_mixed
    ):
        """Test that equity curve is used in performance calculations."""
        # Set up engine state
        backtest_engine.equity_curve = sample_equity_curve_with_drawdown
        backtest_engine.trade_log = sample_trades_mixed
        backtest_engine.balance = Decimal("10100.00")

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify that drawdown was calculated from equity curve
        assert metrics["max_drawdown"] > 0
        assert metrics["max_drawdown_amount"] > 0

        # Verify that Sharpe ratio was calculated from equity curve
        assert metrics["sharpe_ratio"] is not None


class TestComprehensivePerformanceMetrics:
    """Test comprehensive performance metrics calculation."""

    def test_all_metrics_calculated(self, backtest_engine, sample_trades_mixed):
        """Test that all performance metrics are calculated."""
        # Set up engine state
        backtest_engine.trade_log = sample_trades_mixed
        backtest_engine.balance = Decimal("10100.00")
        backtest_engine.equity_curve = [
            {"timestamp": "2024-01-01T10:00:00", "balance": 10000.0},
            {"timestamp": "2024-01-01T11:00:00", "balance": 10050.0},
            {"timestamp": "2024-01-01T12:00:00", "balance": 10020.0},
            {"timestamp": "2024-01-01T13:00:00", "balance": 10080.0},
            {"timestamp": "2024-01-01T14:00:00", "balance": 10050.0},
            {"timestamp": "2024-01-01T15:00:00", "balance": 10100.0},
        ]

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify all expected metrics are present
        expected_keys = [
            "total_trades",
            "final_balance",
            "initial_balance",
            "total_pnl",
            "total_return",
            "winning_trades",
            "losing_trades",
            "win_rate",
            "average_win",
            "average_loss",
            "largest_win",
            "largest_loss",
            "profit_factor",
            "max_drawdown",
            "max_drawdown_amount",
            "sharpe_ratio",
            "average_trade_duration",
        ]

        for key in expected_keys:
            assert key in metrics, f"Missing metric: {key}"

        # Verify metric values are reasonable
        assert metrics["total_trades"] == 5
        assert metrics["final_balance"] == 10100.0
        assert metrics["total_return"] == 1.0  # 100 / 10000 * 100 = 1%
        assert metrics["win_rate"] == 60.0
        assert metrics["profit_factor"] is not None
        assert metrics["max_drawdown"] > 0
        assert metrics["sharpe_ratio"] is not None

    def test_zero_metrics_with_no_trades(self, backtest_engine):
        """Test that zero metrics are returned with no trades."""
        # Set up engine state with no trades
        backtest_engine.trade_log = []
        backtest_engine.balance = Decimal("10000.00")
        backtest_engine.equity_curve = []

        # Calculate metrics
        metrics = backtest_engine.calculate_performance_metrics()

        # Verify zero metrics
        assert metrics["total_trades"] == 0
        assert metrics["total_pnl"] == 0.0
        assert metrics["total_return"] == 0.0
        assert metrics["winning_trades"] == 0
        assert metrics["losing_trades"] == 0
        assert metrics["win_rate"] == 0.0
        assert metrics["profit_factor"] is None
        assert metrics["max_drawdown"] == 0.0
        assert metrics["sharpe_ratio"] is None
