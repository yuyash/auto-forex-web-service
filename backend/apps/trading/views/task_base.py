"""Shared base classes for task viewsets."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

from django.db.models import Q, QuerySet
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.trading.enums import TaskStatus
from apps.trading.tasks.service import (
    TaskCapacityError,
    TaskConflictError,
    TaskService,
    TaskSubmissionError,
    TaskValidationError,
)
from apps.trading.views.mixins import TaskSubResourceMixin

logger = logging.getLogger(__name__)


class TaskViewSetBase(TaskSubResourceMixin, ModelViewSet):
    """Common behavior for backtest and trading task viewsets.

    Subclasses only need to override ``perform_create`` and, optionally,
    ``get_stop_mode`` or ``get_stop_response_extras`` to customise the
    lifecycle actions.
    """

    permission_classes = [IsAuthenticated]
    detail_serializer_class = None
    list_serializer_class = None
    create_serializer_class = None
    task_model_name: str | None = None
    select_related_fields: tuple[str, ...] = ()
    filter_field_map: dict[str, str] = {}
    task_type_label: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.task_service: TaskService = TaskService()

    # ------------------------------------------------------------------
    # Serializer routing
    # ------------------------------------------------------------------

    def get_serializer_class(self):
        if self.action == "list" and self.list_serializer_class is not None:
            return self.list_serializer_class
        if (
            self.action in {"create", "update", "partial_update"}
            and self.create_serializer_class is not None
        ):
            return self.create_serializer_class
        if self.detail_serializer_class is not None:
            return self.detail_serializer_class
        return super().get_serializer_class()

    # ------------------------------------------------------------------
    # Queryset
    # ------------------------------------------------------------------

    def get_queryset(self) -> QuerySet:
        """Return tasks for the authenticated user with common filtering."""
        assert isinstance(self.request, Request)
        task_model = self._get_task_model()
        assert task_model is not None

        queryset = task_model.objects.filter(user=self.request.user.pk)
        if self.select_related_fields:
            queryset = queryset.select_related(*self.select_related_fields)

        for param_name, field_name in self.filter_field_map.items():
            raw_value = self.request.query_params.get(param_name)
            if not raw_value:
                continue
            queryset = queryset.filter(**{field_name: self._coerce_filter_value(raw_value)})

        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))

        ordering = "-created_at"
        if self.action == "list":
            ordering = self.request.query_params.get("ordering", ordering)
        return queryset.order_by(ordering)

    # ------------------------------------------------------------------
    # CRUD overrides
    # ------------------------------------------------------------------

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers({})
        return Response(
            self._serialize_detail(serializer.instance),
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(self._serialize_detail(serializer.instance))

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    # ------------------------------------------------------------------
    # Lifecycle actions (shared by backtest & trading)
    # ------------------------------------------------------------------

    def get_stop_mode(self, request: Request) -> str:
        """Return the stop mode from the request.  Override in subclasses."""
        return "graceful"

    def get_stop_response_extras(self, request: Request) -> dict[str, Any]:
        """Extra fields to include in the stop response body."""
        return {}

    @staticmethod
    def _capacity_error_payload(exc: TaskCapacityError) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "error": "Task capacity exhausted",
            "detail": str(exc),
        }
        decision = getattr(exc, "decision", None)
        if decision is None:
            return payload

        payload["capacity"] = [
            {
                "queue": snapshot.queue,
                "used": snapshot.used,
                "limit": snapshot.limit,
                "available": snapshot.available,
            }
            for snapshot in getattr(decision, "details", ())
        ]
        required_stops = getattr(decision, "required_stops", ())
        if required_stops:
            payload["required_stops"] = list(required_stops)
        return payload

    @staticmethod
    def _task_conflict_payload(*, task_type_label: str) -> dict[str, str]:
        return {
            "error": "Task cannot be started due to a conflict",
            "detail": (
                f"Another active {task_type_label} task or account-level constraint is blocking this "
                "request. Stop the conflicting task and try again."
            ),
        }

    @staticmethod
    def _task_validation_payload(*, action_name: str) -> dict[str, str]:
        return {
            "error": f"Invalid {action_name} request for current task state",
            "detail": (
                f"This task cannot be {action_name}ed with its current configuration or lifecycle "
                "state. Review the task settings and try again."
            ),
        }

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
        except TaskCapacityError as exc:
            logger.warning(
                "Task capacity exhausted on start: task_id=%s, detail=%s",
                task.pk,
                exc,
            )
            return Response(
                self._capacity_error_payload(exc),
                status=status.HTTP_409_CONFLICT,
            )
        except TaskConflictError as exc:
            logger.warning(
                "Task conflict on start: task_id=%s, detail=%s",
                task.pk,
                exc,
            )
            return Response(
                self._task_conflict_payload(task_type_label=self.task_type_label),
                status=status.HTTP_409_CONFLICT,
            )
        except TaskValidationError as exc:
            logger.warning(
                "Task validation failed on start: task_id=%s, detail=%s",
                task.pk,
                exc,
            )
            return Response(
                self._task_validation_payload(action_name="start"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TaskSubmissionError:
            logger.exception(
                "Failed to submit %s task", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                {"error": "Failed to submit task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception(
                "Unexpected %s start failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                {"error": "Internal server error", "detail": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: str | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()
        mode = self.get_stop_mode(request)
        try:
            success = self.task_service.stop_task(task.pk, mode=mode)
        except ValueError as exc:
            logger.warning("Stop validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                {"error": "Invalid stop request for current task state"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s stop failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                {"error": "Failed to stop task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not success:
            return Response(
                {"error": "Failed to stop task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        body: dict[str, Any] = {
            "message": "Task stop requested",
            "task_id": str(task.pk),
            "status": TaskStatus.STOPPING,
        }
        body.update(self.get_stop_response_extras(request))
        return Response(body, status=status.HTTP_202_ACCEPTED)

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
            logger.warning("Pause validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                {"error": "Invalid pause request for current task state"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s pause failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
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
            # Full exception text goes to the log so operators can see
            # the exact conflict; the response body intentionally carries
            # only a fixed, safe description to avoid any chance of
            # leaking internal details (CodeQL py/stack-trace-exposure).
            logger.warning("Resume conflict: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                {
                    "error": "Task cannot be resumed due to a conflict",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except TaskValidationError as exc:
            # ``TaskValidationError`` is raised by the task service on
            # domain-level validation failures (wrong status, missing
            # execution_id, Celery still running, etc.).  We log the
            # message verbatim but return a fixed description to the
            # caller — CodeQL cannot prove the message is safe and
            # future changes to the service layer could unintentionally
            # leak internal text through this path.
            logger.warning("Resume validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                {
                    "error": "Invalid resume request for current task state",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s resume failure",
                self.task_type_label,
                extra={"task_id": str(task.pk)},
            )
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
        except TaskCapacityError as exc:
            logger.warning("Restart capacity exhausted: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                self._capacity_error_payload(exc),
                status=status.HTTP_409_CONFLICT,
            )
        except TaskConflictError as exc:
            logger.warning("Restart conflict: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                self._task_conflict_payload(task_type_label=self.task_type_label),
                status=status.HTTP_409_CONFLICT,
            )
        except ValueError as exc:
            logger.warning("Restart validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                self._task_validation_payload(action_name="restart"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s restart failure",
                self.task_type_label,
                extra={"task_id": str(task.pk)},
            )
            return Response(
                {"error": "Failed to restart task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self._serialize_detail(restarted))

    @action(detail=True, methods=["post"])
    def copy(self, request: Request, pk: str | None = None) -> Response:
        """Create a copy of the task with a new name."""
        task = self.get_object()
        new_name = request.data.get("new_name")
        if not new_name:
            new_name = f"{task.name} (copy)"
        try:
            clone = task.copy(new_name=new_name)
        except Exception:
            logger.exception(
                "Failed to copy %s task", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                {"error": "Failed to copy task"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(self._serialize_detail(clone), status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_detail(self, instance: Any) -> dict[str, Any]:
        serializer = self.get_serializer(instance)
        return serializer.data

    @staticmethod
    def _coerce_filter_value(raw_value: str) -> Any:
        if raw_value.isdigit():
            return int(raw_value)
        return raw_value

    def _get_task_model(self):
        if self.task_model_name is None:
            return None
        module = import_module(self.__module__)
        return getattr(module, self.task_model_name)
