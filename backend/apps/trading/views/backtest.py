"""Backtest task API views."""

import logging
from logging import Logger
from typing import Any

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.trading.models import BacktestTask
from apps.trading.serializers.backtest import (
    BacktestTaskCreateSerializer,
    BacktestTaskListSerializer,
    BacktestTaskSerializer,
)
from apps.trading.views.task_base import TaskViewSetBase

logger: Logger = logging.getLogger(name=__name__)


def _integrity_constraint_id(exc: IntegrityError) -> str:
    """Extract the constraint name from an IntegrityError without leaking internals.

    Checks the psycopg2 diagnostic first, then falls back to the first
    exception arg (which Django uses to wrap the constraint name).
    The return value is only used for ``in`` checks — never sent to clients.
    """
    pg_diag = getattr(getattr(exc, "__cause__", None), "diag", None)
    name = getattr(pg_diag, "constraint_name", None)
    if name:
        return name
    # Fallback: Django wraps the constraint name as the first arg.
    return str(exc.args[0]) if exc.args else ""


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
    executions=extend_schema(
        operation_id="backtest_task_execution_history",
        tags=["Trading"],
    ),
    execution_detail=extend_schema(
        operation_id="backtest_task_execution_detail",
        tags=["Trading"],
    ),
    copy=extend_schema(
        operation_id="backtest_tasks_copy",
        tags=["Trading"],
        responses={201: BacktestTaskSerializer},
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
            exc_text = _integrity_constraint_id(exc)
            if "unique_user_backtest_task_name" in exc_text:
                raise ValidationError(
                    {"name": ["A backtest task with this name already exists."]}
                ) from exc
            raise

    def get_stop_mode(self, request: Request) -> str:
        """Backtest tasks accept the same stop modes as trading tasks.

        Supported values: ``graceful``, ``graceful_close``, ``immediate``,
        ``drain``. Defaults to ``graceful`` to preserve the previous
        behaviour when the client does not send a mode.
        """
        return request.data.get("mode", "graceful")

    def get_stop_response_extras(self, request: Request) -> dict[str, Any]:
        """Echo the resolved stop mode in the stop response."""
        return {"mode": self.get_stop_mode(request)}
