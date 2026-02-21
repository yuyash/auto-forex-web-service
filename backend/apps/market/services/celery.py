from __future__ import annotations

import time
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.market.models import CeleryTaskStatus


class CeleryTaskService:
    def __init__(
        self,
        *,
        task_name: str,
        instance_key: str | None = None,
        stop_check_interval_seconds: float = 1.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        self.task_name = str(task_name)
        self.instance_key = self.normalize_instance_key(instance_key)

        self.stop_check_interval_seconds = float(stop_check_interval_seconds)
        self.heartbeat_interval_seconds = float(heartbeat_interval_seconds)

        self._last_stop_check_monotonic = 0.0
        self._cached_should_stop = False

        self._last_heartbeat_monotonic = 0.0

    @staticmethod
    def normalize_instance_key(instance_key: str | None) -> str:
        return str(instance_key) if instance_key else "default"

    @transaction.atomic
    def start(
        self,
        *,
        celery_task_id: str | None = None,
        worker: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> CeleryTaskStatus:
        now = timezone.now()

        obj, _created = CeleryTaskStatus.objects.select_for_update().update_or_create(
            task_name=self.task_name,
            instance_key=self.instance_key,
            defaults={
                "celery_task_id": celery_task_id or "",
                "worker": worker or "",
                "status": CeleryTaskStatus.Status.RUNNING,
                "status_message": "",
                "meta": meta or {},
                "started_at": now,
                "last_heartbeat_at": now,
                "stopped_at": None,
            },
        )
        return obj

    def heartbeat(
        self,
        *,
        status_message: str | None = None,
        meta_update: dict[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        now_monotonic = time.monotonic()
        if (
            not force
            and (now_monotonic - self._last_heartbeat_monotonic) < self.heartbeat_interval_seconds
        ):
            return

        now = timezone.now()
        updates: dict[str, Any] = {"last_heartbeat_at": now}

        if status_message is not None:
            updates["status_message"] = status_message

        if meta_update is not None:
            # Best-effort shallow merge. Only do the read/merge when we actually
            # decide to heartbeat (throttled).
            current = (
                CeleryTaskStatus.objects.filter(
                    task_name=self.task_name, instance_key=self.instance_key
                )
                .values_list("meta", flat=True)
                .first()
            )
            merged: dict[str, Any] = {}
            if isinstance(current, dict):
                merged.update(current)
            merged.update(meta_update)
            updates["meta"] = merged

        CeleryTaskStatus.objects.filter(
            task_name=self.task_name, instance_key=self.instance_key
        ).update(**updates)

        self._last_heartbeat_monotonic = now_monotonic

    def should_stop(self, *, force: bool = False) -> bool:
        now_monotonic = time.monotonic()
        if (
            not force
            and (now_monotonic - self._last_stop_check_monotonic) < self.stop_check_interval_seconds
        ):
            return self._cached_should_stop

        status = (
            CeleryTaskStatus.objects.filter(
                task_name=self.task_name, instance_key=self.instance_key
            )
            .values_list("status", flat=True)
            .first()
        )
        self._cached_should_stop = status == CeleryTaskStatus.Status.STOPPING
        self._last_stop_check_monotonic = now_monotonic
        return self._cached_should_stop

    def mark_stopped(
        self,
        *,
        status: CeleryTaskStatus.Status = CeleryTaskStatus.Status.STOPPED,
        status_message: str | None = None,
    ) -> None:
        now = timezone.now()
        updates: dict[str, Any] = {
            "status": status,
            "stopped_at": now,
            "last_heartbeat_at": now,
        }
        if status_message is not None:
            updates["status_message"] = status_message

        CeleryTaskStatus.objects.filter(
            task_name=self.task_name, instance_key=self.instance_key
        ).update(**updates)
