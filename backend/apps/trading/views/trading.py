"""Trading task API views."""

import logging
from logging import Logger

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import TaskStatus
from apps.trading.models import TradingTask
from apps.trading.serializers.trading import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
)
from apps.trading.tasks.service import (
    TaskConflictError,
    TaskSubmissionError,
    TaskValidationError,
)
from apps.trading.views.task_base import TaskViewSetBase

logger: Logger = logging.getLogger(name=__name__)


class ConflictError(APIException):
    """API exception for known business conflicts."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "conflict"


@extend_schema_view(
    list=extend_schema(tags=["Trading"]),
    create=extend_schema(tags=["Trading"], responses={201: TradingTaskSerializer}),
    retrieve=extend_schema(tags=["Trading"], responses={200: TradingTaskSerializer}),
    update=extend_schema(tags=["Trading"], responses={200: TradingTaskSerializer}),
    partial_update=extend_schema(tags=["Trading"], responses={200: TradingTaskSerializer}),
    destroy=extend_schema(tags=["Trading"]),
    start=extend_schema(
        operation_id="trading_tasks_start",
        tags=["Trading"],
        responses={200: TradingTaskSerializer},
    ),
    stop=extend_schema(
        operation_id="trading_tasks_stop",
        tags=["Trading"],
        request=inline_serializer(
            "TradingTaskStopRequest",
            fields={
                "mode": serializers.CharField(
                    required=False,
                    default="graceful",
                    help_text="Stop mode. Defaults to graceful.",
                ),
            },
        ),
        responses={
            202: inline_serializer(
                "TradingTaskStopResponse",
                fields={
                    "message": serializers.CharField(),
                    "task_id": serializers.CharField(),
                    "mode": serializers.CharField(),
                    "status": serializers.CharField(),
                },
            ),
        },
    ),
    pause=extend_schema(
        operation_id="trading_tasks_pause",
        tags=["Trading"],
        responses={200: TradingTaskSerializer},
    ),
    resume=extend_schema(
        operation_id="trading_tasks_resume",
        tags=["Trading"],
        responses={200: TradingTaskSerializer},
    ),
    restart=extend_schema(
        operation_id="trading_tasks_restart",
        tags=["Trading"],
        responses={200: TradingTaskSerializer},
    ),
)
@extend_schema(tags=["Trading"])
class TradingTaskViewSet(TaskViewSetBase):
    """ViewSet for TradingTask operations with task-centric API."""

    queryset = TradingTask.objects.none()
    serializer_class = TradingTaskSerializer
    detail_serializer_class = TradingTaskSerializer
    list_serializer_class = TradingTaskListSerializer
    create_serializer_class = TradingTaskCreateSerializer
    task_model_name = "TradingTask"
    lookup_field = "pk"
    task_type_label = "trading"
    select_related_fields = ("config", "user", "oanda_account")
    filter_field_map = {
        "status": "status",
        "config_id": "config_id",
        "account_id": "oanda_account_id",
    }

    def perform_create(self, serializer: TradingTaskCreateSerializer) -> None:
        """Set the user when creating a task."""
        try:
            serializer.save(user=self.request.user)
        except IntegrityError as exc:
            logger.error("IntegrityError creating trading task: %s", exc)
            if "unique_user_trading_task_name" in str(exc):
                raise ConflictError(
                    {"name": ["A trading task with this name already exists."]}
                ) from exc
            if "uniq_active_trading_task_per_account" in str(exc):
                raise ConflictError(
                    {"account_id": ["This account already has an active trading task."]}
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
                            "Use 'restart' to clear execution data and start fresh. "
                            "Resume is only available while the task is paused."
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
            started = self.task_service.start_task(task)
            return Response(self._serialize_detail(started))
        except TaskConflictError as exc:
            return Response(
                {"error": "Account already has an active task", "detail": str(exc)},
                status=status.HTTP_409_CONFLICT,
            )
        except TaskValidationError as exc:
            return Response(
                {"error": "Validation error", "detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TaskSubmissionError:
            logger.exception("Failed to submit trading task", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to submit task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception("Unexpected trading start failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to submit task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: str | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()
        mode = request.data.get("mode", "graceful")
        try:
            success = self.task_service.stop_task(task.pk, mode=mode)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected trading stop failure", extra={"task_id": str(task.pk)})
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
                "mode": mode,
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
            logger.exception("Unexpected trading pause failure", extra={"task_id": str(task.pk)})
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
        except TaskConflictError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected trading resume failure", extra={"task_id": str(task.pk)})
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
        except TaskConflictError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception("Unexpected trading restart failure", extra={"task_id": str(task.pk)})
            return Response(
                {"error": "Failed to restart task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self._serialize_detail(restarted))
