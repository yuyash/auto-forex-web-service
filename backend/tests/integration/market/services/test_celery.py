"""Integration tests for CeleryTaskService."""

import pytest

from apps.market.models import CeleryTaskStatus
from apps.market.services.celery import CeleryTaskService


@pytest.mark.django_db
class TestCeleryTaskServiceIntegration:
    """Integration tests for CeleryTaskService."""

    def test_start_creates_task_status(self) -> None:
        """Test that start() creates CeleryTaskStatus record."""
        service = CeleryTaskService(
            task_name="market.tasks.test_task",
            instance_key="test_instance",
        )

        service.start(
            celery_task_id="test-celery-id",
            worker="test-worker",
            meta={"test": "data"},
        )

        # Verify record was created
        task = CeleryTaskStatus.objects.get(
            task_name="market.tasks.test_task",
            instance_key="test_instance",
        )

        assert task.status == CeleryTaskStatus.Status.RUNNING
        assert task.celery_task_id == "test-celery-id"
        assert task.worker == "test-worker"
        assert task.meta["test"] == "data"

    def test_heartbeat_updates_timestamp(self) -> None:
        """Test that heartbeat() updates last_heartbeat_at."""
        service = CeleryTaskService(
            task_name="market.tasks.test_task2",
            instance_key="test_instance2",
        )

        service.start(celery_task_id="test-id", worker="test-worker")

        # Perform heartbeat
        service.heartbeat(status_message="Running", force=True)

        # Verify heartbeat was recorded
        task = CeleryTaskStatus.objects.get(
            task_name="market.tasks.test_task2",
            instance_key="test_instance2",
        )

        assert task.last_heartbeat_at is not None
        assert task.status_message == "Running"

    def test_mark_stopped_updates_status(self) -> None:
        """Test that mark_stopped() updates status."""
        service = CeleryTaskService(
            task_name="market.tasks.test_task3",
            instance_key="test_instance3",
        )

        service.start(celery_task_id="test-id", worker="test-worker")

        # Mark as stopped
        service.mark_stopped(
            status=CeleryTaskStatus.Status.COMPLETED,
            status_message="Task completed",
        )

        # Verify status was updated
        task = CeleryTaskStatus.objects.get(
            task_name="market.tasks.test_task3",
            instance_key="test_instance3",
        )

        assert task.status == CeleryTaskStatus.Status.COMPLETED
        assert task.status_message == "Task completed"
        assert task.stopped_at is not None

    def test_should_stop_checks_status(self) -> None:
        """Test that should_stop() checks task status."""
        service = CeleryTaskService(
            task_name="market.tasks.test_task4",
            instance_key="test_instance4",
        )

        service.start(celery_task_id="test-id", worker="test-worker")

        # Initially should not stop
        assert service.should_stop(force=True) is False

        # Request stop
        task = CeleryTaskStatus.objects.get(
            task_name="market.tasks.test_task4",
            instance_key="test_instance4",
        )
        task.status = CeleryTaskStatus.Status.STOPPING
        task.save()

        # Now should stop
        assert service.should_stop(force=True) is True
