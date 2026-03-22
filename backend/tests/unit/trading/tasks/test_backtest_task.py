"""Unit tests for backtest Celery tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus


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

    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_skips_if_not_starting(self, mock_model, mock_exec, mock_logging, mock_log):
        from apps.trading.tasks.backtest import run_backtest_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.COMPLETED, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        run_backtest_task.__wrapped__(task.pk)
        mock_exec.assert_not_called()

    @patch("apps.trading.tasks.backtest.finalize_task_terminal_lifecycle")
    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_normal_flow(
        self,
        mock_model,
        mock_exec,
        mock_logging,
        mock_log,
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

    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_exception_handling(self, mock_model, mock_exec, mock_logging, mock_log):
        from apps.trading.tasks.backtest import run_backtest_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.STARTING, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist
        mock_exec.side_effect = RuntimeError("boom")
        with patch("apps.trading.tasks.backtest.handle_exception") as mock_handle:
            with pytest.raises(RuntimeError, match="boom"):
                run_backtest_task.__wrapped__(task.pk)
            mock_handle.assert_called_once()


class TestExecuteBacktest:
    @patch("apps.trading.tasks.backtest.trigger_backtest_publisher")
    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.RedisTickDataSource")
    @patch("apps.trading.tasks.backtest.TradingEngine")
    @patch("apps.trading.tasks.backtest.pip_size_for_instrument")
    def test_normal_flow(self, mock_pip, mock_engine, mock_source, mock_executor, mock_trigger):
        from apps.trading.tasks.backtest import execute_backtest

        task = MagicMock(
            pk=uuid4(), instrument="EUR_USD", pip_size=None, config={}, account_currency="USD"
        )
        mock_pip.return_value = 0.0001
        execute_backtest(task)
        mock_executor.return_value.execute.assert_called_once()

    @patch("apps.trading.tasks.backtest.trigger_backtest_publisher")
    @patch("apps.trading.tasks.backtest.BacktestExecutor")
    @patch("apps.trading.tasks.backtest.RedisTickDataSource")
    @patch("apps.trading.tasks.backtest.TradingEngine")
    @patch("apps.trading.tasks.backtest.pip_size_for_instrument")
    def test_executor_exception(
        self, mock_pip, mock_engine, mock_source, mock_executor, mock_trigger
    ):
        from apps.trading.tasks.backtest import execute_backtest

        task = MagicMock(
            pk=uuid4(), instrument="EUR_USD", pip_size=0.0001, config={}, account_currency="USD"
        )
        mock_executor.return_value.execute.side_effect = RuntimeError("exec fail")
        with pytest.raises(RuntimeError, match="exec fail"):
            execute_backtest(task)


class TestHandleExceptionBacktest:
    @patch("apps.trading.tasks.backtest.TaskLog")
    def test_with_task_none(self, mock_log):
        from apps.trading.tasks.backtest import handle_exception

        handle_exception(uuid4(), None, RuntimeError("test"))
        mock_log.objects.create.assert_not_called()

    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.finalize_task_terminal_lifecycle")
    def test_with_task_updates_status(self, mock_finalize_terminal, mock_log):
        from apps.trading.tasks.backtest import handle_exception

        task_id = uuid4()
        execution_id = uuid4()
        task = MagicMock(pk=task_id, execution_id=execution_id)
        mock_finalize_terminal.return_value = 1
        handle_exception(task_id, task, ValueError("bad"))
        mock_finalize_terminal.assert_called_once()
        mock_log.objects.create.assert_called_once()


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
