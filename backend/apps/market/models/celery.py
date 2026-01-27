"""Celery task status model."""

from django.db import models


class CeleryTaskStatus(models.Model):
    """Track a Celery task instance managed by the market app.

    Long-running tasks should heartbeat and periodically check status to support
    clean shutdowns (e.g., when a cancellation signal is received).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    # Celery task name (e.g. "market.tasks.subscribe_ticks_to_db")
    task_name = models.CharField(max_length=200, db_index=True)

    # Instance key differentiates multiple runs/instances of the same task.
    # Example: backtest publisher uses request_id; subscriber might use "default".
    instance_key = models.CharField(
        max_length=200,
        blank=True,
        default="default",
        db_index=True,
    )

    celery_task_id = models.CharField(max_length=200, default="", blank=True, db_index=True)
    worker = models.CharField(max_length=200, default="", blank=True)

    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.RUNNING,
        db_index=True,
    )

    status_message = models.TextField(default="", blank=True)
    meta = models.JSONField(default=dict, blank=True)

    started_at = models.DateTimeField(null=True, blank=True)
    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "market_celery_tasks"
        verbose_name = "Celery Task Status"
        verbose_name_plural = "Celery Task Statuses"
        constraints = [
            models.UniqueConstraint(
                fields=["task_name", "instance_key"],
                name="uniq_market_task_name_instance_key",
            )
        ]
        indexes = [
            models.Index(
                fields=["task_name", "status"],
                name="market_mana_task_na_57e1fc_idx",
            ),
            models.Index(fields=["celery_task_id"], name="market_mana_celery__e5025a_idx"),
            models.Index(fields=["last_heartbeat_at"], name="market_mana_last_he_d7d6f2_idx"),
        ]

    def __str__(self) -> str:
        key = self.instance_key or "default"
        return f"{self.task_name} ({key}) [{self.status}]"
