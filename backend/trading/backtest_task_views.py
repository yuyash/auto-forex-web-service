"""
API views for BacktestTask management.

This module provides REST API endpoints for:
- Creating and listing backtest tasks
- Retrieving, updating, and deleting backtest tasks
- Task lifecycle operations (start, stop, rerun)
- Task copy functionality
- Execution history retrieval

Requirements: 2.3, 2.4, 2.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3,
6.4, 6.5, 6.6, 6.7, 8.1, 8.2, 8.3, 8.4
"""

import logging
from typing import Type

from django.db.models import Q, QuerySet
from django.utils import timezone

from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .backtest_task_models import BacktestTask
from .backtest_task_serializers import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)
from .enums import TaskStatus
from .serializers import TaskExecutionSerializer

logger = logging.getLogger(__name__)


class BacktestTaskListCreateView(ListCreateAPIView):
    """
    List and create backtest tasks.

    GET: List all backtest tasks for the authenticated user with filtering and pagination
    POST: Create a new backtest task

    Requirements: 2.3, 2.4, 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method == "POST":
            return BacktestTaskCreateSerializer
        return BacktestTaskListSerializer

    def get_queryset(self) -> QuerySet:
        """
        Get backtest tasks for the authenticated user with filtering.

        Query parameters:
        - status: Filter by task status
        - config_id: Filter by configuration ID
        - strategy_type: Filter by strategy type
        - search: Search in name or description
        - ordering: Sort field (e.g., '-created_at', 'name')
        """
        queryset = BacktestTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "user"
        )

        # Filter by status
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

        # Filter by strategy type
        strategy_type = self.request.query_params.get("strategy_type")
        if strategy_type:
            queryset = queryset.filter(config__strategy_type=strategy_type)

        # Search in name or description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        return queryset


class BacktestTaskDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a backtest task.

    GET: Retrieve backtest task details
    PUT/PATCH: Update backtest task
    DELETE: Delete backtest task

    Requirements: 2.3, 2.4, 2.5, 8.1, 8.2
    """

    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "task_id"

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method in ["PUT", "PATCH"]:
            return BacktestTaskCreateSerializer
        return BacktestTaskSerializer

    def get_queryset(self) -> QuerySet:
        """Get backtest tasks for the authenticated user."""
        return BacktestTask.objects.filter(user=self.request.user.pk).select_related(
            "config", "user"
        )

    def perform_destroy(self, instance: BacktestTask) -> None:
        """
        Delete backtest task.

        Prevents deletion if task is running. Ensures all related executions
        are deleted via cascade.

        Requirements: 2.4, 2.5, 7.2
        """
        # Check if task is running
        if instance.status == TaskStatus.RUNNING:
            raise ValidationError("Cannot delete running task. Stop it first.")

        # Delete task (related executions will be deleted via cascade)
        instance.delete()


class BacktestTaskCopyView(APIView):
    """
    Copy a backtest task with a new name.

    POST: Create a copy of the task with all properties except name and ID

    Requirements: 2.5, 2.6, 4.1, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Copy backtest task.

        Request body:
        - new_name: Name for the copied task (required)
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get new name from request
        new_name = request.data.get("new_name")
        if not new_name:
            return Response(
                {"error": "new_name is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Copy the task
        try:
            new_task = task.copy(new_name)
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Serialize and return
        serializer = BacktestTaskSerializer(new_task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class BacktestTaskStartView(APIView):
    """
    Start a backtest task.

    POST: Start the backtest execution

    Requirements: 4.1, 4.2, 6.1, 6.2, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Start backtest task execution.

        Creates a new TaskExecution and queues the backtest for processing.
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate configuration before starting
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Start the task
        try:
            task.start()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Queue the backtest task for execution
        from .tasks import run_backtest_task_v2

        run_backtest_task_v2.delay(task.pk)

        # Return success response
        return Response(
            {
                "message": "Backtest task started successfully",
                "task_id": task.pk,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BacktestTaskStopView(APIView):
    """
    Stop a running backtest task.

    POST: Stop the backtest execution

    Requirements: 2.1, 2.3, 3.1, 3.2, 4.3, 6.3, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Stop backtest task execution.

        Sets cancellation flag via TaskLockManager, performs optimistic status update,
        and broadcasts WebSocket notification. Returns immediately without waiting
        for task to stop.

        Requirements: 2.1, 2.3, 3.1, 3.2
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if task is running
        if task.status != TaskStatus.RUNNING:
            return Response(
                {"error": "Task is not running"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Set cancellation flag via TaskLockManager
        from .services.task_lock_manager import TaskLockManager

        lock_manager = TaskLockManager()
        lock_manager.set_cancellation_flag("backtest", task_id)

        # Optimistic status update
        task.status = TaskStatus.STOPPED
        task.save(update_fields=["status", "updated_at"])

        # Get latest execution for notification
        latest_execution = task.get_latest_execution()
        execution_id = latest_execution.pk if latest_execution else None

        # Broadcast WebSocket notification
        from .services.notifications import send_task_status_notification

        # User is authenticated, so user.pk is guaranteed to be not None
        assert request.user.pk is not None
        send_task_status_notification(
            user_id=request.user.pk,
            task_id=task.pk,
            task_name=task.name,
            task_type="backtest",
            status=TaskStatus.STOPPED,
            execution_id=execution_id,
        )

        # Return immediate response
        return Response(
            {
                "id": task.pk,
                "status": task.status,
                "message": "Task stop initiated",
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskRerunView(APIView):
    """
    Rerun a backtest task from the beginning.

    POST: Create a new execution with the same configuration

    Requirements: 4.4, 4.5, 6.1, 6.2, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Rerun backtest task.

        Creates a new execution with the same configuration. Task can be in any
        state (completed, failed, stopped) to be rerun.
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Validate configuration before rerunning
        is_valid, error_message = task.validate_configuration()
        if not is_valid:
            return Response(
                {"error": f"Configuration validation failed: {error_message}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Rerun the task
        try:
            task.rerun()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Queue the backtest task for execution
        from .tasks import run_backtest_task_v2

        run_backtest_task_v2.delay(task.pk)

        # Return success response
        return Response(
            {
                "message": "Backtest task rerun started successfully",
                "task_id": task.pk,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BacktestTaskStatusView(APIView):
    """
    Get current status of a backtest task.

    GET: Return current status, progress, and execution details

    Requirements: 3.1, 3.6
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get current task status and execution details.

        Used by frontend for polling fallback when WebSocket connection fails.
        Returns current status, progress percentage, and latest execution details.
        Also detects and auto-completes stale running tasks.

        Requirements: 3.1, 3.6
        """
        from trading.services.task_lock_manager import TaskLockManager

        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest execution
        latest_execution = task.get_latest_execution()
        lock_manager = TaskLockManager()

        # Check for stale running tasks and auto-complete them
        if task.status == TaskStatus.RUNNING and latest_execution:
            lock_info = lock_manager.get_lock_info("backtest", task_id)

            # Task is "running" but no lock exists or lock is stale
            is_stale = lock_info is None or lock_info.get("is_stale", False)

            # Check if latest execution is already completed (stale task)
            # BUT only if the execution status is also completed (not just progress 100%)
            execution_completed = latest_execution.status in [
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
                TaskStatus.STOPPED,
            ]

            # Only auto-complete if execution is done AND (no lock OR stale lock)
            if execution_completed and is_stale:
                # Auto-complete stale task
                logger.warning(
                    "Detected stale running task %d (execution_status=%s, is_stale=%s), "
                    "auto-completing",
                    task_id,
                    latest_execution.status,
                    is_stale,
                )

                # Clean up any stale locks
                if lock_info:
                    lock_manager.release_lock("backtest", task_id)

                # Update task status to match execution status
                task.status = latest_execution.status
                task.save(update_fields=["status", "updated_at"])

                # Refresh to get updated values
                task.refresh_from_db()

        # When task is stopped but execution is still running, update execution immediately
        # The task status being STOPPED is authoritative - user requested stop
        if (
            task.status == TaskStatus.STOPPED
            and latest_execution
            and latest_execution.status == TaskStatus.RUNNING
        ):
            logger.info(
                "Task %d is stopped but execution still running, updating execution status",
                task_id,
            )

            # Clean up any locks
            lock_info = lock_manager.get_lock_info("backtest", task_id)
            if lock_info:
                lock_manager.release_lock("backtest", task_id)

            # Update execution to stopped
            latest_execution.status = TaskStatus.STOPPED
            latest_execution.completed_at = timezone.now()
            latest_execution.save(update_fields=["status", "completed_at"])
            latest_execution.refresh_from_db()

        # Determine the correct progress to report
        # If task is RUNNING but latest execution is completed, a new execution is pending
        # In this case, report progress as 0 (pending new execution)
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

        # Build response data
        response_data = {
            "task_id": task.pk,
            "task_type": "backtest",
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

        return Response(response_data, status=status.HTTP_200_OK)


class BacktestTaskExecutionsView(APIView):
    """
    Get execution history for a backtest task.

    GET: List all executions for the task

    Requirements: 4.6, 6.7, 7.3, 7.4, 7.5, 8.4
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get execution history for backtest task.

        Returns all executions ordered by execution number (most recent first).
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get execution history
        executions = task.get_execution_history()

        # Serialize and return
        serializer = TaskExecutionSerializer(executions, many=True)
        return Response(
            {
                "count": executions.count(),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class BacktestTaskExportView(APIView):
    """
    Export backtest results as JSON.

    GET: Export complete backtest results including metrics, trades, and strategy events

    Requirements: 6.7, 8.4
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """
        Export backtest results as JSON.

        Returns complete backtest data including:
        - Task configuration
        - Performance metrics (realized/unrealized P&L)
        - Trade log with floor strategy details
        - Strategy events
        - Equity curve
        """
        # Get the task
        try:
            task = BacktestTask.objects.select_related("config", "user").get(
                id=task_id, user=request.user.pk
            )
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest execution with metrics
        latest_execution = task.get_latest_execution()
        if not latest_execution:
            return Response(
                {"error": "No execution found for this task"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get metrics
        metrics = None
        if hasattr(latest_execution, "metrics") and latest_execution.metrics:
            metrics_obj = latest_execution.metrics
            metrics = {
                "total_return": str(metrics_obj.total_return),
                "total_pnl": str(metrics_obj.total_pnl),
                "realized_pnl": str(getattr(metrics_obj, "realized_pnl", metrics_obj.total_pnl)),
                "unrealized_pnl": str(getattr(metrics_obj, "unrealized_pnl", "0.00")),
                "total_trades": metrics_obj.total_trades,
                "winning_trades": metrics_obj.winning_trades,
                "losing_trades": metrics_obj.losing_trades,
                "win_rate": str(metrics_obj.win_rate),
                "max_drawdown": str(metrics_obj.max_drawdown),
                "sharpe_ratio": str(metrics_obj.sharpe_ratio) if metrics_obj.sharpe_ratio else None,
                "profit_factor": (
                    str(metrics_obj.profit_factor) if metrics_obj.profit_factor else None
                ),
                "average_win": str(metrics_obj.average_win) if metrics_obj.average_win else None,
                "average_loss": str(metrics_obj.average_loss) if metrics_obj.average_loss else None,
                "trade_log": metrics_obj.trade_log or [],
                "strategy_events": metrics_obj.strategy_events or [],
            }

        # Build export data
        strategy_type = task.config.strategy_type if task.config else None
        export_data = {
            "task": {
                "id": task.pk,
                "name": task.name,
                "description": task.description,
                "strategy_type": strategy_type,
                "instrument": task.instrument,
                "start_time": task.start_time.isoformat(),
                "end_time": task.end_time.isoformat(),
                "status": task.status,
            },
            "configuration": {
                "id": task.config.pk if task.config else None,
                "name": task.config.name if task.config else None,
                "strategy_type": strategy_type,
                "parameters": task.config.parameters if task.config else {},
            },
            "execution": {
                "id": latest_execution.pk,
                "execution_number": latest_execution.execution_number,
                "status": latest_execution.status,
                "started_at": (
                    latest_execution.started_at.isoformat() if latest_execution.started_at else None
                ),
                "completed_at": (
                    latest_execution.completed_at.isoformat()
                    if latest_execution.completed_at
                    else None
                ),
                "logs": latest_execution.logs or [],
            },
            "metrics": metrics,
            "exported_at": timezone.now().isoformat(),
        }

        # Return as downloadable JSON response
        return Response(export_data, status=status.HTTP_200_OK)


class BacktestTaskLogsView(APIView):
    """
    Get logs for a backtest task with pagination and filtering.

    GET: Return paginated log entries from TaskExecution.logs JSONField

    Requirements: 1.4, 6.4, 6.5
    """

    permission_classes = [IsAuthenticated]

    def _build_pagination_url(
        self,
        task_id: int,
        offset: int,
        limit: int,
        execution_id: str | None,
        level: str | None,
    ) -> str:
        """Build pagination URL with query parameters."""
        url = f"/api/backtest-tasks/{task_id}/logs/?offset={offset}&limit={limit}"
        if execution_id:
            url += f"&execution_id={execution_id}"
        if level:
            url += f"&level={level}"
        return url

    def _collect_logs(
        self, executions_query: QuerySet, level: str | None
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
        - limit: Number of logs to return (default: 100, max: 1000)
        - offset: Pagination offset (default: 0)

        Returns:
            Paginated log entries with execution_number included
        """
        # Verify task exists and user has access
        try:
            BacktestTask.objects.get(id=task_id, user=request.user.pk)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get and validate query parameters
        execution_id = request.query_params.get("execution_id")
        level = request.query_params.get("level")
        try:
            limit = min(int(request.query_params.get("limit", 100)), 1000)
            offset = int(request.query_params.get("offset", 0))
        except ValueError:
            return Response(
                {"error": "Invalid limit or offset value"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Import and query executions
        from .execution_models import TaskExecution

        executions_query = TaskExecution.objects.filter(
            task_type="backtest",
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

        # Paginate results
        total_count = len(all_logs)
        paginated_logs = all_logs[offset : offset + limit]

        # Build pagination URLs
        next_url = (
            self._build_pagination_url(task_id, offset + limit, limit, execution_id, level)
            if offset + limit < total_count
            else None
        )
        previous_url = (
            self._build_pagination_url(task_id, max(0, offset - limit), limit, execution_id, level)
            if offset > 0
            else None
        )

        # Return paginated response
        return Response(
            {
                "count": total_count,
                "next": next_url,
                "previous": previous_url,
                "results": paginated_logs,
            },
            status=status.HTTP_200_OK,
        )
