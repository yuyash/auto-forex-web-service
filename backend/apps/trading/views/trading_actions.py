"""Views for TradingTask lifecycle operations."""

from datetime import timedelta
from logging import Logger, getLogger
from typing import Any, cast

from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.models import Executions, TradingTasks
from apps.trading.services.lock import TaskLockManager
from apps.trading.views._helpers import (
    TaskExecutionPagination,
    _paginate_list_by_page,
)

logger: Logger = getLogger(name=__name__)


class TradingTaskStartView(APIView):
    """
    Start a trading task.

    POST: Start the live trading execution
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Start trading task execution.

        Validates task status in database AND checks celery task lock status
        before starting. Creates a new TaskExecution and queues the trading
        task for processing. Enforces one active task per account constraint.
        """
        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check database status first
        if task.status == TaskStatus.RUNNING:
            return Response(
                {"error": "Task is already running according to database status"},
                status=status.HTTP_409_CONFLICT,
            )

        # Check if there's an active celery task lock (actual running state)
        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)

        if lock_info is not None:
            # Lock exists - check if it's stale
            if not lock_info.is_stale:
                # Active lock exists - task is actually running
                return Response(
                    {
                        "error": "Task has an active execution lock. "
                        "A celery task may already be running."
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            # Stale lock - clean it up before proceeding
            logger.warning(
                "Cleaning up stale lock for trading task %d before starting",
                task_id,
            )
            lock_manager.release_lock(TaskType.TRADING, task_id)

            # Also sync database status if it's inconsistent
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.STOPPED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # Validate configuration before starting
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Start the task (this also checks for other running tasks on the account)
        try:
            task.start()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        execution: Executions | None
        try:
            with transaction.atomic():
                last_num = (
                    Executions.objects.select_for_update()
                    .filter(task_type=TaskType.TRADING, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = Executions.objects.create(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            # Concurrent starts should be prevented by the RUNNING status, but
            # if it races, fall back to whichever execution was created.
            execution = task.get_latest_execution()

        # Queue the trading task for execution
        from apps.trading.tasks import run_trading_task

        cast(Any, run_trading_task).delay(task.pk, execution_id=execution.pk if execution else None)

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' started by user %s",
            task.pk,
            task.name,
            request.user.pk,
        )

        # Return success response
        return Response(
            {
                "message": "Trading task started successfully",
                "task_id": task.pk,
                "execution_id": execution.pk if execution else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskStopView(APIView):
    """
    Stop a running trading task.

    POST: Stop the live trading execution with configurable stop mode

    Stop modes:
    - immediate: Stop immediately without waiting (fastest, keeps positions)
    - graceful: Stop gracefully, wait for pending operations (keeps positions)
    - graceful_close: Stop gracefully and close all open positions
    """

    permission_classes = [IsAuthenticated]

    # pylint: disable=too-many-locals
    def post(self, request: Request, task_id: int) -> Response:
        """
        Stop trading task execution.

        Validates task status in database AND checks celery task lock status
        before stopping. Updates task to stopped state and triggers cleanup.

        Request body (optional):
        - mode: Stop mode ('immediate', 'graceful', 'graceful_close')
                Default: 'graceful'
        """
        from apps.trading.enums import StopMode
        from apps.trading.tasks import stop_trading_task

        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check celery task lock status to determine actual running state
        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
        has_active_lock = lock_info is not None and not lock_info.is_stale

        # Validate task status - check both database and actual celery state
        db_is_stoppable = task.status in [TaskStatus.RUNNING]  # type: ignore[comparison-overlap]

        if not db_is_stoppable and not has_active_lock:
            # Task is not running in database AND no active celery task
            return Response(
                {"error": "Task is not running"},
                status=status.HTTP_409_CONFLICT,
            )

        # If database says not running but lock exists, sync database first
        if not db_is_stoppable and has_active_lock:
            logger.warning(
                "Trading task %d has active lock but database status is %s. "
                "Syncing database status before stopping.",
                task_id,
                task.status,
            )
            # Don't change to RUNNING, just proceed to stop

        # Get stop mode from request (default: graceful)
        mode_str = request.data.get("mode", StopMode.GRACEFUL)
        try:
            stop_mode = StopMode(mode_str)
        except ValueError:
            return Response(
                {
                    "error": f"Invalid stop mode: {mode_str}. "
                    f"Valid modes: {', '.join([m.value for m in StopMode])}"
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update task status to stopped
        task.status = TaskStatus.STOPPED

        # For graceful_close mode, clear strategy state immediately so can_resume returns false
        # This prevents Resume button from showing when positions are being closed
        update_fields = ["status", "updated_at"]
        if stop_mode == StopMode.GRACEFUL_CLOSE:
            task.strategy_state = {}
            update_fields.append("strategy_state")

        task.save(update_fields=update_fields)

        # Update latest execution if it exists and is running
        latest_execution = task.get_latest_execution()
        if latest_execution and latest_execution.status in [
            TaskStatus.RUNNING,
        ]:  # type: ignore[comparison-overlap]
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])

            # Add lifecycle log to execution
            latest_execution.add_log("INFO", f"=== Task STOPPED (mode: {stop_mode.label}) ===")

        # Queue the stop task with the specified mode to handle cleanup
        # (closing positions, releasing locks, etc.)
        if has_active_lock:
            cast(Any, stop_trading_task).delay(task.pk, stop_mode.value)
        else:
            # No active celery task, just clean up any stale locks
            if lock_info:
                lock_manager.release_lock(TaskType.TRADING, task_id)

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' stopped by user %s (mode: %s)",
            task.pk,
            task.name,
            request.user.pk,
            stop_mode.value,
        )

        return Response(
            {
                "message": f"Trading task stop initiated ({stop_mode.label})",
                "task_id": task.pk,
                "stop_mode": stop_mode.value,
                "status": TaskStatus.STOPPED,
            },
            status=status.HTTP_200_OK,
        )


class TradingTaskResumeView(APIView):
    """Resume a paused trading task."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """Resume trading task execution."""
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if task can be resumed
        if task.status != TaskStatus.STOPPED:
            return Response(
                {"error": f"Cannot resume task with status: {task.status}"},
                status=status.HTTP_409_CONFLICT,
            )

        # Check for active lock
        lock_manager = TaskLockManager()
        lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)

        if lock_info is not None and not lock_info.is_stale:
            return Response(
                {"error": "Task has an active lock. The task may already be running."},
                status=status.HTTP_409_CONFLICT,
            )

        # Clean up stale lock if exists
        if lock_info is not None and lock_info.is_stale:
            logger.warning(
                "Cleaning up stale lock for trading task %d before resuming",
                task_id,
            )
            lock_manager.release_lock(TaskType.TRADING, task_id)

        # Validate configuration
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update task status to running
        task.status = TaskStatus.RUNNING
        task.save(update_fields=["status", "updated_at"])

        # Create new execution for resume
        now = timezone.now()
        execution: Executions | None
        try:
            with transaction.atomic():
                last_num = (
                    Executions.objects.select_for_update()
                    .filter(task_type=TaskType.TRADING, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = Executions.objects.create(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution resumed",
                        }
                    ],
                )
        except IntegrityError:
            execution = task.get_latest_execution()

        # Queue the trading task
        from apps.trading.tasks import run_trading_task

        cast(Any, run_trading_task).delay(task.pk, execution_id=execution.pk if execution else None)

        # Log lifecycle event
        logger.info(
            "Trading task %d '%s' resumed by user %s",
            task.pk,
            task.name,
            request.user.pk,
        )

        return Response(
            {
                "message": "Trading task resumed successfully",
                "task_id": task.pk,
                "execution_id": execution.pk if execution else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskRestartView(APIView):
    """
    Restart a trading task with fresh state.

    POST: Clear strategy state and start fresh execution

    Unlike resume, restart clears all saved strategy state and starts from scratch.
    Use this when you want to abandon the previous state and start over.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Restart trading task with fresh state.

        Clears strategy_state and starts a new execution. Task can be in any
        state (stopped, failed) to be restarted, but not running or paused.

        Request body:
            - clear_state: bool (default: True) - Clear strategy state
        """
        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate configuration before restarting
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get clear_state option (default True)
        clear_state = request.data.get("clear_state", True)

        # Restart the task
        try:
            task.restart(clear_state=clear_state)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        now = timezone.now()
        execution: Executions | None
        try:
            with transaction.atomic():
                last_num = (
                    Executions.objects.select_for_update()
                    .filter(task_type=TaskType.TRADING, task_id=task_id)
                    .order_by("-execution_number")
                    .values_list("execution_number", flat=True)
                    .first()
                )
                next_num = int(last_num or 0) + 1
                execution = Executions.objects.create(
                    task_type=TaskType.TRADING,
                    task_id=task_id,
                    execution_number=next_num,
                    status=TaskStatus.RUNNING,
                    progress=0,
                    started_at=now,
                    logs=[
                        {
                            "timestamp": now.isoformat(),
                            "level": "INFO",
                            "message": "Execution queued",
                        }
                    ],
                )
        except IntegrityError:
            execution = task.get_latest_execution()

        # Queue the trading task for execution
        from apps.trading.tasks import run_trading_task

        cast(Any, run_trading_task).delay(task.pk, execution_id=execution.pk if execution else None)

        # Log lifecycle event
        state_info = "with state cleared" if clear_state else "preserving state"
        logger.info(
            "Trading task %d '%s' restarted by user %s (%s)",
            task.pk,
            task.name,
            request.user.pk,
            state_info,
        )

        # Return success response
        return Response(
            {
                "message": "Trading task restarted successfully",
                "task_id": task.pk,
                "state_cleared": clear_state,
                "execution_id": execution.pk if execution else None,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskExecutionsView(APIView):
    """
    Get execution history for a trading task.

    GET: List all executions for the task
    """

    permission_classes = [IsAuthenticated]
    pagination_class = TaskExecutionPagination

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get execution history for trading task.

        Returns all executions ordered by execution number (most recent first).
        """
        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get execution history
        executions = task.get_execution_history()

        from apps.trading.serializers import ExecutionsListSerializer

        paginator = self.pagination_class()
        paginated = paginator.paginate_queryset(executions, request)
        serializer = ExecutionsListSerializer(paginated, many=True)
        return paginator.get_paginated_response(serializer.data)


class TradingTaskLogsView(APIView):
    """
    Get logs for a trading task with pagination and filtering.

    GET: Return paginated log entries from Executions.logs JSONField
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _collect_logs(
        executions_query: QuerySet, level: str | None
    ) -> list[dict[str, str | int | None]]:
        """Collect and filter logs from executions."""
        all_logs = []
        for execution in executions_query:
            logs = execution.logs if isinstance(execution.logs, list) else []
            for log_entry in logs:
                if level and log_entry.get("level") != level:
                    continue

                all_logs.append(
                    {
                        "timestamp": log_entry.get("timestamp"),
                        "level": log_entry.get("level"),
                        "message": log_entry.get("message"),
                        "execution_id": execution.pk,
                        "execution_number": execution.execution_number,
                    }
                )
        return all_logs

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get task logs with pagination and filtering.

        Query parameters:
        - execution_id: Filter logs for specific execution (optional)
        - level: Filter by log level (INFO, WARNING, ERROR, DEBUG) (optional)
        - page: Page number (default: 1)
        - page_size: Page size (default: 100, max: 1000)

        Returns:
            Paginated log entries with execution_number included
        """
        # Verify task exists and user has access
        try:
            TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get and validate query parameters
        execution_id = request.query_params.get("execution_id")
        level = request.query_params.get("level")

        executions_query = Executions.objects.filter(
            task_type="trading",
            task_id=task_id,
        ).order_by("execution_number")

        if execution_id:
            try:
                executions_query = executions_query.filter(id=int(execution_id))
            except ValueError:
                return Response(
                    {"error": "Invalid execution_id"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Collect, filter, and sort logs
        all_logs = self._collect_logs(executions_query, level)
        all_logs.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=True)

        pagination = _paginate_list_by_page(
            request=request,
            items=all_logs,
            base_url=f"/api/trading/trading-tasks/{task_id}/logs/",
            default_page_size=100,
            max_page_size=1000,
            extra_query={
                "execution_id": execution_id,
                "level": level,
            },
        )

        return Response(pagination, status=status.HTTP_200_OK)


class TradingTaskStatusView(APIView):
    """
    Get current trading task status and execution details.

    GET: Return current status, progress, and execution information
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:  # pylint: disable=too-many-locals
        """
        Get current task status and execution details.

        Used by frontend for polling fallback when WebSocket connection fails.
        Returns current status, progress percentage, and latest execution details.
        Also detects and auto-completes stale running/stopped tasks.
        """
        # Get the task
        try:
            task = TradingTasks.objects.get(id=task_id, user=request.user.pk)
        except TradingTasks.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest execution
        latest_execution = task.get_latest_execution()
        lock_manager = TaskLockManager()

        # Check for stale running tasks and auto-complete them
        # But first check if task was recently started (grace period for Celery to pick up)
        task_recently_started = task.updated_at and (timezone.now() - task.updated_at) < timedelta(
            seconds=30
        )

        if task.status == TaskStatus.RUNNING and latest_execution and not task_recently_started:
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)

            # Task is "running" but no lock exists or lock is stale
            is_stale = lock_info is None or lock_info.is_stale

            # Check if latest execution is already completed (stale task)
            execution_completed = latest_execution.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.STOPPED,
            ]

            # Only auto-complete if execution is done AND (no lock OR stale lock)
            if execution_completed and is_stale:
                logger.warning(
                    "Detected stale running trading task %d (execution_status=%s, is_stale=%s), "
                    "auto-completing",
                    task_id,
                    latest_execution.status,
                    is_stale,
                )

                # Clean up any stale locks
                if lock_info:
                    lock_manager.release_lock(TaskType.TRADING, task_id)

                # Update task status to match execution status
                task.status = latest_execution.status
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # If the API queued an execution but no worker ever started it (no lock acquired),
        # fail the execution so the UI doesn't look "completed" with missing logs.
        if (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
            started_at = latest_execution.started_at
            startup_timeout_seconds = 120
            if (
                lock_info is None
                and started_at is not None
                and (timezone.now() - started_at) > timedelta(seconds=startup_timeout_seconds)
                and int(latest_execution.progress or 0) == 0
            ):
                msg = "Execution did not start (no worker lock acquired)"
                try:
                    latest_execution.add_log("ERROR", msg)
                except Exception as exc:  # pylint: disable=broad-exception-caught  # nosec B110
                    # Log the error but continue with status update
                    import logging

                    logger_local = logging.getLogger(__name__)
                    logger_local.warning("Failed to add execution log: %s", exc)

                latest_execution.status = TaskStatus.FAILED
                latest_execution.completed_at = timezone.now()
                latest_execution.error_message = msg
                latest_execution.save(
                    update_fields=["status", "completed_at", "error_message", "logs"]
                )

                task.status = TaskStatus.FAILED
                task.save(update_fields=["status", "updated_at"])
                task.refresh_from_db()

        # When task is stopped but execution is still running, update execution immediately
        # The task status being STOPPED is authoritative - user requested stop
        if (
            task.status == TaskStatus.STOPPED
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            logger.info(
                "Trading task %d is stopped but execution still running, updating execution status",
                task_id,
            )

            # Clean up any locks
            lock_info = lock_manager.get_lock_info(TaskType.TRADING, task_id)
            if lock_info:
                lock_manager.release_lock(TaskType.TRADING, task_id)

            # Update execution to stopped
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
            latest_execution.refresh_from_db()

        # Determine the correct progress to report
        pending_new_execution = (
            task.status == TaskStatus.RUNNING
            and latest_execution
            and latest_execution.status
            in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.STOPPED]
        )

        if pending_new_execution:
            reported_progress = 0
        elif latest_execution:
            reported_progress = latest_execution.progress
        else:
            reported_progress = 0

        # Build execution details
        execution_data = None
        if latest_execution:
            execution_data = {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "progress": latest_execution.progress,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "error_message": latest_execution.error_message or None,
            }

        # Build response data matching TaskStatusResponse interface
        response_data = {
            "task_id": task.pk,
            "task_type": "trading",
            "status": task.status,
            "progress": reported_progress,
            "pending_new_execution": pending_new_execution,
            "started_at": (
                latest_execution.started_at.isoformat()
                if latest_execution and latest_execution.started_at
                else None
            ),
            "completed_at": (
                latest_execution.completed_at.isoformat()
                if latest_execution and latest_execution.completed_at
                else None
            ),
            "error_message": (latest_execution.error_message or None) if latest_execution else None,
            "execution": execution_data,
        }

        # Include execution_id when task is running
        if task.status == TaskStatus.RUNNING and latest_execution:
            response_data["execution_id"] = latest_execution.pk

        return Response(response_data, status=status.HTTP_200_OK)
