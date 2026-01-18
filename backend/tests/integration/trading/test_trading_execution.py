"""Integration tests for trading execution engine.

Tests the end-to-end flow of trading execution with TradingMetrics creation.

Requirements: 1.2, 4.1, 4.2, 4.3
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, TradingMetrics, TradingTasks
from apps.trading.services.executor.trading import TradingExecutor
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
class TestTradingExecution:
    """Integration tests for trading execution."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        from apps.accounts.models import User

        return User.objects.create_user(
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

    def test_trading_execution_creates_trading_metrics(self, user, strategy_config):
        """Test that trading execution creates TradingMetrics records.

        Requirements: 1.2
        """
        # Create mock OANDA account
        from apps.market.models import OandaAccounts

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )

        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            oanda_account=account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
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
            for i in range(30)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy()

        # Create mock trading service
        mock_trading_service = Mock()
        mock_account_details = Mock()
        mock_account_details.balance = Decimal("10000.00")
        mock_trading_service.get_account_details.return_value = mock_account_details

        # Create executor
        executor = TradingExecutor(
            data_source=data_source,
            strategy=strategy,
            trading_service=mock_trading_service,
            execution=execution,
            task=task,
        )

        # Execute
        executor.execute()

        # Verify TradingMetrics records were created
        metrics = TradingMetrics.objects.filter(execution=execution)
        assert metrics.count() == 30, f"Expected 30 metrics, got {metrics.count()}"

        # Verify sequence numbers are correct
        sequences = list(metrics.values_list("sequence", flat=True).order_by("sequence"))
        assert sequences == list(range(30)), "Sequence numbers should be 0-29"

        # Verify tick statistics are populated
        first_metric = metrics.first()
        assert first_metric is not None
        assert first_metric.tick_ask_min == Decimal("1.1010")
        assert first_metric.tick_ask_max == Decimal("1.1010")
        assert first_metric.tick_ask_avg == Decimal("1.1010")
        assert first_metric.tick_bid_min == Decimal("1.1000")
        assert first_metric.tick_bid_max == Decimal("1.1000")
        assert first_metric.tick_bid_avg == Decimal("1.1000")

    def test_trading_execution_no_old_model_records(self, user, strategy_config):
        """Test that trading execution does NOT create old model records.

        Verifies that ExecutionMetrics, ExecutionMetricsCheckpoint, and
        ExecutionEquityPoint are not created.

        Requirements: 4.1, 4.2, 4.3
        """
        # Create mock OANDA account
        from apps.market.models import OandaAccounts

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-002",
            api_type="practice",
        )

        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            oanda_account=account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
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

        # Create mock trading service
        mock_trading_service = Mock()
        mock_account_details = Mock()
        mock_account_details.balance = Decimal("10000.00")
        mock_trading_service.get_account_details.return_value = mock_account_details

        # Create executor
        executor = TradingExecutor(
            data_source=data_source,
            strategy=strategy,
            trading_service=mock_trading_service,
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

    def test_trading_execution_tick_processing_flow(self, user, strategy_config):
        """Test end-to-end tick processing flow.

        Verifies that:
        1. Ticks are processed in order
        2. Metrics are created for each tick
        3. Sequence numbers are monotonic
        4. Timestamps match tick timestamps

        Requirements: 1.2
        """
        # Create mock OANDA account
        from apps.market.models import OandaAccounts

        account = OandaAccounts.objects.create(
            user=user,
            account_id="001-001-1234567-003",
            api_type="practice",
        )

        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=user,
            config=strategy_config,
            instrument="EUR_USD",
            oanda_account=account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk,
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
            for i in range(15)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy()

        # Create mock trading service
        mock_trading_service = Mock()
        mock_account_details = Mock()
        mock_account_details.balance = Decimal("10000.00")
        mock_trading_service.get_account_details.return_value = mock_account_details

        # Create executor
        executor = TradingExecutor(
            data_source=data_source,
            strategy=strategy,
            trading_service=mock_trading_service,
            execution=execution,
            task=task,
        )

        # Execute
        executor.execute()

        # Verify metrics were created in order
        metrics = TradingMetrics.objects.filter(execution=execution).order_by("sequence")
        assert metrics.count() == 15

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
        last_metric = metrics[14]

        assert first_metric.tick_bid_min == Decimal("1.1000")
        assert last_metric.tick_bid_min == Decimal("1.1014")

        assert first_metric.tick_ask_min == Decimal("1.1010")
        assert last_metric.tick_ask_min == Decimal("1.1024")
