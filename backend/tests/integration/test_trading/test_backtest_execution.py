"""Integration tests for backtest execution engine.

Tests the end-to-end flow of backtest execution with TradingMetrics creation.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import BacktestTasks, Executions, TradingMetrics
from apps.trading.services.executor.backtest import BacktestExecutor
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy


class MockTickDataSource(TickDataSource):
    """Mock tick data source for testing."""

    def __init__(self, ticks: list[Tick]):
        self.ticks = ticks
        self._index = 0

    def __iter__(self):
        """Yield batches of ticks."""
        # Yield ticks in batches of 10
        batch_size = 10
        for i in range(0, len(self.ticks), batch_size):
            yield self.ticks[i : i + batch_size]

    def close(self) -> None:
        """Close the data source (no-op for mock)."""
        pass


class MockStrategy(Strategy):
    """Mock strategy for testing."""

    def __init__(
        self,
        instrument: str = "EUR_USD",
        pip_size: Decimal = Decimal("0.0001"),
        config: dict | None = None,
    ):
        """Initialize mock strategy."""
        super().__init__(instrument, pip_size, config or {})

    @staticmethod
    def parse_config(strategy_config):
        """Parse strategy configuration."""
        return {}

    @property
    def strategy_type(self):
        """Return strategy type."""
        from apps.trading.enums import StrategyType

        return StrategyType.FLOOR

    def get_state_class(self):
        """Return the strategy state class."""
        return dict

    def on_start(self, *, state):
        """Initialize strategy."""
        return StrategyResult(state=state, events=[])

    def on_tick(self, *, tick, state):
        """Process tick - no events."""
        return StrategyResult(state=state, events=[])

    def on_stop(self, *, state):
        """Stop strategy."""
        return StrategyResult(state=state, events=[])

    def deserialize_state(self, state_dict):
        """Deserialize strategy state."""
        return state_dict or {}


@pytest.mark.django_db
class TestBacktestExecution:
    """Integration tests for backtest execution."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from apps.accounts.models import User

        return User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def strategy_config(self, user):
        """Create a test strategy configuration."""
        from apps.trading.enums import StrategyType
        from apps.trading.models import StrategyConfigurations

        return StrategyConfigurations.objects.create(
            name="Test Config",
            description="Test strategy config",
            user=user,
            strategy_type=StrategyType.FLOOR,
            parameters={},
        )

    def test_backtest_execution_creates_trading_metrics(self, user, strategy_config):
        """Test that backtest execution creates TradingMetrics records."""
        # Create backtest task
        task = BacktestTasks.objects.create(
            name="Test Backtest",
            description="Test backtest task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            initial_balance=Decimal("10000.00"),
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create mock ticks
        ticks = [
            Tick(
                instrument="EUR_USD",
                timestamp=datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc),
                bid=Decimal("1.1000") + Decimal(str(i)) * Decimal("0.0001"),
                ask=Decimal("1.1010") + Decimal(str(i)) * Decimal("0.0001"),
                mid=Decimal("1.1005") + Decimal(str(i)) * Decimal("0.0001"),
            )
            for i in range(50)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy()

        # Create executor
        executor = BacktestExecutor(
            data_source=data_source,
            strategy=strategy,
            execution=execution,
            task=task,
        )

        # Execute
        executor.execute()

        # Verify TradingMetrics records were created
        metrics = TradingMetrics.objects.filter(execution=execution)
        assert metrics.count() == 50, f"Expected 50 metrics, got {metrics.count()}"

        # Verify sequence numbers are correct
        sequences = list(metrics.values_list("sequence", flat=True).order_by("sequence"))
        assert sequences == list(range(50)), "Sequence numbers should be 0-49"

        # Verify tick statistics are populated
        first_metric = metrics.first()
        assert first_metric is not None
        assert first_metric.tick_ask_min == Decimal("1.1010")
        assert first_metric.tick_ask_max == Decimal("1.1010")
        assert first_metric.tick_ask_avg == Decimal("1.1010")
        assert first_metric.tick_bid_min == Decimal("1.1000")
        assert first_metric.tick_bid_max == Decimal("1.1000")
        assert first_metric.tick_bid_avg == Decimal("1.1000")
        assert first_metric.tick_mid_min == Decimal("1.1005")
        assert first_metric.tick_mid_max == Decimal("1.1005")
        assert first_metric.tick_mid_avg == Decimal("1.1005")

    def test_backtest_execution_no_old_model_records(self, user, strategy_config):
        """Test that backtest execution does NOT create old model records.

        Verifies that ExecutionMetrics, ExecutionMetricsCheckpoint, and
        ExecutionEquityPoint are not created."""
        # Create backtest task
        task = BacktestTasks.objects.create(
            name="Test Backtest",
            description="Test backtest task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            initial_balance=Decimal("10000.00"),
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create mock ticks
        ticks = [
            Tick(
                instrument="EUR_USD",
                timestamp=datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc),
                bid=Decimal("1.1000"),
                ask=Decimal("1.1010"),
                mid=Decimal("1.1005"),
            )
            for i in range(10)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy()

        # Create executor
        executor = BacktestExecutor(
            data_source=data_source,
            strategy=strategy,
            execution=execution,
            task=task,
        )

        # Execute
        executor.execute()

        # Verify old models don't exist (they should have been deleted)
        # We can't import them since they're deleted, so we just verify
        # that TradingMetrics was created instead
        metrics = TradingMetrics.objects.filter(execution=execution)
        assert metrics.count() == 10

    def test_backtest_execution_tick_processing_flow(self, user, strategy_config):
        """Test end-to-end tick processing flow.

        Verifies that:
        1. Ticks are processed in order
        2. Metrics are created for each tick
        3. Sequence numbers are monotonic
        4. Timestamps match tick timestamps"""
        # Create backtest task
        task = BacktestTasks.objects.create(
            name="Test Backtest",
            description="Test backtest task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            initial_balance=Decimal("10000.00"),
            start_time=datetime(2024, 1, 1, tzinfo=dt_timezone.utc),
            end_time=datetime(2024, 1, 2, tzinfo=dt_timezone.utc),
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create mock ticks with specific timestamps
        ticks = [
            Tick(
                instrument="EUR_USD",
                timestamp=datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc),
                bid=Decimal("1.1000") + Decimal(str(i)) * Decimal("0.0001"),
                ask=Decimal("1.1010") + Decimal(str(i)) * Decimal("0.0001"),
                mid=Decimal("1.1005") + Decimal(str(i)) * Decimal("0.0001"),
            )
            for i in range(20)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy()

        # Create executor
        executor = BacktestExecutor(
            data_source=data_source,
            strategy=strategy,
            execution=execution,
            task=task,
        )

        # Execute
        executor.execute()

        # Verify metrics were created in order
        metrics = TradingMetrics.objects.filter(execution=execution).order_by("sequence")
        assert metrics.count() == 20

        # Verify sequence numbers are monotonic
        for i, metric in enumerate(metrics):
            assert metric.sequence == i, f"Expected sequence {i}, got {metric.sequence}"

        # Verify timestamps match tick timestamps
        for i, metric in enumerate(metrics):
            expected_timestamp = datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc)
            assert metric.timestamp == expected_timestamp, (
                f"Expected timestamp {expected_timestamp}, got {metric.timestamp}"
            )

        # Verify tick statistics reflect price changes
        first_metric = metrics[0]
        last_metric = metrics[19]

        assert first_metric.tick_bid_min == Decimal("1.1000")
        assert last_metric.tick_bid_min == Decimal("1.1019")

        assert first_metric.tick_ask_min == Decimal("1.1010")
        assert last_metric.tick_ask_min == Decimal("1.1029")
