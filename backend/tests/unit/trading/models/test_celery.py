"""Unit tests for trading celery models."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import CeleryTaskStatus

User = get_user_model()


@pytest.mark.django_db
class TestCeleryTaskStatusModel:
    """Test CeleryTaskStatus model."""

    def test_create_celery_task_status(self):
        """Test creating celery task status."""
        task = CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest",
            instance_key="test-instance",
            celery_task_id="test-celery-id-123",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        assert task.task_name == "trading.tasks.run_backtest"
        assert task.instance_key == "test-instance"
        assert task.celery_task_id == "test-celery-id-123"
        assert task.status == CeleryTaskStatus.Status.RUNNING

    def test_unique_constraint_on_task_name_and_instance_key(self):
        """Test unique constraint on task_name and instance_key."""
        CeleryTaskStatus.objects.create(
            task_name="trading.tasks.run_backtest",
            instance_key="test-instance",
            status=CeleryTaskStatus.Status.RUNNING,
        )

        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            CeleryTaskStatus.objects.create(
                task_name="trading.tasks.run_backtest",
                instance_key="test-instance",
                status=CeleryTaskStatus.Status.RUNNING,
            )

    def test_status_choices(self):
        """Test status choices are available."""
        choices = CeleryTaskStatus.Status.choices
        assert len(choices) >= 5
        assert ("running", "Running") in choices
        assert ("completed", "Completed") in choices
        assert ("failed", "Failed") in choices
