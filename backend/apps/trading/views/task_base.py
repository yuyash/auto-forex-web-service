"""Shared base classes for task viewsets."""

from __future__ import annotations

import logging
from importlib import import_module
from typing import Any

from django.db.models import Q, QuerySet
from drf_spectacular.utils import OpenApiParameter
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.querying import (
    OrderingConfig,
    invalid_query_param,
    parse_datetime_param,
)
from apps.trading.enums import TaskStatus
from apps.trading.tasks.service import (
    TaskCapacityError,
    TaskConflictError,
    TaskService,
    TaskSubmissionError,
    TaskValidationError,
)
from apps.trading.views.errors import api_error
from apps.trading.views.mixins import TaskSubResourceMixin
from apps.trading.views.pagination import StandardPagination
from apps.trading.views.throttles import TaskDataRateThrottle

logger = logging.getLogger(__name__)

TASK_ORDERING = OrderingConfig(
    fields={
        "id": "id",
        "name": "name",
        "status": "status",
        "instrument": "instrument",
        "created_at": "created_at",
        "updated_at": "updated_at",
        "started_at": "started_at",
        "completed_at": "completed_at",
        "config_id": "config_id",
    },
    default="-created_at",
)

TASK_LIST_PARAMETERS = [
    OpenApiParameter(name="page", type=int, required=False),
    OpenApiParameter(name="page_size", type=int, required=False),
    OpenApiParameter(name="ordering", type=str, required=False),
    OpenApiParameter(name="search", type=str, required=False),
    OpenApiParameter(name="status", type=str, required=False),
    OpenApiParameter(name="config_id", type=str, required=False),
    OpenApiParameter(name="created_from", type=str, required=False),
    OpenApiParameter(name="created_to", type=str, required=False),
    OpenApiParameter(name="updated_from", type=str, required=False),
    OpenApiParameter(name="updated_to", type=str, required=False),
]


def task_stop_response_fields(
    extra_fields: dict[str, serializers.Field] | None = None,
) -> dict[str, serializers.Field]:
    """Return OpenAPI fields for accepted task stop command responses."""
    fields: dict[str, serializers.Field] = {
        "message": serializers.CharField(),
        "command": serializers.CharField(),
        "task_id": serializers.CharField(),
        "previous_status": serializers.CharField(),
        "next_status": serializers.CharField(),
        "status": serializers.CharField(),
        "accepted": serializers.BooleanField(),
    }
    if extra_fields:
        fields.update(extra_fields)
    return fields


class TaskViewSetBase(TaskSubResourceMixin, ModelViewSet):
    """Common behavior for backtest and trading task viewsets.

    Subclasses only need to override ``perform_create`` and, optionally,
    ``get_stop_mode`` or ``get_stop_response_extras`` to customise the
    lifecycle actions.
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [TaskDataRateThrottle]
    pagination_class = StandardPagination
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

        if self.action == "list":
            created_from = parse_datetime_param(
                self.request.query_params.get("created_from"),
                field_name="created_from",
            )
            created_to = parse_datetime_param(
                self.request.query_params.get("created_to"),
                field_name="created_to",
            )
            updated_from = parse_datetime_param(
                self.request.query_params.get("updated_from"),
                field_name="updated_from",
            )
            updated_to = parse_datetime_param(
                self.request.query_params.get("updated_to"),
                field_name="updated_to",
            )
            if created_from and created_to and created_from > created_to:
                raise invalid_query_param(
                    "created_from must be earlier than or equal to created_to"
                )
            if updated_from and updated_to and updated_from > updated_to:
                raise invalid_query_param(
                    "updated_from must be earlier than or equal to updated_to"
                )
            if created_from:
                queryset = queryset.filter(created_at__gte=created_from)
            if created_to:
                queryset = queryset.filter(created_at__lte=created_to)
            if updated_from:
                queryset = queryset.filter(updated_at__gte=updated_from)
            if updated_to:
                queryset = queryset.filter(updated_at__lte=updated_to)
            ordering = self.request.query_params.get("ordering")
            return TASK_ORDERING.apply_to_queryset(queryset, ordering)

        return queryset.order_by("-created_at")

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

    def get_drain_duration_minutes(self, request: Request) -> int | None:
        """Return the optional per-stop drain duration override in minutes.

        Subclasses may override to read the value from the request body.
        Returning ``None`` (the default) leaves the task's configured
        ``drain_duration_hours`` in place.
        """
        return None

    def get_stop_response_extras(self, request: Request) -> dict[str, Any]:
        """Extra fields to include in the stop response body."""
        return {}

    @staticmethod
    def _status_value(value: Any) -> str:
        return str(getattr(value, "value", value))

    def _resolve_stop_response_status(
        self,
        *,
        task: Any,
        requested_mode: str,
        previous_status: Any,
    ) -> str:
        """Resolve the post-command status to return after stop acceptance."""
        refresh_from_db = getattr(task, "refresh_from_db", None)
        if callable(refresh_from_db):
            try:
                refresh_from_db(fields=["status"])
            except TypeError:
                try:
                    refresh_from_db()
                except Exception:
                    logger.debug(
                        "Unable to refresh task after stop",
                        extra={"task_id": str(getattr(task, "pk", ""))},
                        exc_info=True,
                    )
            except Exception:
                logger.debug(
                    "Unable to refresh task after stop",
                    extra={"task_id": str(getattr(task, "pk", ""))},
                    exc_info=True,
                )

        refreshed_status = getattr(task, "status", None)
        previous_value = self._status_value(previous_status)
        refreshed_value = self._status_value(refreshed_status)
        if refreshed_status is not None and refreshed_value != previous_value:
            return refreshed_value
        if requested_mode == "drain" and previous_value != self._status_value(TaskStatus.DRAINING):
            return self._status_value(TaskStatus.DRAINING)
        return self._status_value(TaskStatus.STOPPING)

    @staticmethod
    def _capacity_error_payload(exc: TaskCapacityError) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **api_error(
                "Task capacity exhausted",
                code="task_capacity_exhausted",
                detail=str(exc),
            ),
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
    def _task_conflict_payload(*, task_type_label: str) -> dict[str, Any]:
        return api_error(
            "Task cannot be started due to a conflict",
            code="task_conflict",
            detail=(
                f"Another active {task_type_label} task or account-level constraint is blocking this "
                "request. Stop the conflicting task and try again."
            ),
        )

    @staticmethod
    def _task_validation_payload(
        *,
        action_name: str,
        exc: TaskValidationError | None = None,
    ) -> dict[str, Any]:
        detail = (
            str(exc)
            if exc
            else (
                f"This task cannot be {action_name}ed with its current configuration or lifecycle "
                "state. Review the task settings and try again."
            )
        )
        return api_error(
            f"Invalid {action_name} request for current task state",
            code=f"invalid_{action_name}_state",
            detail=detail,
        )

    @action(detail=True, methods=["post"])
    def start(self, request: Request, pk: str | None = None) -> Response:
        """Submit task for execution."""
        task = self.get_object()
        if task.status != TaskStatus.CREATED:
            if task.status == TaskStatus.STOPPED:
                return Response(
                    api_error(
                        "Cannot submit a stopped task",
                        code="stopped_task_requires_resume_or_restart",
                        detail=(
                            "Use 'resume' to continue from where the task left off, "
                            "or 'restart' to clear execution data and start fresh."
                        ),
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                api_error(
                    "Task must be in CREATED status to submit",
                    code="invalid_start_state",
                    detail=f"Current status: {task.status}",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            started = self.task_service.start_task(task, user=request.user)
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
                self._task_validation_payload(action_name="start", exc=exc),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except TaskSubmissionError:
            logger.exception(
                "Failed to submit %s task", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                api_error("Failed to submit task", code="task_submission_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception:
            logger.exception(
                "Unexpected %s start failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                api_error(
                    "Internal server error",
                    code="internal_error",
                    detail="An unexpected error occurred",
                ),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    @action(detail=True, methods=["post"])
    def stop(self, request: Request, pk: str | None = None) -> Response:
        """Stop running task asynchronously."""
        task = self.get_object()
        mode = self.get_stop_mode(request)
        drain_minutes = self.get_drain_duration_minutes(request)
        previous_status = task.status
        try:
            success = self.task_service.stop_task(
                task.pk,
                mode=mode,
                drain_duration_minutes=drain_minutes,
                user=request.user,
            )
        except ValueError as exc:
            logger.warning("Stop validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                api_error(
                    "Invalid stop request for current task state",
                    code="invalid_stop_state",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s stop failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                api_error("Failed to stop task", code="stop_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not success:
            return Response(
                api_error("Failed to stop task", code="stop_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        next_status = self._resolve_stop_response_status(
            task=task,
            requested_mode=mode,
            previous_status=previous_status,
        )
        body: dict[str, Any] = {
            "message": "Task stop requested",
            "command": "stop",
            "task_id": str(task.pk),
            "previous_status": self._status_value(previous_status),
            "next_status": next_status,
            "status": next_status,
            "accepted": True,
        }
        body.update(self.get_stop_response_extras(request))
        return Response(body, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"])
    def pause(self, request: Request, pk: str | None = None) -> Response:
        """Pause a running task."""
        task = self.get_object()
        if task.status not in {TaskStatus.RUNNING, TaskStatus.STARTING}:
            return Response(
                api_error(
                    f"Task cannot be paused from {task.status} state",
                    code="invalid_pause_state",
                    detail=f"Current status: {task.status}",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            success = self.task_service.pause_task(task.pk, user=request.user)
        except ValueError as exc:
            logger.warning("Pause validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                api_error(
                    "Invalid pause request for current task state",
                    code="invalid_pause_state",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s pause failure", self.task_type_label, extra={"task_id": str(task.pk)}
            )
            return Response(
                api_error("Failed to pause task", code="pause_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not success:
            return Response(
                api_error("Failed to pause task", code="pause_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        task.refresh_from_db()
        return Response(self._serialize_detail(task))

    @staticmethod
    def _resume_conflict_payload() -> dict[str, Any]:
        """Return the fixed 409 payload for a resume conflict.

        Kept separate from the ``except`` block so CodeQL cannot treat
        the response body as reachable from the caught exception — the
        taint tracker's ``py/stack-trace-exposure`` rule flagged even
        fully-static ``Response`` payloads when they were written
        lexically inside a handler for an exception.
        """
        return api_error("Task cannot be resumed due to a conflict", code="resume_conflict")

    @staticmethod
    def _resume_validation_payload(exc: TaskValidationError | None = None) -> dict[str, Any]:
        """Return the fixed 400 payload for a resume validation failure."""
        config_error = getattr(exc, "resume_config_error", None)
        if isinstance(config_error, dict):
            return api_error(
                "Resume requires a restart because configuration changed incompatibly",
                code=str(config_error.get("code") or "resume_config_incompatible"),
                restart_required=bool(config_error.get("restart_required", True)),
                blocked_fields=list(config_error.get("blocked_fields") or []),
                safe_fields=list(config_error.get("safe_fields") or []),
            )
        return api_error(
            "Invalid resume request for current task state",
            code="invalid_resume_state",
        )

    @action(detail=True, methods=["post"])
    def resume(self, request: Request, pk: str | None = None) -> Response:
        """Resume a paused task."""
        task = self.get_object()
        try:
            resumed = self.task_service.resume_task(task.pk, user=request.user)
        except TaskConflictError:
            logger.exception(
                "Resume conflict",
                extra={"task_id": str(task.pk)},
            )
            return Response(
                self._resume_conflict_payload(),
                status=status.HTTP_409_CONFLICT,
            )
        except TaskValidationError as exc:
            logger.exception(
                "Resume validation failed",
                extra={"task_id": str(task.pk)},
            )
            return Response(
                self._resume_validation_payload(exc),
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception:
            logger.exception(
                "Unexpected %s resume failure",
                self.task_type_label,
                extra={"task_id": str(task.pk)},
            )
            return Response(
                api_error("Failed to resume task", code="resume_failed"),
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(self._serialize_detail(resumed))

    @action(detail=True, methods=["post"])
    def restart(self, request: Request, pk: str | None = None) -> Response:
        """Restart a task from the beginning."""
        task = self.get_object()
        try:
            restarted = self.task_service.restart_task(task.pk, user=request.user)
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
        except TaskValidationError as exc:
            logger.warning("Restart validation failed: task_id=%s, detail=%s", task.pk, exc)
            return Response(
                self._task_validation_payload(action_name="restart", exc=exc),
                status=status.HTTP_400_BAD_REQUEST,
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
                api_error("Failed to restart task", code="restart_failed"),
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
                api_error("Failed to copy task", code="copy_failed"),
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
