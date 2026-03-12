"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import EventType, LogLevel
from apps.trading.models.logs import TaskLog
from apps.trading.serializers.events import (
    OrderSerializer,
    PositionSerializer,
    StrategyEventSerializer,
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.execution import TaskExecutionSerializer
from apps.trading.serializers.summary import TaskSummarySerializer
from apps.trading.serializers.task import TaskLogSerializer
from apps.trading.views.pagination import TaskSubResourcePagination


def _parse_since(request: Request):
    """Return a datetime from the ``since`` query-param, or *None*."""
    raw = request.query_params.get("since")
    if raw:
        return parse_datetime(raw)
    return None


def _parse_execution_id(request: Request):
    """Return execution_id (UUID) from query param when valid."""
    raw = request.query_params.get("execution_id")
    if raw is None:
        return None
    try:
        from uuid import UUID

        return UUID(raw)
    except (TypeError, ValueError):
        return None


def _parse_page_params(request: Request) -> tuple[int, int]:
    """Return ``(page, page_size)`` from query params with defaults."""
    page = 1
    page_size = 1000
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        pass
    try:
        page_size = max(1, min(int(request.query_params.get("page_size", 1000)), 5000))
    except (ValueError, TypeError):
        pass
    return page, page_size


def _paginated_envelope(
    request: Request,
    results: list,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Build a standard paginated response envelope."""
    import math

    total_pages = math.ceil(total / page_size) if page_size else 1
    base_url = request.build_absolute_uri(request.path)
    params = request.query_params.copy()

    def _build_url(p: int) -> str | None:
        if p < 1 or p > total_pages:
            return None
        params["page"] = str(p)
        params["page_size"] = str(page_size)
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base_url}?{qs}"

    return {
        "count": total,
        "next": _build_url(page + 1),
        "previous": _build_url(page - 1),
        "results": results,
    }


class TaskSubResourceMixin:
    """Mixin providing paginated logs / events / trades actions."""

    task_type_label: str

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("until", str, description="RFC3339 upper-bound timestamp (exclusive)"),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int, description="Page number (1-based)"),
            OpenApiParameter(
                "page_size", int, description="Results per page (default 1000, max 5000)"
            ),
            OpenApiParameter(
                "interval",
                int,
                description="Aggregation interval in minutes (default 1). "
                "When > 1, returns one point per N-minute window.",
            ),
        ],
        responses={
            200: inline_serializer(
                "TaskMetricsResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": serializers.ListField(
                        child=inline_serializer(
                            "TaskMetricPoint",
                            fields={
                                "t": serializers.IntegerField(),
                                "metrics": serializers.DictField(),
                            },
                        )
                    ),
                },
            )
        },
        description="Retrieve paginated time-series metrics for the task.",
    )
    @action(detail=True, methods=["get"], url_path="metrics")
    def metrics(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models.metrics import Metrics

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id

        queryset = Metrics.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        ).order_by("timestamp")

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(timestamp__gt=since)

        until_raw = request.query_params.get("until")
        if until_raw:
            until_dt = parse_datetime(until_raw)
            if until_dt:
                queryset = queryset.filter(timestamp__lt=until_dt)

        # Aggregation interval (re-sample to N-minute windows)
        interval = 1
        interval_raw = request.query_params.get("interval")
        if interval_raw:
            try:
                interval = max(1, min(int(interval_raw), 1440))
            except (ValueError, TypeError):
                pass

        if interval > 1:
            from django.db import connection
            from django.db.models.sql import Query  # noqa: F401

            # Build a sub-query that buckets timestamps into N-minute windows
            # and picks the last metrics JSON per window.
            base_where = "task_type = %s AND task_id = %s AND execution_id = %s"
            params: list = [self.task_type_label, str(task.pk), str(execution_id)]

            if since:
                base_where += " AND timestamp > %s"
                params.append(since)
            if until_raw:
                until_dt2 = parse_datetime(until_raw)
                if until_dt2:
                    base_where += " AND timestamp < %s"
                    params.append(until_dt2)

            interval_seconds = interval * 60
            params.append(interval_seconds)

            sql = (
                "SELECT DISTINCT ON (bucket) "  # nosec B608
                "  timestamp, metrics "
                "FROM ("
                "  SELECT timestamp, metrics, "
                "    FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) AS bucket "
                "  FROM metrics "
                f"  WHERE {base_where}"
                ") sub "
                "ORDER BY bucket, timestamp DESC"
            )
            # %s for interval_seconds is the first param in the SELECT,
            # but we appended it last — reorder
            reordered_params = [interval_seconds] + params[:-1]

            with connection.cursor() as cursor:
                cursor.execute(sql, reordered_params)
                rows = cursor.fetchall()

            total_count = len(rows)
            # Manual pagination over raw SQL results
            page, page_size = _parse_page_params(request)
            start = (page - 1) * page_size
            end = start + page_size
            page_rows = rows[start:end]

            data = [{"t": int(ts.timestamp()), "metrics": m} for ts, m in page_rows]
            return Response(_paginated_envelope(request, data, total_count, page, page_size))

        # Default: interval=1, use ORM with cursor pagination
        total_count = queryset.count()
        page, page_size = _parse_page_params(request)
        start = (page - 1) * page_size
        rows = queryset.values_list("timestamp", "metrics")[start : start + page_size]

        data = [{"t": int(ts.timestamp()), "metrics": m} for ts, m in rows]
        return Response(_paginated_envelope(request, data, total_count, page, page_size))

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "level", str, description="Log level filter (comma-separated for multiple)"
            ),
            OpenApiParameter(
                "component",
                str,
                description="Logger/component name filter (comma-separated for multiple)",
            ),
            OpenApiParameter(
                "timestamp_from",
                str,
                description="Filter logs from this RFC3339 timestamp (inclusive)",
            ),
            OpenApiParameter(
                "timestamp_to",
                str,
                description="Filter logs until this RFC3339 timestamp (inclusive)",
            ),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskLogPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TaskLogSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task logs.",
    )
    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        level_param = request.query_params.get("level")
        level_values = (
            [v.strip().upper() for v in level_param.split(",") if v.strip()] if level_param else []
        )
        component_param = request.query_params.get("component")
        component_values = (
            [v.strip() for v in component_param.split(",") if v.strip()] if component_param else []
        )
        position_id_param = request.query_params.get("position_id")
        timestamp_from = request.query_params.get("timestamp_from")
        timestamp_to = request.query_params.get("timestamp_to")
        queryset = TaskLog.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        )
        if level_values:
            resolved = [LogLevel[v] for v in level_values if v in LogLevel.__members__]
            if resolved:
                queryset = queryset.filter(level__in=resolved)
        if component_values:
            queryset = queryset.filter(component__in=component_values)
        if position_id_param:
            # Support prefix match for truncated UUIDs (e.g. first 8 chars).
            # Extract the nested JSON text value: details->'context'->>'position_id'
            from django.db.models.fields.json import KeyTextTransform

            queryset = queryset.annotate(
                _pos_id=KeyTextTransform("position_id", KeyTextTransform("context", "details"))
            ).filter(_pos_id__startswith=position_id_param)
        if timestamp_from:
            queryset = queryset.filter(timestamp__gte=timestamp_from)
        if timestamp_to:
            queryset = queryset.filter(timestamp__lte=timestamp_to)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(timestamp__gt=since)

        queryset = queryset.order_by("-timestamp")
        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TaskLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
        ],
        responses={
            200: inline_serializer(
                "TaskLogComponentsResponse",
                fields={"components": serializers.ListField(child=serializers.CharField())},
            )
        },
        description="Return distinct logger/component names for a task's logs.",
    )
    @action(detail=True, methods=["get"], url_path="log-components")
    def log_components(self, request: Request, pk: int | None = None) -> Response:
        """Return distinct component names for the task's logs."""
        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        components = list(
            TaskLog.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
                execution_id=execution_id,
            )
            .values_list("component", flat=True)
            .distinct()
            .order_by("component")
        )
        return Response({"components": components})

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("event_type", str, description="Event type filter"),
            OpenApiParameter("severity", str, description="Severity filter"),
            OpenApiParameter("scope", str, description="Event scope: all|trading|task"),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskEventPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TradingEventSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task events.",
    )
    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models import TradingEvent

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        scope = (request.query_params.get("scope") or "all").strip().lower()
        queryset = TradingEvent.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        ).order_by("-created_at")
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if severity:
            queryset = queryset.filter(severity=severity)
        if scope in {"trading", "task"}:
            task_scoped_event_types = EventType.task_scoped_values()
            if scope == "task":
                queryset = queryset.filter(
                    Q(details__kind__startswith="task_") | Q(event_type__in=task_scoped_event_types)
                )
            else:
                queryset = queryset.filter(
                    Q(details__kind__isnull=True) | ~Q(details__kind__startswith="task_")
                ).exclude(event_type__in=task_scoped_event_types)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(created_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("event_type", str, description="Event type filter"),
            OpenApiParameter("severity", str, description="Severity filter"),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskStrategyEventPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": StrategyEventSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated strategy-internal events.",
    )
    @action(detail=True, methods=["get"], url_path="strategy-events")
    def strategy_events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models import StrategyEventRecord

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        queryset = StrategyEventRecord.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        ).order_by("-created_at")
        if event_type:
            queryset = queryset.filter(event_type=event_type)
        if severity:
            queryset = queryset.filter(severity=severity)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(created_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = StrategyEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "direction", str, description="Direction filter (buy/sell/long/short)"
            ),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskTradePaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TradeSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task trades.",
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.trades import Trade

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        direction = (request.query_params.get("direction") or "").lower()
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        ).order_by("timestamp")
        if direction:
            if direction == "buy":
                queryset = queryset.filter(direction="long")
            elif direction == "sell":
                queryset = queryset.filter(direction="short")
            else:
                queryset = queryset.filter(direction=direction)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(updated_at__gt=since)

        trades_qs = queryset.values(
            "id",
            "direction",
            "units",
            "instrument",
            "price",
            "execution_method",
            "layer_index",
            "retracement_count",
            "description",
            "timestamp",
            "position_id",
            "updated_at",
        )
        normalized: list[dict] = []
        for trade in trades_qs:
            raw_direction = trade["direction"]
            if raw_direction is None:
                trade["direction"] = None
            else:
                side = str(raw_direction).lower()
                trade["direction"] = (
                    "buy" if side == "long" else "sell" if side == "short" else side
                )
            normalized.append(trade)
        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(normalized, request)
        serializer = TradeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "position_status", str, description="Position status filter (open/closed)"
            ),
            OpenApiParameter("direction", str, description="Direction filter"),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskPositionPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": PositionSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task positions.",
    )
    @action(detail=True, methods=["get"])
    def positions(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.positions import Position

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        queryset = (
            Position.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
                execution_id=execution_id,
            )
            .prefetch_related("trades")
            .order_by("-entry_time")
        )

        status_param = (request.query_params.get("position_status") or "").lower()
        if status_param == "open":
            queryset = queryset.filter(is_open=True)
        elif status_param == "closed":
            queryset = queryset.filter(is_open=False)

        direction = (request.query_params.get("direction") or "").lower()
        if direction:
            queryset = queryset.filter(direction=direction)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(updated_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PositionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    # ------------------------------------------------------------------
    # orders (with incremental fetching via `since`)
    # ------------------------------------------------------------------
    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("status", str, description="Order status filter"),
            OpenApiParameter("order_type", str, description="Order type filter"),
            OpenApiParameter("direction", str, description="Direction filter"),
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskOrderPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": OrderSerializer(many=True),
                },
            )
        },
        description="Retrieve paginated task orders.",
    )
    @action(detail=True, methods=["get"])
    def orders(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.orders import Order

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        ).order_by("-submitted_at")

        status_param = (request.query_params.get("status") or "").lower()
        if status_param:
            queryset = queryset.filter(status=status_param)

        order_type_param = (request.query_params.get("order_type") or "").lower()
        if order_type_param:
            queryset = queryset.filter(order_type=order_type_param)

        direction = (request.query_params.get("direction") or "").lower()
        if direction:
            queryset = queryset.filter(direction=direction)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(updated_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
        ],
        responses={200: TaskSummarySerializer},
        description=(
            "Retrieve structured task summary including PnL, "
            "trade/position counts, execution state, tick info, and task status."
        ),
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve comprehensive task summary."""
        from dataclasses import asdict

        from apps.trading.services.summary import compute_task_summary

        task = self.get_object()  # type: ignore[attr-defined]
        execution_id = _parse_execution_id(request)
        if execution_id is None:
            execution_id = task.execution_id

        result = compute_task_summary(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            execution_id=execution_id,
        )

        serializer = TaskSummarySerializer(asdict(result))
        return Response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("include_metrics", bool, description="Include aggregate metrics"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskExecutionPaginatedResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "next": serializers.CharField(allow_null=True),
                    "previous": serializers.CharField(allow_null=True),
                    "results": TaskExecutionSerializer(many=True),
                },
            )
        },
        description="Retrieve execution history for a task.",
    )
    @action(detail=True, methods=["get"])
    def executions(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.executions import list_task_executions

        task = self.get_object()  # type: ignore[attr-defined]
        include_metrics = str(request.query_params.get("include_metrics", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        rows = list_task_executions(
            task=task,
            task_type=self.task_type_label,
            include_metrics=include_metrics,
        )

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(rows, request)
        serializer = TaskExecutionSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)
