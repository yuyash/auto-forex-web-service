"""Unit tests for backtest Celery tasks."""

from __future__ import annotations

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

    @patch("apps.trading.tasks.backtest.dj_timezone")
    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.TaskLoggingSession")
    @patch("apps.trading.tasks.backtest.execute_backtest")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_normal_flow(self, mock_model, mock_exec, mock_logging, mock_log, mock_tz):
        from apps.trading.tasks.backtest import run_backtest_task

        task_id = uuid4()
        task = MagicMock(
            pk=task_id, status=TaskStatus.STARTING, instrument="EUR_USD", celery_task_id="c-123"
        )
        task.started_at = mock_tz.now.return_value
        task.completed_at = mock_tz.now.return_value
        mock_model.objects.get.return_value = task
        mock_model.objects.filter.return_value.update.return_value = 1
        mock_model.DoesNotExist = _DoesNotExist
        run_backtest_task.__wrapped__(task_id)
        mock_exec.assert_called_once_with(task)

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
    @patch("apps.trading.tasks.backtest.dj_timezone")
    def test_with_task_none(self, mock_tz, mock_log):
        from apps.trading.tasks.backtest import handle_exception

        handle_exception(uuid4(), None, RuntimeError("test"))
        mock_log.objects.create.assert_not_called()

    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.dj_timezone")
    def test_with_task_updates_status(self, mock_tz, mock_log):
        from apps.trading.tasks.backtest import handle_exception

        task_id = uuid4()
        task = MagicMock(pk=task_id, celery_task_id="c-123")
        with patch("apps.trading.models.celery.CeleryTaskStatus") as mock_cs:
            mock_cs.Status.FAILED = "failed"
            handle_exception(task_id, task, ValueError("bad"))
        assert task.status == TaskStatus.FAILED
        task.save.assert_called_once()
        mock_log.objects.create.assert_called_once()

    @patch("apps.trading.tasks.backtest.TaskLog")
    @patch("apps.trading.tasks.backtest.dj_timezone")
    def test_celery_status_updated(self, mock_tz, mock_log):
        from apps.trading.tasks.backtest import handle_exception

        task_id = uuid4()
        task = MagicMock(pk=task_id, celery_task_id="c-456")
        with patch("apps.trading.models.celery.CeleryTaskStatus") as mock_cs:
            mock_cs.Status.FAILED = "failed"
            handle_exception(task_id, task, RuntimeError("fail"))
            mock_cs.objects.filter.assert_called_once_with(
                task_name="trading.tasks.run_backtest_task",
                instance_key=f"{task_id}:1",
            )


class TestTriggerBacktestPublisher:
    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_market_worker_available(self, mock_app, mock_publish):
        from apps.trading.tasks.backtest import trigger_backtest_publisher

        task = MagicMock(pk=uuid4(), instrument="EUR_USD")
        task.start_time.isoformat.return_value = "2024-01-01T00:00:00"
        task.end_time.isoformat.return_value = "2024-01-02T00:00:00"
        mock_app.control.inspect.return_value.active_queues.return_value = {
            "worker1": [{"name": "market"}],
        }
        trigger_backtest_publisher(task)
        mock_publish.delay.assert_called_once()

    @patch("apps.market.tasks.publish_ticks_for_backtest")
    @patch("celery.current_app")
    def test_no_market_worker(self, mock_app, mock_publish):
        from apps.trading.tasks.backtest import trigger_backtest_publisher

        task = MagicMock(pk=uuid4(), instrument="EUR_USD")
        task.start_time.isoformat.return_value = "2024-01-01T00:00:00"
        task.end_time.isoformat.return_value = "2024-01-02T00:00:00"
        mock_app.control.inspect.return_value.active_queues.return_value = None
        with pytest.raises(RuntimeError, match="No active market worker"):
            trigger_backtest_publisher(task)
        mock_publish.delay.assert_not_called()


class TestStopBacktestTask:
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_task_not_found_raises(self, mock_model):
        from apps.trading.tasks.backtest import stop_backtest_task

        mock_model.DoesNotExist = _DoesNotExist
        mock_model.objects.get.side_effect = _DoesNotExist
        with pytest.raises(_DoesNotExist):
            stop_backtest_task.__wrapped__(uuid4())

    @patch("apps.trading.models.CeleryTaskStatus")
    @patch("apps.market.models.CeleryTaskStatus")
    @patch("apps.trading.tasks.backtest.dj_timezone")
    @patch("celery.current_app")
    @patch("apps.market.signals.management.task_management_handler")
    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_stopping_state(
        self,
        mock_model,
        mock_handler,
        mock_app,
        mock_tz,
        mock_market_celery,
        mock_trading_celery,
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
        mock_trading_celery.objects.filter.return_value.update.return_value = 1
        mock_trading_celery.Status.STOPPED = "stopped"
        with patch("time.sleep"):
            stop_backtest_task.__wrapped__(task_id)
        task.save.assert_called()

    @patch("apps.trading.tasks.backtest.BacktestTask")
    def test_completed_transitions_to_stopped(self, mock_model):
        from apps.trading.tasks.backtest import stop_backtest_task

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.COMPLETED)
        mock_model.objects.get.return_value = task
        mock_model.DoesNotExist = _DoesNotExist
        stop_backtest_task.__wrapped__(task_id)
        assert task.status == TaskStatus.STOPPED
        task.save.assert_called()
