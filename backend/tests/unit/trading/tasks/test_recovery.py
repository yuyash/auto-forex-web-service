"""Tests for orphaned task recovery."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.utils import timezone as dj_timezone

from apps.trading.enums import TaskStatus


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
        yield bt, tt, cts, tl, svc_cls


class TestRecoverOrphanedTasks:
    """Tests for recover_orphaned_tasks."""

    @pytest.mark.usefixtures("_mock_models")
    def test_no_orphaned_tasks(self, _mock_models):
        bt, tt, cts, tl, svc_cls = _mock_models
        bt.objects.filter.return_value = []
        tt.objects.filter.return_value = []

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result == {"backtest": 0, "trading": 0}

    @pytest.mark.usefixtures("_mock_models")
    def test_recovers_orphaned_backtest_no_cts_row(self, _mock_models):
        """Task with no CeleryTaskStatus row is treated as orphaned."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        task.celery_task_id = "old-celery-id"
        bt.objects.filter.return_value = [task]
        tt.objects.filter.return_value = []

        # No CeleryTaskStatus row
        cts.objects.filter.return_value.first.return_value = None

        # Reset succeeds
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
        """Task with stale heartbeat is treated as orphaned."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = [task]
        tt.objects.filter.return_value = []

        # Stale heartbeat (10 minutes ago)
        stale_cts = MagicMock()
        stale_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=10)
        cts.objects.filter.return_value.first.return_value = stale_cts

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result["backtest"] == 1

    @pytest.mark.usefixtures("_mock_models")
    def test_skips_task_with_recent_heartbeat(self, _mock_models):
        """Task with recent heartbeat is NOT orphaned."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = [task]
        tt.objects.filter.return_value = []

        # Recent heartbeat (1 minute ago)
        recent_cts = MagicMock()
        recent_cts.last_heartbeat_at = dj_timezone.now() - timedelta(minutes=1)
        cts.objects.filter.return_value.first.return_value = recent_cts

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result["backtest"] == 0

    @pytest.mark.usefixtures("_mock_models")
    def test_marks_failed_when_resubmit_fails(self, _mock_models):
        """If start_task raises, the task is marked FAILED."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = [task]
        tt.objects.filter.return_value = []

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        type(task).objects.filter.return_value.update.return_value = 1

        service_instance = MagicMock()
        service_instance.start_task.side_effect = RuntimeError("Celery down")
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result["backtest"] == 1
        # Should have been called twice: once for reset, once for marking FAILED
        assert type(task).objects.filter.return_value.update.call_count == 2

    @pytest.mark.usefixtures("_mock_models")
    def test_race_condition_reset_returns_zero(self, _mock_models):
        """If another process already reset the task, skip it."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        bt.objects.filter.return_value = [task]
        tt.objects.filter.return_value = []

        cts.objects.filter.return_value.first.return_value = None

        type(task).objects = MagicMock()
        # Another process already handled it
        type(task).objects.filter.return_value.update.return_value = 0

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        # Count is 0 because the reset didn't actually happen
        assert result["backtest"] == 0
        service_instance.start_task.assert_not_called()

    @pytest.mark.usefixtures("_mock_models")
    def test_recovers_trading_task_in_same_run(self, _mock_models):
        """Trading orphan recovery must preserve run and call recover_trading_task."""
        bt, tt, cts, tl, svc_cls = _mock_models

        task = MagicMock()
        task.pk = uuid4()
        task.status = TaskStatus.RUNNING
        task.celery_task_id = "old-celery-id"
        task.execution_run_id = 5
        bt.objects.filter.return_value = []
        tt.objects.filter.return_value = [task]

        # No CeleryTaskStatus row -> orphan.
        cts.objects.filter.return_value.first.return_value = None

        service_instance = MagicMock()
        svc_cls.return_value = service_instance

        from apps.trading.tasks.recovery import recover_orphaned_tasks

        result = recover_orphaned_tasks(source="test")

        assert result["trading"] == 1
        service_instance.recover_trading_task.assert_called_once_with(task)
        service_instance.start_task.assert_not_called()


class TestRecoverOrphanedTasksBeat:
    """Tests for the Celery Beat wrapper."""

    @patch("apps.trading.tasks.recovery.recover_orphaned_tasks")
    def test_calls_core_with_celery_beat_source(self, mock_recover):
        mock_recover.return_value = {"backtest": 0, "trading": 0}

        from apps.trading.tasks.recovery import recover_orphaned_tasks_beat

        result = recover_orphaned_tasks_beat()

        mock_recover.assert_called_once_with(source="celery_beat")
        assert result == {"backtest": 0, "trading": 0}
