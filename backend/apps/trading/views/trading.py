"""Trading task API views."""

import logging
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
from apps.trading.models import TradingTask
from apps.trading.models.logs import TaskLog
from apps.trading.serializers import (
    EquityPointSerializer,
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.task import (
    TaskLogSerializer,
    TradingTaskSerializer,
)
from apps.trading.tasks.service import TaskService

logger: Logger = logging.getLogger(name=__name__)


class TradingTaskViewSet(ModelViewSet):
    """
    ViewSet for TradingTask operations with task-centric API.

    Provides CRUD operations and task lifecycle management including:
    - submit: Submit task for execution
    - stop: Stop running task
    - restart: Restart task from beginning
    - resume: Resume cancelled task
    - logs: Retrieve task logs with pagination
    - events: Retrieve task events
    - trades: Retrieve trade history
    - equity: Retrieve equity curve
    """

    permission_classes = [IsAuthenticated]
    serializer_class = TradingTaskSerializer
    lookup_field = "pk"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskService()

    def get_queryset(self) -> QuerySet[TradingTask]:
        """Get trading tasks for the authenticated user with filtering."""
        assert isinstance(self.request, Request)
        queryset = TradingTask.objects.filter(user=self.request.user.pk).select_related(
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
    def start(self, request: Request, pk: int | None = None) -> Response:
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
            task = self.task_service.start_task(task)
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

        try:
            # Get stop mode from request (default: graceful)
            mode = request.data.get("mode", "graceful")

            # Use TaskService to stop the task
            success = self.task_service.stop_task(task.pk, mode=mode)

            if success:
                logger.info(
                    "API: Stop task initiated",
                    extra={"task_id": task.pk, "mode": mode},
                )

                return Response(
                    {
                        "message": "Stop request submitted (graceful stop)",
                        "task_id": task.pk,
                        "mode": mode,
                        "status": "stopping",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                return Response(
                    {"error": "Failed to initiate stop"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except ValueError as e:
            # Task not found or not in stoppable state
            logger.warning(
                "API: Cannot stop task",
                extra={"task_id": task.pk, "error": str(e)},
            )
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
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
                task_type="trading",
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
        """Get task events with filtering."""
        from apps.trading.models import TradingEvent

        task = self.get_object()

        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        celery_task_id = request.query_params.get("celery_task_id")
        limit = int(request.query_params.get("limit", 100))

        try:
            queryset = TradingEvent.objects.filter(task_type="trading", task_id=task.pk).order_by(
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
        from apps.trading.models.trades import Trade

        task = self.get_object()
        direction = request.query_params.get("direction")

        try:
            # Query trades from database
            queryset = Trade.objects.filter(
                task_type="trading",
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
    def equities(self, request: Request, pk: int | None = None) -> Response:
        """Get task equity curve from database."""
        from apps.trading.models.equities import Equity

        task = self.get_object()

        try:
            # Query equity points from database
            equity_points = (
                Equity.objects.filter(
                    task_type="trading",
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
