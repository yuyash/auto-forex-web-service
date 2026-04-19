"""Tests for orphaned task recovery."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus


def _make_qs(task_list):
    """Return a mock queryset that supports .order_by()[:N] → iterable."""
    qs = MagicMock()
    sliceable = MagicMock()
    sliceable.__iter__ = MagicMock(return_value=iter(task_list))
    qs.order_by.return_value.__getitem__ = MagicMock(return_value=sliceable)
    return qs


@pytest.fixture()
def _mock_models():
    """Patch BacktestTask, TradingTask, CeleryTaskStatus, TaskLog."""
    with (
        patch("apps.trading.tasks.recovery.BacktestTask") as bt,
        patch("apps.trading.tasks.recovery.TradingTask") as tt,
        patch("apps.trading.tasks.recovery.CeleryTaskStatus") as cts,
        patch("apps.trading.tasks.recovery.TaskLog") as tl,
        patch("apps.trading.tasks.service.TaskService") as svc_cls,
        patch("apps.trading.tasks.recovery._active_celery_task_ids", return_value=set()),
    ):
        bt.objects.filter.return_value = _make_qs([])
        tt.objects.filter.return_value = _make_qs([])
        # Default: prefetch returns no heartbeats (empty iterable)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([]))
        cts.objects.filter.return_value.first.return_value = None
        yield bt, tt, cts, tl, svc_cls


class TestRecoverOrphanedTasks:
    """Tests for recover_orphaned_tasks."""

    @pytest.mark.usefixtures("_mock_models")
    def test_no_orphaned_tasks(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result == {"backtest": 0, "trading": 0}

    @pytest.mark.usefixtures("_mock_models")
    def test_recovers_orphaned_backtest_no_cts_row(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        task.celery_task_id = "old-celery-id"
        bt.objects.filter.return_value = _make_qs([task])

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 1
        service_instance.start_task.assert_not_called()
        type(task).objects.filter.return_value.update.assert_called_once()

    @pytest.mark.usefixtures("_mock_models")
    def test_recovers_orphaned_backtest_stale_heartbeat(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        stale_cts = MagicMock()
        stale_cts.instance_key = f"{task.pk}:{task.execution_id}"
        stale_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=10)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([stale_cts]))

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 1
        service_instance.start_task.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_skips_task_with_recent_heartbeat(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        recent_cts = MagicMock()
        recent_cts.instance_key = f"{task.pk}:{task.execution_id}"
        recent_cts.last_heartbeat_at = dj_timezone.now() - timedelta(seconds=30)
        # Prefetch returns the recent heartbeat
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([recent_cts]))

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 0
        tl.objects.create.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_worker_ready_recovers_even_with_recent_heartbeat_when_no_active_celery_task(
        self, _mock_models
    ):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        tt.objects.filter.side_effect = [
            _make_qs([task]),
            MagicMock(update=MagicMock(return_value=1)),
        ]

        recent_cts = MagicMock()
        recent_cts.instance_key = f"{task.pk}:{task.execution_id}"
        recent_cts.last_heartbeat_at = dj_timezone.now() - timedelta(seconds=5)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([recent_cts]))

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="worker_ready")
        assert result["trading"] == 1
        service_instance.recover_trading_task.assert_called_once_with(task)

    @pytest.mark.usefixtures("_mock_models")
    def test_worker_ready_skips_task_when_execution_is_still_active(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        recent_cts = MagicMock()
        recent_cts.instance_key = f"{task.pk}:{task.execution_id}"
        recent_cts.last_heartbeat_at = dj_timezone.now() - timedelta(seconds=5)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([recent_cts]))

        with patch(
            "apps.trading.tasks.recovery._active_celery_task_ids",
            return_value={str(task.celery_task_id)},
        ):
            from apps.trading.tasks.recovery import recover_orphaned_tasks

            result = recover_orphaned_tasks(source="worker_ready")

        assert result["backtest"] == 0
        tl.objects.create.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_backtest_recovery_no_longer_attempts_resubmit(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 1
        service_instance.start_task.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_race_condition_reset_returns_zero(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 0

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 0
        service_instance.start_task.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_recovers_trading_task_in_same_run(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        task.celery_task_id = "old-celery-id"
        task.execution_run_id = 5

        # Calls: 1) recovery queryset, 2) optimistic lock update
        optimistic_lock_qs = MagicMock()
        optimistic_lock_qs.update.return_value = 1
        tt.objects.filter.side_effect = [_make_qs([task]), optimistic_lock_qs]

        cts.objects.filter.return_value.first.return_value = None

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["trading"] == 1
        service_instance.recover_trading_task.assert_called_once_with(task)
        service_instance.start_task.assert_not_called()
        tl.objects.create.assert_called_once()
        assert "persisted strategy and grid state" in tl.objects.create.call_args.kwargs["message"]

    @pytest.mark.usefixtures("_mock_models")
    def test_backtest_recovery_logs_marked_stopped_instead_of_restart(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        stale_cts = MagicMock()
        stale_cts.instance_key = f"{task.pk}:{task.execution_id}"
        stale_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=6)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([stale_cts]))

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="worker_ready")
        assert result["backtest"] == 1
        tl.objects.create.assert_called_once()
        message = tl.objects.create.call_args.kwargs["message"]
        assert "marked stopped" in message
        assert "restarting the backtest from the beginning automatically" in message

    @pytest.mark.usefixtures("_mock_models")
    def test_backtest_recovery_updates_existing_celery_status_to_stopped(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        stale_cts = MagicMock()
        stale_cts.instance_key = f"{task.pk}:{task.execution_id}"
        stale_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=6)

        trading_cts_qs = MagicMock()
        trading_cts_qs.__iter__.return_value = iter([stale_cts])
        cts.objects.filter.return_value = trading_cts_qs

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result["backtest"] == 1
        trading_cts_qs.update.assert_called_once()

    @pytest.mark.usefixtures("_mock_models")
    def test_backtest_uses_longer_stale_heartbeat_threshold(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        recent_for_backtest = MagicMock()
        recent_for_backtest.instance_key = f"{task.pk}:{task.execution_id}"
        recent_for_backtest.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=2)
        cts.objects.filter.return_value.__iter__ = MagicMock(
            return_value=iter([recent_for_backtest])
        )

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 0
        tl.objects.create.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_failed_trading_recovery_is_not_counted(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING

        # Calls: 1) recovery queryset, 2) optimistic lock update, 3) FAILED update
        optimistic_lock_qs = MagicMock()
        optimistic_lock_qs.update.return_value = 1  # lock acquired
        failed_update_qs = MagicMock()
        failed_update_qs.update.return_value = 1
        tt.objects.filter.side_effect = [_make_qs([task]), optimistic_lock_qs, failed_update_qs]
        cts.objects.filter.return_value.first.return_value = None

        service_instance = MagicMock()
        service_instance.recover_trading_task.side_effect = RuntimeError("resume failed")
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["trading"] == 0

    @pytest.mark.usefixtures("_mock_models")
    def test_trading_still_uses_shorter_stale_heartbeat_threshold(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING

        optimistic_lock_qs = MagicMock()
        optimistic_lock_qs.update.return_value = 1
        tt.objects.filter.side_effect = [_make_qs([task]), optimistic_lock_qs]

        stale_for_trading = MagicMock()
        stale_for_trading.instance_key = f"{task.pk}:{task.execution_id}"
        stale_for_trading.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=2)
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([stale_for_trading]))

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["trading"] == 1
        service_instance.recover_trading_task.assert_called_once_with(task)


class TestRecoverOrphanedTasksBeat:
    """Tests for the Celery Beat wrapper."""

    @patch("apps.trading.tasks.recovery.recover_orphaned_tasks")
    def test_calls_core_with_celery_beat_source(self, mock_recover):
        mock_recover.return_value = {"backtest": 0, "trading": 0}

        from apps.trading.tasks.recovery import recover_orphaned_tasks_beat

        result = recover_orphaned_tasks_beat()
        mock_recover.assert_called_once_with(source="celery_beat")
        assert result == {"backtest": 0, "trading": 0}

    @patch("apps.trading.tasks.recovery.recover_orphaned_tasks")
    def test_startup_wrapper_uses_worker_ready_source(self, mock_recover):
        mock_recover.return_value = {"backtest": 0, "trading": 1}

        from apps.trading.tasks.recovery import recover_orphaned_tasks_startup

        result = recover_orphaned_tasks_startup()
        mock_recover.assert_called_once_with(source="worker_ready")
        assert result == {"backtest": 0, "trading": 1}
