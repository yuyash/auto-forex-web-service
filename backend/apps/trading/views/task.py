"""Task-centric API views for unified task management."""

import logging
from datetime import datetime
from logging import Logger
from typing import Any
from uuid import UUID

from django.db.models import Q, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import BacktestTasks, TradingTasks
from apps.trading.models.logs import TaskLog
from apps.trading.serializers import (
    EquityPointSerializer,
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.task import (
    BacktestTaskSerializer,
    TaskLogSerializer,
    TaskMetricSerializer,
    TradingTaskSerializer,
)
from apps.trading.services.service import TaskService, TaskServiceImpl

# Configure structured logging
logger: Logger = logging.getLogger(name=__name__)


def _validate_pagination_params(limit: int, offset: int) -> tuple[bool, str | None]:
    """Validate pagination parameters.

    Args:
        limit: Maximum number of items to return
        offset: Number of items to skip

    Returns:
        Tuple of (is_valid, error_message)
    """
    if limit < 1 or limit > 1000:
        return False, "Limit must be between 1 and 1000"
    if offset < 0:
        return False, "Offset must be non-negative"
    return True, None


def _handle_service_error(
    error: Exception, operation: str, task_id: int, logger_instance: logging.Logger
) -> Response:
    """Handle service layer errors and return appropriate HTTP response.

    Args:
        error: The exception that was raised
        operation: Description of the operation (for logging)
        task_id: ID of the task being operated on
        logger_instance: Logger instance to use

    Returns:
        Response with appropriate status code and error message
    """
    if isinstance(error, ValueError):
        error_msg = str(error)
        if "does not exist" in error_msg:
            logger_instance.error(
                f"API: Task not found for {operation}",
                extra={"task_id": task_id},
            )
            return Response(
                {"error": "Task not found", "detail": error_msg},
                status=status.HTTP_404_NOT_FOUND,
            )
        else:
            logger_instance.warning(
                f"API: {operation} validation failed",
                extra={"task_id": task_id, "error": error_msg},
            )
            return Response(
                {"error": "Validation error", "detail": error_msg},
                status=status.HTTP_400_BAD_REQUEST,
            )
    elif isinstance(error, RuntimeError):
        logger_instance.error(
            f"API: {operation} failed",
            extra={"task_id": task_id},
            exc_info=True,
        )
        return Response(
            {"error": f"Failed to {operation}", "detail": str(error)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    else:
        logger_instance.error(
            f"API: Unexpected error during {operation}",
            extra={"task_id": task_id},
            exc_info=True,
        )
        return Response(
            {"error": "Internal server error", "detail": "An unexpected error occurred"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


class BacktestTaskViewSet(ModelViewSet):
    """
    ViewSet for BacktestTask operations with task-centric API.

    Provides CRUD operations and task lifecycle management including:
    - submit: Submit task for execution
    - cancel: Cancel running task
    - restart: Restart task from beginning
    - resume: Resume cancelled task
    - logs: Retrieve task logs with pagination
    - metrics: Retrieve task metrics with filtering
    - results: Retrieve task results
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BacktestTaskSerializer
    lookup_field = "pk"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskServiceImpl()

    def get_queryset(self) -> QuerySet[BacktestTasks]:
        """Get backtest tasks for the authenticated user with filtering."""
        assert isinstance(self.request, Request)
        queryset = BacktestTasks.objects.filter(user=self.request.user.pk).select_related(
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

        # Search in name or description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer: BacktestTaskSerializer) -> None:
        """Set the user when creating a task."""
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Submit task for execution",
        description="Submit a pending task to Celery for execution. Only tasks in CREATED status can be submitted. Use restart or resume for STOPPED tasks.",
        responses={200: BacktestTaskSerializer, 400: dict, 500: dict},
    )
    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: int | None = None) -> Response:
        """Submit task for execution."""
        task = self.get_object()

        logger.info(
            "API: Submitting task",
            extra={"task_id": task.pk, "user_id": request.user.pk},
        )

        # Validate task status - only CREATED tasks can be submitted
        if task.status != TaskStatus.CREATED:
            logger.warning(
                "API: Task not in valid status to submit",
                extra={"task_id": task.pk, "status": task.status},
            )

            # Provide helpful error message for STOPPED tasks
            if task.status == TaskStatus.STOPPED:
                return Response(
                    {
                        "error": "Cannot submit a stopped task",
                        "detail": "Use 'restart' to clear execution data and start fresh, or 'resume' to continue from where it stopped",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "error": "Task must be in CREATED status to submit",
                    "detail": f"Current status: {task.status}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = self.task_service.submit_task(task)
            serializer = self.get_serializer(task)
            logger.info(
                "API: Task submitted successfully",
                extra={"task_id": task.pk, "celery_task_id": task.celery_task_id},
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Configuration or validation errors
            logger.warning(
                "API: Task submission validation failed",
                extra={"task_id": task.pk, "error": str(e)},
            )
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RuntimeError as e:
            # Celery connection or submission errors
            logger.error(
                "API: Task submission failed",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Failed to submit task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            # Unexpected errors
            logger.error(
                "API: Unexpected error submitting task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Stop running task",
        description="Stop a currently running or paused task asynchronously",
        responses={202: dict, 400: dict, 404: dict, 500: dict},
    )
    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: int | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()

        logger.info(
            "API: Stopping task asynchronously",
            extra={"task_id": task.pk, "user_id": request.user.pk},
        )

        # Validate task status
        if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            logger.warning(
                "API: Task not in stoppable state",
                extra={"task_id": task.pk, "status": task.status},
            )
            return Response(
                {
                    "error": "Task cannot be stopped",
                    "detail": f"Task is in {task.status} status",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Import and dispatch async stop task
            from apps.trading.tasks.trading import async_stop_backtest_task

            # Dispatch async task
            result = async_stop_backtest_task.apply_async(
                args=[task.pk],
                countdown=0,
            )

            logger.info(
                "API: Async stop task dispatched",
                extra={"task_id": task.pk, "celery_task_id": result.id},
            )

            return Response(
                {
                    "message": "Stop request submitted",
                    "task_id": task.pk,
                    "stop_task_id": result.id,
                    "status": "stopping",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            # Unexpected errors
            logger.error(
                "API: Unexpected error stopping task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Pause running task",
        description="Pause a running task, preserving execution state",
        responses={200: BacktestTaskSerializer, 400: dict},
    )
    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk: int | None = None) -> Response:
        """Pause running task."""
        task = self.get_object()

        if task.status != TaskStatus.RUNNING:
            return Response(
                {"error": "Task must be running to pause"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.pause()
            serializer = self.get_serializer(task)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to pause task: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Restart task from beginning",
        description="Restart a task from the beginning, clearing all execution data",
        responses={200: BacktestTaskSerializer, 400: dict, 404: dict, 500: dict},
    )
    @action(detail=True, methods=["post"])
    def restart(self, request: Request, pk: int | None = None) -> Response:
        """Restart task from beginning."""
        task = self.get_object()

        logger.info(
            "API: Restarting task",
            extra={"task_id": task.pk, "user_id": request.user.pk},
        )

        try:
            # Restart clears data and sets to CREATED
            task.restart()
            # Then submit to start execution
            task = self.task_service.submit_task(task)
            serializer = self.get_serializer(task)
            logger.info(
                "API: Task restarted and submitted successfully",
                extra={"task_id": task.pk, "retry_count": task.retry_count},
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Task not found, retry limit exceeded, or invalid state
            error_msg = str(e)
            logger.warning(
                "API: Task restart validation failed",
                extra={"task_id": task.pk, "error": error_msg},
            )
            return Response(
                {"error": "Validation error", "detail": error_msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RuntimeError as e:
            # Celery submission errors
            logger.error(
                "API: Task restart submission failed",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Failed to restart task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            # Unexpected errors
            logger.error(
                "API: Unexpected error restarting task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Resume paused task",
        description="Resume a paused task, continuing execution from where it left off",
        responses={200: BacktestTaskSerializer, 400: dict, 404: dict, 500: dict},
    )
    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: int | None = None) -> Response:
        """Resume paused task."""
        task = self.get_object()

        logger.info(
            "API: Resuming task",
            extra={"task_id": task.pk, "user_id": request.user.pk},
        )

        if task.status != TaskStatus.PAUSED:
            return Response(
                {"error": "Task must be paused to resume"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task.resume()
            # Resubmit to Celery
            task = self.task_service.submit_task(task)
            serializer = self.get_serializer(task)
            logger.info(
                "API: Task resumed successfully",
                extra={"task_id": task.pk},
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Task not found or invalid state
            error_msg = str(e)
            if "does not exist" in error_msg:
                logger.error(
                    "API: Task not found for resume",
                    extra={"task_id": task.pk},
                )
                return Response(
                    {"error": "Task not found", "detail": error_msg},
                    status=status.HTTP_404_NOT_FOUND,
                )
            else:
                logger.warning(
                    "API: Task resume validation failed",
                    extra={"task_id": task.pk, "error": error_msg},
                )
                return Response(
                    {"error": "Validation error", "detail": error_msg},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except RuntimeError as e:
            # Celery submission errors
            logger.error(
                "API: Task resume submission failed",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Failed to resume task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception:
            # Unexpected errors
            logger.error(
                "API: Unexpected error resuming task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get task logs",
        description="Retrieve task execution logs with pagination and filtering",
        parameters=[
            OpenApiParameter(
                name="level",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by log level (DEBUG, INFO, WARNING, ERROR)",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of logs to return (default: 100)",
            ),
            OpenApiParameter(
                name="offset",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of logs to skip (default: 0)",
            ),
        ],
        responses={200: TaskLogSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        """Get task logs with pagination and filtering."""
        task = self.get_object()

        level_param = request.query_params.get("level")
        level = LogLevel[level_param.upper()] if level_param else None
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))

        try:
            # Filter by current execution (celery_task_id)
            logs_queryset = TaskLog.objects.filter(
                task_type="backtest",
                task_id=task.pk,
            )

            if level:
                logs_queryset = logs_queryset.filter(level=level)

            logs = logs_queryset.order_by("-timestamp")[offset : offset + limit]
            serializer = TaskLogSerializer(logs, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve logs: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task metrics",
        description="Retrieve task execution metrics with filtering",
        parameters=[
            OpenApiParameter(
                name="metric_name",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by metric name",
            ),
            OpenApiParameter(
                name="start_time",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter metrics after this timestamp (ISO format)",
            ),
            OpenApiParameter(
                name="end_time",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter metrics before this timestamp (ISO format)",
            ),
        ],
        responses={200: TaskMetricSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def metrics(self, request: Request, pk: int | None = None) -> Response:
        """Get task metrics with filtering."""
        task = self.get_object()

        metric_name = request.query_params.get("metric_name")
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        # Parse timestamps if provided
        start_time = datetime.fromisoformat(start_time_str) if start_time_str else None
        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None

        try:
            metrics = self.task_service.get_task_metrics(
                UUID(int=task.pk),
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
            )
            serializer = TaskMetricSerializer(metrics, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve metrics: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task events",
        description="Retrieve task events with filtering",
        parameters=[
            OpenApiParameter(
                name="event_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by event type",
            ),
            OpenApiParameter(
                name="severity",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by severity (info, warning, error)",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of events to return (default: 100)",
            ),
        ],
        responses={200: TradingEventSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: int | None = None) -> Response:
        """Get task events with filtering.

        Query parameters:
        - event_type: Filter by event type
        - severity: Filter by severity level
        - celery_task_id: Filter by specific execution (optional)
        - limit: Maximum number of events to return (default: 100)
        """
        from apps.trading.models import TradingEvents
        from apps.trading.serializers import TradingEventSerializer

        task = self.get_object()

        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        celery_task_id = request.query_params.get("celery_task_id")
        limit = int(request.query_params.get("limit", 100))

        try:
            queryset = TradingEvents.objects.filter(task_type="backtest", task_id=task.pk).order_by(
                "-created_at"
            )

            if event_type:
                queryset = queryset.filter(event_type=event_type)
            if severity:
                queryset = queryset.filter(severity=severity)
            if celery_task_id:
                queryset = queryset.filter(celery_task_id=celery_task_id)

            events = queryset[:limit]
            serializer = TradingEventSerializer(events, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve events: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task trades",
        description="Retrieve trade history from task execution state",
        parameters=[
            OpenApiParameter(
                name="direction",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by trade direction (buy/sell)",
            ),
        ],
        responses={200: TradeSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: int | None = None) -> Response:
        """Get task trades from database."""
        from apps.trading.models.trades import Trades
        from apps.trading.serializers import TradeSerializer

        task = self.get_object()
        direction = request.query_params.get("direction")

        try:
            # Query trades from database
            queryset = Trades.objects.filter(
                task_type="backtest",
                task_id=task.pk,
            ).order_by("timestamp")

            # Filter by direction if specified
            if direction:
                queryset = queryset.filter(direction=direction)

            trades = queryset.values(
                "direction",
                "units",
                "instrument",
                "price",
                "execution_method",
                "pnl",
                "timestamp",
            )

            serializer = TradeSerializer(data=list(trades), many=True)
            serializer.is_valid(raise_exception=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve trades: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task equity curve",
        description="Retrieve equity curve data from task execution state",
        responses={200: EquityPointSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def equity(self, request: Request, pk: int | None = None) -> Response:
        """Get task equity curve from database."""
        from apps.trading.models.equities import Equities
        from apps.trading.serializers import EquityPointSerializer

        task = self.get_object()

        try:
            # Query equity points from database
            equity_points = (
                Equities.objects.filter(
                    task_type="backtest",
                    task_id=task.pk,
                )
                .order_by("timestamp")
                .values("timestamp", "balance")
            )

            serializer = EquityPointSerializer(data=list(equity_points), many=True)
            serializer.is_valid(raise_exception=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve equity: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )


class TradingTaskViewSet(ModelViewSet):
    """
    ViewSet for TradingTask operations with task-centric API.

    Provides CRUD operations and task lifecycle management including:
    - submit: Submit task for execution
    - cancel: Cancel running task
    - restart: Restart task from beginning
    - resume: Resume cancelled task
    - logs: Retrieve task logs with pagination
    - metrics: Retrieve task metrics with filtering
    - results: Retrieve task results
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TradingTaskSerializer
    lookup_field = "pk"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskServiceImpl()

    def get_queryset(self) -> QuerySet[TradingTasks]:
        """Get trading tasks for the authenticated user with filtering."""
        assert isinstance(self.request, Request)
        queryset = TradingTasks.objects.filter(user=self.request.user.pk).select_related(
            "config", "user", "oanda_account"
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
        account_id = self.request.query_params.get("account_id")
        if account_id:
            queryset = queryset.filter(oanda_account_id=int(account_id))

        # Search in name or description
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        # Ordering
        ordering = self.request.query_params.get("ordering", "-created_at")
        queryset = queryset.order_by(ordering)

        return queryset

    def perform_create(self, serializer: TradingTaskSerializer) -> None:
        """Set the user when creating a task."""
        serializer.save(user=self.request.user)

    @extend_schema(
        summary="Submit task for execution",
        description="Submit a pending task to Celery for execution. Only tasks in CREATED status can be submitted. Use restart or resume for STOPPED tasks.",
        responses={200: TradingTaskSerializer, 400: dict},
    )
    @action(detail=True, methods=["post"])
    def submit(self, request: Request, pk: int | None = None) -> Response:
        """Submit task for execution."""
        task = self.get_object()

        if task.status != TaskStatus.CREATED:
            # Provide helpful error message for STOPPED tasks
            if task.status == TaskStatus.STOPPED:
                return Response(
                    {
                        "error": "Cannot submit a stopped task",
                        "detail": "Use 'restart' to clear execution data and start fresh, or 'resume' to continue from where it stopped",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {
                    "error": "Task must be in CREATED status to submit",
                    "detail": f"Current status: {task.status}",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            task = self.task_service.submit_task(task)
            serializer = self.get_serializer(task)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to submit task: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Stop running task",
        description="Stop a currently running task asynchronously (graceful stop for trading tasks)",
        responses={202: dict, 400: dict},
    )
    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: int | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()

        logger.info(
            "API: Stopping trading task asynchronously",
            extra={"task_id": task.pk, "user_id": request.user.pk},
        )

        # Validate task status
        if task.status not in [TaskStatus.RUNNING, TaskStatus.PAUSED]:
            logger.warning(
                "API: Task not in stoppable state",
                extra={"task_id": task.pk, "status": task.status},
            )
            return Response(
                {
                    "error": "Task cannot be stopped",
                    "detail": f"Task is in {task.status} status",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Import and dispatch async stop task
            from apps.trading.tasks.trading import async_stop_trading_task

            # Get stop mode from request (default: graceful)
            mode = request.data.get("mode", "graceful")

            # Dispatch async task
            result = async_stop_trading_task.apply_async(  # type: ignore[attr-defined]
                args=[task.pk],
                kwargs={"mode": mode},
                countdown=0,
            )

            logger.info(
                "API: Async stop task dispatched",
                extra={"task_id": task.pk, "celery_task_id": result.id, "mode": mode},
            )

            return Response(
                {
                    "message": "Stop request submitted (graceful stop)",
                    "task_id": task.pk,
                    "stop_task_id": result.id,
                    "mode": mode,
                    "status": "stopping",
                },
                status=status.HTTP_202_ACCEPTED,
            )

        except Exception:
            logger.error(
                "API: Unexpected error stopping task",
                extra={"task_id": task.pk},
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Restart task from beginning",
        description="Restart a task from the beginning, clearing all execution data",
        responses={200: TradingTaskSerializer, 400: dict},
    )
    @action(detail=True, methods=["post"])
    def restart(self, request: Request, pk: int | None = None) -> Response:
        """Restart task from beginning."""
        task = self.get_object()

        try:
            task = self.task_service.restart_task(UUID(int=task.pk))
            serializer = self.get_serializer(task)
            return Response({"results": serializer.data})
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to restart task: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Resume cancelled task",
        description="Resume a cancelled task, preserving execution context",
        responses={200: TradingTaskSerializer, 400: dict},
    )
    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: int | None = None) -> Response:
        """Resume cancelled task."""
        task = self.get_object()

        try:
            task = self.task_service.resume_task(UUID(int=task.pk))
            serializer = self.get_serializer(task)
            return Response({"results": serializer.data})
        except ValueError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to resume task: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task logs",
        description="Retrieve task execution logs with pagination and filtering",
        parameters=[
            OpenApiParameter(
                name="level",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by log level (DEBUG, INFO, WARNING, ERROR)",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of logs to return (default: 100)",
            ),
            OpenApiParameter(
                name="offset",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Number of logs to skip (default: 0)",
            ),
        ],
        responses={200: TaskLogSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        """Get task logs with pagination and filtering."""
        task = self.get_object()

        level_param = request.query_params.get("level")
        level = LogLevel[level_param.upper()] if level_param else None
        limit = int(request.query_params.get("limit", 100))
        offset = int(request.query_params.get("offset", 0))

        try:
            # Filter by current execution (celery_task_id)
            logs_queryset = TaskLog.objects.filter(
                task_type="backtest",
                task_id=task.pk,
            )

            if level:
                logs_queryset = logs_queryset.filter(level=level)

            logs = logs_queryset.order_by("-timestamp")[offset : offset + limit]
            serializer = TaskLogSerializer(logs, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve logs: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task metrics",
        description="Retrieve task execution metrics with filtering",
        parameters=[
            OpenApiParameter(
                name="metric_name",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by metric name",
            ),
            OpenApiParameter(
                name="start_time",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter metrics after this timestamp (ISO format)",
            ),
            OpenApiParameter(
                name="end_time",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter metrics before this timestamp (ISO format)",
            ),
        ],
        responses={200: TaskMetricSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def metrics(self, request: Request, pk: int | None = None) -> Response:
        """Get task metrics with filtering."""
        task = self.get_object()

        metric_name = request.query_params.get("metric_name")
        start_time_str = request.query_params.get("start_time")
        end_time_str = request.query_params.get("end_time")

        # Parse timestamps if provided
        start_time = datetime.fromisoformat(start_time_str) if start_time_str else None
        end_time = datetime.fromisoformat(end_time_str) if end_time_str else None

        try:
            metrics = self.task_service.get_task_metrics(
                UUID(int=task.pk),
                metric_name=metric_name,
                start_time=start_time,
                end_time=end_time,
            )
            serializer = TaskMetricSerializer(metrics, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve metrics: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task events",
        description="Retrieve task events with filtering",
        parameters=[
            OpenApiParameter(
                name="event_type",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by event type",
            ),
            OpenApiParameter(
                name="severity",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by severity (info, warning, error)",
            ),
            OpenApiParameter(
                name="limit",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Maximum number of events to return (default: 100)",
            ),
        ],
        responses={200: TradingEventSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: int | None = None) -> Response:
        """Get task events with filtering.

        Query parameters:
        - event_type: Filter by event type
        - severity: Filter by severity level
        - celery_task_id: Filter by specific execution (optional)
        - limit: Maximum number of events to return (default: 100)
        """
        from apps.trading.models import TradingEvents
        from apps.trading.serializers import TradingEventSerializer

        task = self.get_object()

        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        celery_task_id = request.query_params.get("celery_task_id")
        limit = int(request.query_params.get("limit", 100))

        try:
            queryset = TradingEvents.objects.filter(task_type="trading", task_id=task.pk).order_by(
                "-created_at"
            )

            if event_type:
                queryset = queryset.filter(event_type=event_type)
            if severity:
                queryset = queryset.filter(severity=severity)
            if celery_task_id:
                queryset = queryset.filter(celery_task_id=celery_task_id)

            events = queryset[:limit]
            serializer = TradingEventSerializer(events, many=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve events: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task trades",
        description="Retrieve trade history from task execution state",
        parameters=[
            OpenApiParameter(
                name="direction",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Filter by trade direction (buy/sell)",
            ),
        ],
        responses={200: TradeSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: int | None = None) -> Response:
        """Get task trades from database."""
        from apps.trading.models.trades import Trades
        from apps.trading.serializers import TradeSerializer

        task = self.get_object()
        direction = request.query_params.get("direction")

        try:
            # Query trades from database
            queryset = Trades.objects.filter(
                task_type="backtest",
                task_id=task.pk,
            ).order_by("timestamp")

            # Filter by direction if specified
            if direction:
                queryset = queryset.filter(direction=direction)

            trades = queryset.values(
                "direction",
                "units",
                "instrument",
                "price",
                "execution_method",
                "pnl",
                "timestamp",
            )

            serializer = TradeSerializer(data=list(trades), many=True)
            serializer.is_valid(raise_exception=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve trades: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        summary="Get task equity curve",
        description="Retrieve equity curve data from task execution state",
        responses={200: EquityPointSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def equity(self, request: Request, pk: int | None = None) -> Response:
        """Get task equity curve from database."""
        from apps.trading.models.equities import Equities
        from apps.trading.serializers import EquityPointSerializer

        task = self.get_object()

        try:
            # Query equity points from database
            equity_points = (
                Equities.objects.filter(
                    task_type="backtest",
                    task_id=task.pk,
                )
                .order_by("timestamp")
                .values("timestamp", "balance")
            )

            serializer = EquityPointSerializer(data=list(equity_points), many=True)
            serializer.is_valid(raise_exception=True)
            return Response({"results": serializer.data})
        except Exception as e:
            return Response(
                {"error": f"Failed to retrieve equity: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
