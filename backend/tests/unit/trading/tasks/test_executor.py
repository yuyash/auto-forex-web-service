"""Unit tests for task executor module."""

from __future__ import annotations

from decimal import Decimal
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
        state.refresh_from_db.assert_called_once()


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
        mock_record = MagicMock()

        # Patch at the import source since save_events does a lazy import
        with patch("apps.trading.models.TradingEvent") as mock_te:
            mock_te.from_event.return_value = mock_record
            result = executor.save_events([mock_event])

            mock_te.from_event.assert_called_once_with(
                event=mock_event,
                context=executor.event_context,
                celery_task_id="celery-123",
            )
            mock_te.objects.bulk_create.assert_called_once_with([mock_record])
            assert result == [mock_record]
