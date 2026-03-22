"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

import json

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
    TradeSerializer,
    TradingEventSerializer,
)
from apps.trading.serializers.execution import TaskExecutionSerializer
from apps.trading.serializers.summary import TaskSummarySerializer
from apps.trading.serializers.task import TaskLogSerializer
from apps.trading.serializers.trend_replay import TaskTrendReplaySerializer
from apps.trading.views.query_params import (
    DateRangeQuery,
    ExecutionScopedQuery,
    PaginationParams,
    PositionQuery,
    TrendReplayQueryParams,
)
from apps.trading.views.pagination import TaskSubResourcePagination


def _parse_since(request: Request):
    """Return a datetime from the ``since`` query-param, or *None*."""
    raw = request.query_params.get("since")
    if raw:
        return parse_datetime(raw)
    return None


def _parse_datetime_param(request: Request, key: str):
    """Return a datetime from an arbitrary query param, or *None*."""
    raw = request.query_params.get(key)
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
    pagination = PaginationParams.from_request(request)
    return pagination.page, pagination.page_size


def _ensure_dict(value) -> dict:
    """Ensure a metrics value is a dict (handles double-encoded JSON strings)."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )

        queryset = Metrics.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
        ).order_by("timestamp")

        if query.since:
            queryset = queryset.filter(timestamp__gt=query.since)

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

            if connection.vendor != "postgresql":
                rows = list(queryset.values_list("timestamp", "metrics"))
                bucketed: dict[int, tuple] = {}
                interval_seconds = interval * 60
                for ts, metrics in rows:
                    bucket = int(ts.timestamp()) // interval_seconds
                    bucketed[bucket] = (ts, metrics)

                aggregated = [bucketed[key] for key in sorted(bucketed)]
                total_count = len(aggregated)
                page, page_size = query.pagination.page, query.pagination.page_size
                start = (page - 1) * page_size
                end = start + page_size
                page_rows = aggregated[start:end]

                data = [
                    {"t": int(ts.timestamp()), "metrics": _ensure_dict(metrics)}
                    for ts, metrics in page_rows
                ]
                return Response(_paginated_envelope(request, data, total_count, page, page_size))

            # Build a sub-query that buckets timestamps into N-minute windows
            # and picks the last metrics JSON per window.
            base_where = "task_type = %s AND task_id = %s"
            params: list = [self.task_type_label, str(task.pk)]

            if query.execution_id is None:
                base_where += " AND execution_id IS NULL"
            else:
                base_where += " AND execution_id = %s"
                params.append(str(query.execution_id))

            if query.since:
                base_where += " AND timestamp > %s"
                params.append(query.since)
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
            page, page_size = query.pagination.page, query.pagination.page_size
            start = (page - 1) * page_size
            end = start + page_size
            page_rows = rows[start:end]

            data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in page_rows]
            return Response(_paginated_envelope(request, data, total_count, page, page_size))

        # Default: interval=1, use ORM with cursor pagination
        total_count = queryset.count()
        page, page_size = query.pagination.page, query.pagination.page_size
        start = (page - 1) * page_size
        rows = queryset.values_list("timestamp", "metrics")[start : start + page_size]

        data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in rows]
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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
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
            execution_id=query.execution_id,
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

        if query.since:
            queryset = queryset.filter(timestamp__gt=query.since)

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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        components = list(
            TaskLog.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
                execution_id=query.execution_id,
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
            OpenApiParameter(
                "created_from",
                str,
                description="Filter events created at or after this RFC3339 timestamp",
            ),
            OpenApiParameter(
                "created_to",
                str,
                description="Filter events created at or before this RFC3339 timestamp",
            ),
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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        scope = (request.query_params.get("scope") or "all").strip().lower()
        queryset = TradingEvent.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
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

        if query.since:
            queryset = queryset.filter(created_at__gt=query.since)
        created_range = DateRangeQuery.from_request(
            request, start_key="created_from", end_key="created_to"
        )
        if created_range.start:
            queryset = queryset.filter(created_at__gte=created_range.start)
        if created_range.end:
            queryset = queryset.filter(created_at__lte=created_range.end)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("root_entry_id", int, description="Optional group filter"),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={
            200: inline_serializer(
                "TaskStrategyVisualizationResponse",
                fields={
                    "strategy_type": serializers.CharField(),
                    "supported": serializers.BooleanField(),
                    "execution_id": serializers.CharField(allow_null=True),
                    "generated_at": serializers.DateTimeField(allow_null=True),
                    "summary": serializers.JSONField(),
                    "view_model": serializers.JSONField(),
                    "message": serializers.CharField(required=False),
                },
            )
        },
        description="Retrieve strategy visualization data.",
    )
    @action(detail=True, methods=["get"], url_path="strategy-events")
    def strategy_events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.services.strategy_visualization import (
            StrategyVisualizationService,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        root_entry_id = request.query_params.get("root_entry_id")
        response = StrategyVisualizationService().build(
            task=task,
            task_type=self.task_type_label,
            execution_id=query.execution_id,
            root_entry_id=int(root_entry_id) if root_entry_id else None,
        )
        return Response(response)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "direction", str, description="Direction filter (buy/sell/long/short)"
            ),
            OpenApiParameter(
                "timestamp_from",
                str,
                description="Filter trades executed at or after this RFC3339 timestamp",
            ),
            OpenApiParameter(
                "timestamp_to",
                str,
                description="Filter trades executed at or before this RFC3339 timestamp",
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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        direction = (request.query_params.get("direction") or "").lower()
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
        ).order_by("timestamp")
        if direction:
            if direction == "buy":
                queryset = queryset.filter(direction="long")
            elif direction == "sell":
                queryset = queryset.filter(direction="short")
            else:
                queryset = queryset.filter(direction=direction)

        if query.since:
            queryset = queryset.filter(updated_at__gt=query.since)
        timestamp_range = DateRangeQuery.from_request(
            request, start_key="timestamp_from", end_key="timestamp_to"
        )
        if timestamp_range.start:
            queryset = queryset.filter(timestamp__gte=timestamp_range.start)
        if timestamp_range.end:
            queryset = queryset.filter(timestamp__lte=timestamp_range.end)

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
            OpenApiParameter(
                "include_trade_ids",
                bool,
                description="Include position trade_ids in the response",
            ),
            OpenApiParameter(
                "range_from",
                str,
                description="RFC3339 lower bound for positions overlapping a chart range",
            ),
            OpenApiParameter(
                "range_to",
                str,
                description="RFC3339 upper bound for positions overlapping a chart range",
            ),
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
        query = PositionQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = Position.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("-entry_time")
        if query.include_trade_ids:
            queryset = queryset.prefetch_related("trades")

        if query.position_status == "open":
            queryset = queryset.filter(is_open=True)
        elif query.position_status == "closed":
            queryset = queryset.filter(is_open=False)

        if query.direction:
            queryset = queryset.filter(direction=query.direction)

        if query.execution.since:
            queryset = queryset.filter(updated_at__gt=query.execution.since)

        if query.range.end:
            queryset = queryset.filter(entry_time__lte=query.range.end)
        if query.range.start:
            queryset = queryset.filter(
                Q(exit_time__isnull=True) | Q(exit_time__gte=query.range.start)
            )

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PositionSerializer(
            page,
            many=True,
            context={"include_trade_ids": query.include_trade_ids},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("execution_id", str, description="Filter by execution ID (UUID)"),
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "range_from",
                str,
                description="RFC3339 lower bound for the chart window",
            ),
            OpenApiParameter(
                "range_to",
                str,
                description="RFC3339 upper bound for the chart window",
            ),
            OpenApiParameter("page", int),
            OpenApiParameter("page_size", int),
        ],
        responses={200: TaskTrendReplaySerializer},
        description="Retrieve chart-oriented trades and positions for task trend replay.",
    )
    @action(detail=True, methods=["get"], url_path="trend-replay")
    def trend_replay(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.trend_replay import (
            DEFAULT_TREND_REPLAY_PAGE_SIZE,
            MAX_TREND_REPLAY_PAGE_SIZE,
            TrendReplayQuery,
            build_trend_replay_payload,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        query = TrendReplayQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=DEFAULT_TREND_REPLAY_PAGE_SIZE,
            max_page_size=MAX_TREND_REPLAY_PAGE_SIZE,
        )

        payload = build_trend_replay_payload(
            TrendReplayQuery(
                task_type=self.task_type_label,
                task_id=str(task.pk),
                execution_id=(
                    str(query.execution.execution_id)
                    if query.execution.execution_id is not None
                    else None
                ),
                range_from=query.range.start,
                range_to=query.range.end,
                since=query.execution.since,
                page=query.execution.pagination.page,
                page_size=query.execution.pagination.page_size,
            )
        )
        serializer = TaskTrendReplaySerializer(payload)
        return Response(serializer.data)

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
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
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

        if query.since:
            queryset = queryset.filter(updated_at__gt=query.since)

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

        from apps.trading.services.summary import compute_cached_task_summary

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionScopedQuery.from_request(
            request,
            default_execution_id=task.execution_id,
        )

        result = compute_cached_task_summary(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            execution_id=query.execution_id,
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
        pagination = PaginationParams.from_request(request)
        total_count, rows = list_task_executions(
            task=task,
            task_type=self.task_type_label,
            include_metrics=include_metrics,
            page=pagination.page,
            page_size=pagination.page_size,
        )
        serializer = TaskExecutionSerializer(rows, many=True)
        return Response(
            _paginated_envelope(
                request,
                serializer.data,
                total_count,
                pagination.page,
                pagination.page_size,
            )
        )

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("include_metrics", bool, description="Include aggregate metrics"),
        ],
        responses={200: TaskExecutionSerializer},
        description="Retrieve a single execution record for a task.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path=r"executions/(?P<execution_id>[^/.]+)",
    )
    def execution_detail(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        from apps.trading.services.executions import get_task_execution

        task = self.get_object()  # type: ignore[attr-defined]
        include_metrics = str(request.query_params.get("include_metrics", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        row = get_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
            include_metrics=include_metrics,
        )
        if row is None:
            return Response({"detail": "Execution not found."}, status=404)
        serializer = TaskExecutionSerializer(row)
        return Response(serializer.data)
