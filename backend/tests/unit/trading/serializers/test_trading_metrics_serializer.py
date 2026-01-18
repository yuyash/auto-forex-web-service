"""Unit tests for TradingMetricsSerializer.

Requirements: 8.3
"""

from decimal import Decimal

import pytest
from django.utils import timezone

from apps.trading.models import BacktestTasks, Executions, TradingMetrics
from apps.trading.serializers import TradingMetricsSerializer


@pytest.mark.django_db
class TestTradingMetricsSerializer:
    """Test suite for TradingMetricsSerializer."""

    @pytest.fixture
    def execution(self, user, strategy_config):
        """Create a test execution."""
        backtest_task = BacktestTasks.objects.create(
            user=user,
            config=strategy_config,
            name="Test Backtest",
            data_source="athena",
            start_time=timezone.now(),
            end_time=timezone.now(),
            initial_balance=Decimal("10000.00"),
            instrument="EUR_USD",
        )
        return Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.id,
            execution_number=1,
            status="running",
        )

    @pytest.fixture
    def trading_metrics(self, execution):
        """Create a test TradingMetrics instance."""
        return TradingMetrics.objects.create(
            execution=execution,
            sequence=1,
            timestamp=timezone.now(),
            realized_pnl=Decimal("100.50"),
            unrealized_pnl=Decimal("50.25"),
            total_pnl=Decimal("150.75"),
            open_positions=2,
            total_trades=5,
            tick_ask_min=Decimal("1.1000"),
            tick_ask_max=Decimal("1.1050"),
            tick_ask_avg=Decimal("1.1025"),
            tick_bid_min=Decimal("1.0990"),
            tick_bid_max=Decimal("1.1040"),
            tick_bid_avg=Decimal("1.1015"),
            tick_mid_min=Decimal("1.0995"),
            tick_mid_max=Decimal("1.1045"),
            tick_mid_avg=Decimal("1.1020"),
        )

    def test_serialization(self, trading_metrics):
        """Test serialization of TradingMetrics instance."""
        serializer = TradingMetricsSerializer(trading_metrics)
        data = serializer.data

        # Check all fields are present
        assert "id" in data
        assert "execution_id" in data
        assert "sequence" in data
        assert "timestamp" in data

        # PnL metrics
        assert "realized_pnl" in data
        assert "unrealized_pnl" in data
        assert "total_pnl" in data

        # Position metrics
        assert "open_positions" in data
        assert "total_trades" in data

        # Tick statistics
        assert "tick_ask_min" in data
        assert "tick_ask_max" in data
        assert "tick_ask_avg" in data
        assert "tick_bid_min" in data
        assert "tick_bid_max" in data
        assert "tick_bid_avg" in data
        assert "tick_mid_min" in data
        assert "tick_mid_max" in data
        assert "tick_mid_avg" in data

        # Timestamps
        assert "created_at" in data
        assert "updated_at" in data

    def test_field_values(self, trading_metrics):
        """Test that serialized field values match model values."""
        serializer = TradingMetricsSerializer(trading_metrics)
        data = serializer.data

        assert data["execution_id"] == trading_metrics.execution.id
        assert data["sequence"] == trading_metrics.sequence
        assert Decimal(data["realized_pnl"]) == trading_metrics.realized_pnl
        assert Decimal(data["unrealized_pnl"]) == trading_metrics.unrealized_pnl
        assert Decimal(data["total_pnl"]) == trading_metrics.total_pnl
        assert data["open_positions"] == trading_metrics.open_positions
        assert data["total_trades"] == trading_metrics.total_trades

    def test_deserialization(self, execution):
        """Test deserialization of TradingMetrics data."""
        data = {
            "execution": execution.id,
            "sequence": 2,
            "timestamp": timezone.now().isoformat(),
            "realized_pnl": "200.00",
            "unrealized_pnl": "100.00",
            "total_pnl": "300.00",
            "open_positions": 3,
            "total_trades": 10,
            "tick_ask_min": "1.2000",
            "tick_ask_max": "1.2050",
            "tick_ask_avg": "1.2025",
            "tick_bid_min": "1.1990",
            "tick_bid_max": "1.2040",
            "tick_bid_avg": "1.2015",
            "tick_mid_min": "1.1995",
            "tick_mid_max": "1.2045",
            "tick_mid_avg": "1.2020",
        }

        serializer = TradingMetricsSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        metrics = serializer.save()
        assert metrics.execution.id == execution.id
        assert metrics.sequence == 2
        assert metrics.realized_pnl == Decimal("200.00")
        assert metrics.total_trades == 10

    def test_read_only_fields(self, trading_metrics):
        """Test that read-only fields cannot be updated."""
        serializer = TradingMetricsSerializer(trading_metrics)
        data = serializer.data

        # These fields should be read-only
        assert "id" in data
        assert "execution_id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_multiple_metrics_serialization(self, execution):
        """Test serialization of multiple TradingMetrics instances."""
        metrics_list = []
        for i in range(3):
            metrics = TradingMetrics.objects.create(
                execution=execution,
                sequence=i + 1,
                timestamp=timezone.now(),
                realized_pnl=Decimal(f"{100 * (i + 1)}.00"),
                unrealized_pnl=Decimal(f"{50 * (i + 1)}.00"),
                total_pnl=Decimal(f"{150 * (i + 1)}.00"),
                open_positions=i + 1,
                total_trades=(i + 1) * 5,
                tick_ask_min=Decimal("1.1000"),
                tick_ask_max=Decimal("1.1050"),
                tick_ask_avg=Decimal("1.1025"),
                tick_bid_min=Decimal("1.0990"),
                tick_bid_max=Decimal("1.1040"),
                tick_bid_avg=Decimal("1.1015"),
                tick_mid_min=Decimal("1.0995"),
                tick_mid_max=Decimal("1.1045"),
                tick_mid_avg=Decimal("1.1020"),
            )
            metrics_list.append(metrics)

        serializer = TradingMetricsSerializer(metrics_list, many=True)
        data = serializer.data

        assert len(data) == 3
        assert data[0]["sequence"] == 1
        assert data[1]["sequence"] == 2
        assert data[2]["sequence"] == 3
