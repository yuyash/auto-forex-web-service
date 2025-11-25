"""
State synchronization service for task execution.

This module provides the StateSynchronizer class for managing state transitions
between frontend and backend, ensuring consistency and proper cleanup.

Requirements: 3.1, 3.2, 3.4
"""

import logging

from django.db import transaction
from django.utils import timezone

from trading.backtest_task_models import BacktestTask
from trading.enums import TaskStatus
from trading.execution_models import TaskExecution
from trading.services.notifications import send_task_status_notification

logger = logging.getLogger(__name__)


class StateSynchronizer:
    """
    Synchronizes task state between frontend and backend.

    This service manages state transitions for tasks and their executions,
    ensuring database consistency and broadcasting notifications to connected
    frontend clients via WebSocket.

    Requirements: 3.1, 3.2, 3.4
    """

    def __init__(self, task_type: str = "backtest"):
        """
        Initialize state synchronizer.

        Args:
            task_type: Type of task (backtest or trading)
        """
        self.task_type = task_type
        logger.debug("StateSynchronizer initialized for task_type=%s", task_type)

    @transaction.atomic
    def transition_to_running(self, task: BacktestTask, execution: TaskExecution) -> None:
        """
        Transition task to running state with notifications.

        Updates both task and execution status to RUNNING, sets started_at
        timestamp, and broadcasts WebSocket notification to frontend.

        Args:
            task: BacktestTask instance
            execution: TaskExecution instance

        Requirements: 3.1, 3.2, 3.4
        """
        try:
            logger.info(
                "Transitioning task %d (execution %d) to RUNNING state",
                task.pk,
                execution.pk,
            )

            # Update task status
            task.status = TaskStatus.RUNNING
            task.save(update_fields=["status", "updated_at"])

            # Update execution status and timestamp
            execution.status = TaskStatus.RUNNING
            execution.started_at = timezone.now()
            execution.progress = 0
            execution.save(update_fields=["status", "started_at", "progress"])

            # Broadcast notification
            send_task_status_notification(
                user_id=task.user.pk,
                task_id=task.pk,
                task_name=task.name,
                task_type=self.task_type,
                status=TaskStatus.RUNNING,
                execution_id=execution.pk,
            )

            logger.info(
                "Task %d transitioned to RUNNING (execution %d)",
                task.pk,
                execution.pk,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to transition task %d to RUNNING: %s",
                task.pk,
                e,
                exc_info=True,
            )
            raise

    @transaction.atomic
    def transition_to_stopped(self, task: BacktestTask, execution: TaskExecution) -> None:
        """
        Transition task to stopped state with cleanup.

        Updates both task and execution status to STOPPED, sets completed_at
        timestamp, and broadcasts WebSocket notification. This method should
        be called when a task is manually stopped by the user.

        Args:
            task: BacktestTask instance
            execution: TaskExecution instance

        Requirements: 3.1, 3.2, 3.4
        """
        try:
            logger.info(
                "Transitioning task %d (execution %d) to STOPPED state",
                task.pk,
                execution.pk,
            )

            # Update task status
            task.status = TaskStatus.STOPPED
            task.save(update_fields=["status", "updated_at"])

            # Update execution status and timestamp
            execution.status = TaskStatus.STOPPED
            execution.completed_at = timezone.now()
            execution.save(update_fields=["status", "completed_at"])

            # Broadcast notification
            send_task_status_notification(
                user_id=task.user.pk,
                task_id=task.pk,
                task_name=task.name,
                task_type=self.task_type,
                status=TaskStatus.STOPPED,
                execution_id=execution.pk,
            )

            logger.info(
                "Task %d transitioned to STOPPED (execution %d)",
                task.pk,
                execution.pk,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to transition task %d to STOPPED: %s",
                task.pk,
                e,
                exc_info=True,
            )
            raise

    @transaction.atomic
    def transition_to_completed(self, task: BacktestTask, execution: TaskExecution) -> None:
        """
        Transition task to completed state with final metrics.

        Updates both task and execution status to COMPLETED, sets completed_at
        timestamp, sets progress to 100%, and broadcasts WebSocket notification.

        Args:
            task: BacktestTask instance
            execution: TaskExecution instance

        Requirements: 3.1, 3.2, 3.4
        """
        try:
            logger.info(
                "Transitioning task %d (execution %d) to COMPLETED state",
                task.pk,
                execution.pk,
            )

            # Update task status
            task.status = TaskStatus.COMPLETED
            task.save(update_fields=["status", "updated_at"])

            # Update execution status, timestamp, and progress
            execution.status = TaskStatus.COMPLETED
            execution.completed_at = timezone.now()
            execution.progress = 100
            execution.save(update_fields=["status", "completed_at", "progress"])

            # Broadcast notification
            send_task_status_notification(
                user_id=task.user.pk,
                task_id=task.pk,
                task_name=task.name,
                task_type=self.task_type,
                status=TaskStatus.COMPLETED,
                execution_id=execution.pk,
            )

            logger.info(
                "Task %d transitioned to COMPLETED (execution %d)",
                task.pk,
                execution.pk,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to transition task %d to COMPLETED: %s",
                task.pk,
                e,
                exc_info=True,
            )
            raise

    @transaction.atomic
    def transition_to_failed(
        self, task: BacktestTask, execution: TaskExecution, error: str
    ) -> None:
        """
        Transition task to failed state with error details.

        Updates both task and execution status to FAILED, sets completed_at
        timestamp, stores error message, and broadcasts WebSocket notification
        with error details.

        Args:
            task: BacktestTask instance
            execution: TaskExecution instance
            error: Error message describing the failure

        Requirements: 3.1, 3.2, 3.4
        """
        try:
            logger.error(
                "Transitioning task %d (execution %d) to FAILED state: %s",
                task.pk,
                execution.pk,
                error,
            )

            # Update task status
            task.status = TaskStatus.FAILED
            task.save(update_fields=["status", "updated_at"])

            # Update execution status, timestamp, and error message
            execution.status = TaskStatus.FAILED
            execution.completed_at = timezone.now()
            execution.error_message = error
            execution.save(update_fields=["status", "completed_at", "error_message"])

            # Broadcast notification with error message
            send_task_status_notification(
                user_id=task.user.pk,
                task_id=task.pk,
                task_name=task.name,
                task_type=self.task_type,
                status=TaskStatus.FAILED,
                execution_id=execution.pk,
                error_message=error,
            )

            logger.info(
                "Task %d transitioned to FAILED (execution %d)",
                task.pk,
                execution.pk,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Failed to transition task %d to FAILED: %s",
                task.pk,
                e,
                exc_info=True,
            )
            raise

    def verify_state_consistency(self, task_id: int) -> tuple[bool, str]:
        """
        Verify task state matches execution state.

        Checks that the task status is consistent with its latest execution
        status. This is useful for debugging state synchronization issues.

        Args:
            task_id: ID of the task to verify

        Returns:
            Tuple of (is_consistent, message)

        Requirements: 3.4
        """
        try:
            # Get task
            task = BacktestTask.objects.get(id=task_id)

            # Get latest execution
            latest_execution = task.get_latest_execution()

            if not latest_execution:
                # No executions yet - task should be in CREATED state
                if task.status == TaskStatus.CREATED:
                    return True, "Task has no executions and is in CREATED state"
                return (
                    False,
                    f"Task has no executions but status is {task.status} " f"(expected CREATED)",
                )

            # Check if statuses match
            if task.status == latest_execution.status:
                return (
                    True,
                    f"Task and execution states are consistent: {task.status}",
                )

            # States don't match
            return (
                False,
                f"State mismatch: task status is {task.status}, "
                f"but latest execution status is {latest_execution.status}",
            )

        except BacktestTask.DoesNotExist:
            return False, f"Task {task_id} not found"
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(
                "Error verifying state consistency for task %d: %s",
                task_id,
                e,
                exc_info=True,
            )
            return False, f"Error checking consistency: {str(e)}"
