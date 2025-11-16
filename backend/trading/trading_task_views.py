"""
API views for TradingTask management.

This module provides REST API endpoints for:
- Creating and listing trading tasks
- Retrieving, updating, and deleting trading tasks
- Task lifecycle operations (start, stop, pause, resume, rerun)
- Task copy functionality
- Execution history retrieval

Requirements: 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2, 6.3,
6.4, 6.5, 6.6, 6.7, 8.1, 8.2, 8.3, 8.4, 8.6
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

from .enums import TaskStatus
from .serializers import TaskExecutionSerializer
from .trading_task_models import TradingTask
from .trading_task_serializers import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)


class TradingTaskListCreateView(ListCreateAPIView):
    """
    List and create trading tasks.

    GET: List all trading tasks for the authenticated user with filtering and pagination
    POST: Create a new trading task

    Requirements: 3.2, 3.3, 8.1, 8.2, 8.6
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method == "POST":
            return TradingTaskCreateSerializer
        return TradingTaskListSerializer

    def get_queryset(self) -> QuerySet:
        """
        Get trading tasks for the authenticated user with filtering.

        Query parameters:
        - status: Filter by task status
        - config_id: Filter by configuration ID
        - oanda_account_id: Filter by account ID
        - strategy_type: Filter by strategy type
        - search: Search in name or description
        - ordering: Sort field (e.g., '-created_at', 'name')
        """
        queryset = TradingTask.objects.filter(user=self.request.user.id).select_related(
            "config", "oanda_account", "user"
        )

        # Filter by status
        status_param = self.request.query_params.get("status")
        if status_param:
            queryset = queryset.filter(status=status_param)

        # Filter by config ID
        config_id = self.request.query_params.get("config_id")
        if config_id:
            queryset = queryset.filter(config_id=int(config_id))

        # Filter by account ID
        oanda_account_id = self.request.query_params.get("oanda_account_id")
        if oanda_account_id:
            queryset = queryset.filter(oanda_account_id=int(oanda_account_id))

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


class TradingTaskDetailView(RetrieveUpdateDestroyAPIView):
    """
    Retrieve, update, or delete a trading task.

    GET: Retrieve trading task details
    PUT/PATCH: Update trading task
    DELETE: Delete trading task

    Requirements: 3.2, 3.3, 3.4, 8.1, 8.2, 8.6
    """

    permission_classes = [IsAuthenticated]
    lookup_url_kwarg = "task_id"

    def get_serializer_class(self) -> Type[drf_serializers.Serializer]:
        """Return appropriate serializer based on request method."""
        if self.request.method in ["PUT", "PATCH"]:
            return TradingTaskCreateSerializer
        return TradingTaskSerializer

    def get_queryset(self) -> QuerySet:
        """Get trading tasks for the authenticated user."""
        return TradingTask.objects.filter(user=self.request.user.id).select_related(
            "config", "oanda_account", "user"
        )

    def perform_destroy(self, instance: TradingTask) -> None:
        """
        Delete trading task.

        Prevents deletion if task is running.
        """
        if instance.status == TaskStatus.RUNNING:
            raise ValidationError("Cannot delete a running task. Stop it first.")
        instance.delete()


class TradingTaskCopyView(APIView):
    """
    Copy a trading task with a new name.

    POST: Create a copy of the task with all properties except name and ID

    Requirements: 3.4, 4.1, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Copy trading task.

        Request body:
        - new_name: Name for the copied task (required)
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
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
        serializer = TradingTaskSerializer(new_task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class TradingTaskStartView(APIView):
    """
    Start a trading task.

    POST: Start the live trading execution

    Requirements: 4.1, 4.2, 6.1, 6.3, 8.3, 8.6
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Start trading task execution.

        Creates a new TaskExecution and queues the trading task for processing.
        Enforces one active task per account constraint.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
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

        # TODO: Queue the trading task for execution (will be implemented in task 6.3)
        # from .tasks import run_trading_task
        # run_trading_task.delay(task.id)

        # Return success response
        return Response(
            {
                "message": "Trading task started successfully",
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskStopView(APIView):
    """
    Stop a running trading task.

    POST: Stop the live trading execution

    Requirements: 4.3, 6.3, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Stop trading task execution.

        Transitions task to stopped state and marks current execution as stopped.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
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

        # TODO: Cancel the Celery task (will be implemented in task 6.3)
        # This would require storing the Celery task ID in TaskExecution

        return Response(
            {"message": "Trading task stopped successfully"},
            status=status.HTTP_200_OK,
        )


class TradingTaskPauseView(APIView):
    """
    Pause a running trading task.

    POST: Pause the live trading execution

    Requirements: 3.4, 4.3, 6.3, 8.3
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Pause trading task execution.

        Transitions task to paused state. Strategy stops making new trades but
        execution continues to track.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Pause the task
        try:
            task.pause()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"message": "Trading task paused successfully"},
            status=status.HTTP_200_OK,
        )


class TradingTaskResumeView(APIView):
    """
    Resume a paused trading task.

    POST: Resume the live trading execution

    Requirements: 3.4, 4.4, 6.3, 8.3, 8.6
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Resume trading task execution.

        Transitions task back to running state. Enforces one active task per account.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Resume the task
        try:
            task.resume()
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )

        return Response(
            {"message": "Trading task resumed successfully"},
            status=status.HTTP_200_OK,
        )


class TradingTaskRerunView(APIView):
    """
    Rerun a trading task from the beginning.

    POST: Create a new execution with the same configuration

    Requirements: 4.4, 4.5, 6.1, 6.3, 8.3, 8.6
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, task_id: int) -> Response:
        """
        Rerun trading task.

        Creates a new execution with the same configuration. Task can be in any
        state (stopped, failed) to be rerun, but not running or paused.
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
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

        # TODO: Queue the trading task for execution (will be implemented in task 6.3)
        # from .tasks import run_trading_task
        # run_trading_task.delay(task.id)

        # Return success response
        return Response(
            {
                "message": "Trading task rerun started successfully",
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class TradingTaskExecutionsView(APIView):
    """
    Get execution history for a trading task.

    GET: List all executions for the task

    Requirements: 4.6, 6.7, 7.3, 7.4, 7.5, 8.4
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, task_id: int) -> Response:
        """
        Get execution history for trading task.

        Returns all executions ordered by execution number (most recent first).
        """
        # Get the task
        try:
            task = TradingTask.objects.get(id=task_id, user=request.user.id)
        except TradingTask.DoesNotExist:
            return Response(
                {"error": "Trading task not found"},
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
