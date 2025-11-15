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

        Prevents deletion if task is running.
        """
        if instance.status == TaskStatus.RUNNING:
            raise ValidationError("Cannot delete a running task. Stop it first.")
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
            execution = task.start()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Queue the backtest task for execution
        from .tasks import run_backtest_task_v2

        run_backtest_task_v2.delay(task.id)

        # Serialize and return
        execution_serializer = TaskExecutionSerializer(execution)
        return Response(
            {
                "message": "Backtest task started successfully",
                "task_id": task.id,
                "execution": execution_serializer.data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class BacktestTaskStopView(APIView):
    """
    Stop a running backtest task.

    POST: Stop the backtest execution

    Requirements: 4.3, 6.3, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Stop backtest task execution.

        Transitions task to stopped state and marks current execution as stopped.
        """
        # Get the task
        try:
            task = BacktestTask.objects.get(id=task_id, user=request.user.id)
        except BacktestTask.DoesNotExist:
            return Response(
                {"error": "Backtest task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Stop the task
        try:
            task.stop()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # TODO: Cancel the Celery task (will be implemented in task 6.2)
        # This would require storing the Celery task ID in TaskExecution

        return Response(
            {"message": "Backtest task stopped successfully"},
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
            execution = task.rerun()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        # Queue the backtest task for execution
        from .tasks import run_backtest_task_v2

        run_backtest_task_v2.delay(task.id)

        # Serialize and return
        execution_serializer = TaskExecutionSerializer(execution)
        return Response(
            {
                "message": "Backtest task rerun started successfully",
                "task_id": task.id,
                "execution": execution_serializer.data,
            },
            status=status.HTTP_202_ACCEPTED,
        )


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
                "task_id": task.id,
                "task_name": task.name,
                "total_executions": executions.count(),
                "executions": serializer.data,
            },
            status=status.HTTP_200_OK,
        )
