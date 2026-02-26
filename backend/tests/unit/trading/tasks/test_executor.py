"""Unit tests for task executor module."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

from freezegun import freeze_time

from apps.trading.enums import TaskType


class TestIsForexMarketClosed:
    """Tests for is_forex_market_closed function."""

    @freeze_time("2024-01-15 12:00:00", tz_offset=0)  # Monday noon UTC
    def test_weekday_market_open(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is False

    @freeze_time("2024-01-16 15:00:00", tz_offset=0)  # Tuesday 3pm UTC
    def test_tuesday_market_open(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is False

    @freeze_time("2024-01-13 12:00:00", tz_offset=0)  # Saturday noon UTC
    def test_saturday_market_closed(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is True

    @freeze_time("2024-01-14 10:00:00", tz_offset=0)  # Sunday 10am UTC (before 21:00)
    def test_sunday_before_open_market_closed(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is True

    @freeze_time("2024-01-14 22:00:00", tz_offset=0)  # Sunday 10pm UTC (after 21:00)
    def test_sunday_after_open_market_open(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is False

    @freeze_time("2024-01-12 21:30:00", tz_offset=0)  # Friday 9:30pm UTC
    def test_friday_after_close(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is True

    @freeze_time("2024-01-12 20:00:00", tz_offset=0)  # Friday 8pm UTC (before 21:00)
    def test_friday_before_close(self):
        from apps.trading.tasks.executor import is_forex_market_closed

        assert is_forex_market_closed() is False


class TestTaskExecutorInit:
    """Tests for TaskExecutor.__init__."""

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.OrderService")
    def test_init_stores_attributes(self, mock_order_svc, mock_handler):
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.__class__.__name__ = "BacktestTask"
        task.initial_balance = Decimal("10000")

        engine = MagicMock()
        data_source = MagicMock()
        event_context = MagicMock()
        order_service = MagicMock()
        state_manager = MagicMock()

        with patch.object(TaskExecutor, "_get_initial_balance", return_value=Decimal("10000")):
            executor = TaskExecutor(
                task=task,
                engine=engine,
                data_source=data_source,
                event_context=event_context,
                order_service=order_service,
                state_manager=state_manager,
            )

        assert executor.task is task
        assert executor.engine is engine
        assert executor.data_source is data_source
        assert executor.instrument == "EUR_USD"
        assert executor.pip_size == Decimal("0.0001")
        assert executor.initial_balance == Decimal("10000")


class TestGetInitialBalance:
    """Tests for TaskExecutor._get_initial_balance."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_backtest_task_returns_initial_balance(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("50000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        assert executor.initial_balance == Decimal("50000")

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_trading_task_returns_account_balance(self, mock_handler):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.oanda_account.balance = Decimal("25000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        assert executor.initial_balance == Decimal("25000")


class TestTaskType:
    """Tests for TaskExecutor.task_type property."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_backtest_task_type(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        assert executor.task_type == TaskType.BACKTEST

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_trading_task_type(self, mock_handler):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.oanda_account.balance = Decimal("10000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        assert executor.task_type == TaskType.TRADING


class TestLoadState:
    """Tests for TaskExecutor.load_state."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_load_existing_state(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")
        task.pk = uuid4()
        task.celery_task_id = "celery-123"

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        mock_state = MagicMock()
        with patch("apps.trading.tasks.executor.ExecutionState") as mock_es:
            mock_es.objects.get.return_value = mock_state
            result = executor.load_state()

        assert result is mock_state

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_load_state_creates_initial_when_not_found(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")
        task.pk = uuid4()
        task.celery_task_id = "celery-123"
        task.start_time = MagicMock()

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        mock_new_state = MagicMock()
        with patch("apps.trading.tasks.executor.ExecutionState") as mock_es:
            mock_es.DoesNotExist = type("DoesNotExist", (Exception,), {})
            mock_es.objects.get.side_effect = mock_es.DoesNotExist
            mock_es.objects.create.return_value = mock_new_state
            result = executor.load_state()

        assert result is mock_new_state


class TestSaveState:
    """Tests for TaskExecutor.save_state."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_save_state_calls_save(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        state = MagicMock()
        state.task_id = uuid4()
        state.ticks_processed = 100
        state.last_tick_timestamp = None
        state.current_balance = Decimal("10000")

        executor.save_state(state)

        state.save.assert_called_once()
        state.refresh_from_db.assert_not_called()


class TestSaveEvents:
    """Tests for TaskExecutor.save_events."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_save_events_empty_list(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        result = executor.save_events([])
        assert result == []

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_save_events_creates_records(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")
        task.celery_task_id = "celery-123"

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        mock_event = MagicMock()
        mock_event.event_type = "margin_protection"
        mock_record = MagicMock()

        # Patch at the import source since save_events does a lazy import.
        with (
            patch("apps.trading.models.TradingEvent") as mock_te,
            patch("apps.trading.models.StrategyEventRecord") as mock_se,
        ):
            mock_te.from_event.return_value = mock_record
            result = executor.save_events([mock_event])

            mock_te.from_event.assert_called_once_with(
                event=mock_event,
                context=executor.event_context,
                celery_task_id="celery-123",
                execution_run_id=1,
            )
            mock_te.objects.bulk_create.assert_called_once_with([mock_record])
            mock_se.objects.bulk_create.assert_not_called()
            assert result == [mock_record]

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_save_events_routes_strategy_internal_events(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")
        task.celery_task_id = "celery-123"

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        strategy_event = MagicMock()
        strategy_event.event_type = "add_layer"
        strategy_record = MagicMock()

        with (
            patch("apps.trading.models.TradingEvent") as mock_te,
            patch("apps.trading.models.StrategyEventRecord") as mock_se,
        ):
            mock_se.from_event.return_value = strategy_record
            result = executor.save_events([strategy_event])

            mock_te.from_event.assert_not_called()
            mock_te.objects.bulk_create.assert_not_called()
            mock_se.from_event.assert_called_once_with(
                event=strategy_event,
                context=executor.event_context,
                celery_task_id="celery-123",
                execution_run_id=1,
            )
            mock_se.objects.bulk_create.assert_called_once_with([strategy_record])
            assert result == []

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_save_events_creates_generic_trading_event_and_strategy_event_for_floor_open(
        self, mock_handler
    ):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.initial_balance = Decimal("10000")
        task.celery_task_id = "celery-123"

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        floor_event = MagicMock()
        floor_event.event_type = "initial_entry"
        floor_event.to_dict.return_value = {"event_type": "initial_entry", "entry_id": 10}

        strategy_record = MagicMock()

        with (
            patch("apps.trading.models.TradingEvent") as mock_te,
            patch("apps.trading.models.StrategyEventRecord") as mock_se,
        ):
            mock_se.from_event.return_value = strategy_record
            result = executor.save_events([floor_event])

            assert len(result) == 1
            created_kwargs = mock_te.call_args.kwargs
            assert created_kwargs["event_type"] == "open_position"
            assert created_kwargs["details"]["event_type"] == "open_position"
            assert created_kwargs["details"]["strategy_event_type"] == "initial_entry"
            mock_te.from_event.assert_not_called()
            mock_te.objects.bulk_create.assert_called_once()
            mock_se.from_event.assert_called_once_with(
                event=floor_event,
                context=executor.event_context,
                celery_task_id="celery-123",
                execution_run_id=1,
            )
            mock_se.objects.bulk_create.assert_called_once_with([strategy_record])


class TestResumeLifecycle:
    """Tests for resume lifecycle behavior in TaskExecutor."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_start_execution_uses_on_resume_for_resumed_trading_state(self, mock_handler):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.celery_task_id = "celery-resume"
        task.execution_run_id = 3
        task.oanda_account.balance = Decimal("10000")

        state = MagicMock()
        state.current_balance = Decimal("12345")
        state.ticks_processed = 500

        resume_result = MagicMock()
        resume_result.state = state
        resume_result.events = []

        engine = MagicMock()
        engine.on_resume.return_value = resume_result

        executor = TaskExecutor(
            task=task,
            engine=engine,
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        with (
            patch.object(
                executor,
                "_load_state_with_metadata",
                return_value=(state, True),
            ),
            patch.object(executor, "_replay_unprocessed_events") as mock_replay,
            patch.object(executor, "save_events"),
            patch.object(executor, "save_state"),
        ):
            executor._start_execution()

        engine.on_resume.assert_called_once_with(state=state)
        engine.on_start.assert_not_called()
        mock_replay.assert_called_once_with(state)

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_start_execution_replays_pending_events_before_on_resume(self, mock_handler):
        from apps.trading.dataclasses.result import StrategyResult
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.celery_task_id = "celery-resume"
        task.execution_run_id = 7
        task.oanda_account.balance = Decimal("10000")

        state = MagicMock()
        state.current_balance = Decimal("12345")
        state.ticks_processed = 500

        order: list[str] = []

        def replay_side_effect(_state):
            order.append("replay")

        def on_resume_side_effect(*, state):
            _ = state
            order.append("resume")
            return StrategyResult.from_state(state)

        engine = MagicMock()
        engine.on_resume.side_effect = on_resume_side_effect

        executor = TaskExecutor(
            task=task,
            engine=engine,
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        with (
            patch.object(
                executor,
                "_load_state_with_metadata",
                return_value=(state, True),
            ),
            patch.object(
                executor,
                "_replay_unprocessed_events",
                side_effect=replay_side_effect,
            ) as mock_replay,
            patch.object(executor, "save_events"),
            patch.object(executor, "save_state"),
        ):
            executor._start_execution()

        assert order == ["replay", "resume"]
        mock_replay.assert_called_once_with(state)


class TestTradingDurability:
    """Tests for trading-specific durability behavior."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_handle_events_persists_state_per_processed_event(self, mock_handler):
        from apps.trading.dataclasses.execution import EventExecutionResult
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.celery_task_id = "celery-123"
        task.execution_run_id = 3
        task.oanda_account.balance = Decimal("10000")

        engine = MagicMock()
        executor = TaskExecutor(
            task=task,
            engine=engine,
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        state = MagicMock()
        state.current_balance = Decimal("100")

        event = MagicMock()
        event.is_processed = False
        event.pk = 1

        with (
            patch.object(executor, "_event_already_applied", return_value=False),
            patch.object(executor, "_mark_event_processed") as mark_processed,
            patch.object(executor, "save_state") as save_state,
            patch.object(
                executor.event_handler,
                "handle_event",
                return_value=EventExecutionResult(realized_pnl_delta=Decimal("5")),
            ),
        ):
            executor.handle_events(state, [event])

        assert state.current_balance == Decimal("105")
        engine.apply_event_execution_result.assert_called_once()
        mark_processed.assert_called_once_with(event)
        save_state.assert_called_once_with(state)

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_process_single_tick_persists_state_before_handling_events(self, mock_handler):
        from apps.trading.dataclasses.result import StrategyResult
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.celery_task_id = "celery-123"
        task.execution_run_id = 4
        task.oanda_account.balance = Decimal("10000")

        engine = MagicMock()
        executor = TaskExecutor(
            task=task,
            engine=engine,
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        state = MagicMock()
        state.ticks_processed = 0
        state.strategy_state = {}

        strategy_event = MagicMock()
        persisted_event = MagicMock()
        tick = SimpleNamespace(
            timestamp="2026-02-25T00:00:00Z",
            mid=1.1,
            bid=1.0999,
            ask=1.1001,
        )

        engine.on_tick.return_value = StrategyResult.with_events(state, [strategy_event])

        call_order: list[str] = []

        def save_state_side_effect(_state):
            call_order.append("save_state")

        def handle_events_side_effect(_state, _events):
            call_order.append("handle_events")

        with (
            patch.object(executor, "save_events", return_value=[persisted_event]),
            patch.object(executor, "save_state", side_effect=save_state_side_effect),
            patch.object(executor, "handle_events", side_effect=handle_events_side_effect),
        ):
            loop = ExecutionLoopState(state=state)
            should_stop = executor._process_single_tick(loop, tick)

        assert should_stop is False
        assert call_order[:2] == ["save_state", "handle_events"]
