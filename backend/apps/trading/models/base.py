"""Base models for trading app with UUID support."""

import uuid
from datetime import timedelta
from typing import List

from django.db import models

from apps.trading.enums import TaskStatus


class UUIDModel(models.Model):
    """Abstract base model with UUID primary key and timestamps.

    This model provides:
    - UUID primary key for better distribution and security
    - Automatic created_at timestamp
    - Automatic updated_at timestamp

    All models that need UUID primary keys should inherit from this class.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for this record",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when this record was last updated",
    )

    class Meta:
        abstract = True
        ordering: List[str] = ["-created_at"]


class ExecutableTaskBehaviorMixin:
    """Shared behavior for task models that have execution lifecycle fields."""

    started_at: object
    completed_at: object
    status: str
    celery_task_id: object
    execution_id: object

    @property
    def duration(self) -> timedelta | None:
        """Calculate task execution duration when start and completion are known."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at  # type: ignore[operator]
        return None

    def _revoke_stopping_celery_task(self) -> None:
        celery_id = self.celery_task_id or self.execution_id
        if self.status == TaskStatus.STOPPING and celery_id:
            from celery import current_app

            current_app.control.revoke(str(celery_id), terminate=True, signal="SIGKILL")

    def delete(self, *args, **kwargs) -> tuple[int, dict[str, int]]:
        """Delete the task if it is not actively running."""
        if self.status in [TaskStatus.STARTING, TaskStatus.RUNNING]:
            raise ValueError(
                f"Cannot delete task in {self.status} state. Stop the task first before deleting."
            )

        self._revoke_stopping_celery_task()
        return super().delete(*args, **kwargs)  # type: ignore[misc]
