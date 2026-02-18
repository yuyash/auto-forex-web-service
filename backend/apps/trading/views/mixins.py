"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades) used by
both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import LogLevel
from apps.trading.models.logs import TaskLog
from apps.trading.views.pagination import TaskSubResourcePagination

# Common pagination parameters for sub-resource actions
_PAGINATION_PARAMS = [
    OpenApiParameter(name="page", type=int, required=False, description="Page number"),
    OpenApiParameter(
        name="page_size",
        type=int,
        required=False,
        description="Number of results per page (default: 100, max: 1000)",
    ),
]


def _task_log_serializer():
    from apps.trading.serializers.task import TaskLogSerializer

    return TaskLogSerializer


def _trading_event_serializer():
    from apps.trading.serializers.events import TradingEventSerializer

    return TradingEventSerializer


def _trade_serializer():
    from apps.trading.serializers.events import TradeSerializer

    return TradeSerializer


class TaskSubResourceMixin:
    """Mixin providing paginated logs / events / trades actions."""

    task_type_label: str

    @extend_schema(
        summary="Get task logs",
        description="Get task logs with pagination and filtering.",
        parameters=[
            OpenApiParameter(
                name="level", type=str, required=False, description="Filter by log level"
            ),
            OpenApiParameter(
                name="celery_task_id",
                type=str,
                required=False,
                description="Filter by celery task ID",
            ),
            *_PAGINATION_PARAMS,
        ],
        responses={200: _task_log_serializer()(many=True)},
    )
    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.serializers.task import TaskLogSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        level_param = request.query_params.get("level")
        level = LogLevel[level_param.upper()] if level_param else None
        celery_task_id = request.query_params.get("celery_task_id") or task.celery_task_id
        queryset = TaskLog.objects.filter(task_type=self.task_type_label, task_id=task.pk)
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
        else:
            queryset = queryset.none()
        if level:
            queryset = queryset.filter(level=level)
        queryset = queryset.order_by("-timestamp")
        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TaskLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Get task events",
        description="Get task events with pagination and filtering.",
        parameters=[
            OpenApiParameter(
                name="event_type", type=str, required=False, description="Filter by event type"
            ),
            OpenApiParameter(
                name="severity", type=str, required=False, description="Filter by severity"
            ),
            OpenApiParameter(
                name="celery_task_id",
                type=str,
                required=False,
                description="Filter by celery task ID",
            ),
            *_PAGINATION_PARAMS,
        ],
        responses={200: _trading_event_serializer()(many=True)},
    )
    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models import TradingEvent
        from apps.trading.serializers.events import TradingEventSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = TradingEvent.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("-created_at")
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        summary="Get task trades",
        description="Get task trades with pagination.",
        parameters=[
            OpenApiParameter(
                name="direction",
                type=str,
                required=False,
                description="Filter by direction (buy/sell)",
            ),
            OpenApiParameter(
                name="celery_task_id",
                type=str,
                required=False,
                description="Filter by celery task ID",
            ),
            *_PAGINATION_PARAMS,
        ],
        responses={200: _trade_serializer()(many=True)},
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.trades import Trade
        from apps.trading.serializers.events import TradeSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        direction = (request.query_params.get("direction") or "").lower()
        celery_task_id = request.query_params.get("celery_task_id") or task.celery_task_id
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("timestamp")
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
        else:
            queryset = queryset.none()
        if direction:
            if direction == "buy":
                queryset = queryset.filter(direction="long")
            elif direction == "sell":
                queryset = queryset.filter(direction="short")
            else:
                queryset = queryset.filter(direction=direction)
        trades_qs = queryset.values(
            "direction",
            "units",
            "instrument",
            "price",
            "execution_method",
            "layer_index",
            "pnl",
            "timestamp",
            "open_price",
            "open_timestamp",
            "close_price",
            "close_timestamp",
        )
        normalized: list[dict] = []
        for trade in trades_qs:
            side = str(trade["direction"]).lower()
            trade["direction"] = "buy" if side == "long" else "sell" if side == "short" else side
            normalized.append(trade)
        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(normalized, request)
        serializer = TradeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
