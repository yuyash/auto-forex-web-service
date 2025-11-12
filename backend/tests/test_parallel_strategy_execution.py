"""
Unit tests for parallel strategy execution and comparison.

This module tests:
- Parallel execution of multiple strategies
- Strategy isolation (no shared state)
- Comparison metrics calculation
- Comparison report generation
- API endpoints for strategy comparison
- Maximum concurrent strategy limit (10)

Requirements: 5.1, 5.3, 12.4
"""

# mypy: disable-error-code="attr-defined"

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from trading.historical_data_loader import TickDataPoint
from trading.parallel_strategy_executor import (
    ParallelStrategyExecutor,
    StrategyComparisonConfig,
    StrategyComparisonEngine,
)
from trading.strategy_comparison_views import StrategyComparison

User = get_user_model()


class TestParallelStrategyExecution(TestCase):
    """Test parallel execution of multiple strategies."""

    def setUp(self):
        """Set up test data."""
        self.start_date = datetime(2024, 1, 1, 0, 0, 0)
        self.end_date = datetime(2024, 1, 31, 23, 59, 59)

        # Create sample tick data
        self.tick_data = [
            TickDataPoint(
                instrument="EUR_USD",
                timestamp=self.start_date + timedelta(minutes=i),
                bid=Decimal("1.1000") + Decimal(str(i * 0.0001)),
                ask=Decimal("1.1002") + Decimal(str(i * 0.0001)),
                mid=Decimal("1.1001") + Decimal(str(i * 0.0001)),
                spread=Decimal("0.0002"),
            )
            for i in range(100)
        ]

        # Create strategy configs
        self.strategy_configs = [
            {
                "strategy_type": "floor",
                "name": "Floor Strategy A",
                "config": {
                    "base_lot": 1000,
                    "scaling_factor": 1.5,
                    "max_layers": 3,
                },
            },
            {
                "strategy_type": "trend_following",
                "name": "Trend Following B",
                "config": {
                    "fast_period": 10,
                    "slow_period": 20,
                    "lot_size": 1000,
                },
            },
        ]

    def test_parallel_execution_success(self):
        """Test successful parallel execution of multiple strategies."""
        config = StrategyComparisonConfig(
            strategy_configs=self.strategy_configs,
            instrument="EUR_USD",
            start_date=self.start_date,
            end_date=self.end_date,
            initial_balance=Decimal("10000"),
            commission_per_trade=Decimal("2.0"),
            max_workers=2,
        )

        executor = ParallelStrategyExecutor(config)
        results = executor.execute_strategies(self.tick_data)

        # Verify results
        assert len(results) == 2
        assert all("strategy_name" in r for r in results)
        assert all("strategy_type" in r for r in results)
        assert all("success" in r for r in results)
        assert all("performance_metrics" in r for r in results)

    def test_parallel_execution_max_strategies_limit(self):
        """Test maximum concurrent strategy limit (10)."""
        # Create 11 strategy configs
        many_configs = [
            {
                "strategy_type": "floor",
                "name": f"Strategy {i}",
                "config": {"base_lot": 1000},
            }
            for i in range(11)
        ]

        config = StrategyComparisonConfig(
            strategy_configs=many_configs,
            instrument="EUR_USD",
            start_date=self.start_date,
            end_date=self.end_date,
            initial_balance=Decimal("10000"),
        )

        executor = ParallelStrategyExecutor(config)

        # Should raise ValueError for more than 10 strategies
        with pytest.raises(ValueError, match="Maximum 10 strategies allowed"):
            executor.execute_strategies(self.tick_data)

    def test_strategy_isolation(self):
        """Test strategy isolation (no shared state)."""
        # Create two identical strategy configs
        identical_configs = [
            {
                "strategy_type": "floor",
                "name": "Floor Strategy 1",
                "config": {"base_lot": 1000},
            },
            {
                "strategy_type": "floor",
                "name": "Floor Strategy 2",
                "config": {"base_lot": 1000},
            },
        ]

        config = StrategyComparisonConfig(
            strategy_configs=identical_configs,
            instrument="EUR_USD",
            start_date=self.start_date,
            end_date=self.end_date,
            initial_balance=Decimal("10000"),
        )

        executor = ParallelStrategyExecutor(config)
        results = executor.execute_strategies(self.tick_data)

        # Both strategies should have identical results (no shared state)
        assert len(results) == 2
        assert results[0]["success"] == results[1]["success"]

        # If both succeeded, verify they have independent results
        if results[0]["success"] and results[1]["success"]:
            # Results should be similar but not the exact same object
            assert results[0] is not results[1]
            assert results[0]["strategy_name"] != results[1]["strategy_name"]

    def test_parallel_execution_with_failures(self):
        """Test parallel execution handles strategy failures gracefully."""
        # Create configs with one invalid strategy
        mixed_configs = [
            {
                "strategy_type": "floor",
                "name": "Valid Strategy",
                "config": {"base_lot": 1000},
            },
            {
                "strategy_type": "invalid_strategy_type",
                "name": "Invalid Strategy",
                "config": {},
            },
        ]

        config = StrategyComparisonConfig(
            strategy_configs=mixed_configs,
            instrument="EUR_USD",
            start_date=self.start_date,
            end_date=self.end_date,
            initial_balance=Decimal("10000"),
        )

        executor = ParallelStrategyExecutor(config)
        results = executor.execute_strategies(self.tick_data)

        # Should return results for both, with one failed
        assert len(results) == 2
        assert any(r["success"] is False for r in results)
        assert any(r["error"] is not None for r in results)


class TestStrategyComparisonEngine(TestCase):
    """Test comparison metrics calculation and report generation."""

    def setUp(self):
        """Set up test data."""
        # Create sample strategy results
        self.strategy_results = [
            {
                "strategy_name": "Strategy A",
                "strategy_type": "floor",
                "config": {},
                "success": True,
                "error": None,
                "trade_log": [
                    {"pnl": 100},
                    {"pnl": -50},
                    {"pnl": 150},
                ],
                "equity_curve": [
                    {"timestamp": "2024-01-01T00:00:00", "balance": 10000},
                    {"timestamp": "2024-01-01T01:00:00", "balance": 10100},
                    {"timestamp": "2024-01-01T02:00:00", "balance": 10050},
                    {"timestamp": "2024-01-01T03:00:00", "balance": 10200},
                ],
                "performance_metrics": {
                    "total_return": 2.0,
                    "total_trades": 3,
                    "win_rate": 66.67,
                    "sharpe_ratio": 1.5,
                    "max_drawdown": 5.0,
                    "profit_factor": 2.5,
                    "final_balance": 10200,
                    "winning_trades": 2,
                    "losing_trades": 1,
                    "average_win": 125.0,
                    "average_loss": -50.0,
                },
            },
            {
                "strategy_name": "Strategy B",
                "strategy_type": "trend_following",
                "config": {},
                "success": True,
                "error": None,
                "trade_log": [
                    {"pnl": 50},
                    {"pnl": 75},
                ],
                "equity_curve": [
                    {"timestamp": "2024-01-01T00:00:00", "balance": 10000},
                    {"timestamp": "2024-01-01T01:00:00", "balance": 10050},
                    {"timestamp": "2024-01-01T02:00:00", "balance": 10125},
                ],
                "performance_metrics": {
                    "total_return": 1.25,
                    "total_trades": 2,
                    "win_rate": 100.0,
                    "sharpe_ratio": 2.0,
                    "max_drawdown": 0.0,
                    "profit_factor": None,
                    "final_balance": 10125,
                    "winning_trades": 2,
                    "losing_trades": 0,
                    "average_win": 62.5,
                    "average_loss": 0.0,
                },
            },
        ]

    def test_comparison_metrics_calculation(self):
        """Test comparison metrics calculation."""
        engine = StrategyComparisonEngine(self.strategy_results)
        report = engine.generate_comparison_report()

        # Verify metrics table
        assert "metrics_table" in report
        assert len(report["metrics_table"]) == 2

        # Verify all metrics are present
        for row in report["metrics_table"]:
            assert "strategy_name" in row
            assert "total_return" in row
            assert "win_rate" in row
            assert "sharpe_ratio" in row
            assert "max_drawdown" in row

    def test_comparison_report_generation(self):
        """Test comparison report generation."""
        engine = StrategyComparisonEngine(self.strategy_results)
        report = engine.generate_comparison_report()

        # Verify report structure
        assert "metrics_table" in report
        assert "equity_curves" in report
        assert "rankings" in report
        assert "summary" in report
        assert "total_strategies" in report
        assert "successful_strategies" in report
        assert "failed_strategies" in report

        # Verify counts
        assert report["total_strategies"] == 2
        assert report["successful_strategies"] == 2
        assert report["failed_strategies"] == 0

    def test_comparison_rankings(self):
        """Test strategy rankings by different metrics."""
        engine = StrategyComparisonEngine(self.strategy_results)
        report = engine.generate_comparison_report()

        rankings = report["rankings"]

        # Verify ranking categories
        assert "by_total_return" in rankings
        assert "by_sharpe_ratio" in rankings
        assert "by_win_rate" in rankings
        assert "by_max_drawdown" in rankings

        # Verify ranking by total return (Strategy A should be first)
        assert rankings["by_total_return"][0]["strategy_name"] == "Strategy A"
        assert rankings["by_total_return"][0]["value"] == 2.0

        # Verify ranking by Sharpe ratio (Strategy B should be first)
        assert rankings["by_sharpe_ratio"][0]["strategy_name"] == "Strategy B"
        assert rankings["by_sharpe_ratio"][0]["value"] == 2.0

    def test_comparison_summary(self):
        """Test comparison summary generation."""
        engine = StrategyComparisonEngine(self.strategy_results)
        report = engine.generate_comparison_report()

        summary = report["summary"]

        # Verify summary fields
        assert "best_strategy" in summary
        assert "worst_strategy" in summary
        assert "average_return" in summary
        assert "average_win_rate" in summary

        # Verify best/worst strategies
        assert summary["best_strategy"]["name"] == "Strategy A"
        assert summary["worst_strategy"]["name"] == "Strategy B"

    def test_comparison_with_failed_strategies(self):
        """Test comparison report handles failed strategies."""
        # Add a failed strategy
        failed_result = {
            "strategy_name": "Failed Strategy",
            "strategy_type": "invalid",
            "config": {},
            "success": False,
            "error": "Strategy not found",
            "trade_log": [],
            "equity_curve": [],
            "performance_metrics": {},
        }

        results_with_failure = self.strategy_results + [failed_result]
        engine = StrategyComparisonEngine(results_with_failure)
        report = engine.generate_comparison_report()

        # Verify failed strategy is included in metrics table
        assert len(report["metrics_table"]) == 3
        failed_row = next(r for r in report["metrics_table"] if not r["success"])
        assert failed_row["error"] == "Strategy not found"
        assert failed_row["total_return"] is None

        # Verify counts
        assert report["total_strategies"] == 3
        assert report["successful_strategies"] == 2
        assert report["failed_strategies"] == 1

    def test_equity_curves_overlay(self):
        """Test equity curves preparation for overlay."""
        engine = StrategyComparisonEngine(self.strategy_results)
        report = engine.generate_comparison_report()

        equity_curves = report["equity_curves"]

        # Verify equity curves for both strategies
        assert "Strategy A" in equity_curves
        assert "Strategy B" in equity_curves

        # Verify equity curve data
        assert len(equity_curves["Strategy A"]) == 4
        assert len(equity_curves["Strategy B"]) == 3


class TestStrategyComparisonAPI(TestCase):
    """Test API endpoints for strategy comparison."""

    def setUp(self):
        """Set up test client and user."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            username="testuser",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)

    @patch("trading.strategy_comparison_views.HistoricalDataLoader")
    @patch("trading.strategy_comparison_views.ParallelStrategyExecutor")
    def test_strategy_compare_endpoint(self, mock_executor, mock_loader):
        """Test POST /api/strategies/compare endpoint."""
        # Mock historical data loader
        mock_loader_instance = MagicMock()
        mock_loader_instance.load_data.return_value = [
            TickDataPoint(
                instrument="EUR_USD",
                timestamp=datetime(2024, 1, 1, 0, 0, 0),
                bid=Decimal("1.1000"),
                ask=Decimal("1.1002"),
                mid=Decimal("1.1001"),
                spread=Decimal("0.0002"),
            )
        ]
        mock_loader.return_value = mock_loader_instance

        # Mock executor
        mock_executor_instance = MagicMock()
        mock_executor_instance.execute_strategies.return_value = [
            {
                "strategy_name": "Test Strategy",
                "strategy_type": "floor",
                "config": {},
                "success": True,
                "error": None,
                "trade_log": [],
                "equity_curve": [],
                "performance_metrics": {
                    "total_return": 5.0,
                    "total_trades": 10,
                    "win_rate": 60.0,
                },
            }
        ]
        mock_executor.return_value = mock_executor_instance

        # Make request
        data = {
            "strategy_configs": [
                {
                    "strategy_type": "floor",
                    "name": "Test Strategy",
                    "config": {"base_lot": 1000},
                }
            ],
            "instrument": "EUR_USD",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
            "initial_balance": 10000,
            "commission_per_trade": 2.0,
        }

        response = self.client.post("/api/strategies/compare/", data, format="json")

        # Verify response
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert response.data["status"] == "completed"

    def test_strategy_compare_max_strategies_validation(self):
        """Test maximum concurrent strategy limit (10) validation."""
        # Create 11 strategy configs
        data = {
            "strategy_configs": [
                {
                    "strategy_type": "floor",
                    "name": f"Strategy {i}",
                    "config": {"base_lot": 1000},
                }
                for i in range(11)
            ],
            "instrument": "EUR_USD",
            "start_date": "2024-01-01T00:00:00Z",
            "end_date": "2024-01-31T23:59:59Z",
        }

        response = self.client.post("/api/strategies/compare/", data, format="json")

        # Should return 400 Bad Request
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Maximum 10 strategies" in response.data["error"]

    def test_strategy_compare_results_endpoint(self):
        """Test GET /api/strategies/compare/{id}/results endpoint."""
        # Create a completed comparison
        comparison = StrategyComparison.objects.create(
            user=self.user,
            strategy_configs=[
                {
                    "strategy_type": "floor",
                    "name": "Test Strategy",
                    "config": {},
                }
            ],
            instrument="EUR_USD",
            start_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=datetime(2024, 1, 31, 23, 59, 59),
            initial_balance=Decimal("10000"),
            status="completed",
            results={
                "metrics_table": [],
                "equity_curves": {},
                "rankings": {},
                "summary": {},
            },
        )

        # Make request
        response = self.client.get(f"/api/strategies/compare/{comparison.id}/results/")

        # Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == comparison.id
        assert response.data["status"] == "completed"
        assert "results" in response.data

    def test_strategy_compare_results_not_found(self):
        """Test GET /api/strategies/compare/{id}/results with invalid ID."""
        response = self.client.get("/api/strategies/compare/99999/results/")

        # Should return 404 Not Found
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_strategy_compare_results_not_completed(self):
        """Test GET /api/strategies/compare/{id}/results for pending comparison."""
        # Create a pending comparison
        comparison = StrategyComparison.objects.create(
            user=self.user,
            strategy_configs=[],
            instrument="EUR_USD",
            start_date=datetime(2024, 1, 1, 0, 0, 0),
            end_date=datetime(2024, 1, 31, 23, 59, 59),
            initial_balance=Decimal("10000"),
            status="pending",
        )

        # Make request
        response = self.client.get(f"/api/strategies/compare/{comparison.id}/results/")

        # Should return 200 with status message
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "pending"
        assert "not completed yet" in response.data["message"]
