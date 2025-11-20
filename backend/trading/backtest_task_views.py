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

from typing import Type

from django.db.models import Q, QuerySet

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
        queryset = BacktestTask.objects.filter(user=self.request.user.id).select_related(
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
        return BacktestTask.objects.filter(user=self.request.user.id).select_related(
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
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
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
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
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

        run_backtest_task_v2.delay(task.id)

        # Return success response
        return Response(
            {
                "message": "Backtest task started successfully",
                "task_id": task.id,
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
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
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
        execution_id = latest_execution.id if latest_execution else None

        # Broadcast WebSocket notification
        from .services.notifications import send_task_status_notification

        # User is authenticated, so user.id is guaranteed to be not None
        assert request.user.id is not None
        send_task_status_notification(
            user_id=request.user.id,
            task_id=task.id,
            task_name=task.name,
            task_type="backtest",
            status=TaskStatus.STOPPED,
            execution_id=execution_id,
        )

        # Return immediate response
        return Response(
            {
                "id": task.id,
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
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
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

        run_backtest_task_v2.delay(task.id)

        # Return success response
        return Response(
            {
                "message": "Backtest task rerun started successfully",
                "task_id": task.id,
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

        Requirements: 3.1, 3.6
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Get latest execution
        latest_execution = task.get_latest_execution()

        # Build response data
        response_data = {
            "id": task.id,
            "name": task.name,
            "status": task.status,
            "updated_at": task.updated_at.isoformat(),
        }

        # Add execution details if available
        if latest_execution:
            response_data["execution"] = {
                "id": latest_execution.id,
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
                "error_message": latest_execution.error_message,
            }
        else:
            response_data["execution"] = None

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
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
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
                        "execution_id": execution.id,
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
            BacktestTask.objects.get(id=task_id, user=request.user.id)
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
