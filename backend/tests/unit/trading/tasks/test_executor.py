"""Unit tests for task executor module."""

from __future__ import annotations

from decimal import Decimal
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
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


class TestExecutorPauseControl:
    """Tests for pause control handling in the executor."""

    def test_should_stop_before_batch_honors_pause_signal(self):
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task_model = type("DummyTradingTask", (), {"objects": MagicMock()})
        task = task_model()
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.oanda_account = SimpleNamespace(balance=Decimal("10000"))

        state_manager = MagicMock()
        state_manager.check_control.return_value = SimpleNamespace(
            should_stop=False, should_pause=True
        )

        with patch.object(TaskExecutor, "_get_initial_balance", return_value=Decimal("10000")):
            executor = TaskExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
                event_context=MagicMock(),
                order_service=MagicMock(),
                state_manager=state_manager,
            )

        loop = ExecutionLoopState(state=MagicMock())

        assert executor._should_stop_before_batch(loop) is True
        assert loop.paused_early is True
        assert loop.stopped_early is False

    def test_finalize_execution_marks_task_paused(self):
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task_model = type("DummyTradingTask", (), {"objects": MagicMock()})
        task = task_model()
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.oanda_account = SimpleNamespace(balance=Decimal("10000"))
        task.refresh_from_db = MagicMock()
        task_model.objects.filter.return_value.update.return_value = 1

        engine = MagicMock()
        engine.on_stop.return_value = SimpleNamespace(state=MagicMock(), events=[])
        state_manager = MagicMock()

        with patch.object(TaskExecutor, "_get_initial_balance", return_value=Decimal("10000")):
            executor = TaskExecutor(
                task=task,
                engine=engine,
                data_source=MagicMock(),
                event_context=MagicMock(),
                order_service=MagicMock(),
                state_manager=state_manager,
            )

        executor.save_events = MagicMock(return_value=[])
        executor.save_state = MagicMock()
        executor._metrics_aggregator = MagicMock()

        state = MagicMock()
        state.current_balance = Decimal("10000")
        state.ticks_processed = 12
        loop = ExecutionLoopState(state=state, paused_early=True)

        executor._finalize_execution(loop)

        task_model.objects.filter.assert_called_once()
        state_manager.pause.assert_called_once_with(status_message="Execution paused")


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
    @patch("apps.trading.tasks.executor.ExecutionState")
    def test_save_state_calls_optimistic_update(self, mock_es, mock_handler):
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
        state.resume_cursor_timestamp = None
        state.last_tick_price = None
        state.last_tick_bid = None
        state.last_tick_ask = None
        state.pk = uuid4()
        state.state_version = 3

        mock_es.objects.filter.return_value.update.return_value = 1

        executor.save_state(state)

        mock_es.objects.filter.assert_called_once_with(pk=state.pk, state_version=3)
        assert state.state_version == 4


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
        task.config.strategy_type = "snowball"

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
                execution_id=task.execution_id,
                strategy_type="snowball",
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
        task.config.strategy_type = "snowball"

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
                execution_id=task.execution_id,
                strategy_type="snowball",
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
        task.config.strategy_type = "snowball"

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        mock_event = MagicMock()
        mock_event.event_type = "initial_entry"
        mock_event.to_dict.return_value = {"event_type": "initial_entry", "entry_id": 10}

        trading_record = MagicMock()
        strategy_record = MagicMock()

        with (
            patch("apps.trading.models.TradingEvent") as mock_te,
            patch("apps.trading.models.StrategyEventRecord") as mock_se,
        ):
            mock_te.from_event.return_value = trading_record
            mock_se.from_event.return_value = strategy_record
            result = executor.save_events([mock_event])

            assert len(result) == 1
            assert result == [trading_record]
            mock_te.from_event.assert_called_once_with(
                event=mock_event,
                context=executor.event_context,
                execution_id=task.execution_id,
                strategy_type="snowball",
            )
            assert trading_record.event_type == "open_position"
            assert trading_record.details["event_type"] == "open_position"
            assert trading_record.details["strategy_event_type"] == "initial_entry"
            mock_te.objects.bulk_create.assert_called_once()
            mock_se.from_event.assert_called_once_with(
                event=mock_event,
                context=executor.event_context,
                execution_id=task.execution_id,
                strategy_type="snowball",
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
            patch.object(executor, "_restore_metric_counters"),
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
            patch.object(executor, "_restore_metric_counters"),
            patch.object(executor, "save_events"),
            patch.object(executor, "save_state"),
        ):
            executor._start_execution()

        assert order == ["replay", "resume"]
        mock_replay.assert_called_once_with(state)


class TestTradingDurability:
    """Tests for trading-specific durability behavior."""

    def test_classify_replay_event_flags_trade_impacting(self):
        from apps.trading.tasks.executor import TaskExecutor

        event = MagicMock()
        event.event_type = "open_position"

        assert TaskExecutor._classify_replay_event(event) == "trade-impacting"

    def test_classify_replay_event_flags_lifecycle(self):
        from apps.trading.tasks.executor import TaskExecutor

        event = MagicMock()
        event.event_type = "strategy_stopped"

        assert TaskExecutor._classify_replay_event(event) == "lifecycle"

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
            patch.object(executor, "_mark_event_processed"),
            patch.object(executor, "save_state"),
            patch.object(
                executor.event_handler,
                "handle_event_with_replay",
                return_value=EventExecutionResult(realized_pnl_delta=Decimal("5")),
            ),
        ):
            executor.handle_events(state, [event])

        assert state.current_balance == Decimal("105")
        engine.apply_event_execution_result.assert_called_once()


class TestTradingExecutorSafety:
    """Tests for live trading safety reconciliation hooks."""

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.StateManager")
    @patch("apps.trading.tasks.executor.OrderService")
    @patch("apps.trading.services.reconciliation.TradingResumeReconciler")
    def test_prepare_state_for_execution_blocks_when_reconciliation_has_blockers(
        self,
        mock_reconciler_cls,
        _mock_order_service,
        _mock_state_manager,
        _mock_handler,
    ):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TradingExecutor
        from apps.trading.services.reconciliation import ReconciliationReport, TradingSafetyError

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.dry_run = False
        task.config.strategy_type = "snowball"
        task.config.config_dict = {}
        task.oanda_account.balance = Decimal("10000")
        task.oanda_account.currency = "USD"

        with patch(
            "apps.trading.tasks.executor.TaskExecutor._get_initial_balance",
            return_value=Decimal("10000"),
        ):
            executor = TradingExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
            )

        state = MagicMock()
        report = ReconciliationReport(blockers=["unsafe broker state"])
        mock_reconciler_cls.return_value.reconcile.return_value = report

        with pytest.raises(TradingSafetyError):
            executor.prepare_state_for_execution(state=state, resumed=True)

        mock_reconciler_cls.return_value.reconcile.assert_called_once_with(resumed=True)

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.StateManager")
    @patch("apps.trading.tasks.executor.OrderService")
    @patch("apps.trading.services.reconciliation.TradingResumeReconciler")
    def test_prepare_state_for_execution_reconciles_on_fresh_start(
        self,
        mock_reconciler_cls,
        _mock_order_service,
        _mock_state_manager,
        _mock_handler,
    ):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TradingExecutor
        from apps.trading.services.reconciliation import ReconciliationReport

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.dry_run = False
        task.config.strategy_type = "snowball"
        task.config.config_dict = {}
        task.oanda_account.balance = Decimal("10000")
        task.oanda_account.currency = "USD"

        with patch(
            "apps.trading.tasks.executor.TaskExecutor._get_initial_balance",
            return_value=Decimal("10000"),
        ):
            executor = TradingExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
            )

        state = MagicMock()
        mock_reconciler_cls.return_value.reconcile.return_value = ReconciliationReport()

        assert executor.prepare_state_for_execution(state=state, resumed=False) is state
        mock_reconciler_cls.return_value.reconcile.assert_called_once_with(resumed=False)

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.StateManager")
    @patch("apps.trading.tasks.executor.OrderService")
    @patch("apps.trading.services.reconciliation.TradingResumeReconciler")
    def test_prepare_state_for_execution_allows_fresh_start_with_reconciliation_warnings(
        self,
        mock_reconciler_cls,
        _mock_order_service,
        _mock_state_manager,
        _mock_handler,
    ):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import TradingExecutor
        from apps.trading.services.reconciliation import ReconciliationReport

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.dry_run = False
        task.config.strategy_type = "snowball"
        task.config.config_dict = {}
        task.oanda_account.balance = Decimal("10000")
        task.oanda_account.currency = "USD"

        with patch(
            "apps.trading.tasks.executor.TaskExecutor._get_initial_balance",
            return_value=Decimal("10000"),
        ):
            executor = TradingExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
            )

        state = MagicMock()
        mock_reconciler_cls.return_value.reconcile.return_value = ReconciliationReport(
            warnings=["adopted broker positions"]
        )

        assert executor.prepare_state_for_execution(state=state, resumed=False) is state
        mock_reconciler_cls.return_value.reconcile.assert_called_once_with(resumed=False)

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.StateManager")
    @patch("apps.trading.tasks.executor.OrderService")
    @patch("apps.trading.services.reconciliation.TradingResumeReconciler")
    def test_after_batch_processed_fails_on_runtime_broker_drift(
        self,
        mock_reconciler_cls,
        _mock_order_service,
        _mock_state_manager,
        _mock_handler,
    ):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import ExecutionLoopState, TradingExecutor
        from apps.trading.services.reconciliation import ReconciliationReport, TradingSafetyError

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.dry_run = False
        task.config.strategy_type = "snowball"
        task.config.config_dict = {}
        task.oanda_account.balance = Decimal("10000")
        task.oanda_account.currency = "USD"

        with patch(
            "apps.trading.tasks.executor.TaskExecutor._get_initial_balance",
            return_value=Decimal("10000"),
        ):
            executor = TradingExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
            )

        loop = ExecutionLoopState(state=MagicMock(), batch_count=5)
        mock_reconciler_cls.return_value.detect_runtime_drift.return_value = ReconciliationReport(
            blockers=["broker trade missing"]
        )

        with pytest.raises(TradingSafetyError, match="broker state drift was detected"):
            executor._after_batch_processed(loop)

        mock_reconciler_cls.return_value.detect_runtime_drift.assert_called_once_with()

    @patch("apps.trading.tasks.executor.EventHandler")
    @patch("apps.trading.tasks.executor.StateManager")
    @patch("apps.trading.tasks.executor.OrderService")
    @patch("apps.trading.services.reconciliation.TradingResumeReconciler")
    def test_after_batch_processed_skips_runtime_check_between_intervals(
        self,
        mock_reconciler_cls,
        _mock_order_service,
        _mock_state_manager,
        _mock_handler,
    ):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import ExecutionLoopState, TradingExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.execution_id = uuid4()
        task.instrument = "EUR_USD"
        task.pip_size = Decimal("0.0001")
        task.dry_run = False
        task.config.strategy_type = "snowball"
        task.config.config_dict = {}
        task.oanda_account.balance = Decimal("10000")
        task.oanda_account.currency = "USD"

        with patch(
            "apps.trading.tasks.executor.TaskExecutor._get_initial_balance",
            return_value=Decimal("10000"),
        ):
            executor = TradingExecutor(
                task=task,
                engine=MagicMock(),
                data_source=MagicMock(),
            )

        loop = ExecutionLoopState(state=MagicMock(), batch_count=4)

        executor._after_batch_processed(loop)

        mock_reconciler_cls.return_value.detect_runtime_drift.assert_not_called()

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


class TestCommonRuntimeMetrics:
    """Tests for executor-managed common metrics."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_process_single_tick_populates_common_metrics_without_strategy_metrics(
        self, mock_handler
    ):
        from apps.trading.dataclasses.result import StrategyResult
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.instrument = "USD_JPY"
        task.pip_size = Decimal("0.01")
        task.initial_balance = Decimal("100000")
        task.account_currency = "JPY"
        task.config.config_dict = {}
        task.execution_id = uuid4()

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
        state.current_balance = Decimal("100000")
        state.strategy_state = {}

        tick = SimpleNamespace(
            timestamp=datetime(2026, 3, 22, 10, 0, tzinfo=UTC),
            mid=Decimal("150.10"),
            bid=Decimal("150.09"),
            ask=Decimal("150.11"),
        )
        engine.on_tick.return_value = StrategyResult.from_state(state)

        with patch.object(executor, "save_events", return_value=[]):
            loop = ExecutionLoopState(state=state)
            should_stop = executor._process_single_tick(loop, tick)

        assert should_stop is False
        metrics = state.strategy_state["metrics"]
        assert metrics["margin_ratio"] == "0"
        assert "current_atr" in metrics

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_restore_metric_counters_prefers_persisted_metrics(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.instrument = "USD_JPY"
        task.pip_size = Decimal("0.01")
        task.initial_balance = Decimal("100000")
        task.account_currency = "USD"
        task.config.config_dict = {}
        task.execution_id = uuid4()

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )
        executor._runtime_metrics.restore_counters = MagicMock()  # type: ignore[method-assign]

        state = MagicMock()
        state.last_tick_price = Decimal("150")
        state.strategy_state = {
            "metrics": {
                "realized_pnl": "120.5",
                "realized_pnl_quote": "18075",
                "total_trades": "10",
                "closed_positions": "6",
                "winning_trades": "4",
                "losing_trades": "2",
            }
        }

        executor._restore_metric_counters(state=state)

        executor._runtime_metrics.restore_counters.assert_called_once_with(
            realized_pnl=Decimal("120.5"),
            realized_pnl_quote=Decimal("18075"),
            total_trades=10,
            closed_positions=6,
            winning_trades=4,
            losing_trades=2,
        )

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_restore_metric_counters_derives_quote_when_missing(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.instrument = "USD_JPY"
        task.pip_size = Decimal("0.01")
        task.initial_balance = Decimal("100000")
        task.account_currency = "USD"
        task.config.config_dict = {}
        task.execution_id = uuid4()

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )
        executor._runtime_metrics.restore_counters = MagicMock()  # type: ignore[method-assign]

        state = MagicMock()
        state.last_tick_price = Decimal("150")
        state.strategy_state = {
            "metrics": {
                "realized_pnl": "100",
                "total_trades": "3",
                "closed_positions": "2",
                "winning_trades": "1",
                "losing_trades": "1",
            }
        }

        executor._restore_metric_counters(state=state)

        executor._runtime_metrics.restore_counters.assert_called_once_with(
            realized_pnl=Decimal("100"),
            realized_pnl_quote=Decimal("15000"),
            total_trades=3,
            closed_positions=2,
            winning_trades=1,
            losing_trades=1,
        )


class TestHandleEmptyBatch:
    """Tests for empty-batch handling in the executor loop."""

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_live_trading_keeps_waiting_after_empty_batch_threshold(self, mock_handler):
        from apps.trading.models import TradingTask
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.instrument = "USD_JPY"
        task.pip_size = Decimal("0.01")
        task.execution_id = uuid4()

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        loop = ExecutionLoopState(state=MagicMock())
        loop.no_tick_batches = loop.max_no_tick_batches - 1

        with patch("apps.trading.tasks.executor.is_forex_market_closed", return_value=False):
            should_stop = executor._handle_empty_batch(loop)

        assert should_stop is False
        assert loop.no_tick_batches == loop.max_no_tick_batches

    @patch("apps.trading.tasks.executor.EventHandler")
    def test_backtest_stops_after_empty_batch_threshold(self, mock_handler):
        from apps.trading.models import BacktestTask
        from apps.trading.tasks.executor import ExecutionLoopState, TaskExecutor

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.instrument = "USD_JPY"
        task.pip_size = Decimal("0.01")
        task.initial_balance = Decimal("10000")
        task.account_currency = "JPY"
        task.config.config_dict = {}
        task.execution_id = uuid4()

        executor = TaskExecutor(
            task=task,
            engine=MagicMock(),
            data_source=MagicMock(),
            event_context=MagicMock(),
            order_service=MagicMock(),
            state_manager=MagicMock(),
        )

        loop = ExecutionLoopState(state=MagicMock())
        loop.no_tick_batches = loop.max_no_tick_batches - 1

        should_stop = executor._handle_empty_batch(loop)

        assert should_stop is True


class TestSuspiciousTickGapDetection:
    """Runtime gap detection used by backtest tick delivery."""

    def test_accepts_small_gap(self) -> None:
        from apps.trading.tasks.executor import TaskExecutor

        previous = datetime(2024, 6, 12, 10, 0, 0, tzinfo=UTC)
        current = datetime(2024, 6, 12, 10, 5, 0, tzinfo=UTC)  # 5 min
        assert TaskExecutor._is_suspicious_tick_gap(previous, current) is False

    def test_accepts_same_timestamp(self) -> None:
        from apps.trading.tasks.executor import TaskExecutor

        previous = datetime(2024, 6, 12, 10, 0, 0, tzinfo=UTC)
        assert TaskExecutor._is_suspicious_tick_gap(previous, previous) is False

    def test_accepts_weekend_close(self) -> None:
        from apps.trading.tasks.executor import TaskExecutor

        # Friday 2024-06-14 20:30 UTC → Sunday 2024-06-16 21:05 UTC ≈ 48.5h
        previous = datetime(2024, 6, 14, 20, 30, 0, tzinfo=UTC)
        current = datetime(2024, 6, 16, 21, 5, 0, tzinfo=UTC)
        assert TaskExecutor._is_suspicious_tick_gap(previous, current) is False

    def test_flags_multi_day_gap_midweek(self) -> None:
        """A 5-day jump in the middle of the week is never legitimate."""
        from apps.trading.tasks.executor import TaskExecutor

        previous = datetime(2023, 7, 24, 6, 15, 0, tzinfo=UTC)  # Monday
        current = datetime(2023, 9, 11, 10, 22, 0, tzinfo=UTC)  # weeks later
        assert TaskExecutor._is_suspicious_tick_gap(previous, current) is True

    def test_threshold_is_configurable(self, settings) -> None:
        """Lowering the threshold makes previously-tolerated gaps fail."""
        from apps.trading.tasks.executor import TaskExecutor

        settings.MARKET_BACKTEST_MAX_TICK_GAP_HOURS = 2

        previous = datetime(2024, 6, 12, 10, 0, 0, tzinfo=UTC)
        current = datetime(2024, 6, 12, 14, 0, 0, tzinfo=UTC)  # 4h
        assert TaskExecutor._is_suspicious_tick_gap(previous, current) is True

    def test_explicit_threshold_parameter_overrides_settings(self, settings) -> None:
        """Task-level override should take precedence over the global default."""
        from apps.trading.tasks.executor import TaskExecutor

        settings.MARKET_BACKTEST_MAX_TICK_GAP_HOURS = 2

        previous = datetime(2024, 6, 12, 10, 0, 0, tzinfo=UTC)
        current = datetime(2024, 6, 15, 10, 0, 0, tzinfo=UTC)  # 72h

        assert TaskExecutor._is_suspicious_tick_gap(previous, current, max_gap_hours=120) is False

    def test_flags_friday_midday_to_sunday_gap_when_threshold_exceeded(self) -> None:
        """Only Friday evening closure is exempt once the gap exceeds threshold."""
        from apps.trading.tasks.executor import TaskExecutor

        previous = datetime(2024, 6, 14, 12, 0, 0, tzinfo=UTC)  # Friday noon
        current = datetime(2024, 6, 16, 21, 5, 0, tzinfo=UTC)  # Sunday reopen

        assert TaskExecutor._is_suspicious_tick_gap(previous, current, max_gap_hours=24) is True
