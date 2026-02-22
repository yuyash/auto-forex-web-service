"""Unit tests for CeleryTaskStatus model."""

import pytest
from django.utils import timezone

from apps.market.models import CeleryTaskStatus


@pytest.mark.django_db
class TestCeleryTaskStatusModel:
    """Test CeleryTaskStatus model."""

    def test_create_celery_task_status(self) -> None:
        """Test creating celery task status."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.subscribe_ticks",
            instance_key="test_instance",
            celery_task_id="abc-123",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task.task_name == "market.tasks.subscribe_ticks"
        assert task.instance_key == "test_instance"
        assert task.celery_task_id == "abc-123"
        assert task.status == CeleryTaskStatus.Status.RUNNING

    def test_status_choices(self) -> None:
        """Test status choices."""
        assert CeleryTaskStatus.Status.RUNNING == "running"
        assert CeleryTaskStatus.Status.STOPPING == "stopping"
        assert CeleryTaskStatus.Status.STOPPED == "stopped"
        assert CeleryTaskStatus.Status.COMPLETED == "completed"
        assert CeleryTaskStatus.Status.FAILED == "failed"

    def test_update_status(self) -> None:
        """Test updating task status."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.test_task",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        task.status = CeleryTaskStatus.Status.COMPLETED
        task.status_message = "Task completed successfully"
        task.stopped_at = timezone.now()
        task.save()

        task.refresh_from_db()
        assert task.status == CeleryTaskStatus.Status.COMPLETED
        assert task.status_message == "Task completed successfully"
        assert task.stopped_at is not None

    def test_unique_constraint(self) -> None:
        """Test unique constraint on task_name and instance_key."""
        CeleryTaskStatus.objects.create(
            task_name="market.tasks.unique_task",
            instance_key="instance1",
        )

        # Should raise error for duplicate
        with pytest.raises(Exception):
            CeleryTaskStatus.objects.create(
                task_name="market.tasks.unique_task",
                instance_key="instance1",
            )

    def test_str_representation(self) -> None:
        """Test string representation."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.test_task",
            instance_key="test_key",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        str_repr = str(task)
        assert "market.tasks.test_task" in str_repr
        assert "test_key" in str_repr
        assert "running" in str_repr.lower()

    def test_meta_field(self) -> None:
        """Test meta JSON field."""
        task = CeleryTaskStatus.objects.create(
            task_name="market.tasks.test_task",
            meta={"instrument": "EUR_USD", "count": 100},
        )

        assert task.meta["instrument"] == "EUR_USD"
        assert task.meta["count"] == 100
