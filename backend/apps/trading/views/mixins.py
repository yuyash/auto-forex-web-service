"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response

from apps.trading.enums import LogLevel
from apps.trading.models.logs import TaskLog
from apps.trading.serializers.summary import TaskSummarySerializer
from apps.trading.views.pagination import TaskSubResourcePagination


def _parse_since(request: Request):
    """Return a datetime from the ``since`` query-param, or *None*."""
    raw = request.query_params.get("since")
    if raw:
        return parse_datetime(raw)
    return None


class TaskSubResourceMixin:
    """Mixin providing paginated logs / events / trades actions."""

    task_type_label: str

    @extend_schema(
        parameters=[
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "max_points",
                int,
                description="Max data points (100-100000, default 10000)",
            ),
            OpenApiParameter(
                "since",
                str,
                description="ISO datetime; return only records after this time",
            ),
        ],
        responses={
            200: inline_serializer(
                name="MetricsResponse",
                fields={
                    "metrics": drf_serializers.ListField(help_text="Array of metric data points"),
                    "total": drf_serializers.IntegerField(
                        help_text="Total number of metric records"
                    ),
                    "returned": drf_serializers.IntegerField(
                        help_text="Number of records returned"
                    ),
                },
            )
        },
        description="Retrieve time-series strategy metrics with optional downsampling.",
    )
    @action(detail=True, methods=["get"])
    def metrics(self, request: Request, pk: int | None = None) -> Response:
        """Retrieve time-series strategy metrics."""
        from apps.trading.models.metrics import Metrics

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")

        max_points_raw = request.query_params.get("max_points")
        max_points = 10_000
        if max_points_raw is not None:
            try:
                max_points = max(100, min(int(max_points_raw), 100_000))
            except (ValueError, TypeError):
                pass

        queryset = Metrics.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("timestamp")
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(timestamp__gt=since)

        total_count = queryset.count()

        if total_count <= max_points:
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
            from django.db import connection

            stride = total_count // max_points
            params: list = [self.task_type_label, str(task.pk)]
            celery_filter = ""
            if celery_task_id:
                celery_filter = " AND celery_task_id = %s"
                params.append(celery_task_id)

            sql = (
                "SELECT timestamp, margin_ratio, current_atr,"
                " baseline_atr, volatility_threshold "  # nosec B608
                "FROM ("
                "  SELECT timestamp, margin_ratio, current_atr,"
                " baseline_atr, volatility_threshold, "
                "         ROW_NUMBER() OVER (ORDER BY timestamp) AS rn "
                "  FROM metrics "
                "  WHERE task_type = %s AND task_id = %s" + celery_filter + ") sub "
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
        parameters=[
            OpenApiParameter(
                "level", str, description="Filter by log level (e.g., INFO, WARNING, ERROR)"
            ),
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "since", str, description="ISO datetime; return only records after this time"
            ),
        ],
        responses={
            200: inline_serializer(
                name="TaskLogPaginatedResponse",
                fields={
                    "count": drf_serializers.IntegerField(),
                    "next": drf_serializers.CharField(allow_null=True),
                    "previous": drf_serializers.CharField(allow_null=True),
                    "results": drf_serializers.ListField(
                        child=inline_serializer(
                            name="TaskLogItem",
                            fields={
                                "id": drf_serializers.IntegerField(),
                                "task_type": drf_serializers.CharField(),
                                "task_id": drf_serializers.CharField(),
                                "celery_task_id": drf_serializers.CharField(allow_null=True),
                                "timestamp": drf_serializers.DateTimeField(),
                                "level": drf_serializers.CharField(),
                                "component": drf_serializers.CharField(allow_null=True),
                                "message": drf_serializers.CharField(),
                                "details": drf_serializers.DictField(allow_null=True),
                            },
                        ),
                    ),
                },
            )
        },
        description="Retrieve task logs with pagination.",
    )
    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
        """Retrieve task logs with pagination."""
        from apps.trading.serializers.task import TaskLogSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        level_param = request.query_params.get("level")
        level = LogLevel[level_param.upper()] if level_param else None
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = TaskLog.objects.filter(task_type=self.task_type_label, task_id=task.pk)
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
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
        parameters=[
            OpenApiParameter("event_type", str, description="Filter by event type"),
            OpenApiParameter("severity", str, description="Filter by severity"),
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "since", str, description="ISO datetime; return only records after this time"
            ),
        ],
        responses={
            200: inline_serializer(
                name="TradingEventPaginatedResponse",
                fields={
                    "count": drf_serializers.IntegerField(),
                    "next": drf_serializers.CharField(allow_null=True),
                    "previous": drf_serializers.CharField(allow_null=True),
                    "results": drf_serializers.ListField(
                        child=inline_serializer(
                            name="TradingEventItem",
                            fields={
                                "id": drf_serializers.IntegerField(),
                                "event_type": drf_serializers.CharField(),
                                "event_type_display": drf_serializers.CharField(),
                                "severity": drf_serializers.CharField(),
                                "description": drf_serializers.CharField(),
                                "user": drf_serializers.IntegerField(allow_null=True),
                                "account": drf_serializers.IntegerField(allow_null=True),
                                "instrument": drf_serializers.CharField(allow_null=True),
                                "task_type": drf_serializers.CharField(),
                                "task_id": drf_serializers.CharField(),
                                "celery_task_id": drf_serializers.CharField(allow_null=True),
                                "details": drf_serializers.DictField(allow_null=True),
                                "created_at": drf_serializers.DateTimeField(),
                            },
                        ),
                    ),
                },
            )
        },
        description="Retrieve task events with pagination.",
    )
    @action(detail=True, methods=["get"])
    def events(self, request: Request, pk: int | None = None) -> Response:
        """Retrieve task events with pagination."""
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

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(created_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter("direction", str, description="Filter by direction (buy/sell)"),
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "since", str, description="ISO datetime; return only records after this time"
            ),
        ],
        responses={
            200: inline_serializer(
                name="TradePaginatedResponse",
                fields={
                    "count": drf_serializers.IntegerField(),
                    "next": drf_serializers.CharField(allow_null=True),
                    "previous": drf_serializers.CharField(allow_null=True),
                    "results": drf_serializers.ListField(
                        child=inline_serializer(
                            name="TradeItem",
                            fields={
                                "id": drf_serializers.UUIDField(),
                                "direction": drf_serializers.CharField(allow_null=True),
                                "units": drf_serializers.IntegerField(),
                                "instrument": drf_serializers.CharField(),
                                "price": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10
                                ),
                                "execution_method": drf_serializers.CharField(),
                                "execution_method_display": drf_serializers.CharField(),
                                "layer_index": drf_serializers.IntegerField(allow_null=True),
                                "retracement_count": drf_serializers.IntegerField(allow_null=True),
                                "timestamp": drf_serializers.DateTimeField(),
                                "position_id": drf_serializers.UUIDField(allow_null=True),
                                "updated_at": drf_serializers.DateTimeField(allow_null=True),
                            },
                        ),
                    ),
                },
            )
        },
        description="Retrieve trade history with pagination.",
    )
    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve trade history with pagination."""
        from apps.trading.models.trades import Trade
        from apps.trading.serializers.events import TradeSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        direction = (request.query_params.get("direction") or "").lower()
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = Trade.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("timestamp")
        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)
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
        parameters=[
            OpenApiParameter("position_status", str, description="Filter by status (open/closed)"),
            OpenApiParameter("direction", str, description="Filter by direction"),
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "since", str, description="ISO datetime; return only records after this time"
            ),
        ],
        responses={
            200: inline_serializer(
                name="PositionPaginatedResponse",
                fields={
                    "count": drf_serializers.IntegerField(),
                    "next": drf_serializers.CharField(allow_null=True),
                    "previous": drf_serializers.CharField(allow_null=True),
                    "results": drf_serializers.ListField(
                        child=inline_serializer(
                            name="PositionItem",
                            fields={
                                "id": drf_serializers.UUIDField(),
                                "instrument": drf_serializers.CharField(),
                                "direction": drf_serializers.CharField(),
                                "units": drf_serializers.IntegerField(),
                                "entry_price": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10
                                ),
                                "entry_time": drf_serializers.DateTimeField(),
                                "exit_price": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10, allow_null=True
                                ),
                                "exit_time": drf_serializers.DateTimeField(allow_null=True),
                                "is_open": drf_serializers.BooleanField(),
                                "layer_index": drf_serializers.IntegerField(allow_null=True),
                                "retracement_count": drf_serializers.IntegerField(allow_null=True),
                                "trade_ids": drf_serializers.ListField(
                                    child=drf_serializers.UUIDField()
                                ),
                                "updated_at": drf_serializers.DateTimeField(allow_null=True),
                            },
                        ),
                    ),
                },
            )
        },
        description="Retrieve positions with pagination.",
    )
    @action(detail=True, methods=["get"])
    def positions(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve positions with pagination."""
        from apps.trading.models.positions import Position
        from apps.trading.serializers.events import PositionSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = (
            Position.objects.filter(
                task_type=self.task_type_label,
                task_id=task.pk,
            )
            .prefetch_related("trades")
            .order_by("-entry_time")
        )

        if celery_task_id:
            queryset = queryset.filter(celery_task_id=celery_task_id)

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

    @extend_schema(
        parameters=[
            OpenApiParameter("status", str, description="Filter by order status"),
            OpenApiParameter("order_type", str, description="Filter by order type"),
            OpenApiParameter("direction", str, description="Filter by direction"),
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
            OpenApiParameter(
                "since", str, description="ISO datetime; return only records after this time"
            ),
        ],
        responses={
            200: inline_serializer(
                name="OrderPaginatedResponse",
                fields={
                    "count": drf_serializers.IntegerField(),
                    "next": drf_serializers.CharField(allow_null=True),
                    "previous": drf_serializers.CharField(allow_null=True),
                    "results": drf_serializers.ListField(
                        child=inline_serializer(
                            name="OrderItem",
                            fields={
                                "id": drf_serializers.UUIDField(),
                                "celery_task_id": drf_serializers.CharField(allow_null=True),
                                "broker_order_id": drf_serializers.CharField(allow_null=True),
                                "oanda_trade_id": drf_serializers.CharField(allow_null=True),
                                "position_id": drf_serializers.UUIDField(allow_null=True),
                                "instrument": drf_serializers.CharField(),
                                "order_type": drf_serializers.CharField(),
                                "direction": drf_serializers.CharField(allow_null=True),
                                "units": drf_serializers.IntegerField(),
                                "requested_price": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10, allow_null=True
                                ),
                                "fill_price": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10, allow_null=True
                                ),
                                "status": drf_serializers.CharField(),
                                "submitted_at": drf_serializers.DateTimeField(),
                                "filled_at": drf_serializers.DateTimeField(allow_null=True),
                                "cancelled_at": drf_serializers.DateTimeField(allow_null=True),
                                "stop_loss": drf_serializers.DecimalField(
                                    max_digits=20, decimal_places=10, allow_null=True
                                ),
                                "error_message": drf_serializers.CharField(allow_null=True),
                                "is_dry_run": drf_serializers.BooleanField(),
                            },
                        ),
                    ),
                },
            )
        },
        description="Retrieve orders with pagination.",
    )
    @action(detail=True, methods=["get"])
    def orders(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve orders with pagination."""
        from apps.trading.models.orders import Order
        from apps.trading.serializers.events import OrderSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("-submitted_at")

        effective_celery_id = celery_task_id or getattr(task, "celery_task_id", None)
        if effective_celery_id:
            queryset = queryset.filter(celery_task_id=effective_celery_id)

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
        parameters=[
            OpenApiParameter("celery_task_id", str, description="Filter by Celery task ID"),
        ],
        responses={200: TaskSummarySerializer},
        description=(
            "Retrieve comprehensive task summary including PnL, "
            "trade/position counts, execution state, and task status."
        ),
    )
    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request: Request, pk: str | None = None) -> Response:
        """Retrieve comprehensive task summary."""
        from apps.trading.services.summary import compute_task_summary

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")

        result = compute_task_summary(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            celery_task_id=celery_task_id,
        )

        serializer = TaskSummarySerializer(
            {
                "realized_pnl": result.realized_pnl,
                "unrealized_pnl": result.unrealized_pnl,
                "total_trades": result.total_trades,
                "open_position_count": result.open_position_count,
                "closed_position_count": result.closed_position_count,
                "current_balance": result.current_balance,
                "ticks_processed": result.ticks_processed,
                "last_tick_time": result.last_tick_time,
                "last_tick_price": result.last_tick_price,
                "status": result.status,
                "started_at": result.started_at,
                "completed_at": result.completed_at,
                "error_message": result.error_message,
                "progress": result.progress,
            }
        )
        return Response(serializer.data)
