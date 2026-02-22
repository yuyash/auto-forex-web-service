"""Unit tests for trading Celery tasks."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus


class _DoesNotExist(Exception):
    pass


class TestRunTradingTask:
    @patch("apps.trading.tasks.trading.TaskLoggingSession")
    @patch("apps.trading.tasks.trading.execute_trading")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_task_not_found_raises(self, mock_model, mock_exec, mock_logging):
        from apps.trading.tasks.trading import run_trading_task

        mock_model.DoesNotExist = _DoesNotExist
        mock_model.objects.get.side_effect = _DoesNotExist("not found")

        with pytest.raises(_DoesNotExist):
            run_trading_task.__wrapped__(uuid4())

    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.TaskLoggingSession")
    @patch("apps.trading.tasks.trading.execute_trading")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_skips_if_not_starting(self, mock_model, mock_exec, mock_logging, mock_log):
        from apps.trading.tasks.trading import run_trading_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.COMPLETED, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist

        run_trading_task.__wrapped__(task.pk)
        mock_exec.assert_not_called()

    @patch("apps.trading.tasks.trading.dj_timezone")
    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.TaskLoggingSession")
    @patch("apps.trading.tasks.trading.execute_trading")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_normal_flow(self, mock_model, mock_exec, mock_logging, mock_log, mock_tz):
        from apps.trading.tasks.trading import run_trading_task

        task_id = uuid4()
        task = MagicMock(
            pk=task_id,
            status=TaskStatus.STARTING,
            instrument="EUR_USD",
            celery_task_id="c-123",
            started_at=mock_tz.now.return_value,
        )
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist

        count = [0]

        def refresh():
            count[0] += 1
            if count[0] >= 2:
                task.status = TaskStatus.RUNNING

        task.refresh_from_db = refresh

        run_trading_task.__wrapped__(task_id)
        mock_exec.assert_called_once_with(task)

    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.TaskLoggingSession")
    @patch("apps.trading.tasks.trading.execute_trading")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_exception_handling(self, mock_model, mock_exec, mock_logging, mock_log):
        from apps.trading.tasks.trading import run_trading_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.STARTING, instrument="EUR_USD")
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist
        mock_exec.side_effect = RuntimeError("boom")

        with patch("apps.trading.tasks.trading.handle_exception") as mock_handle:
            with pytest.raises(RuntimeError, match="boom"):
                run_trading_task.__wrapped__(task.pk)
            mock_handle.assert_called_once()


class TestExecuteTrading:
    @patch("apps.trading.tasks.trading.TradingExecutor")
    @patch("apps.trading.tasks.trading.LiveTickDataSource")
    @patch("apps.trading.tasks.trading.TradingEngine")
    @patch("apps.trading.tasks.trading.pip_size_for_instrument")
    def test_normal_flow(self, mock_pip, mock_engine, mock_source, mock_executor):
        from apps.trading.tasks.trading import execute_trading

        task = MagicMock(pk=uuid4(), instrument="EUR_USD", pip_size=None, config={})
        task.oanda_account.account_id = "001-001-123"
        task.oanda_account.currency = "USD"
        mock_pip.return_value = 0.0001

        execute_trading(task)

        mock_engine.assert_called_once()
        mock_executor.return_value.execute.assert_called_once()

    @patch("apps.trading.tasks.trading.TradingExecutor")
    @patch("apps.trading.tasks.trading.LiveTickDataSource")
    @patch("apps.trading.tasks.trading.TradingEngine")
    @patch("apps.trading.tasks.trading.pip_size_for_instrument")
    def test_uses_existing_pip_size(self, mock_pip, mock_engine, mock_source, mock_executor):
        from apps.trading.tasks.trading import execute_trading

        task = MagicMock(pk=uuid4(), instrument="EUR_USD", pip_size=0.0001, config={})
        task.oanda_account.account_id = "001-001-123"
        task.oanda_account.currency = "USD"

        execute_trading(task)
        mock_pip.assert_not_called()
        task.save.assert_not_called()


class TestHandleExceptionTrading:
    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.dj_timezone")
    def test_with_task_none(self, mock_tz, mock_log):
        from apps.trading.tasks.trading import handle_exception

        handle_exception(uuid4(), None, RuntimeError("test"))
        mock_log.objects.create.assert_not_called()

    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.dj_timezone")
    def test_with_task_updates_status(self, mock_tz, mock_log):
        from apps.trading.tasks.trading import handle_exception

        task_id = uuid4()
        task = MagicMock(pk=task_id, celery_task_id="c-123")

        with patch("apps.trading.models.celery.CeleryTaskStatus") as mock_cs:
            mock_cs.Status.FAILED = "failed"
            handle_exception(task_id, task, ValueError("bad"))

        assert task.status == TaskStatus.FAILED
        task.save.assert_called_once()
        mock_log.objects.create.assert_called_once()

    @patch("apps.trading.tasks.trading.TaskLog")
    @patch("apps.trading.tasks.trading.dj_timezone")
    def test_error_message_stored(self, mock_tz, mock_log):
        from apps.trading.tasks.trading import handle_exception

        task = MagicMock(pk=uuid4(), celery_task_id="c-456")

        with patch("apps.trading.models.celery.CeleryTaskStatus") as mock_cs:
            mock_cs.Status.FAILED = "failed"
            handle_exception(task.pk, task, RuntimeError("specific error"))

        assert task.error_message == "specific error"


class TestStopTradingTask:
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_task_not_found_raises(self, mock_model):
        from apps.trading.tasks.trading import stop_trading_task

        mock_model.DoesNotExist = _DoesNotExist
        mock_model.objects.get.side_effect = _DoesNotExist("not found")

        with pytest.raises(_DoesNotExist):
            stop_trading_task.__wrapped__(uuid4())

    @patch("apps.trading.tasks.trading.CeleryTaskStatus")
    @patch("apps.trading.tasks.trading.dj_timezone")
    @patch("celery.current_app")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_stopping_state(self, mock_model, mock_app, mock_tz, mock_celery):
        from apps.trading.tasks.trading import stop_trading_task

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.STOPPING, celery_task_id="c-123")
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        mock_celery.Status.STOPPED = "stopped"

        stop_trading_task.__wrapped__(task_id)

        assert task.status == TaskStatus.STOPPED
        task.save.assert_called()
        mock_app.control.revoke.assert_called_once_with("c-123", terminate=True)

    @patch("apps.trading.tasks.trading.TradingTask")
    def test_already_stopped_noop(self, mock_model):
        from apps.trading.tasks.trading import stop_trading_task

        task = MagicMock(pk=uuid4(), status=TaskStatus.STOPPED)
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist

        stop_trading_task.__wrapped__(task.pk)
        task.save.assert_not_called()

    @patch("apps.trading.tasks.trading.CeleryTaskStatus")
    @patch("apps.trading.tasks.trading.dj_timezone")
    @patch("celery.current_app")
    @patch("apps.trading.tasks.trading.TradingTask")
    def test_stop_graceful_mode(self, mock_model, mock_app, mock_tz, mock_celery):
        from apps.trading.tasks.trading import stop_trading_task

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.STOPPING, celery_task_id="c-789")
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        mock_celery.Status.STOPPED = "stopped"

        stop_trading_task.__wrapped__(task_id, "graceful")

        assert task.status == TaskStatus.STOPPED
