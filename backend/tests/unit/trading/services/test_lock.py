from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.trading.enums import TaskType
from apps.trading.models import CeleryTaskStatus
from apps.trading.services.lock import TaskLockManager


@pytest.mark.django_db
class TestTaskLockManager:
    def test_get_lock_info_none_when_missing(self):
        mgr = TaskLockManager()
        assert mgr.get_lock_info(TaskType.TRADING, 123) is None

    def test_get_lock_info_only_for_running_or_stop_requested(self):
        mgr = TaskLockManager()

        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_trading_task",
            instance_key="1",
            status=CeleryTaskStatus.Status.COMPLETED,
            last_heartbeat_at=timezone.now(),
        )
        assert mgr.get_lock_info(TaskType.TRADING, 1) is None

        CeleryTaskStatus.objects.update_or_create(
            task_name="trading.tasks.run_trading_task",
            instance_key="1",
            defaults={
                "status": CeleryTaskStatus.Status.RUNNING,
                "last_heartbeat_at": timezone.now(),
            },
        )

        info = mgr.get_lock_info(TaskType.TRADING, 1)
        assert info is not None
        assert info.task_name == "trading.tasks.run_trading_task"
        assert info.instance_key == "1"
        assert info.is_stale is False

    def test_lock_is_stale_when_heartbeat_old(self):
        mgr = TaskLockManager()
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest_task",
            instance_key="2",
            status=CeleryTaskStatus.Status.RUNNING,
            last_heartbeat_at=timezone.now() - timedelta(seconds=60),
        )
        info = mgr.get_lock_info(TaskType.BACKTEST, 2)
        assert info is not None
        assert info.is_stale is True
