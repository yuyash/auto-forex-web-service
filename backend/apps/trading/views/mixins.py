"""Shared mixins for task viewsets.

Extracts common paginated action logic (logs, events, trades, positions)
used by both BacktestTaskViewSet and TradingTaskViewSet.
"""

from __future__ import annotations

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiParameter, extend_schema
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

    @action(detail=True, methods=["get"], url_path="metrics")
    def metric_snapshots(self, request: Request, pk: int | None = None) -> Response:
        from apps.trading.models.metrics import Metrics as MetricSnapshot

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")

        max_points_raw = request.query_params.get("max_points")
        max_points = 10_000  # sensible default
        if max_points_raw is not None:
            try:
                max_points = max(100, min(int(max_points_raw), 100_000))
            except (ValueError, TypeError):
                pass

        queryset = MetricSnapshot.objects.filter(
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
            params: list = [self.task_type_label, str(task.pk)]
            celery_filter = ""
            if celery_task_id:
                celery_filter = " AND celery_task_id = %s"
                params.append(celery_task_id)

            sql = (
                "SELECT timestamp, margin_ratio, current_atr, baseline_atr, volatility_threshold "  # nosec B608
                "FROM ("
                "  SELECT timestamp, margin_ratio, current_atr, baseline_atr, volatility_threshold, "
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
        return Response({"snapshots": data, "total": total_count, "returned": len(data)})

    @action(detail=True, methods=["get"])
    def logs(self, request: Request, pk: int | None = None) -> Response:
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

        since = _parse_since(request)
        if since:
            queryset = queryset.filter(created_at__gt=since)

        paginator = TaskSubResourcePagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = TradingEventSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)

    @action(detail=True, methods=["get"])
    def trades(self, request: Request, pk: str | None = None) -> Response:
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

    @action(detail=True, methods=["get"])
    def positions(self, request: Request, pk: str | None = None) -> Response:
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

    # ------------------------------------------------------------------
    # orders (with incremental fetching via `since`)
    # ------------------------------------------------------------------
    @action(detail=True, methods=["get"])
    def orders(self, request: Request, pk: str | None = None) -> Response:
        from apps.trading.models.orders import Order
        from apps.trading.serializers.events import OrderSerializer

        task = self.get_object()  # type: ignore[attr-defined]
        celery_task_id = request.query_params.get("celery_task_id")
        queryset = Order.objects.filter(
            task_type=self.task_type_label,
            task_id=task.pk,
        ).order_by("-submitted_at")

        # Filter by celery execution ID: use explicit param, fall back to task's current ID.
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
        celery_task_id = request.query_params.get("celery_task_id")

        result = compute_task_summary(
            task_type=self.task_type_label,
            task_id=str(task.pk),
            celery_task_id=celery_task_id,
        )

        serializer = TaskSummarySerializer(asdict(result))
        return Response(serializer.data)
