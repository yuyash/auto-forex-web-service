"""Unit tests for backtest Celery tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus, TaskType


class _DoesNotExist(Exception):
    pass


class TestRunBacktestTask:
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_task_not_found_raises(self, mock_model, mock_exec, mock_logging):
        from apps.trading.tasks.backtest import run_backtest_task

        mock_model.DoesNotExist = _DoesNotExist
        mock_model.objects.get.side_effect = _DoesNotExist("not found")
        with pytest.raises(_DoesNotExist):
            run_backtest_task.__wrapped__(uuid4())

    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_skips_if_not_starting(self, mock_model, mock_exec, mock_logging):
        from apps.trading.tasks.backtest import run_backtest_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.COMPLETED, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        run_backtest_task.__wrapped__(task.pk)
        mock_exec.assert_not_called()

    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_skips_stale_redelivery_when_idempotency_key_mismatches(
        self, mock_model, mock_exec, mock_logging
    ):
        from apps.trading.tasks.backtest import run_backtest_task

        task = MagicMock(
            pk=uuid4(),
            status=TaskStatus.STARTING,
            instrument="EUR_USD",
            dispatch_idempotency_key=uuid4(),
        )
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist

        run_backtest_task.__wrapped__(task.pk, str(uuid4()))
        mock_exec.assert_not_called()

    @patch("apps.trading.tasks.backtest.finalize_task_terminal_lifecycle")
    @patch("apps.trading.tasks.backtest.publish_task_lifecycle_event")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_normal_flow(
        self,
        mock_model,
        mock_exec,
        mock_logging,
        mock_publish_event,
        mock_finalize_terminal,
    ):
        from apps.trading.tasks.backtest import run_backtest_task

        task_id = uuid4()
        task = MagicMock(
            pk=task_id, status=TaskStatus.STARTING, instrument="EUR_USD", celery_task_id="c-123"
        )
        task.started_at = datetime.now(UTC)
        task.completed_at = datetime.now(UTC)
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist
        mock_finalize_terminal.return_value = 1
        run_backtest_task.__wrapped__(task_id)
        mock_exec.assert_called_once_with(task)
        mock_finalize_terminal.assert_called_once()

    @patch("apps.trading.tasks.backtest.publish_task_lifecycle_event")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_exception_handling(self, mock_model, mock_exec, mock_logging, mock_publish_event):
        from apps.trading.tasks.backtest import run_backtest_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.STARTING, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist
        mock_exec.side_effect = RuntimeError("boom")
        with patch("apps.trading.tasks.backtest.handle_task_exception") as mock_handle:
            with pytest.raises(RuntimeError, match="boom"):
                run_backtest_task.__wrapped__(task.pk)
            mock_handle.assert_called_once()


class TestExecuteBacktest:
    @patch("apps.trading.tasks.backtest._purge_stale_task_streams")
    @patch("apps.trading.tasks.backtest._stop_previous_publisher")
    @patch("apps.trading.tasks.backtest.trigger_backtest_publisher")
    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.RedisStreamTickDataSource")
    @patch("apps.trading.tasks.backtest.DirectBacktestTickDataSource")
    @patch("apps.trading.tasks.backtest.TradingEngine")
    @patch("apps.trading.tasks.backtest.pip_size_for_instrument")
    def test_normal_flow(
        self,
        mock_pip,
        mock_engine,
        mock_direct_source,
        mock_source,
        mock_executor,
        mock_trigger,
        mock_stop_pub,
        mock_purge,
    ):
        from apps.trading.tasks.backtest import execute_backtest

        task = MagicMock(
            pk=uuid4(),
            instrument="EUR_USD",
            pip_size=None,
            config={},
            account_currency="USD",
            execution_id=uuid4(),
            in_memory_mode=False,
            backtest_tick_batch_size=2500,
        )
        mock_pip.return_value = 0.0001
        execute_backtest(task)
        mock_stop_pub.assert_called_once_with(str(task.pk))
        mock_purge.assert_called_once()
        mock_direct_source.from_task.assert_not_called()
        assert mock_source.call_args.kwargs["batch_size"] == 2500
        assert mock_source.call_args.kwargs["read_count"] == 2500
        mock_executor.return_value.execute.assert_called_once()

    @patch("apps.trading.tasks.backtest._purge_stale_task_streams")
    @patch("apps.trading.tasks.backtest._stop_previous_publisher")
    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.RedisStreamTickDataSource")
    @patch("apps.trading.tasks.backtest.DirectBacktestTickDataSource")
    @patch("apps.trading.tasks.backtest.TradingEngine")
    @patch("apps.trading.tasks.backtest.pip_size_for_instrument")
    @patch("apps.trading.tasks.backtest._backtest_resume_start_time")
    def test_in_memory_flow_uses_direct_data_source(
        self,
        mock_resume_start,
        mock_pip,
        mock_engine,
        mock_direct_source,
        mock_redis_source,
        mock_executor,
        mock_stop_pub,
        mock_purge,
    ):
        from apps.trading.tasks.backtest import execute_backtest

        resume_start = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
        mock_resume_start.return_value = resume_start
        task = MagicMock(
            pk=uuid4(),
            instrument="EUR_USD",
            pip_size=0.0001,
            config={},
            account_currency="USD",
            execution_id=uuid4(),
            in_memory_mode=True,
            backtest_tick_batch_size=3000,
        )

        execute_backtest(task)

        mock_stop_pub.assert_called_once_with(str(task.pk))
        mock_purge.assert_not_called()
        mock_redis_source.assert_not_called()
        mock_direct_source.from_task.assert_called_once_with(
            task,
            batch_size=3000,
            start_dt=resume_start,
        )
        mock_executor.return_value.execute.assert_called_once()

    @patch("apps.trading.tasks.backtest._purge_stale_task_streams")
    @patch("apps.trading.tasks.backtest._stop_previous_publisher")
    @patch("apps.trading.tasks.backtest.trigger_backtest_publisher")
    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.RedisStreamTickDataSource")
    @patch("apps.trading.tasks.backtest.DirectBacktestTickDataSource")
    @patch("apps.trading.tasks.backtest.TradingEngine")
    @patch("apps.trading.tasks.backtest.pip_size_for_instrument")
    def test_executor_exception(
        self,
        mock_pip,
        mock_engine,
        mock_direct_source,
        mock_source,
        mock_executor,
        mock_trigger,
        mock_stop_pub,
        mock_purge,
    ):
        from apps.trading.tasks.backtest import execute_backtest

        task = MagicMock(
            pk=uuid4(),
            instrument="EUR_USD",
            pip_size=0.0001,
            config={},
            account_currency="USD",
            execution_id=uuid4(),
            in_memory_mode=False,
        )
        mock_executor.return_value.execute.side_effect = RuntimeError("exec fail")
        with pytest.raises(RuntimeError, match="exec fail"):
            execute_backtest(task)


class TestHandleExceptionBacktest:
    def test_with_task_none(self):
        from apps.trading.tasks.task_runner import handle_task_exception

        handle_task_exception(
            task_id=uuid4(),
            task=None,
            error=RuntimeError("test"),
            task_type=TaskType.BACKTEST,
            task_label="Backtest",
            component="test",
        )

    @patch("apps.trading.tasks.task_runner.finalize_task_terminal_lifecycle")
    def test_with_task_updates_status(self, mock_finalize_terminal):
        from apps.trading.tasks.task_runner import handle_task_exception

        task_id = uuid4()
        execution_id = uuid4()
        task = MagicMock(pk=task_id, execution_id=execution_id)
        mock_finalize_terminal.return_value = 1
        handle_task_exception(
            task_id=task_id,
            task=task,
            error=ValueError("bad"),
            task_type=TaskType.BACKTEST,
            task_label="Backtest",
            component="test",
        )
        mock_finalize_terminal.assert_called_once()


class TestTriggerBacktestPublisher:
    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_backtest_worker_available(self, mock_app, mock_publish):
        from apps.trading.tasks.backtest import trigger_backtest_publisher

        task = MagicMock(pk=uuid4(), instrument="EUR_USD")
        task.start_time.isoformat.return_value = "2024-01-01T00:00:00"
        task.end_time.isoformat.return_value = "2024-01-02T00:00:00"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "backtest"}],
        }
        trigger_backtest_publisher(task)
        mock_publish.apply_async.assert_called_once()
        assert mock_publish.apply_async.call_args.kwargs["queue"] == "backtest_publisher"

    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_no_market_worker(self, mock_app, mock_publish):
        from apps.trading.tasks.backtest import trigger_backtest_publisher

        task = MagicMock(pk=uuid4(), instrument="EUR_USD")
        task.start_time.isoformat.return_value = "2024-01-01T00:00:00"
        task.end_time.isoformat.return_value = "2024-01-02T00:00:00"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "trading"}],
        }
        trigger_backtest_publisher(task)
        mock_publish.apply_async.assert_called_once()

    @patch("apps.trading.tasks.backtest.ExecutionState")
    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_passes_execution_id_and_start_time(self, mock_app, mock_publish, mock_execution_state):
        """Publisher starts at task.start_time when no resume state exists."""
        from apps.trading.tasks.backtest import trigger_backtest_publisher

        execution_id = uuid4()
        task = MagicMock(pk=uuid4(), instrument="EUR_USD", execution_id=execution_id)
        task.start_time.isoformat.return_value = "2024-01-01T00:00:00"
        task.end_time.isoformat.return_value = "2024-01-02T00:00:00"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "backtest"}],
        }
        mock_execution_state.objects.filter.return_value.only.return_value.first.return_value = None
        trigger_backtest_publisher(task)
        kwargs = mock_publish.apply_async.call_args.kwargs["kwargs"]
        assert kwargs["start"] == "2024-01-01T00:00:00"
        assert kwargs["execution_id"] == str(execution_id)

    @patch("apps.trading.tasks.backtest.ExecutionState")
    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_resume_starts_after_last_processed_tick(
        self, mock_app, mock_publish, mock_execution_state
    ):
        """A resumed backtest must not replay ticks already reflected in state."""
        from datetime import datetime, timezone

        from apps.trading.tasks.backtest import trigger_backtest_publisher

        execution_id = uuid4()
        last_tick = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        state = MagicMock(
            last_tick_timestamp=last_tick,
            resume_cursor_timestamp=None,
            ticks_processed=123,
        )
        mock_execution_state.objects.filter.return_value.only.return_value.first.return_value = (
            state
        )

        task = MagicMock(pk=uuid4(), instrument="EUR_USD", execution_id=execution_id)
        task.start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        task.end_time = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        task.tick_granularity = "tick"
        task.tick_window_value_mode = "last"
        task.pip_size = "0.0001"
        task.spread_filter_enabled = True
        task.max_spread_pips = "12.5"
        task.oanda_candle_filter_enabled = True
        task.oanda_candle_filter_account_id = 42
        task.oanda_candle_filter_granularity = "M1"
        task.oanda_candle_filter_tolerance_pips = "5"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "backtest"}],
        }

        trigger_backtest_publisher(task)

        kwargs = mock_publish.apply_async.call_args.kwargs["kwargs"]
        assert kwargs["start"] == "2024-01-01T12:00:00.000001+00:00"
        assert kwargs["spread_filter_enabled"] is True
        assert kwargs["max_spread_pips"] == "12.5"
        assert kwargs["oanda_candle_filter_enabled"] is True
        assert kwargs["oanda_candle_filter_account_id"] == 42
        assert kwargs["oanda_candle_filter_granularity"] == "M1"
        assert kwargs["oanda_candle_filter_tolerance_pips"] == "5"

    @patch("apps.trading.tasks.backtest.ExecutionState")
    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_resume_prefers_resume_cursor_timestamp(
        self, mock_app, mock_publish, mock_execution_state
    ):
        from datetime import datetime, timezone

        from apps.trading.tasks.backtest import trigger_backtest_publisher

        execution_id = uuid4()
        last_tick = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resume_cursor = datetime(2024, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
        state = MagicMock(
            last_tick_timestamp=last_tick,
            resume_cursor_timestamp=resume_cursor,
            ticks_processed=123,
        )
        mock_execution_state.objects.filter.return_value.only.return_value.first.return_value = (
            state
        )

        task = MagicMock(pk=uuid4(), instrument="EUR_USD", execution_id=execution_id)
        task.start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        task.end_time = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
        task.tick_granularity = "tick"
        task.tick_window_value_mode = "last"
        task.pip_size = "0.0001"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "backtest"}],
        }

        trigger_backtest_publisher(task)
        kwargs = mock_publish.apply_async.call_args.kwargs["kwargs"]
        assert kwargs["start"] == "2024-01-01T12:05:00.000001+00:00"


class TestStopBacktestTask:
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_task_not_found_raises(self, mock_model):
        from apps.trading.tasks.backtest import stop_backtest_task

        mock_model.DoesNotExist = _DoesNotExist
        mock_model.objects.get.side_effect = _DoesNotExist
        with pytest.raises(_DoesNotExist):
            stop_backtest_task.__wrapped__(uuid4())

    @patch("apps.market.models.CeleryTaskStatus")
    @patch("celery.current_app")
    @patch("apps.trading.tasks.backtest.finalize_task_terminal_lifecycle")
    @patch("apps.market.signals.management.task_management_handler")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_stopping_state(
        self,
        mock_model,
        mock_handler,
        mock_finalize_terminal,
        mock_app,
        mock_market_celery,
    ):
        from apps.trading.tasks.backtest import stop_backtest_task

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.STOPPING, celery_task_id="c-123")
        task.refresh_from_db = MagicMock()
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        mock_market_celery.objects.filter.return_value.first.return_value = MagicMock(
            celery_task_id="pub-123"
        )
        mock_market_celery.objects.filter.return_value.update.return_value = 1
        mock_market_celery.Status.STOPPED = "stopped"
        mock_finalize_terminal.return_value = 1
        mock_finalize_terminal.side_effect = (
            lambda **kwargs: setattr(task, "status", TaskStatus.STOPPED) or 1
        )
        with patch("time.sleep"):
            stop_backtest_task.__wrapped__(task_id)
        mock_finalize_terminal.assert_called_once()

    @patch("apps.trading.tasks.backtest.finalize_task_terminal_lifecycle")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_completed_transitions_to_stopped(
        self,
        mock_model,
        mock_finalize_terminal,
    ):
        from apps.trading.tasks.backtest import stop_backtest_task

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.COMPLETED)
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        mock_finalize_terminal.return_value = 1
        mock_finalize_terminal.side_effect = (
            lambda **kwargs: setattr(task, "status", TaskStatus.STOPPED) or 1
        )
        stop_backtest_task.__wrapped__(task_id)
        assert task.status == TaskStatus.STOPPED
        mock_finalize_terminal.assert_called_once()


class TestPurgeStaleTaskStreams:
    """``_purge_stale_task_streams`` must remove any stream key belonging
    to the task except the current execution's key."""

    def test_deletes_legacy_and_other_execution_keys(self):
        import fakeredis

        from apps.trading.tasks.backtest import _purge_stale_task_streams

        task_id = "task-123"
        keep_execution_id = "execution-new"

        fake_client = fakeredis.FakeRedis(decode_responses=True)
        fake_client.xadd(f"market:backtest:stream:{task_id}", {"x": "legacy"})
        fake_client.xadd(f"market:backtest:stream:{task_id}:execution-old", {"x": "old"})
        fake_client.xadd(f"market:backtest:stream:{task_id}:{keep_execution_id}", {"x": "keep"})
        # Unrelated key under a different task id — must be untouched.
        fake_client.xadd("market:backtest:stream:other-task", {"x": "unrelated"})

        with patch("apps.market.tasks.base.redis_client", return_value=fake_client):
            _purge_stale_task_streams(task_id, keep_execution_id=keep_execution_id)

        assert not fake_client.exists(f"market:backtest:stream:{task_id}")
        assert not fake_client.exists(f"market:backtest:stream:{task_id}:execution-old")
        assert fake_client.exists(f"market:backtest:stream:{task_id}:{keep_execution_id}")
        assert fake_client.exists("market:backtest:stream:other-task")

    def test_no_op_when_nothing_matches(self):
        import fakeredis

        from apps.trading.tasks.backtest import _purge_stale_task_streams

        fake_client = fakeredis.FakeRedis(decode_responses=True)
        fake_client.xadd("market:backtest:stream:other-task", {"x": "1"})

        with patch("apps.market.tasks.base.redis_client", return_value=fake_client):
            _purge_stale_task_streams("unknown-task", keep_execution_id="execution-none")

        assert fake_client.exists("market:backtest:stream:other-task")
