"""Task lock manager service for trading/backtest executions.

Historically, the trading app used a dedicated lock manager.
This implementation is backed by the trading app's CeleryTaskStatus table.

This module lives in the trading service layer and is the preferred import:
`from apps.trading.services.task_lock_manager import TaskLockManager`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.utils import timezone

from apps.trading.enums import TaskType
from apps.trading.models import CeleryTaskStatus


@dataclass(frozen=True, slots=True)
class TaskLockInfo:
    task_name: str
    instance_key: str
    last_heartbeat_at: datetime | None

    @property
    def is_stale(self) -> bool:
        if not self.last_heartbeat_at:
            return True
        return (timezone.now() - self.last_heartbeat_at) > timedelta(seconds=30)


class TaskLockManager:
    """Service object expected by trading views."""

    def _task_name_for_type(self, task_type: str) -> str:
        if task_type == TaskType.TRADING:
            return "trading.tasks.run_trading_task"
        if task_type == TaskType.BACKTEST:
            return "trading.tasks.run_backtest_task"
        return str(task_type)

    def get_lock_info(self, task_type: str, task_id: int) -> TaskLockInfo | None:
        task_name = self._task_name_for_type(task_type)
        instance_key = str(task_id)
        row = (
            CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key)
            .values("status", "last_heartbeat_at")
            .first()
        )
        if not row:
            return None

        status = str(row.get("status") or "")
        if status not in {
            CeleryTaskStatus.Status.RUNNING,
            CeleryTaskStatus.Status.STOP_REQUESTED,
        }:
            return None

        heartbeat = row.get("last_heartbeat_at")
        last_heartbeat_at = heartbeat if isinstance(heartbeat, datetime) else None

        return TaskLockInfo(
            task_name=task_name,
            instance_key=instance_key,
            last_heartbeat_at=last_heartbeat_at,
        )

    def release_lock(self, task_type: str, task_id: int) -> None:
        task_name = self._task_name_for_type(task_type)
        instance_key = str(task_id)
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
            status=CeleryTaskStatus.Status.STOPPED,
            stopped_at=timezone.now(),
            last_heartbeat_at=timezone.now(),
        )

    def set_cancellation_flag(self, task_type: str, task_id: int) -> None:
        task_name = self._task_name_for_type(task_type)
        instance_key = str(task_id)
        CeleryTaskStatus.objects.filter(task_name=task_name, instance_key=instance_key).update(
            status=CeleryTaskStatus.Status.STOP_REQUESTED,
            updated_at=timezone.now(),
        )
