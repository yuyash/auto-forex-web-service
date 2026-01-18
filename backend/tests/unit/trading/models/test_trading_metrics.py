"""Unit tests for TradingMetrics model."""

from decimal import Decimal

import pytest
from django.db import IntegrityError
from django.utils import timezone

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import TaskExecution, TradingMetrics


@pytest.mark.django_db
class TestTradingMetricsModel:
    """Test suite for TradingMetrics model."""

    @pytest.fixture
    def execution(self):
        """Create a test execution."""
        return TaskExecution.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=1,
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

    def test_create_trading_metrics_with_valid_data(self, execution):
        """Test creating TradingMetrics with all valid fields."""
        timestamp = timezone.now()

        metrics = TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.50"),
            unrealized_pnl=Decimal("50.25"),
            total_pnl=Decimal("150.75"),
            open_positions=2,
            total_trades=5,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        assert metrics.id is not None
        assert metrics.execution == execution
        assert metrics.sequence == 0
        assert metrics.timestamp == timestamp
        assert metrics.realized_pnl == Decimal("100.50")
        assert metrics.unrealized_pnl == Decimal("50.25")
        assert metrics.total_pnl == Decimal("150.75")
        assert metrics.open_positions == 2
        assert metrics.total_trades == 5
        assert metrics.tick_ask_min == Decimal("1.10000")
        assert metrics.tick_ask_max == Decimal("1.10050")
        assert metrics.tick_ask_avg == Decimal("1.10025")
        assert metrics.tick_bid_min == Decimal("1.09990")
        assert metrics.tick_bid_max == Decimal("1.10040")
        assert metrics.tick_bid_avg == Decimal("1.10015")
        assert metrics.tick_mid_min == Decimal("1.09995")
        assert metrics.tick_mid_max == Decimal("1.10045")
        assert metrics.tick_mid_avg == Decimal("1.10020")
        assert metrics.created_at is not None
        assert metrics.updated_at is not None

    def test_unique_constraint_on_execution_sequence(self, execution):
        """Test that (execution, sequence) must be unique."""
        timestamp = timezone.now()

        # Create first metrics record
        TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        # Attempt to create duplicate with same execution and sequence
        with pytest.raises(IntegrityError):
            TradingMetrics.objects.create(
                execution=execution,
                sequence=0,  # Same sequence
                timestamp=timestamp,
                realized_pnl=Decimal("200.00"),
                unrealized_pnl=Decimal("100.00"),
                total_pnl=Decimal("300.00"),
                open_positions=2,
                total_trades=2,
                tick_ask_min=Decimal("1.10000"),
                tick_ask_max=Decimal("1.10050"),
                tick_ask_avg=Decimal("1.10025"),
                tick_bid_min=Decimal("1.09990"),
                tick_bid_max=Decimal("1.10040"),
                tick_bid_avg=Decimal("1.10015"),
                tick_mid_min=Decimal("1.09995"),
                tick_mid_max=Decimal("1.10045"),
                tick_mid_avg=Decimal("1.10020"),
            )

    def test_multiple_metrics_different_sequences(self, execution):
        """Test creating multiple metrics with different sequences."""
        timestamp = timezone.now()

        # Create multiple metrics with different sequences
        metrics1 = TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        metrics2 = TradingMetrics.objects.create(
            execution=execution,
            sequence=1,
            timestamp=timestamp,
            realized_pnl=Decimal("200.00"),
            unrealized_pnl=Decimal("100.00"),
            total_pnl=Decimal("300.00"),
            open_positions=2,
            total_trades=2,
            tick_ask_min=Decimal("1.10100"),
            tick_ask_max=Decimal("1.10150"),
            tick_ask_avg=Decimal("1.10125"),
            tick_bid_min=Decimal("1.10090"),
            tick_bid_max=Decimal("1.10140"),
            tick_bid_avg=Decimal("1.10115"),
            tick_mid_min=Decimal("1.10095"),
            tick_mid_max=Decimal("1.10145"),
            tick_mid_avg=Decimal("1.10120"),
        )

        assert metrics1.id != metrics2.id
        assert metrics1.sequence == 0
        assert metrics2.sequence == 1

    def test_related_name_access_from_execution(self, execution):
        """Test accessing TradingMetrics from Execution via related_name."""
        timestamp = timezone.now()

        # Create multiple metrics
        TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        TradingMetrics.objects.create(
            execution=execution,
            sequence=1,
            timestamp=timestamp,
            realized_pnl=Decimal("200.00"),
            unrealized_pnl=Decimal("100.00"),
            total_pnl=Decimal("300.00"),
            open_positions=2,
            total_trades=2,
            tick_ask_min=Decimal("1.10100"),
            tick_ask_max=Decimal("1.10150"),
            tick_ask_avg=Decimal("1.10125"),
            tick_bid_min=Decimal("1.10090"),
            tick_bid_max=Decimal("1.10140"),
            tick_bid_avg=Decimal("1.10115"),
            tick_mid_min=Decimal("1.10095"),
            tick_mid_max=Decimal("1.10145"),
            tick_mid_avg=Decimal("1.10120"),
        )

        # Access via related_name
        metrics_list = list(execution.trading_metrics.all())
        assert len(metrics_list) == 2
        assert metrics_list[0].sequence == 0
        assert metrics_list[1].sequence == 1

    def test_decimal_precision_for_pnl_fields(self, execution):
        """Test that PnL fields maintain 5 decimal places precision."""
        timestamp = timezone.now()

        metrics = TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("123.45678"),  # 5 decimal places
            unrealized_pnl=Decimal("987.65432"),
            total_pnl=Decimal("1111.11111"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        # Refresh from database
        metrics.refresh_from_db()

        # Check precision is maintained
        assert metrics.realized_pnl == Decimal("123.45678")
        assert metrics.unrealized_pnl == Decimal("987.65432")
        assert metrics.total_pnl == Decimal("1111.11111")

    def test_decimal_precision_for_tick_fields(self, execution):
        """Test that tick fields maintain 5 decimal places precision."""
        timestamp = timezone.now()

        metrics = TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.12345"),
            tick_ask_max=Decimal("1.23456"),
            tick_ask_avg=Decimal("1.34567"),
            tick_bid_min=Decimal("1.45678"),
            tick_bid_max=Decimal("1.56789"),
            tick_bid_avg=Decimal("1.67890"),
            tick_mid_min=Decimal("1.78901"),
            tick_mid_max=Decimal("1.89012"),
            tick_mid_avg=Decimal("1.90123"),
        )

        # Refresh from database
        metrics.refresh_from_db()

        # Check precision is maintained
        assert metrics.tick_ask_min == Decimal("1.12345")
        assert metrics.tick_ask_max == Decimal("1.23456")
        assert metrics.tick_ask_avg == Decimal("1.34567")
        assert metrics.tick_bid_min == Decimal("1.45678")
        assert metrics.tick_bid_max == Decimal("1.56789")
        assert metrics.tick_bid_avg == Decimal("1.67890")
        assert metrics.tick_mid_min == Decimal("1.78901")
        assert metrics.tick_mid_max == Decimal("1.89012")
        assert metrics.tick_mid_avg == Decimal("1.90123")

    def test_ordering_by_execution_and_sequence(self, execution):
        """Test that metrics are ordered by execution and sequence."""
        timestamp = timezone.now()

        # Create metrics in reverse order
        TradingMetrics.objects.create(
            execution=execution,
            sequence=2,
            timestamp=timestamp,
            realized_pnl=Decimal("300.00"),
            unrealized_pnl=Decimal("150.00"),
            total_pnl=Decimal("450.00"),
            open_positions=3,
            total_trades=3,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        TradingMetrics.objects.create(
            execution=execution,
            sequence=0,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        TradingMetrics.objects.create(
            execution=execution,
            sequence=1,
            timestamp=timestamp,
            realized_pnl=Decimal("200.00"),
            unrealized_pnl=Decimal("100.00"),
            total_pnl=Decimal("300.00"),
            open_positions=2,
            total_trades=2,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        # Query all metrics - should be ordered by sequence
        metrics_list = list(TradingMetrics.objects.filter(execution=execution))
        assert len(metrics_list) == 3
        assert metrics_list[0].sequence == 0
        assert metrics_list[1].sequence == 1
        assert metrics_list[2].sequence == 2

    def test_str_representation(self, execution):
        """Test string representation of TradingMetrics."""
        timestamp = timezone.now()

        metrics = TradingMetrics.objects.create(
            execution=execution,
            sequence=5,
            timestamp=timestamp,
            realized_pnl=Decimal("100.00"),
            unrealized_pnl=Decimal("50.00"),
            total_pnl=Decimal("150.00"),
            open_positions=1,
            total_trades=1,
            tick_ask_min=Decimal("1.10000"),
            tick_ask_max=Decimal("1.10050"),
            tick_ask_avg=Decimal("1.10025"),
            tick_bid_min=Decimal("1.09990"),
            tick_bid_max=Decimal("1.10040"),
            tick_bid_avg=Decimal("1.10015"),
            tick_mid_min=Decimal("1.09995"),
            tick_mid_max=Decimal("1.10045"),
            tick_mid_avg=Decimal("1.10020"),
        )

        str_repr = str(metrics)
        assert f"execution={execution.id}" in str_repr
        assert "sequence=5" in str_repr
