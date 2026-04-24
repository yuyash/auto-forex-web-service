"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

import json
from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.db.models.functions import Cast
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.views.throttles import TaskDataRateThrottle

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
    ExecutionDetailQueryParams,
    ExecutionDetailQueryParamsSchemaSerializer,
    ExecutionsQueryParams,
    ExecutionsQueryParamsSchemaSerializer,
    EventsQueryParams,
    EventsQueryParamsSchemaSerializer,
    LogComponentsQueryParams,
    LogComponentsQueryParamsSchemaSerializer,
    LogsQueryParams,
    LogsQueryParamsSchemaSerializer,
    MetricsQueryParams,
    MetricsQueryParamsSchemaSerializer,
    OrdersQueryParams,
    OrdersQueryParamsSchemaSerializer,
    PositionLifecycleQueryParams,
    PositionLifecycleQueryParamsSchemaSerializer,
    PositionQuery,
    PositionsQueryParamsSchemaSerializer,
    StrategyEventsQueryParams,
    StrategyEventsQueryParamsSchemaSerializer,
    SummaryQueryParams,
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
                    "data_source": serializers.CharField(),
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
    @action(
        detail=True, methods=["get"], url_path="metrics", throttle_classes=[TaskDataRateThrottle]
    )
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
                envelope = _paginated_envelope(request, data, total_count, page, page_size)
                envelope["data_source"] = "db_window_last_python"
                return Response(envelope)

            # Build a sub-query that buckets timestamps into N-minute windows
            # and picks the last metrics JSON per window.
            base_where = "task_type = %s AND task_id = %s"
            where_params: list = [self.task_type_label, str(task.pk)]

            if query.execution.execution_id is None:
                base_where += " AND execution_id IS NULL"
            else:
                base_where += " AND execution_id = %s"
                where_params.append(str(query.execution.execution_id))

            if query.execution.since:
                base_where += " AND timestamp > %s"
                where_params.append(query.execution.since)
            if query.until:
                base_where += " AND timestamp < %s"
                where_params.append(query.until)

            interval_seconds = interval * 60
            page, page_size = (
                query.execution.pagination.page,
                query.execution.pagination.page_size,
            )
            offset = (page - 1) * page_size

            # base_where is assembled from fixed clauses; all user values use cursor params.
            count_sql = (
                "SELECT COUNT(*) "  # nosec B608
                "FROM ("
                "  SELECT FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) AS bucket "
                "  FROM metrics "
                f"  WHERE {base_where} "
                "  GROUP BY bucket"
                ") sub"
            )

            sql = (
                "SELECT DISTINCT ON (bucket) "  # nosec B608
                "  timestamp, metrics "
                "FROM ("
                "  SELECT timestamp, metrics, "
                "    FLOOR(EXTRACT(EPOCH FROM timestamp) / %s) AS bucket "
                "  FROM metrics "
                f"  WHERE {base_where}"
                ") sub "
                "ORDER BY bucket, timestamp DESC "
                "LIMIT %s OFFSET %s"
            )

            with connection.cursor() as cursor:
                cursor.execute(count_sql, [interval_seconds, *where_params])
                total_count = int(cursor.fetchone()[0])
                cursor.execute(sql, [interval_seconds, *where_params, page_size, offset])
                rows = cursor.fetchall()

            data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in rows]
            envelope = _paginated_envelope(request, data, total_count, page, page_size)
            envelope["data_source"] = "db_window_last"
            return Response(envelope)

        # Default: interval=1, use ORM with cursor pagination
        total_count = queryset.count()
        page, page_size = (
            query.execution.pagination.page,
            query.execution.pagination.page_size,
        )
        start = (page - 1) * page_size
        rows = queryset.values_list("timestamp", "metrics")[start : start + page_size]

        data = [{"t": int(ts.timestamp()), "metrics": _ensure_dict(m)} for ts, m in rows]
        envelope = _paginated_envelope(request, data, total_count, page, page_size)
        envelope["data_source"] = "db_raw"
        return Response(envelope)

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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
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
            # Also match on original_position_id so that rebuild chains are
            # visible when searching by either the original or rebuilt ID.
            from django.db.models import Q
            from django.db.models.fields.json import KeyTextTransform

            queryset = queryset.annotate(
                _pos_id=KeyTextTransform("position_id", KeyTextTransform("context", "details")),
                _orig_pos_id=KeyTextTransform(
                    "original_position_id", KeyTextTransform("context", "details")
                ),
            ).filter(
                Q(_pos_id__startswith=query.position_id)
                | Q(_orig_pos_id__startswith=query.position_id)
            )
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
    @action(
        detail=True,
        methods=["get"],
        url_path="log-components",
        throttle_classes=[TaskDataRateThrottle],
    )
    def log_components(self, request: Request, pk: int | None = None) -> Response:
        """Return distinct component names for the task's logs."""
        task = self.get_object()  # type: ignore[attr-defined]
        query = LogComponentsQueryParams.from_request(
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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
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
                "TaskStrategyCyclesResponse",
                fields={
                    "execution_id": serializers.CharField(allow_null=True),
                    "cycles": serializers.ListField(child=serializers.JSONField()),
                    "summary": serializers.JSONField(),
                },
            )
        },
        description="Retrieve strategy cycles built from Trade.cycle_id.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="strategy-events",
        throttle_classes=[TaskDataRateThrottle],
    )
    def strategy_events(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.services.strategy_cycles import StrategyCyclesService

        task = self.get_object()  # type: ignore[attr-defined]
        query = StrategyEventsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        cycle_id = request.query_params.get("cycle_id")
        response = StrategyCyclesService().build(
            task=task,
            task_type=self.task_type_label,
            execution_id=query.execution_id,
            cycle_id=cycle_id,
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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
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
        )
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

        # Optional cycle_id filter
        if query.cycle_id:
            queryset = queryset.filter(cycle_id=query.cycle_id)

        # Optional trade_id prefix filter (e.g. first 8 chars of UUID).
        if query.trade_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.trade_id)

        ordering = ("-timestamp", "-sequence_number")
        if query.ordering == "asc":
            ordering = ("timestamp", "sequence_number")
        queryset = queryset.order_by(*ordering)

        total_count = queryset.count()
        page, page_size = (
            query.execution.pagination.page,
            query.execution.pagination.page_size,
        )
        start = (page - 1) * page_size
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
            "order_id",
            "oanda_trade_id",
            "cycle_id",
            "replayed_at",
            "updated_at",
            "is_rebuild",
            stop_loss_price=models.F("position__stop_loss_price"),
            entry_price=models.F("position__entry_price"),
        )[start : start + page_size]
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
            trade["pnl"] = None
            if trade["execution_method"] not in {"open_position", "rebuild_position"}:
                entry_price = trade.pop("entry_price", None)
                if entry_price is not None and trade["price"] is not None:
                    entry = Decimal(str(entry_price))
                    exit_price = Decimal(str(trade["price"]))
                    units = abs(int(trade["units"]))
                    if trade["direction"] == "buy":
                        trade["pnl"] = exit_price - entry
                    elif trade["direction"] == "sell":
                        trade["pnl"] = entry - exit_price
                    if trade["pnl"] is not None:
                        trade["pnl"] *= units
            else:
                trade.pop("entry_price", None)
            normalized.append(trade)
        serializer = TradeSerializer(normalized, many=True)
        return Response(_paginated_envelope(request, serializer.data, total_count, page, page_size))

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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def positions(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.positions import Position

        task = self.get_object()  # type: ignore[attr-defined]
        query = PositionQuery.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )
        queryset = (
            Position.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
                execution_id=query.execution.execution_id,
            )
            .prefetch_related("trades")
            .order_by("-entry_time")
        )

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

        # Optional cycle_id filter — positions linked via trades
        if query.cycle_id:
            queryset = queryset.filter(trades__cycle_id=query.cycle_id).distinct()

        # Optional position_id prefix filter (e.g. first 8 chars of UUID).
        if query.position_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.position_id)

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
        parameters=[PositionLifecycleQueryParamsSchemaSerializer],
        responses={
            200: inline_serializer(
                "TaskPositionLifecycleResponse",
                fields={
                    "requested_position_id": serializers.CharField(),
                    "matched_position_id": serializers.UUIDField(),
                    "position_ids": serializers.ListField(child=serializers.UUIDField()),
                    "positions": serializers.ListField(child=serializers.DictField()),
                    "chain_realized_pnl": serializers.CharField(allow_null=True),
                },
            )
        },
        description="Retrieve the full lifecycle chain for one position, including rebuild links.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="position-lifecycle",
        throttle_classes=[TaskDataRateThrottle],
    )
    def position_lifecycle(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.position_lifecycle import (
            PositionLifecycleQuery,
            PositionLifecycleService,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        query = PositionLifecycleQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        try:
            payload = PositionLifecycleService().build(
                PositionLifecycleQuery(
                    task_type=self.task_type_label,
                    task_id=task.pk,
                    execution_id=query.execution_id,
                    position_id_query=query.position_id,
                )
            )
        except ValueError as exc:
            raise ValidationError(
                {"code": "invalid_query_param", "detail": "Invalid query parameters."}
            ) from exc
        return Response(payload)

    @extend_schema(
        tags=["Trading"],
        parameters=[TrendReplayQueryParamsSchemaSerializer],
        responses={200: TaskTrendReplaySerializer},
        description="Retrieve chart-oriented trades and positions for task trend replay.",
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="trend-replay",
        throttle_classes=[TaskDataRateThrottle],
    )
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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
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

        # Optional order_id prefix filter (e.g. first 8 chars of UUID).
        if query.order_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.order_id)

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
    @action(
        detail=True, methods=["get"], url_path="summary", throttle_classes=[TaskDataRateThrottle]
    )
    def summary(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve comprehensive task summary."""
        from dataclasses import asdict

        from apps.trading.services.summary import compute_cached_task_summary

        task = self.get_object()  # type: ignore[attr-defined]
        query = SummaryQueryParams.from_request(
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
    @action(detail=True, methods=["get"], throttle_classes=[TaskDataRateThrottle])
    def executions(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.services.executions import list_task_executions

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionsQueryParams.from_request(
            request,
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
        )
        total_count, rows = list_task_executions(
            task=task,
            task_type=self.task_type_label,
            include_metrics=query.include_metrics,
            page=query.pagination.page,
            page_size=query.pagination.page_size,
        )
        serializer = TaskExecutionSerializer(rows, many=True)
        return Response(
            _paginated_envelope(
                request,
                serializer.data,
                total_count,
                query.pagination.page,
                query.pagination.page_size,
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
        throttle_classes=[TaskDataRateThrottle],
    )
    def execution_detail(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        from apps.trading.services.executions import get_task_execution

        task = self.get_object()  # type: ignore[attr-defined]
        query = ExecutionDetailQueryParams.from_request(request)
        row = get_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
            include_metrics=query.include_metrics,
        )
        if row is None:
            return Response({"detail": "Execution not found."}, status=404)
        serializer = TaskExecutionSerializer(row)
        return Response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        responses={204: None},
        description="Delete execution records for a task.",
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"executions/(?P<execution_id>[^/.]+)/delete",
        throttle_classes=[TaskDataRateThrottle],
    )
    def delete_execution(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        """Delete a single execution and all its associated data."""
        from apps.trading.services.executions import delete_task_execution

        task = self.get_object()  # type: ignore[attr-defined]
        deleted = delete_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
        )
        if not deleted:
            return Response({"detail": "Execution not found."}, status=404)
        return Response(status=204)

    @extend_schema(
        tags=["Trading"],
        request=inline_serializer(
            "ExecutionNotesRequest",
            fields={
                "notes": serializers.CharField(allow_blank=True),
            },
        ),
        responses={200: TaskExecutionSerializer},
        description="Update notes for an execution.",
    )
    @action(
        detail=True,
        methods=["patch"],
        url_path=r"executions/(?P<execution_id>[^/.]+)/notes",
        throttle_classes=[TaskDataRateThrottle],
    )
    def update_execution_notes(
        self, request: Request, pk: str | None = None, execution_id: str | None = None
    ) -> Response:
        """Update notes for a specific execution."""
        from apps.trading.services.executions import (
            get_task_execution,
            update_execution_notes,
        )

        task = self.get_object()  # type: ignore[attr-defined]
        notes = request.data.get("notes", "")
        update_execution_notes(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            execution_id=execution_id or "",
            notes=str(notes),
        )
        row = get_task_execution(
            task=task,
            task_type=self.task_type_label,
            execution_id=execution_id or "",
            include_metrics=False,
        )
        if row is None:
            return Response({"detail": "Execution not found."}, status=404)
        serializer = TaskExecutionSerializer(row)
        return Response(serializer.data)
