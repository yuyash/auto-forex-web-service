"""apps.trading.services.controller

Task lifecycle controller for managing task execution state and control flow.

This module provides the TaskController class which manages the lifecycle
of task executions, including starting, stopping, pausing, and heartbeating.
It wraps the CeleryTaskStatus model to provide a clean interface for task
control operations.

Requirements: 2.6, 8.1, 17.5
"""

from __future__ import annotations

from typing import Any

from apps.trading.dataclasses import TaskControl
from apps.trading.services.task import CeleryTaskService


class TaskController:
    """Controller for managing task execution lifecycle.

    This class provides a high-level interface for controlling task execution,
    including lifecycle management (start, stop, pause, resume), heartbeating,
    and checking control signals. It wraps the CeleryTaskService to provide
    a cleaner API aligned with the refactored architecture.

    The controller maintains task state through the CeleryTaskStatus model
    and provides methods to check for stop/pause requests during execution.

    Attributes:
        task_name: Name of the Celery task (e.g., "trading.tasks.run_trading_task")
        instance_key: Unique identifier for this task instance
        _service: Underlying CeleryTaskService instance

    Requirements:
        - 2.6: Handle all lifecycle transitions
        - 8.1: Support graceful error handling
        - 17.5: Handle Celery worker restarts gracefully

    Example:
        >>> controller = TaskController(
        ...     task_name="trading.tasks.run_trading_task",
        ...     instance_key="123"
        ... )
        >>> controller.start(celery_task_id="abc-123")
        >>> controller.heartbeat(status_message="Processing tick 100")
        >>> control = controller.check_control()
        >>> if control.should_stop:
        ...     controller.stop()
    """

    def __init__(
        self,
        *,
        task_name: str,
        instance_key: str,
        stop_check_interval_seconds: float = 1.0,
        heartbeat_interval_seconds: float = 5.0,
    ) -> None:
        """Initialize the task controller.

        Args:
            task_name: Name of the Celery task
            instance_key: Unique identifier for this task instance
            stop_check_interval_seconds: How often to check for stop signals (default: 1.0)
            heartbeat_interval_seconds: How often to send heartbeats (default: 5.0)
        """
        self.task_name = task_name
        self.instance_key = instance_key
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

        Requirements: 2.6
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

        Requirements: 2.6, 17.5
        """
        self._service.heartbeat(
            status_message=status_message,
            meta_update=meta_update,
            force=force,
        )

    def check_control(self, *, force: bool = False) -> TaskControl:
        """Check for control signals (stop, pause requests).

        This method checks the task status in the database to see if a stop
        or pause has been requested. Checks are throttled based on
        stop_check_interval_seconds to avoid excessive database queries.

        Args:
            force: If True, bypass throttling and check immediately

        Returns:
            TaskControl: Control flags indicating requested actions

        Requirements: 2.6, 10.5
        """
        should_stop = self._service.should_stop(force=force)
        # Note: Current implementation only supports stop requests.
        # Pause functionality can be added when needed by extending
        # CeleryTaskStatus.Status to include PAUSE_REQUESTED.
        return TaskControl(should_stop=should_stop, should_pause=False)

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

        Requirements: 2.6, 8.1
        """
        from apps.trading.models import CeleryTaskStatus

        status = CeleryTaskStatus.Status.FAILED if failed else CeleryTaskStatus.Status.STOPPED
        self._service.mark_stopped(
            status=status,
            status_message=status_message,
        )
