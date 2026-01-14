"""Unit tests for EquityService."""

from decimal import Decimal
from typing import Any

from apps.trading.services.equity import EquityService


class TestEquityServiceStatistics:
    """Test equity statistics calculation."""

    def test_calculate_equity_statistics_with_valid_data(self):
        """Test calculating statistics with valid equity curve data."""
        service = EquityService()

        equity_curve = [
            {"balance": "1000.00", "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": "1100.00", "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": "950.00", "timestamp": "2024-01-01T02:00:00Z"},
            {"balance": "1200.00", "timestamp": "2024-01-01T03:00:00Z"},
            {"balance": "1050.00", "timestamp": "2024-01-01T04:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1200.00")
        assert stats.trough == Decimal("950.00")
        assert stats.total_points == 5
        assert stats.peak_timestamp is not None
        assert stats.trough_timestamp is not None
        assert stats.volatility > Decimal("0")

    def test_calculate_equity_statistics_with_numeric_balances(self):
        """Test calculating statistics with numeric balance values."""
        service = EquityService()

        equity_curve = [
            {"balance": 1000, "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": 1100.50, "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": 950.25, "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1100.50")
        assert stats.trough == Decimal("950.25")
        assert stats.total_points == 3

    def test_calculate_equity_statistics_with_decimal_balances(self):
        """Test calculating statistics with Decimal balance values."""
        service = EquityService()

        equity_curve = [
            {"balance": Decimal("1000.00"), "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": Decimal("1100.00"), "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": Decimal("950.00"), "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1100.00")
        assert stats.trough == Decimal("950.00")

    def test_calculate_equity_statistics_single_point(self):
        """Test calculating statistics with single equity point."""
        service = EquityService()

        equity_curve = [
            {"balance": "1000.00", "timestamp": "2024-01-01T00:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1000.00")
        assert stats.trough == Decimal("1000.00")
        assert stats.volatility == Decimal("0")
        assert stats.total_points == 1

    def test_calculate_equity_statistics_two_points(self):
        """Test calculating statistics with two equity points."""
        service = EquityService()

        equity_curve = [
            {"balance": "1000.00", "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": "1100.00", "timestamp": "2024-01-01T01:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1100.00")
        assert stats.trough == Decimal("1000.00")
        assert stats.volatility > Decimal("0")
        assert stats.total_points == 2

    def test_calculate_equity_statistics_without_timestamps(self):
        """Test calculating statistics when timestamps are missing."""
        service = EquityService()

        equity_curve = [
            {"balance": "1000.00"},
            {"balance": "1100.00"},
            {"balance": "950.00"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1100.00")
        assert stats.trough == Decimal("950.00")
        assert stats.peak_timestamp is None
        assert stats.trough_timestamp is None

    def test_calculate_equity_statistics_empty_list(self):
        """Test calculating statistics with empty equity curve."""
        service = EquityService()

        stats = service.calculate_equity_statistics([])

        assert stats is None

    def test_calculate_equity_statistics_none_input(self):
        """Test calculating statistics with None input."""
        service = EquityService()

        stats = service.calculate_equity_statistics(None)

        assert stats is None

    def test_calculate_equity_statistics_invalid_input(self):
        """Test calculating statistics with invalid input type."""
        service = EquityService()

        stats = service.calculate_equity_statistics("not a list")  # type: ignore

        assert stats is None

    def test_calculate_equity_statistics_missing_balance_fields(self):
        """Test calculating statistics when balance fields are missing."""
        service = EquityService()

        equity_curve = [
            {"timestamp": "2024-01-01T00:00:00Z"},
            {"balance": None, "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": "1000.00", "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.total_points == 1
        assert stats.peak == Decimal("1000.00")
        assert stats.trough == Decimal("1000.00")

    def test_calculate_equity_statistics_invalid_balance_values(self):
        """Test calculating statistics with invalid balance values."""
        service = EquityService()

        equity_curve = [
            {"balance": "invalid", "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": "1000.00", "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": {"nested": "dict"}, "timestamp": "2024-01-01T02:00:00Z"},
            {"balance": "1100.00", "timestamp": "2024-01-01T03:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.total_points == 2
        assert stats.peak == Decimal("1100.00")
        assert stats.trough == Decimal("1000.00")

    def test_calculate_equity_statistics_volatility_calculation(self):
        """Test that volatility is calculated correctly."""
        service = EquityService()

        # Use values where we can verify the standard deviation
        equity_curve = [
            {"balance": "100.00", "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": "200.00", "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": "300.00", "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        # Mean = 200, variance = ((100-200)^2 + (200-200)^2 + (300-200)^2) / 2 = 10000
        # Std dev = sqrt(10000) = 100
        assert abs(stats.volatility - Decimal("100")) < Decimal("0.01")

    def test_calculate_equity_statistics_all_same_values(self):
        """Test calculating statistics when all balance values are the same."""
        service = EquityService()

        equity_curve = [
            {"balance": "1000.00", "timestamp": "2024-01-01T00:00:00Z"},
            {"balance": "1000.00", "timestamp": "2024-01-01T01:00:00Z"},
            {"balance": "1000.00", "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)

        assert stats is not None
        assert stats.peak == Decimal("1000.00")
        assert stats.trough == Decimal("1000.00")
        assert stats.volatility == Decimal("0")

    def test_calculate_equity_statistics_mixed_valid_invalid_points(self):
        """Test calculating statistics with mix of valid and invalid points."""
        service = EquityService()

        equity_curve: list[dict[str, Any] | str | None] = [
            {"balance": "1000.00", "timestamp": "2024-01-01T00:00:00Z"},
            "not a dict",
            {"balance": "1100.00", "timestamp": "2024-01-01T01:00:00Z"},
            None,
            {"balance": "950.00", "timestamp": "2024-01-01T02:00:00Z"},
        ]

        stats = service.calculate_equity_statistics(equity_curve)  # type: ignore[arg-type]

        assert stats is not None
        assert stats.total_points == 3
        assert stats.peak == Decimal("1100.00")
        assert stats.trough == Decimal("950.00")
