"""Unit tests for task service module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, TradingTask


class _DoesNotExist(Exception):
    pass


class TestGetCeleryResult:
    def test_returns_none_for_none_id(self):
        from apps.trading.tasks.service import TaskService

        assert TaskService.get_celery_result(None) is None

    def test_returns_none_for_empty_string(self):
        from apps.trading.tasks.service import TaskService

        assert TaskService.get_celery_result("") is None

    @patch("apps.trading.tasks.service.AsyncResult")
    def test_returns_async_result_for_valid_id(self, mock_async):
        from apps.trading.tasks.service import TaskService

        mock_result = MagicMock()
        mock_async.return_value = mock_result
        result = TaskService.get_celery_result("celery-123")
        mock_async.assert_called_once_with("celery-123")
        assert result is mock_result


class TestStartTask:
    @patch("celery.current_app")
    @patch("apps.trading.tasks.service.uuid4")
    @patch("apps.trading.tasks.service.run_backtest_task")
    def test_start_backtest_task(self, mock_celery_task, mock_uuid, mock_app):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.status = TaskStatus.CREATED
        task.instrument = "EUR_USD"
        task.validate_configuration.return_value = (True, None)
        mock_uuid.return_value = "generated-uuid"
        mock_celery_task.apply_async.return_value = MagicMock(id="generated-uuid")
        mock_app.control.inspect.return_value.active.return_value = {"worker1": []}

        service = TaskService()
        result = service.start_task(task)

        assert result is task
        assert task.status == TaskStatus.STARTING
        assert task.celery_task_id == "generated-uuid"
        mock_celery_task.apply_async.assert_called_once()

    @patch("celery.current_app")
    @patch("apps.trading.tasks.service.uuid4")
    @patch("apps.trading.tasks.service.run_trading_task")
    def test_start_trading_task(self, mock_celery_task, mock_uuid, mock_app):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.status = TaskStatus.CREATED
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()
        task.oanda_account.pk = uuid4()
        task.validate_configuration.return_value = (True, None)
        mock_uuid.return_value = "generated-uuid"
        mock_celery_task.apply_async.return_value = MagicMock(id="generated-uuid")
        mock_app.control.inspect.return_value.active.return_value = {"worker1": []}

        service = TaskService()
        with patch.object(TradingTask, "objects") as mock_objects:
            mock_objects.filter.return_value.exclude.return_value.first.return_value = None
            result = service.start_task(task)

        assert result is task
        assert task.status == TaskStatus.STARTING

    def test_rejects_non_created_status(self):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        task.instrument = "EUR_USD"

        with pytest.raises(ValueError, match="CREATED"):
            TaskService().start_task(task)

    def test_rejects_invalid_config(self):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.status = TaskStatus.CREATED
        task.instrument = "EUR_USD"
        task.validate_configuration.return_value = (False, "Missing strategy")

        with pytest.raises(ValueError, match="Missing strategy"):
            TaskService().start_task(task)

    @patch("apps.trading.tasks.service.run_backtest_task")
    def test_rolls_back_on_celery_failure(self, mock_celery_task):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=BacktestTask)
        task.pk = uuid4()
        task.status = TaskStatus.CREATED
        task.instrument = "EUR_USD"
        task.validate_configuration.return_value = (True, None)
        mock_celery_task.apply_async.side_effect = ConnectionError("broker down")

        with pytest.raises(RuntimeError, match="Failed to submit"):
            TaskService().start_task(task)

        assert task.status == TaskStatus.CREATED
        assert task.celery_task_id is None

    @patch("apps.trading.tasks.service.run_trading_task")
    def test_rejects_already_running_account(self, mock_celery_task):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(spec=TradingTask)
        task.pk = uuid4()
        task.status = TaskStatus.CREATED
        task.instrument = "EUR_USD"
        task.oanda_account = MagicMock()

        active_task = MagicMock(pk=uuid4(), name="Existing", status=TaskStatus.RUNNING)

        with patch.object(TradingTask, "objects") as mock_objects:
            mock_objects.filter.return_value.exclude.return_value.first.return_value = active_task
            with pytest.raises(ValueError, match="already has an active task"):
                TaskService().start_task(task)


class TestStopTask:
    @patch("apps.trading.tasks.service.stop_backtest_task")
    @patch("celery.current_app")
    @patch("redis.Redis")
    @patch("apps.trading.tasks.service.BacktestTask")
    def test_stop_backtest_task(self, mock_bt, mock_redis_cls, mock_app, mock_stop):
        from apps.trading.tasks.service import TaskService

        task_id = uuid4()
        task = MagicMock(pk=task_id, status=TaskStatus.RUNNING, celery_task_id="c-123")
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist
        mock_redis_cls.from_url.return_value = MagicMock()

        result = TaskService().stop_task(task_id)

        assert result is True
        assert task.status == TaskStatus.STOPPING
        task.save.assert_called()
        mock_stop.delay.assert_called_once_with(task_id)

    @patch("apps.trading.tasks.service.BacktestTask")
    @patch("apps.trading.tasks.service.TradingTask")
    def test_task_not_found_raises(self, mock_tt, mock_bt):
        from apps.trading.tasks.service import TaskService

        task_id = uuid4()
        mock_bt.DoesNotExist = _DoesNotExist
        mock_bt.objects.get.side_effect = _DoesNotExist
        mock_tt.DoesNotExist = _DoesNotExist
        mock_tt.objects.get.side_effect = _DoesNotExist

        with pytest.raises(ValueError, match="does not exist"):
            TaskService().stop_task(task_id)

    @patch("apps.trading.tasks.service.BacktestTask")
    def test_already_stopped_returns_true(self, mock_bt):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(pk=uuid4(), status=TaskStatus.STOPPED)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        assert TaskService().stop_task(task.pk) is True
        task.save.assert_not_called()


class TestPauseTask:
    @patch("apps.trading.tasks.service.BacktestTask")
    def test_pause_running_task(self, mock_bt):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(pk=uuid4(), status=TaskStatus.RUNNING)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        assert TaskService().pause_task(task.pk) is True
        assert task.status == TaskStatus.PAUSED

    @patch("apps.trading.tasks.service.BacktestTask")
    def test_pause_non_running_raises(self, mock_bt):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(pk=uuid4(), status=TaskStatus.STOPPED)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        with pytest.raises(ValueError, match="cannot be paused"):
            TaskService().pause_task(task.pk)

    @patch("apps.trading.tasks.service.BacktestTask")
    @patch("apps.trading.tasks.service.TradingTask")
    def test_pause_not_found_raises(self, mock_tt, mock_bt):
        from apps.trading.tasks.service import TaskService

        mock_bt.DoesNotExist = _DoesNotExist
        mock_bt.objects.get.side_effect = _DoesNotExist
        mock_tt.DoesNotExist = _DoesNotExist
        mock_tt.objects.get.side_effect = _DoesNotExist

        with pytest.raises(ValueError, match="does not exist"):
            TaskService().pause_task(uuid4())


class TestCancelTask:
    @patch("apps.trading.tasks.service.timezone")
    @patch("apps.trading.tasks.service.BacktestTask")
    def test_cancel_running_task(self, mock_bt, mock_tz):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(pk=uuid4(), status=TaskStatus.RUNNING, celery_task_id="c-123")
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        service = TaskService()
        with patch.object(TaskService, "get_celery_result") as mock_get:
            mock_result = MagicMock()
            mock_get.return_value = mock_result
            result = service.cancel_task(task.pk)

        assert result is True
        assert task.status == TaskStatus.STOPPED
        mock_result.revoke.assert_called_once_with(terminate=True)

    @patch("apps.trading.tasks.service.BacktestTask")
    def test_cancel_non_active_returns_false(self, mock_bt):
        from apps.trading.tasks.service import TaskService

        task = MagicMock(pk=uuid4(), status=TaskStatus.COMPLETED)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        assert TaskService().cancel_task(task.pk) is False

    @patch("apps.trading.tasks.service.BacktestTask")
    @patch("apps.trading.tasks.service.TradingTask")
    def test_cancel_not_found_raises(self, mock_tt, mock_bt):
        from apps.trading.tasks.service import TaskService

        mock_bt.DoesNotExist = _DoesNotExist
        mock_bt.objects.get.side_effect = _DoesNotExist
        mock_tt.DoesNotExist = _DoesNotExist
        mock_tt.objects.get.side_effect = _DoesNotExist

        with pytest.raises(ValueError, match="does not exist"):
            TaskService().cancel_task(uuid4())


class TestRestartTask:
    @patch("apps.trading.models.state.ExecutionState")
    @patch("apps.trading.tasks.service.TradingEvent")
    @patch("apps.trading.tasks.service.BacktestTask")
    def test_restart_stopped_task(self, mock_bt, mock_events, mock_state):
        from apps.trading.tasks.service import TaskService

        task_id = uuid4()
        task = MagicMock(
            pk=task_id, status=TaskStatus.STOPPED, celery_task_id=None, instrument="EUR_USD"
        )
        task.validate_configuration.return_value = (True, None)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        model_class = type(task)
        model_class.objects = MagicMock()
        model_class.objects.filter.return_value.update.return_value = 1

        task.refresh_from_db = lambda: setattr(task, "status", TaskStatus.CREATED)

        service = TaskService()
        with patch.object(service, "start_task", return_value=task) as mock_start:
            result = service.restart_task(task_id)

        mock_start.assert_called_once_with(task)
        assert result is task

    @patch("apps.trading.tasks.service.BacktestTask")
    @patch("apps.trading.tasks.service.TradingTask")
    def test_restart_not_found_raises(self, mock_tt, mock_bt):
        from apps.trading.tasks.service import TaskService

        mock_bt.DoesNotExist = _DoesNotExist
        mock_bt.objects.get.side_effect = _DoesNotExist
        mock_tt.DoesNotExist = _DoesNotExist
        mock_tt.objects.get.side_effect = _DoesNotExist

        with pytest.raises(ValueError, match="does not exist"):
            TaskService().restart_task(uuid4())

    @patch("apps.trading.models.state.ExecutionState")
    @patch("celery.current_app")
    @patch("apps.trading.tasks.service.TradingEvent")
    @patch("apps.trading.tasks.service.BacktestTask")
    def test_restart_running_stops_first(self, mock_bt, mock_events, mock_app, mock_state):
        from apps.trading.tasks.service import TaskService

        task_id = uuid4()
        task = MagicMock(
            pk=task_id, status=TaskStatus.RUNNING, celery_task_id="c-123", instrument="EUR_USD"
        )
        task.validate_configuration.return_value = (True, None)
        mock_bt.objects.get.return_value = task
        mock_bt.DoesNotExist = _DoesNotExist

        model_class = type(task)
        model_class.objects = MagicMock()
        model_class.objects.filter.return_value.update.return_value = 1

        count = [0]

        def refresh():
            count[0] += 1
            if count[0] >= 2:
                task.status = TaskStatus.CREATED

        task.refresh_from_db = refresh

        service = TaskService()
        with patch.object(service, "stop_task") as mock_stop:
            with patch.object(service, "start_task", return_value=task):
                with patch("time.sleep"):
                    service.restart_task(task_id)
            mock_stop.assert_called_once_with(task_id)
