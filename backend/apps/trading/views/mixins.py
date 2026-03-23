"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

import json

from django.db.models import Q
from drf_spectacular.utils import extend_schema, inline_serializer
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
    ExecutionDetailQueryParamsSchemaSerializer,
    ExecutionScopedQuery,
    ExecutionsQueryParamsSchemaSerializer,
    EventsQueryParams,
    EventsQueryParamsSchemaSerializer,
    LogComponentsQueryParamsSchemaSerializer,
    LogsQueryParams,
    LogsQueryParamsSchemaSerializer,
    MetricsQueryParams,
    MetricsQueryParamsSchemaSerializer,
    OrdersQueryParams,
    OrdersQueryParamsSchemaSerializer,
    PaginationParams,
    PositionQuery,
    PositionsQueryParamsSchemaSerializer,
    StrategyEventsQueryParamsSchemaSerializer,
    SummaryQueryParamsSchemaSerializer,
    TradesQueryParams,
    TradesQueryParamsSchemaSerializer,
    TrendReplayQueryParams,
    TrendReplayQueryParamsSchemaSerializer,
)
from apps.trading.views.pagination import (
    ActivityPagination,
    MetricsPagination,
    TradePositionPagination,
)


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
        parameters=[MetricsQueryParamsSchemaSerializer],
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
        query = MetricsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=MetricsPagination.page_size,
            max_page_size=MetricsPagination.max_page_size,
        )

        queryset = Metrics.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("timestamp")

        if query.execution.since:
            queryset = queryset.filter(timestamp__gt=query.execution.since)

        if query.until:
            queryset = queryset.filter(timestamp__lt=query.until)

        interval = query.interval

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
                page, page_size = (
                    query.execution.pagination.page,
                    query.execution.pagination.page_size,
                )
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

            if query.execution.execution_id is None:
                base_where += " AND execution_id IS NULL"
            else:
                base_where += " AND execution_id = %s"
                params.append(str(query.execution.execution_id))

            if query.execution.since:
                base_where += " AND timestamp > %s"
                params.append(query.execution.since)
            if query.until:
                base_where += " AND timestamp < %s"
                params.append(query.until)

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
            page, page_size = (
                query.execution.pagination.page,
                query.execution.pagination.page_size,
            )
            start = (page - 1) * page_size
            end = start + page_size
            page_rows = rows[start:end]

            data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in page_rows]
            return Response(_paginated_envelope(request, data, total_count, page, page_size))

        # Default: interval=1, use ORM with cursor pagination
        total_count = queryset.count()
        page, page_size = (
            query.execution.pagination.page,
            query.execution.pagination.page_size,
        )
        start = (page - 1) * page_size
        rows = queryset.values_list("timestamp", "metrics")[start : start + page_size]

        data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in rows]
        return Response(_paginated_envelope(request, data, total_count, page, page_size))

    @extend_schema(
        tags=["Trading"],
        parameters=[LogsQueryParamsSchemaSerializer],
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
        query = LogsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
        )
        queryset = TaskLog.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        )
        if query.levels:
            resolved = [LogLevel[v] for v in query.levels if v in LogLevel.__members__]
            if resolved:
                queryset = queryset.filter(level__in=resolved)
        if query.components:
            queryset = queryset.filter(component__in=query.components)
        if query.position_id:
            # Support prefix match for truncated UUIDs (e.g. first 8 chars).
            # Extract the nested JSON text value: details->'context'->>'position_id'
            from django.db.models.fields.json import KeyTextTransform

            queryset = queryset.annotate(
                _pos_id=KeyTextTransform("position_id", KeyTextTransform("context", "details"))
            ).filter(_pos_id__startswith=query.position_id)
        if query.timestamp_range.start:
            queryset = queryset.filter(timestamp__gte=query.timestamp_range.start)
        if query.timestamp_range.end:
            queryset = queryset.filter(timestamp__lte=query.timestamp_range.end)

        if query.execution.since:
            queryset = queryset.filter(timestamp__gt=query.execution.since)

        queryset = queryset.order_by("-timestamp")
        paginator = ActivityPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TaskLogSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[LogComponentsQueryParamsSchemaSerializer],
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
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
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
        parameters=[EventsQueryParamsSchemaSerializer],
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
        query = EventsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = TradingEvent.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("-created_at")
        if query.event_type:
            queryset = queryset.filter(event_type=query.event_type)
        if query.severity:
            queryset = queryset.filter(severity=query.severity)
        if query.scope in {"trading", "task"}:
            task_scoped_event_types = EventType.task_scoped_values()
            if query.scope == "task":
                queryset = queryset.filter(
                    Q(details__kind__startswith="task_") | Q(event_type__in=task_scoped_event_types)
                )
            else:
                queryset = queryset.filter(
                    Q(details__kind__isnull=True) | ~Q(details__kind__startswith="task_")
                ).exclude(event_type__in=task_scoped_event_types)

        if query.execution.since:
            queryset = queryset.filter(created_at__gt=query.execution.since)
        if query.created_range.start:
            queryset = queryset.filter(created_at__gte=query.created_range.start)
        if query.created_range.end:
            queryset = queryset.filter(created_at__lte=query.created_range.end)

        paginator = ActivityPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[StrategyEventsQueryParamsSchemaSerializer],
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
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
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
        parameters=[TradesQueryParamsSchemaSerializer],
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
        query = TradesQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("timestamp")
        if query.direction:
            if query.direction == "buy":
                queryset = queryset.filter(direction="long")
            elif query.direction == "sell":
                queryset = queryset.filter(direction="short")
            else:
                queryset = queryset.filter(direction=query.direction)

        if query.execution.since:
            queryset = queryset.filter(updated_at__gt=query.execution.since)
        if query.timestamp_range.start:
            queryset = queryset.filter(timestamp__gte=query.timestamp_range.start)
        if query.timestamp_range.end:
            queryset = queryset.filter(timestamp__lte=query.timestamp_range.end)

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
        paginator = TradePositionPagination()
        page = paginator.paginate_queryset(normalized, request)
        serializer = TradeSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[PositionsQueryParamsSchemaSerializer],
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
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
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

        paginator = TradePositionPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = PositionSerializer(
            page,
            many=True,
            context={"include_trade_ids": query.include_trade_ids},
        )
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[TrendReplayQueryParamsSchemaSerializer],
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
        parameters=[OrdersQueryParamsSchemaSerializer],
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
        query = OrdersQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("-submitted_at")

        if query.status:
            queryset = queryset.filter(status=query.status)

        if query.order_type:
            queryset = queryset.filter(order_type=query.order_type)

        if query.direction:
            queryset = queryset.filter(direction=query.direction)

        if query.execution.since:
            queryset = queryset.filter(updated_at__gt=query.execution.since)

        paginator = TradePositionPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = OrderSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[SummaryQueryParamsSchemaSerializer],
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
        parameters=[ExecutionsQueryParamsSchemaSerializer],
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
        parameters=[ExecutionDetailQueryParamsSchemaSerializer],
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
