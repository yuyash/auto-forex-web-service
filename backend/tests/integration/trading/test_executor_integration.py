"""Integration tests for TaskExecutor components with real DB.

Tests handle_events, load_state, save_state, save_events,
_flush_metrics, and executor __init__ methods.
External services (Redis, Celery) are mocked.
"""

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from apps.trading.enums import TaskType
from apps.trading.dataclasses import EventExecutionResult
from apps.trading.models import (
    BacktestTask,
    ExecutionState,
    Metrics,
    TradingEvent,
)
from apps.trading.order import OrderService
from apps.trading.tasks.executor import BacktestExecutor, TaskExecutor, TradingExecutor
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


def _make_executor(task: BacktestTask | None = None) -> TaskExecutor:
    """Create a TaskExecutor with mocked external dependencies."""
    if task is None:
        task = BacktestTaskFactory(status="running")
    task.celery_task_id = "celery-exec-test-123"
    task.save()

    engine = MagicMock()
    data_source = MagicMock()
    event_context = MagicMock()
    event_context.task_type = TaskType.BACKTEST
    event_context.task_id = task.pk
    event_context.instrument = task.instrument
    event_context.user = task.user
    event_context.account = None

    order_service = OrderService(account=None, task=task, dry_run=True)
    state_manager = MagicMock()

    executor = TaskExecutor(
        task=task,
        engine=engine,
        data_source=data_source,
        event_context=event_context,
        order_service=order_service,
        state_manager=state_manager,
    )
    return executor


@pytest.mark.django_db
class TestHandleEvents:
    """Tests for TaskExecutor.handle_events."""

    def test_processes_events_and_updates_balance(self):
        executor = _make_executor()
        state = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=0,
        )

        # Create a trading event that the handler will process
        event = TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            event_type="initial_entry",
            severity="info",
            description="Test entry event",
            user=executor.task.user,
            instrument="USD_JPY",
            details={
                "event_type": "initial_entry",
                "instrument": "USD_JPY",
                "direction": "long",
                "units": 1000,
                "entry_price": "150.000",
                "layer_index": 0,
            },
        )

        # Mock the event handler to avoid complex order execution
        with patch.object(
            executor.event_handler,
            "handle_event",
            return_value=EventExecutionResult(realized_pnl_delta=Decimal("0")),
        ):
            executor.handle_events(state, [event])

        # Balance should remain unchanged since realized_delta is 0
        assert state.current_balance == Decimal("10000")

    def test_balance_updated_on_realized_pnl(self):
        executor = _make_executor()
        state = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=0,
        )

        event = TradingEvent.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            event_type="take_profit",
            severity="info",
            description="Take profit",
            user=executor.task.user,
            instrument="USD_JPY",
            details={"event_type": "take_profit"},
        )

        # Simulate a realized PnL of +250
        with patch.object(
            executor.event_handler,
            "handle_event",
            return_value=EventExecutionResult(realized_pnl_delta=Decimal("250")),
        ):
            executor.handle_events(state, [event])

        assert state.current_balance == Decimal("10250")


@pytest.mark.django_db
class TestLoadState:
    """Tests for TaskExecutor.load_state."""

    def test_creates_new_state(self):
        executor = _make_executor()

        state = executor.load_state()

        assert isinstance(state, ExecutionState)
        assert state.task_id == executor.task.pk
        assert state.ticks_processed == 0
        assert state.current_balance == executor.task.initial_balance
        assert ExecutionState.objects.filter(pk=state.pk).exists()

    def test_loads_existing_state(self):
        executor = _make_executor()

        # Pre-create state
        existing = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            strategy_state={"layers": [1, 2]},
            current_balance=Decimal("12345.67"),
            ticks_processed=500,
        )

        state = executor.load_state()
        assert state.pk == existing.pk
        assert state.ticks_processed == 500
        assert state.current_balance == Decimal("12345.67")
        assert state.strategy_state == {"layers": [1, 2]}


@pytest.mark.django_db
class TestSaveState:
    """Tests for TaskExecutor.save_state."""

    def test_persists_state(self):
        executor = _make_executor()

        state = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=0,
        )

        state.ticks_processed = 100
        state.current_balance = Decimal("10500")
        state.last_tick_timestamp = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        executor.save_state(state)

        reloaded = ExecutionState.objects.get(pk=state.pk)
        assert reloaded.ticks_processed == 100
        assert reloaded.current_balance == Decimal("10500")
        assert reloaded.last_tick_timestamp is not None


@pytest.mark.django_db
class TestSaveEvents:
    """Tests for TaskExecutor.save_events."""

    def test_bulk_creates_events(self):
        executor = _make_executor()

        # Create mock StrategyEvent objects
        mock_event_1 = MagicMock()
        mock_event_1.event_type = "initial_entry"
        mock_event_1.to_dict.return_value = {"event_type": "initial_entry", "units": 1000}

        mock_event_2 = MagicMock()
        mock_event_2.event_type = "retracement"
        mock_event_2.to_dict.return_value = {"event_type": "retracement", "units": 500}

        result = executor.save_events([mock_event_1, mock_event_2])

        assert len(result) == 2
        assert all(isinstance(e, TradingEvent) for e in result)
        assert TradingEvent.objects.filter(task_id=executor.task.pk).count() == 2

    def test_empty_events(self):
        executor = _make_executor()
        result = executor.save_events([])
        assert result == []


@pytest.mark.django_db
class TestFlushMetrics:
    """Tests for TaskExecutor._flush_metrics."""

    def test_bulk_creates_snapshots(self):
        executor = _make_executor()
        state = ExecutionState.objects.create(
            task_type=TaskType.BACKTEST,
            task_id=executor.task.pk,
            celery_task_id=executor.task.celery_task_id,
            strategy_state={},
            current_balance=Decimal("10000"),
            ticks_processed=0,
        )

        now = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        executor._metric_buffer = [
            {
                "timestamp": now,
                "margin_ratio": Decimal("0.05"),
                "current_atr": Decimal("0.0012"),
                "baseline_atr": Decimal("0.0010"),
                "volatility_threshold": Decimal("0.0015"),
            },
            {
                "timestamp": datetime(2024, 6, 1, 12, 1, 0, tzinfo=timezone.utc),
                "margin_ratio": Decimal("0.06"),
                "current_atr": None,
                "baseline_atr": None,
                "volatility_threshold": None,
            },
        ]

        executor._flush_metrics(state)

        assert executor._metric_buffer == []
        assert Metrics.objects.filter(task_id=executor.task.pk).count() == 2

    def test_empty_buffer(self):
        executor = _make_executor()
        state = MagicMock()
        executor._metric_buffer = []
        executor._flush_metrics(state)
        assert Metrics.objects.filter(task_id=executor.task.pk).count() == 0


@pytest.mark.django_db
class TestBacktestExecutorInit:
    """Tests for BacktestExecutor.__init__."""

    @patch("apps.trading.tasks.executor.StateManager")
    def test_creates_all_components(self, mock_state_manager_cls):
        task = BacktestTaskFactory(status="running")
        engine = MagicMock()
        data_source = MagicMock()

        executor = BacktestExecutor(task=task, engine=engine, data_source=data_source)

        assert executor.task == task
        assert executor.engine == engine
        assert executor.data_source == data_source
        assert executor.instrument == task.instrument
        assert executor.initial_balance == task.initial_balance
        assert isinstance(executor.order_service, OrderService)
        assert executor.order_service.dry_run is True
        assert executor.order_service.account is None
        mock_state_manager_cls.assert_called_once()


@pytest.mark.django_db
class TestTradingExecutorInit:
    """Tests for TradingExecutor.__init__."""

    @patch("apps.trading.tasks.executor.StateManager")
    def test_creates_all_components(self, mock_state_manager_cls):
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)
        task = TradingTaskFactory(user=user, oanda_account=account, config=config)
        engine = MagicMock()
        data_source = MagicMock()

        executor = TradingExecutor(task=task, engine=engine, data_source=data_source)

        assert executor.task == task
        assert executor.engine == engine
        assert executor.data_source == data_source
        assert executor.instrument == task.instrument
        assert isinstance(executor.order_service, OrderService)
        assert executor.order_service.dry_run is False
        assert executor.order_service.account == account
        mock_state_manager_cls.assert_called_once()
