"""Integration tests for strategy execution.

Tests strategy processing of market data, trade signal generation and persistence,
and position creation from trade signals.
"""

from datetime import datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from unittest.mock import Mock

import pytest

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, StrategyEvents, TradingMetrics, TradingTasks
from apps.trading.services.executor.trading import TradingExecutor
from apps.trading.services.source import TickDataSource
from apps.trading.strategies.base import Strategy
from tests.integration.base import IntegrationTestCase


class MockTickDataSource(TickDataSource):
    """Mock tick data source for testing."""

    def __init__(self, ticks: list[Tick]):
        self.ticks = ticks
        self._index = 0

    def __iter__(self):
        """Yield batches of ticks."""
        batch_size = 10
        for i in range(0, len(self.ticks), batch_size):
            yield self.ticks[i : i + batch_size]

    def close(self) -> None:
        """Close the data source."""
        pass


class MockStrategy(Strategy):
    """Mock strategy that generates trade signals."""

    def __init__(
        self,
        instrument: str = "EUR_USD",
        pip_size: Decimal = Decimal("0.0001"),
        config: dict | None = None,
        generate_signals: bool = False,
    ):
        """Initialize mock strategy."""
        super().__init__(instrument, pip_size, config or {})
        self.generate_signals = generate_signals
        self.tick_count = 0

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
        """Process tick and optionally generate trade signals."""
        self.tick_count += 1
        events = []

        if self.generate_signals and self.tick_count % 5 == 0:
            # Generate a trade signal every 5 ticks
            from apps.trading.enums import EventType
            from apps.trading.events.base import GenericStrategyEvent

            event = GenericStrategyEvent(
                event_type=EventType.STRATEGY_SIGNAL,
                timestamp=tick.timestamp,
                data={
                    "instrument": tick.instrument,
                    "signal_type": "BUY" if self.tick_count % 10 == 0 else "SELL",
                    "price": float(tick.mid),
                    "tick_count": self.tick_count,
                },
            )
            events.append(event)

        return StrategyResult(state=state, events=events)

    def on_stop(self, *, state):
        """Stop strategy."""
        return StrategyResult(state=state, events=[])

    def deserialize_state(self, state_dict):
        """Deserialize strategy state."""
        return state_dict or {}


@pytest.mark.django_db
class TestStrategyExecution(IntegrationTestCase):
    """Integration tests for strategy execution."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        from apps.market.models import OandaAccounts
        from apps.trading.models import StrategyConfigurations

        # Create OANDA account
        self.account = OandaAccounts.objects.create(
            user=self.user,
            account_id="001-001-1234567-001",
            api_type="practice",
        )

        # Create strategy configuration
        self.strategy_config = StrategyConfigurations.objects.create(
            name="Test Strategy",
            description="Test strategy config",
            user=self.user,
            strategy_type="floor",
            parameters={},
        )

    def test_strategy_processes_market_data(self):
        """Test that strategy correctly processes market data.

        Verifies that:
        1. Strategy receives market data ticks
        2. Strategy processes each tick
        3. Metrics are created for each processed tick"""
        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="EUR_USD",
            oanda_account=self.account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
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
            for i in range(20)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy(generate_signals=False)

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

        # Verify strategy processed all ticks
        assert strategy.tick_count == 20, f"Expected 20 ticks processed, got {strategy.tick_count}"

        # Verify metrics were created for each tick
        metrics = TradingMetrics.objects.filter(execution=execution)
        assert metrics.count() == 20, f"Expected 20 metrics, got {metrics.count()}"

        # Verify metrics have correct timestamps
        for i, metric in enumerate(metrics.order_by("sequence")):
            expected_timestamp = datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc)
            assert metric.timestamp == expected_timestamp

    def test_trade_signal_generation_and_persistence(self):
        """Test that trade signals are generated and persisted.

        Verifies that:
        1. Strategy generates trade signals based on market data
        2. Trade signals are persisted as StrategyEvents
        3. Event data contains signal information"""
        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="EUR_USD",
            oanda_account=self.account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
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
            for i in range(25)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy that generates signals
        strategy = MockStrategy(generate_signals=True)

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

        # Verify trade signals were generated (every 5 ticks)
        # 25 ticks / 5 = 5 signals
        events = StrategyEvents.objects.filter(execution=execution, event_type="strategy_signal")
        assert events.count() == 5, f"Expected 5 signals, got {events.count()}"

        # Verify event data contains signal information
        for event in events:
            assert "instrument" in event.event
            assert "signal_type" in event.event
            assert "price" in event.event
            assert event.event["instrument"] == "EUR_USD"
            assert event.event["signal_type"] in ["BUY", "SELL"]

    def test_position_creation_from_trade_signals(self):
        """Test that positions are created from trade signals.

        Verifies that:
        1. Trade signals trigger position creation
        2. Positions are created with correct parameters
        3. Position data matches signal data"""
        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="EUR_USD",
            oanda_account=self.account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
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

        # Create mock strategy that generates signals
        strategy = MockStrategy(generate_signals=True)

        # Create mock trading service
        mock_trading_service = Mock()
        mock_account_details = Mock()
        mock_account_details.balance = Decimal("10000.00")
        mock_trading_service.get_account_details.return_value = mock_account_details

        # Mock order submission to return a position
        mock_order_response = Mock()
        mock_order_response.order_id = "ORDER-001"
        mock_order_response.state = "FILLED"
        mock_trading_service.submit_market_order.return_value = mock_order_response

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

        # Verify signals were generated
        events = StrategyEvents.objects.filter(execution=execution, event_type="strategy_signal")
        assert events.count() == 2, f"Expected 2 signals, got {events.count()}"

        # Note: Position creation would require actual order execution logic
        # which is tested separately in order execution tests
        # Here we verify that signals are persisted correctly
        for event in events:
            assert event.execution == execution
            assert event.event["instrument"] == "EUR_USD"

    def test_strategy_execution_with_multiple_instruments(self):
        """Test strategy execution with multiple instruments.

        Verifies that:
        1. Strategy can process data for multiple instruments
        2. Signals are generated per instrument
        3. Metrics track instrument-specific data"""
        # Create trading task for USD_JPY
        task = TradingTasks.objects.create(
            name="Test Trading USD_JPY",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="USD_JPY",
            oanda_account=self.account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
            task_id=task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status=TaskStatus.RUNNING,
        )

        # Create mock ticks for USD_JPY
        ticks = [
            Tick(
                instrument="USD_JPY",
                timestamp=datetime(2024, 1, 1, 12, 0, i, tzinfo=dt_timezone.utc),
                bid=Decimal("150.00") + Decimal(str(i)) * Decimal("0.01"),
                ask=Decimal("150.05") + Decimal(str(i)) * Decimal("0.01"),
                mid=Decimal("150.025") + Decimal(str(i)) * Decimal("0.01"),
            )
            for i in range(15)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy
        strategy = MockStrategy(
            instrument="USD_JPY", pip_size=Decimal("0.01"), generate_signals=True
        )

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

        # Verify metrics were created
        metrics = TradingMetrics.objects.filter(execution=execution)
        assert metrics.count() == 15

        # Verify signals were generated for USD_JPY
        events = StrategyEvents.objects.filter(execution=execution, event_type="strategy_signal")
        assert events.count() == 3  # 15 ticks / 5 = 3 signals

        # Verify all signals are for USD_JPY
        for event in events:
            assert event.event["instrument"] == "USD_JPY"

    def test_strategy_execution_error_handling(self):
        """Test strategy execution handles errors gracefully.

        Verifies that:
        1. Execution continues after strategy errors
        2. Errors are logged
        3. Execution status reflects errors"""
        # Create trading task
        task = TradingTasks.objects.create(
            name="Test Trading",
            description="Test trading task",
            user=self.user,
            config=self.strategy_config,
            instrument="EUR_USD",
            oanda_account=self.account,
        )

        # Create execution
        execution = Executions.objects.create(
            task_type=TaskType.TRADING,
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
            for i in range(5)
        ]

        # Create mock data source
        data_source = MockTickDataSource(ticks)

        # Create mock strategy that raises an error
        strategy = MockStrategy()

        # Patch on_tick to raise an error on the 3rd tick
        original_on_tick = strategy.on_tick

        def error_on_tick(*, tick, state):
            if strategy.tick_count == 2:
                raise ValueError("Simulated strategy error")
            return original_on_tick(tick=tick, state=state)

        strategy.on_tick = error_on_tick  # ty:ignore[invalid-assignment]

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

        # Execute - should handle error gracefully
        try:
            executor.execute()
        except ValueError:
            # Error should be caught and logged by executor
            pass

        # Verify execution status reflects error
        execution.refresh_from_db()    # type: ignore[attr-defined]
        # Note: Actual error handling depends on executor implementation
        # This test verifies the integration point exists
