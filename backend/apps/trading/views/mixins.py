"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import LogLevel
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
from apps.trading.views.pagination import TaskSubResourcePagination


def _parse_since(request: Request):
    """Return a datetime from the ``since`` query-param, or *None*."""
    raw = request.query_params.get("since")
    if raw:
        return parse_datetime(raw)
    return None


def _parse_execution_run_id(request: Request) -> int | None:
    """Return execution_run_id from query param when valid."""
    raw = request.query_params.get("execution_run_id")
    if raw is None:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


class TaskSubResourceMixin:
    """Mixin providing paginated logs / events / trades actions."""

    task_type_label: str

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
            OpenApiParameter("max_points", int, description="Maximum number of points to return"),
        ],
        responses={
            200: inline_serializer(
                "TaskMetricsResponse",
                fields={
                    "metrics": serializers.ListField(
                        child=inline_serializer(
                            "TaskMetricPoint",
                            fields={
                                "t": serializers.IntegerField(),
                                "mr": serializers.FloatField(allow_null=True),
                                "atr": serializers.FloatField(allow_null=True),
                                "base": serializers.FloatField(allow_null=True),
                                "vt": serializers.FloatField(allow_null=True),
                            },
                        )
                    ),
                    "total": serializers.IntegerField(),
                    "returned": serializers.IntegerField(),
                },
            )
        },
        description="Retrieve time-series metrics for the task.",
    )
    @action(detail=True, methods=["get"], url_path="metrics")
    def metrics(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models.metrics import Metrics

        task = self.get_object()  # type: ignore[attr-defined]
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)

        max_points_raw = request.query_params.get("max_points")
        max_points = 10_000  # sensible default
        if max_points_raw is not None:
            try:
                max_points = max(100, min(int(max_points_raw), 100_000))
            except (ValueError, TypeError):
                pass

        queryset = Metrics.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_run_id=execution_run_id,
        ).order_by("timestamp")

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(timestamp__gt=since)

        total_count = queryset.count()

        if total_count <= max_points:
            # Small enough — return everything
            rows = list(
                queryset.values_list(
                    "timestamp",
                    "margin_ratio",
                    "current_atr",
                    "baseline_atr",
                    "volatility_threshold",
                )
            )
        else:
            # Down-sample: fetch only every Nth row using a window function.
            # We use raw SQL with ROW_NUMBER for efficient server-side stride.
            from django.db import connection

            stride = total_count // max_points

            # Build the filtered WHERE clause
            params: list = [self.task_type_label, str(task.pk), execution_run_id]

            sql = (
                "SELECT timestamp, margin_ratio, current_atr, baseline_atr, volatility_threshold "  # nosec B608
                "FROM ("
                "  SELECT timestamp, margin_ratio, current_atr, baseline_atr, volatility_threshold, "
                "         ROW_NUMBER() OVER (ORDER BY timestamp) AS rn "
                "  FROM metrics "
                "  WHERE task_type = %s AND task_id = %s AND execution_run_id = %s" + ") sub "
                "WHERE rn %% %s = 1 "
                "ORDER BY timestamp"
            )
            params.append(stride)

            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

        data = [
            {
                "t": int(ts.timestamp()),
                "mr": float(mr) if mr is not None else None,
                "atr": float(atr) if atr is not None else None,
                "base": float(base) if base is not None else None,
                "vt": float(vt) if vt is not None else None,
            }
            for ts, mr, atr, base, vt in rows
        ]
        return Response({"metrics": data, "total": total_count, "returned": len(data)})

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("level", str, description="Log level filter"),
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        level_param = request.query_params.get("level")
        level = LogLevel[level_param.upper()] if level_param else None
        queryset = TaskLog.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_run_id=execution_run_id,
        )
        if level:
            queryset = queryset.filter(level=level)

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
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter("event_type", str, description="Event type filter"),
            OpenApiParameter("severity", str, description="Severity filter"),
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        event_type = request.query_params.get("event_type")
        severity = request.query_params.get("severity")
        queryset = TradingEvent.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_run_id=execution_run_id,
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
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        tags=["Trading"],
        parameters=[
            OpenApiParameter("since", str, description="RFC3339 timestamp for incremental fetch"),
            OpenApiParameter(
                "direction", str, description="Direction filter (buy/sell/long/short)"
            ),
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        direction = (request.query_params.get("direction") or "").lower()
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_run_id=execution_run_id,
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
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        queryset = (
            Position.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
                execution_run_id=execution_run_id,
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
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
            execution_run_id=execution_run_id,
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
            OpenApiParameter("execution_run_id", int, description="Filter by execution run ID"),
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
        execution_run_id = _parse_execution_run_id(request)
        if execution_run_id is None:
            execution_run_id = int(getattr(task, "execution_run_id", 0) or 0)

        result = compute_task_summary(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            execution_run_id=execution_run_id,
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
