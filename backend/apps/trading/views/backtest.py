"""Backtest task API views."""

import logging
from logging import Logger

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask
from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)
from apps.trading.tasks.service import (
    TaskSubmissionError,
    TaskValidationError,
)
from apps.trading.views.task_base import TaskViewSetBase

logger: Logger = logging.getLogger(name=__name__)


@extend_schema_view(
    list=extend_schema(tags=["Trading"]),
    create=extend_schema(tags=["Trading"], responses={201: BacktestTaskSerializer}),
    retrieve=extend_schema(tags=["Trading"], responses={200: BacktestTaskSerializer}),
    update=extend_schema(tags=["Trading"], responses={200: BacktestTaskSerializer}),
    partial_update=extend_schema(tags=["Trading"], responses={200: BacktestTaskSerializer}),
    destroy=extend_schema(tags=["Trading"]),
    start=extend_schema(
        operation_id="backtest_tasks_start",
        tags=["Trading"],
        responses={200: BacktestTaskSerializer},
    ),
    stop=extend_schema(
        operation_id="backtest_tasks_stop",
        tags=["Trading"],
        responses={
            202: inline_serializer(
                "BacktestTaskStopResponse",
                fields={
                    "message": serializers.CharField(),
                    "task_id": serializers.CharField(),
                    "status": serializers.CharField(),
                },
            )
        },
    ),
    pause=extend_schema(
        operation_id="backtest_tasks_pause",
        tags=["Trading"],
        responses={200: BacktestTaskSerializer},
    ),
    resume=extend_schema(
        operation_id="backtest_tasks_resume",
        tags=["Trading"],
        responses={200: BacktestTaskSerializer},
    ),
    restart=extend_schema(
        operation_id="backtest_tasks_restart",
        tags=["Trading"],
        responses={200: BacktestTaskSerializer},
    ),
)
@extend_schema(tags=["Trading"])
class BacktestTaskViewSet(TaskViewSetBase):
    """ViewSet for BacktestTask operations with task-centric API."""

    queryset = BacktestTask.objects.none()
    serializer_class = BacktestTaskSerializer
    detail_serializer_class = BacktestTaskSerializer
    list_serializer_class = BacktestTaskListSerializer
    create_serializer_class = BacktestTaskCreateSerializer
    task_model_name = "BacktestTask"
    lookup_field = "pk"
    task_type_label = "backtest"
    select_related_fields = ("config", "user")
    filter_field_map = {
        "status": "status",
        "config_id": "config_id",
    }

    def perform_create(self, serializer: BacktestTaskCreateSerializer) -> None:
        """Set the user when creating a task."""
        try:
            serializer.save(user=self.request.user)
        except IntegrityError as exc:
            logger.error("IntegrityError creating backtest task: %s", exc)
            if "unique_user_backtest_task_name" in str(exc):
                raise ValidationError(
                    {"name": ["A backtest task with this name already exists."]}
                ) from exc
            raise

    @action(detail=True, methods=["post"])
    def start(self, request: Request, pk: str | None = None) -> Response:
        """Submit task for execution."""
        task = self.get_object()
        if task.status != TaskStatus.CREATED:
            if task.status == TaskStatus.STOPPED:
                return Response(
                    {
                        "error": "Cannot submit a stopped task",
                        "detail": (
                            "Use 'restart' to clear execution data and start fresh, "
                            "or 'resume' to continue from where it stopped"
                        ),
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
            return Response(self._serialize_detail(task))
        except TaskValidationError as exc:
            return Response(
                {"error": "Validation error", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TaskSubmissionError:
            logger.exception("Failed to submit backtest task", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to submit task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unexpected backtest start failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: str | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()
        try:
            success = self.task_service.stop_task(task.pk)
        except ValueError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception("Unexpected backtest stop failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to stop task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not success:
            return Response(
                {"error": "Failed to stop task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Task stop requested",
                "task_id": str(task.pk),
                "status": TaskStatus.STOPPING,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk: str | None = None) -> Response:
        """Pause a running task."""
        task = self.get_object()
        if task.status not in {TaskStatus.RUNNING, TaskStatus.STARTING}:
            return Response(
                {"error": f"Task cannot be paused from {task.status} state"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            success = self.task_service.pause_task(task.pk)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected backtest pause failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to pause task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not success:
            return Response(
                {"error": "Failed to pause task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        task.refresh_from_db()
        return Response(self._serialize_detail(task))

    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: str | None = None) -> Response:
        """Resume a paused task."""
        task = self.get_object()
        try:
            resumed = self.task_service.resume_task(task.pk)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected backtest resume failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to resume task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self._serialize_detail(resumed))

    @action(detail=True, methods=["post"])
    def restart(self, request: Request, pk: str | None = None) -> Response:
        """Restart a task from the beginning."""
        task = self.get_object()
        try:
            restarted = self.task_service.restart_task(task.pk)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected backtest restart failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to restart task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self._serialize_detail(restarted))
