from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.market.models import CeleryTaskStatus
from apps.market.services.celery import CeleryTaskService


@pytest.mark.django_db
class TestCeleryTaskService:
    def test_start_creates_row(self) -> None:
        svc = CeleryTaskService(task_name="market.tasks.example", instance_key="k1")
        obj = svc.start(celery_task_id="abc", worker="w1", meta={"a": 1})

        assert obj.task_name == "market.tasks.example"
        assert obj.instance_key == "k1"
        assert obj.celery_task_id == "abc"
        assert obj.worker == "w1"
        assert obj.status == CeleryTaskStatus.Status.RUNNING
        assert obj.meta == {"a": 1}

    def test_should_stop_is_throttled_and_force_overrides(self) -> None:
        # Long stop-check interval means result is cached.
        svc = CeleryTaskService(
            task_name="market.tasks.example",
            instance_key="k2",
            stop_check_interval_seconds=999.0,
        )
        svc.start()

        assert svc.should_stop(force=True) is False

        CeleryTaskStatus.objects.filter(
            task_name=svc.task_name, instance_key=svc.instance_key
        ).update(status=CeleryTaskStatus.Status.STOP_REQUESTED)

        # Cached value should remain False.
        assert svc.should_stop() is False

        # Force should see the DB change.
        assert svc.should_stop(force=True) is True

    def test_heartbeat_is_throttled(self, monkeypatch) -> None:
        fixed = datetime(2025, 1, 1, tzinfo=UTC)

        # Patch timezone.now used by the service module.
        import apps.market.services.celery as task_module

        monkeypatch.setattr(task_module.timezone, "now", lambda: fixed)

        svc = CeleryTaskService(
            task_name="market.tasks.example",
            instance_key="k3",
            heartbeat_interval_seconds=999.0,
        )
        svc.start(meta={"x": 1})

        svc.heartbeat(status_message="one", meta_update={"b": 2}, force=True)
        row = CeleryTaskStatus.objects.get(task_name=svc.task_name, instance_key=svc.instance_key)
        assert row.status_message == "one"
        assert row.last_heartbeat_at == fixed
        assert row.meta == {"x": 1, "b": 2}

        # Second heartbeat should be throttled when force=False.
        svc.heartbeat(status_message="two", meta_update={"c": 3}, force=False)
        row2 = CeleryTaskStatus.objects.get(task_name=svc.task_name, instance_key=svc.instance_key)
        assert row2.status_message == "one"
        assert row2.meta == {"x": 1, "b": 2}

    def test_mark_stopped_updates_fields(self, monkeypatch) -> None:
        fixed = datetime(2025, 1, 2, tzinfo=UTC)

        import apps.market.services.celery as task_module

        monkeypatch.setattr(task_module.timezone, "now", lambda: fixed)

        svc = CeleryTaskService(task_name="market.tasks.example", instance_key="k4")
        svc.start()
        svc.mark_stopped(status=CeleryTaskStatus.Status.COMPLETED, status_message="done")

        row = CeleryTaskStatus.objects.get(task_name=svc.task_name, instance_key=svc.instance_key)
        assert row.status == CeleryTaskStatus.Status.COMPLETED
        assert row.status_message == "done"
        assert row.stopped_at == fixed
        assert row.last_heartbeat_at == fixed
