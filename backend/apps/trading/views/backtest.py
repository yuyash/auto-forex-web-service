"""Backtest task API views."""

import logging
from logging import Logger
from typing import Any

from django.db.models import Q, QuerySet
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.trading.enums import LogLevel, TaskStatus
from apps.trading.models import BacktestTask
from apps.trading.models.logs import TaskLog
from apps.trading.serializers import (
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.task import (
    BacktestTaskSerializer,
    TaskLogSerializer,
)
from apps.trading.tasks.service import TaskService

logger: Logger = logging.getLogger(name=__name__)


@extend_schema_view(
    list=extend_schema(
        parameters=[
            OpenApiParameter(
                name="status", type=str, required=False, description="Filter by task status"
            ),
            OpenApiParameter(
                name="config_id", type=str, required=False, description="Filter by configuration ID"
            ),
            OpenApiParameter(
                name="search", type=str, required=False, description="Search in name or description"
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                required=False,
                description="Ordering field (e.g. -created_at)",
            ),
            OpenApiParameter(name="page", type=int, required=False, description="Page number"),
            OpenApiParameter(
                name="page_size", type=int, required=False, description="Number of results per page"
            ),
        ],
    ),
)
class BacktestTaskViewSet(ModelViewSet):
    """
    ViewSet for BacktestTask operations with task-centric API.

    Provides CRUD operations and task lifecycle management including:
    - submit: Submit task for execution
    - stop: Stop running task
    - pause: Pause running task
    - restart: Restart task from beginning
    - resume: Resume paused task
    - logs: Retrieve task logs with pagination
    - events: Retrieve task events
    - trades: Retrieve trade history
    """

    permission_classes = [IsAuthenticated]
    serializer_class = BacktestTaskSerializer
    lookup_field = "pk"

    def get_serializer_class(self):
        """Use BacktestTaskCreateSerializer for create/update actions."""
        if self.action in ("create", "update", "partial_update"):
            from apps.trading.serializers.backtest import BacktestTaskCreateSerializer

            return BacktestTaskCreateSerializer
        return BacktestTaskSerializer

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskService()

    def get_queryset(self) -> QuerySet[BacktestTask]:
        """Get backtest tasks for the authenticated user with filtering."""
        assert isinstance(self.request, Request)
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
        from django.db import IntegrityError
        from rest_framework.exceptions import ValidationError

        try:
            serializer.save(user=self.request.user)
        except IntegrityError as e:
            logger.error(f"IntegrityError creating backtest task: {e}")
            if "unique_user_backtest_task_name" in str(e):
                raise ValidationError({"name": ["A backtest task with this name already exists."]})
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating backtest task: {type(e).__name__}: {e}")
            raise

    @extend_schema(
        summary="Submit task for execution",
        description="Submit a pending task to Celery for execution. Only tasks in CREATED status can be submitted. Use restart or resume for STOPPED tasks.",
        responses={200: BacktestTaskSerializer, 400: dict, 500: dict},
    )
    @action(detail=True, methods=["post"])
    def start(self, request: Request, pk: int | None = None) -> Response:
        """Submit task for execution."""
        task = self.get_object()

        logger.info(
            f"[API:START] Request received - task_id={task.pk}, user_id={request.user.pk}, "
            f"current_status={task.status}, instrument={task.instrument}, "
            f"start_time={task.start_time}, end_time={task.end_time}"
        )

        # Validate task status - only CREATED tasks can be submitted
        if task.status != TaskStatus.CREATED:
            logger.warning(
                f"[API:START] INVALID_STATUS - task_id={task.pk}, status={task.status}, "
                f"expected=CREATED"
            )

            # Provide helpful error message for STOPPED tasks
            if task.status == TaskStatus.STOPPED:
                logger.info(
                    f"[API:START] Task is STOPPED, suggesting restart/resume - task_id={task.pk}"
                )
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
            logger.info(f"[API:START] Calling TaskService.start_task - task_id={task.pk}")
            task = self.task_service.start_task(task)
            serializer = self.get_serializer(task)
            logger.info(
                f"[API:START] SUCCESS - task_id={task.pk}, celery_task_id={task.celery_task_id}, "
                f"new_status={task.status}"
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Configuration or validation errors
            logger.warning(f"[API:START] VALIDATION_FAILED - task_id={task.pk}, error={str(e)}")
            return Response(
                {"error": "Validation error", "detail": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RuntimeError as e:
            # Celery connection or submission errors
            logger.error(
                f"[API:START] SUBMISSION_FAILED - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to submit task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"[API:START] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
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
            f"[API:STOP] Request received - task_id={task.pk}, user_id={request.user.pk}, "
            f"current_status={task.status}, celery_task_id={task.celery_task_id}"
        )

        try:
            # Use TaskService to stop the task
            logger.info(f"[API:STOP] Calling TaskService.stop_task - task_id={task.pk}")
            success = self.task_service.stop_task(task.pk)

            if success:
                logger.info(f"[API:STOP] SUCCESS - Stop request initiated for task_id={task.pk}")

                return Response(
                    {
                        "message": "Stop request submitted",
                        "task_id": task.pk,
                        "status": "stopping",
                    },
                    status=status.HTTP_202_ACCEPTED,
                )
            else:
                logger.error(
                    f"[API:STOP] FAILED - TaskService returned False for task_id={task.pk}"
                )
                return Response(
                    {"error": "Failed to initiate stop"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except ValueError as e:
            # Task not found or not in stoppable state
            logger.warning(f"[API:STOP] VALIDATION_FAILED - task_id={task.pk}, error={str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            # Unexpected errors
            logger.error(
                f"[API:STOP] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
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

        logger.info(
            f"[API:PAUSE] Request received - task_id={task.pk}, user_id={request.user.pk}, "
            f"current_status={task.status}"
        )

        if task.status != TaskStatus.RUNNING:
            logger.warning(
                f"[API:PAUSE] INVALID_STATUS - task_id={task.pk}, status={task.status}, "
                f"expected=RUNNING"
            )
            return Response(
                {"error": "Task must be running to pause"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Use TaskService to pause the task
            logger.info(f"[API:PAUSE] Calling TaskService.pause_task - task_id={task.pk}")
            success = self.task_service.pause_task(task.pk)
            if success:
                logger.info(f"[API:PAUSE] SUCCESS - task_id={task.pk}")
                serializer = self.get_serializer(task)
                return Response({"results": serializer.data})
            else:
                logger.error(
                    f"[API:PAUSE] FAILED - TaskService returned False for task_id={task.pk}"
                )
                return Response(
                    {"error": "Failed to pause task"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except Exception as e:
            logger.error(
                f"[API:PAUSE] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
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
            f"[API:RESTART] Request received - task_id={task.pk}, user_id={request.user.pk}, "
            f"current_status={task.status}, celery_task_id={task.celery_task_id}"
        )

        try:
            # Use TaskService to restart and resubmit
            logger.info(f"[API:RESTART] Calling TaskService.restart_task for task_id={task.pk}")
            task = self.task_service.restart_task(task.pk)
            serializer = self.get_serializer(task)
            logger.info(
                f"[API:RESTART] SUCCESS - task_id={task.pk}, new_status={task.status}, "
                f"new_celery_task_id={task.celery_task_id}"
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Task not found, retry limit exceeded, or invalid state
            error_msg = str(e)
            logger.warning(
                f"[API:RESTART] VALIDATION_FAILED - task_id={task.pk}, "
                f"current_status={task.status}, error={error_msg}"
            )
            return Response(
                {"error": "Validation error", "detail": error_msg},
                status=status.HTTP_400_BAD_REQUEST,
            )

        except RuntimeError as e:
            # Celery submission errors
            logger.error(
                f"[API:RESTART] SUBMISSION_FAILED - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to restart task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"[API:RESTART] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
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
            f"[API:RESUME] Request received - task_id={task.pk}, user_id={request.user.pk}, "
            f"current_status={task.status}"
        )

        if task.status != TaskStatus.PAUSED:
            logger.warning(
                f"[API:RESUME] INVALID_STATUS - task_id={task.pk}, status={task.status}, "
                f"expected=PAUSED"
            )
            return Response(
                {"error": "Task must be paused to resume"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Use TaskService to resume and resubmit
            logger.info(f"[API:RESUME] Calling TaskService.resume_task - task_id={task.pk}")
            task = self.task_service.resume_task(task.pk)
            serializer = self.get_serializer(task)
            logger.info(
                f"[API:RESUME] SUCCESS - task_id={task.pk}, new_celery_task_id={task.celery_task_id}"
            )
            return Response({"results": serializer.data})

        except ValueError as e:
            # Task not found or invalid state
            error_msg = str(e)
            if "does not exist" in error_msg:
                logger.error(f"[API:RESUME] TASK_NOT_FOUND - task_id={task.pk}, error={error_msg}")
                return Response(
                    {"error": "Task not found", "detail": error_msg},
                    status=status.HTTP_404_NOT_FOUND,
                )
            else:
                logger.warning(
                    f"[API:RESUME] VALIDATION_FAILED - task_id={task.pk}, error={error_msg}"
                )
                return Response(
                    {"error": "Validation error", "detail": error_msg},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except RuntimeError as e:
            # Celery submission errors
            logger.error(
                f"[API:RESUME] SUBMISSION_FAILED - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Failed to resume task", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            # Unexpected errors
            logger.error(
                f"[API:RESUME] UNEXPECTED_ERROR - task_id={task.pk}, error={str(e)}",
                exc_info=True,
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @extend_schema(
        summary="Get task logs",
        description="Retrieve task execution logs for the latest execution with pagination and filtering",
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
            OpenApiParameter(
                name="celery_task_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Optional explicit execution ID. If omitted, current task celery_task_id is used.",
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
        celery_task_id = request.query_params.get("celery_task_id") or task.celery_task_id

        # Guardrails for predictable paging
        limit = max(1, min(limit, 1000))
        offset = max(0, offset)

        try:
            logs_queryset = TaskLog.objects.filter(
                task_type="backtest",
                task_id=task.pk,
            )

            # Default to latest execution only (no historical logs)
            if celery_task_id:
                logs_queryset = logs_queryset.filter(celery_task_id=celery_task_id)
            else:
                logs_queryset = logs_queryset.none()

            if level:
                logs_queryset = logs_queryset.filter(level=level)

            total = logs_queryset.count()
            logs = logs_queryset.order_by("-timestamp")[offset : offset + limit]
            serializer = TaskLogSerializer(logs, many=True)

            next_offset = offset + limit if (offset + limit) < total else None
            prev_offset = max(0, offset - limit) if offset > 0 else None

            return Response(
                {
                    "count": total,
                    "next": next_offset,
                    "previous": prev_offset,
                    "results": serializer.data,
                }
            )
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

        queryset = TradingEvent.objects.filter(task_type="backtest", task_id=task.pk).order_by(
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

        # Return paginated format expected by frontend
        return Response(
            {"count": queryset.count(), "next": None, "previous": None, "results": serializer.data}
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
            OpenApiParameter(
                name="celery_task_id",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Execution ID. Defaults to current task celery_task_id.",
            ),
        ],
        responses={200: TradeSerializer(many=True)},
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: str | None = None) -> Response:
        """Get task trades from database."""
        from apps.trading.models.trades import Trade

        task = self.get_object()
        direction = (request.query_params.get("direction") or "").lower()
        celery_task_id = request.query_params.get("celery_task_id") or task.celery_task_id

        # Query trades from database
        queryset = Trade.objects.filter(
            task_type="backtest",
            task_id=task.pk,
        ).order_by("timestamp")

        # Default behavior: only show latest/current execution run.
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
        else:
            queryset = queryset.none()

        # Filter by direction if specified
        if direction:
            if direction == "buy":
                queryset = queryset.filter(direction="long")
            elif direction == "sell":
                queryset = queryset.filter(direction="short")
            else:
                queryset = queryset.filter(direction=direction)

        trades = queryset.values(
            "direction",
            "units",
            "instrument",
            "price",
            "execution_method",
            "layer_index",
            "pnl",
            "timestamp",
        )

        normalized_trades = []
        for trade in trades:
            side = str(trade["direction"]).lower()
            trade["direction"] = "buy" if side == "long" else "sell" if side == "short" else side
            normalized_trades.append(trade)

        serializer = TradeSerializer(normalized_trades, many=True)

        # Return paginated format expected by frontend
        return Response(
            {"count": queryset.count(), "next": None, "previous": None, "results": serializer.data}
        )
