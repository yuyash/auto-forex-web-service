"""Celery task status models."""

from __future__ import annotations

from typing import Any

from django.db import models, transaction
from django.utils import timezone


class CeleryTaskStatusManager(models.Manager):
    """Custom manager for CeleryTaskStatus with lifecycle operations."""

    @staticmethod
    def normalize_instance_key(instance_key: str | None) -> str:
        """Normalize instance key to a string."""
        return str(instance_key) if instance_key else "default"

    @transaction.atomic
    def start_task(
        self,
        *,
        task_name: str,
        instance_key: str | None = None,
        celery_task_id: str | None = None,
        worker: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> "CeleryTaskStatus":
        """Start tracking a new task execution.

        Args:
            task_name: Name of the Celery task
            instance_key: Unique identifier for this task instance
            celery_task_id: Celery task ID
            worker: Worker hostname
            meta: Additional metadata

        Returns:
            CeleryTaskStatus: The created or updated task status record
        """
        now = timezone.now()
        normalized_key = self.normalize_instance_key(instance_key)

        obj, _created = self.select_for_update().update_or_create(
            task_name=str(task_name),
            instance_key=normalized_key,
            defaults={
                "celery_task_id": celery_task_id,
                "worker": worker,
                "status": CeleryTaskStatus.Status.RUNNING,
                "status_message": None,
                "meta": meta or {},
                "started_at": now,
                "last_heartbeat_at": now,
                "stopped_at": None,
            },
        )
        return obj


class CeleryTaskStatus(models.Model):
    """Track a Celery task instance managed by the trading app.

    Long-running tasks should heartbeat and periodically check status to support
    clean shutdowns (e.g., when a cancellation signal is received).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    objects = CeleryTaskStatusManager()

    # Celery task name (e.g. "trading.tasks.run_trading_task")
    task_name = models.CharField(max_length=200, db_index=True)

    # Instance key differentiates multiple runs/instances of the same task.
    instance_key = models.CharField(
        max_length=200,
        blank=True,
        default="default",
        db_index=True,
    )

    celery_task_id = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    worker = models.CharField(max_length=200, null=True, blank=True)

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )

    status_message = models.TextField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "trading_celery_tasks"
        verbose_name = "Trading Celery Task Status"
        verbose_name_plural = "Trading Celery Task Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["task_name", "instance_key"],
                name="uniq_trading_task_name_instance_key",
            )
        ]
        indexes = [
            models.Index(fields=["task_name", "status"], name="tcs_tn_st_idx"),
            models.Index(fields=["celery_task_id"], name="tcs_celery_id_idx"),
            models.Index(fields=["last_heartbeat_at"], name="tcs_hb_idx"),
        ]

    def __str__(self) -> str:
        key = self.instance_key or "default"
        return f"{self.task_name} ({key}) [{self.status}]"

    def heartbeat(
        self,
        *,
        status_message: str | None = None,
        meta_update: dict[str, Any] | None = None,
    ) -> None:
        """Update heartbeat timestamp and optional metadata.

        Args:
            status_message: Optional status message to update
            meta_update: Optional metadata updates to merge with existing meta
        """
        now = timezone.now()
        updates: dict[str, Any] = {"last_heartbeat_at": now}

        if status_message is not None:
            updates["status_message"] = status_message

        if meta_update is not None:
            # Convert Decimal objects to strings for JSON serialization
            from decimal import Decimal

            json_safe_meta = {
                k: str(v) if isinstance(v, Decimal) else v for k, v in meta_update.items()
            }

            # Merge with existing meta
            merged_meta = {**self.meta, **json_safe_meta}
            updates["meta"] = merged_meta

        type(self).objects.filter(pk=self.pk).update(**updates)

        # Update instance attributes
        for key, value in updates.items():
            setattr(self, key, value)

    def mark_stopped(
        self,
        *,
        status: "CeleryTaskStatus.Status" | None = None,
        status_message: str | None = None,
    ) -> None:
        """Mark task as stopped/completed/failed.

        Args:
            status: Status to set (defaults to STOPPED)
            status_message: Optional status message
        """
        if status is None:
            status = self.Status.STOPPED

        now = timezone.now()
        updates: dict[str, Any] = {
            "status": status,
            "stopped_at": now,
            "last_heartbeat_at": now,
        }

        if status_message is not None:
            updates["status_message"] = status_message

        type(self).objects.filter(pk=self.pk).update(**updates)

        # Update instance attributes
        for key, value in updates.items():
            setattr(self, key, value)
