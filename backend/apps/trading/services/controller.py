"""apps.trading.services.controller

Task lifecycle controller for managing task execution state and control flow.

This module provides the TaskController class which manages the lifecycle
of task executions, including starting, stopping, pausing, and heartbeating.
It wraps the CeleryTaskStatus model to provide a clean interface for task
control operations.
"""

from __future__ import annotations

from typing import Any

from apps.trading.dataclasses import TaskControl
from apps.trading.services.celery import CeleryTaskService


class TaskController:
    """Controller for managing task execution lifecycle.

    This class provides a high-level interface for controlling task execution,
    including lifecycle management (start, stop, pause, resume), heartbeating,
    and checking control signals. It wraps the CeleryTaskService to provide
    a cleaner API aligned with the refactored architecture.

    The controller maintains task state through the CeleryTaskStatus model
    and provides methods to check for stop/pause requests during execution.
    """

    def __init__(
        self,
        *,
        task_name: str,
        instance_key: str,
        task_id: int,
        stop_check_interval_seconds: float = 1.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize the task controller.

        Args:
            task_name: Name of the Celery task
            instance_key: Unique identifier for this task instance
            task_id: ID of the task model (BacktestTask or TradingTask)
            stop_check_interval_seconds: How often to check for stop signals (default: 1.0)
            heartbeat_interval_seconds: How often to send heartbeats (default: 5.0)
        """
        self.task_name = task_name
        self.instance_key = instance_key
        self.task_id = task_id
        self._last_stop_check = 0.0
        self._cached_should_stop = False
        self.stop_check_interval_seconds = stop_check_interval_seconds
        self._service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=stop_check_interval_seconds,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )

    def start(
        self,
        *,
        celery_task_id: str | None = None,
        worker: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Start the task execution.

        This method initializes the task status in the database, marking it
        as running and recording the start time. It should be called at the
        beginning of task execution.

        Args:
            celery_task_id: Celery task ID for this execution
            worker: Worker hostname executing the task
            meta: Additional metadata to store with the task status
        """
        self._service.start(
            celery_task_id=celery_task_id,
            worker=worker,
            meta=meta,
        )

    def heartbeat(
        self,
        *,
        status_message: str | None = None,
        meta_update: dict[str, Any] | None = None,
        force: bool = False,
    ) -> None:
        """Send a heartbeat to indicate the task is still alive.

        Heartbeats are throttled based on heartbeat_interval_seconds to avoid
        excessive database writes. Use force=True to bypass throttling.

        Args:
            status_message: Optional status message to update
            meta_update: Optional metadata updates to merge with existing meta
            force: If True, bypass throttling and send heartbeat immediately
        """
        self._service.heartbeat(
            status_message=status_message,
            meta_update=meta_update,
            force=force,
        )

    def check_control(self, *, force: bool = False) -> TaskControl:
        """Check for control signals (stop, pause requests).

        This method checks the task's status in the database to see if a stop
        has been requested (status == STOPPING). Checks are throttled based on
        stop_check_interval_seconds to avoid excessive database queries.

        Args:
            force: If True, bypass throttling and check immediately

        Returns:
            TaskControl: Control flags indicating requested actions
        """
        import time

        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTask, TradingTask

        now = time.monotonic()
        if not force and (now - self._last_stop_check) < self.stop_check_interval_seconds:
            return TaskControl(should_stop=self._cached_should_stop)  # type: ignore[call-arg]

        # Check task status directly
        try:
            task = (
                BacktestTask.objects.filter(pk=self.task_id)
                .values_list("status", flat=True)
                .first()
            )
            if task is None:
                task = (
                    TradingTask.objects.filter(pk=self.task_id)
                    .values_list("status", flat=True)
                    .first()
                )

            self._cached_should_stop = task == TaskStatus.STOPPING
        except Exception:
            self._cached_should_stop = False

        self._last_stop_check = now
        return TaskControl(should_stop=self._cached_should_stop)  # type: ignore[call-arg]

    def stop(
        self,
        *,
        status_message: str | None = None,
        failed: bool = False,
    ) -> None:
        """Mark the task as stopped.

        This method updates the task status to indicate it has stopped,
        either normally or due to failure. It records the stop time and
        final status message.

        Args:
            status_message: Optional message describing why the task stopped
            failed: If True, mark as FAILED instead of STOPPED
        """
        from apps.trading.models import CeleryTaskStatus

        status = CeleryTaskStatus.Status.FAILED if failed else CeleryTaskStatus.Status.STOPPED
        self._service.mark_stopped(
            status=status,
            status_message=status_message,
        )
