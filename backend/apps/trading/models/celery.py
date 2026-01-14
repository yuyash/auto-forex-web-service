"""Celery task status models."""

from django.db import models


class CeleryTaskStatus(models.Model):
    """Track a Celery task instance managed by the trading app.

    Long-running tasks should heartbeat and periodically check status to support
    clean shutdowns (e.g., when a cancellation signal is received).
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        STOP_REQUESTED = "stop_requested", "Stop Requested"
        STOPPED = "stopped", "Stopped"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

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
