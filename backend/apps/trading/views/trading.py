"""Trading task API views."""

import logging
from logging import Logger
from typing import Any

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import APIException
from rest_framework.request import Request

from apps.trading.models import TradingTask
from apps.trading.serializers.trading import (
    TradingTaskCreateSerializer,
    TradingTaskListSerializer,
    TradingTaskSerializer,
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
    executions=extend_schema(
        operation_id="trading_task_execution_history",
        tags=["Trading"],
    ),
    execution_detail=extend_schema(
        operation_id="trading_task_execution_detail",
        tags=["Trading"],
    ),
    copy=extend_schema(
        operation_id="trading_tasks_copy",
        tags=["Trading"],
        responses={201: TradingTaskSerializer},
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

    def get_stop_mode(self, request: Request) -> str:
        """Trading tasks support a configurable stop mode."""
        return request.data.get("mode", "graceful")

    def get_stop_response_extras(self, request: Request) -> dict[str, Any]:
        """Include the stop mode in the response."""
        return {"mode": self.get_stop_mode(request)}
