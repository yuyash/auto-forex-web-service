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
        service_instance.start_task.assert_called_once()

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

    @pytest.mark.usefixtures("_mock_models")
    def test_skips_task_with_recent_heartbeat(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        recent_cts = MagicMock()
        recent_cts.instance_key = f"{task.pk}:{task.execution_id}"
        recent_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=1)
        # Prefetch returns the recent heartbeat
        cts.objects.filter.return_value.__iter__ = MagicMock(return_value=iter([recent_cts]))

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 0

    @pytest.mark.usefixtures("_mock_models")
    def test_marks_failed_when_resubmit_fails(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = _make_qs([task])

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        service_instance.start_task.side_effect = RuntimeError("Celery down")
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")
        assert result["backtest"] == 0
        assert type(task).objects.filter.return_value.update.call_count == 2

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


class TestRecoverOrphanedTasksBeat:
    """Tests for the Celery Beat wrapper."""

    @patch("apps.trading.tasks.recovery.recover_orphaned_tasks")
    def test_calls_core_with_celery_beat_source(self, mock_recover):
        mock_recover.return_value = {"backtest": 0, "trading": 0}

        from apps.trading.tasks.recovery import recover_orphaned_tasks_beat

        result = recover_orphaned_tasks_beat()
        mock_recover.assert_called_once_with(source="celery_beat")
        assert result == {"backtest": 0, "trading": 0}
