"""Unit tests for task executor."""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.utils import timezone

from apps.trading.dataclasses import (
    EventContext,
    ExecutionMetrics,
    ExecutionState,
    StrategyResult,
    Tick,
)
from apps.trading.dataclasses.control import TaskControl
from apps.trading.events import StrategyEvent
from apps.trading.services.executor import BacktestExecutor, TaskExecutor, TradingExecutor


class MockStrategyState:
    """Mock strategy state for testing."""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def to_dict(self) -> dict:
        return {"value": self.value}

    @staticmethod
    def from_dict(data: dict) -> "MockStrategyState":
        return MockStrategyState(value=data.get("value", 0))


class MockStrategy:
    """Mock strategy for testing."""

    def __init__(self, instrument: str, pip_size: Decimal, config: dict) -> None:
        self.instrument = instrument
        self.pip_size = pip_size
        self.config = config
        self.on_start_called = False
        self.on_tick_called = False
        self.on_stop_called = False

    def get_state_class(self) -> type:
        return MockStrategyState

    def deserialize_state(self, state_dict: dict) -> MockStrategyState:
        return MockStrategyState.from_dict(state_dict)

    def serialize_state(self, state: MockStrategyState) -> dict:
        return state.to_dict()

    def on_start(self, *, state: ExecutionState) -> StrategyResult:
        self.on_start_called = True
        return StrategyResult.from_state(state)

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        self.on_tick_called = True
        # Increment strategy state value
        new_strategy_state = MockStrategyState(value=state.strategy_state.value + 1)
        new_state = state.copy_with(strategy_state=new_strategy_state)
        return StrategyResult.from_state(new_state)

    def on_stop(self, *, state: ExecutionState) -> StrategyResult:
        self.on_stop_called = True
        return StrategyResult.from_state(state)


class MockDataSource:
    """Mock data source for testing."""

    def __init__(self, ticks: list[list[Tick]]) -> None:
        self.ticks = ticks
        self.closed = False

    def __iter__(self):
        return iter(self.ticks)

    def close(self) -> None:
        self.closed = True


class ConcreteExecutor(TaskExecutor):
    """Concrete executor for testing."""

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.state_loaded = False
        self.state_saved = False
        self.events_emitted: list[StrategyEvent] = []
        self._state: ExecutionState | None = None

    def load_state(self) -> ExecutionState:
        self.state_loaded = True
        if self._state:
            return self._state
        return ExecutionState(
            strategy_state=MockStrategyState(),
            current_balance=self.initial_balance,
            open_positions=[],
            ticks_processed=0,
            last_tick_timestamp=None,
            metrics=ExecutionMetrics(),
        )

    def save_state(self, state: ExecutionState) -> None:
        self.state_saved = True
        self._state = state

    def emit_events(self, events: list[StrategyEvent]) -> None:
        self.events_emitted.extend(events)


@pytest.fixture
def mock_strategy():
    """Create a mock strategy."""
    return MockStrategy(
        instrument="USD_JPY",
        pip_size=Decimal("0.01"),
        config={},
    )


@pytest.fixture
def mock_controller():
    """Create a mock controller."""
    controller = Mock()
    controller.check_control.return_value = TaskControl(should_stop=False)
    return controller


@pytest.fixture
def mock_event_context():
    """Create a mock event context."""
    return EventContext(
        user=Mock(),
        account=None,
        instrument="USD_JPY",
    )


@pytest.fixture
def sample_tick():
    """Create a sample tick."""
    return Tick(
        instrument="USD_JPY",
        timestamp=timezone.now(),
        bid=Decimal("150.25"),
        ask=Decimal("150.27"),
        mid=Decimal("150.26"),
    )


class TestTaskExecutor:
    """Tests for TaskExecutor."""

    def test_execute_calls_lifecycle_methods(
        self, mock_strategy, mock_controller, mock_event_context, sample_tick
    ):
        """Test that execute calls all lifecycle methods."""
        # Create data source with one batch
        data_source = MockDataSource([[sample_tick]])

        # Create executor
        executor = ConcreteExecutor(
            strategy=mock_strategy,
            data_source=data_source,
            controller=mock_controller,
            event_context=mock_event_context,
            initial_balance=Decimal("10000"),
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
        )

        # Execute
        executor.execute()

        # Verify lifecycle methods were called
        assert mock_strategy.on_start_called
        assert mock_strategy.on_tick_called
        assert mock_strategy.on_stop_called

        # Verify controller methods were called
        mock_controller.start.assert_called_once()
        mock_controller.stop.assert_called_once()

        # Verify data source was closed
        assert data_source.closed

    def test_execute_processes_multiple_batches(
        self, mock_strategy, mock_controller, mock_event_context, sample_tick
    ):
        """Test that execute processes multiple batches."""
        # Create data source with multiple batches
        data_source = MockDataSource(
            [
                [sample_tick],
                [sample_tick, sample_tick],
                [sample_tick],
            ]
        )

        # Create executor
        executor = ConcreteExecutor(
            strategy=mock_strategy,
            data_source=data_source,
            controller=mock_controller,
            event_context=mock_event_context,
            initial_balance=Decimal("10000"),
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
        )

        # Execute
        executor.execute()

        # Verify state was saved
        assert executor.state_saved
        assert executor._state is not None

        # Verify ticks were processed (4 total ticks)
        assert executor._state.ticks_processed == 4

        # Verify strategy state was updated (incremented for each tick)
        assert executor._state.strategy_state.value == 4

    def test_execute_stops_on_control_signal(
        self, mock_strategy, mock_controller, mock_event_context, sample_tick
    ):
        """Test that execute stops when control signal is received."""
        # Create data source with many batches
        data_source = MockDataSource([[sample_tick] for _ in range(100)])

        # Configure controller to signal stop after first check
        mock_controller.check_control.side_effect = [
            TaskControl(should_stop=False),
            TaskControl(should_stop=True),
        ]

        # Create executor
        executor = ConcreteExecutor(
            strategy=mock_strategy,
            data_source=data_source,
            controller=mock_controller,
            event_context=mock_event_context,
            initial_balance=Decimal("10000"),
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
        )

        # Execute
        executor.execute()

        # Verify execution stopped early (processed only 1 tick from first batch)
        assert executor._state.ticks_processed == 1

        # Verify on_stop was still called
        assert mock_strategy.on_stop_called

    def test_execute_handles_exception(self, mock_strategy, mock_controller, mock_event_context):
        """Test that execute handles exceptions properly."""
        # Create data source that raises exception
        data_source = Mock()
        data_source.__iter__ = Mock(side_effect=RuntimeError("Test error"))
        data_source.close = Mock()

        # Create executor
        executor = ConcreteExecutor(
            strategy=mock_strategy,
            data_source=data_source,
            controller=mock_controller,
            event_context=mock_event_context,
            initial_balance=Decimal("10000"),
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
        )

        # Execute should raise exception
        with pytest.raises(RuntimeError, match="Test error"):
            executor.execute()

        # Verify controller was notified of failure
        mock_controller.stop.assert_called_once()
        call_args = mock_controller.stop.call_args
        assert call_args.kwargs["failed"] is True

        # Verify data source was closed
        data_source.close.assert_called_once()

    def test_execute_sends_heartbeats(
        self, mock_strategy, mock_controller, mock_event_context, sample_tick
    ):
        """Test that execute sends heartbeats periodically."""
        # Create data source with many batches (more than 10 to trigger heartbeat)
        data_source = MockDataSource([[sample_tick] for _ in range(15)])

        # Create executor
        executor = ConcreteExecutor(
            strategy=mock_strategy,
            data_source=data_source,
            controller=mock_controller,
            event_context=mock_event_context,
            initial_balance=Decimal("10000"),
            instrument="USD_JPY",
            pip_size=Decimal("0.01"),
        )

        # Execute
        executor.execute()

        # Verify heartbeat was called (at batch 10)
        assert mock_controller.heartbeat.call_count >= 1


class TestBacktestExecutor:
    """Tests for BacktestExecutor."""

    @patch("apps.trading.models.ExecutionStrategyEvent")
    def test_backtest_executor_saves_state_to_task(self, mock_event_model, mock_strategy):
        """Test that BacktestExecutor saves state to task model."""
        from apps.trading.models import BacktestTasks

        # Create mock task
        task = Mock(spec=BacktestTasks)
        task.pk = 1
        task.user = Mock()
        task.instrument = "USD_JPY"
        task.initial_balance = Decimal("10000")
        task._pip_size = Decimal("0.01")
        task.result_data = {}
        task.refresh_from_db = Mock()

        # Create mock data source
        data_source = MockDataSource([])

        # Create mock controller
        controller = Mock()
        controller.check_control.return_value = TaskControl(should_stop=False)

        # Create executor
        executor = BacktestExecutor(
            task=task,
            strategy=mock_strategy,
            data_source=data_source,
            controller=controller,
        )

        # Execute
        executor.execute()

        # Verify task.save was called
        assert task.save.called

        # Verify result_data was updated
        assert "execution_state" in task.result_data
        assert "final_balance" in task.result_data
        assert "ticks_processed" in task.result_data


class TestTradingExecutor:
    """Tests for TradingExecutor."""

    @patch("apps.trading.models.TradingEvent")
    def test_trading_executor_saves_state_to_task(self, mock_event_model, mock_strategy):
        """Test that TradingExecutor saves state to task model."""
        from apps.trading.models import TradingTasks

        # Create mock task
        task = Mock(spec=TradingTasks)
        task.pk = 1
        task.user = Mock()
        task.instrument = "USD_JPY"
        task.oanda_account = Mock()
        task.oanda_account.balance = Decimal("10000")
        task._pip_size = Decimal("0.01")
        task.result_data = {}
        task.refresh_from_db = Mock()

        # Create mock data source
        data_source = MockDataSource([])

        # Create mock controller
        controller = Mock()
        controller.check_control.return_value = TaskControl(should_stop=False)

        # Create executor
        executor = TradingExecutor(
            task=task,
            strategy=mock_strategy,
            data_source=data_source,
            controller=controller,
        )

        # Execute
        executor.execute()

        # Verify task.save was called
        assert task.save.called

        # Verify result_data was updated
        assert "execution_state" in task.result_data
        assert "current_balance" in task.result_data
        assert "ticks_processed" in task.result_data
