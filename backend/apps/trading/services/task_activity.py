"""Query services for task activity resources such as trades and positions."""

from __future__ import annotations

from decimal import Decimal

from django.db import models
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast
from rest_framework.request import Request

from apps.trading.enums import EventType, LogLevel
from apps.trading.models import TradingEvent
from apps.trading.models.logs import TaskLog
from apps.trading.models.orders import Order
from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade
from apps.trading.views.pagination import ActivityPagination, TradePositionPagination
from apps.trading.views.query_params import (
    EventsQueryParams,
    LogComponentsQueryParams,
    LogsQueryParams,
    OrdersQueryParams,
    PositionQuery,
    TradesQueryParams,
)


class TaskActivityQueryService:
    """Build querysets and rows for task activity endpoints."""

    def logs_queryset(self, *, request: Request, task, task_type_label: str):
        query = LogsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
        )
        queryset = TaskLog.objects.filter(
            task_type=task_type_label,
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
        return queryset.order_by("-timestamp")

    @staticmethod
    def log_components(*, request: Request, task, task_type_label: str) -> list[str]:
        query = LogComponentsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        return list(
            TaskLog.objects.filter(
                task_type=task_type_label,
                task_id=task.pk,
                execution_id=query.execution_id,
            )
            .values_list("component", flat=True)
            .distinct()
            .order_by("component")
        )

    def events_queryset(self, *, request: Request, task, task_type_label: str):
        query = EventsQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = TradingEvent.objects.filter(
            task_type=task_type_label,
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
        return queryset

    @staticmethod
    def orders_queryset(*, request: Request, task, task_type_label: str):
        query = OrdersQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )
        queryset = Order.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=query.execution.execution_id,
        ).order_by("-submitted_at")
        if query.status:
            queryset = queryset.filter(status=query.status)
        if query.order_type:
            queryset = queryset.filter(order_type=query.order_type)
        if query.direction:
            queryset = queryset.filter(direction=query.direction)
        if query.order_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.order_id)
        if query.execution.since:
            queryset = queryset.filter(updated_at__gt=query.execution.since)
        return queryset

    def trades(
        self, *, request: Request, task, task_type_label: str
    ) -> tuple[list[dict], int, int, int]:
        query = TradesQueryParams.from_request(
            request,
            default_execution_id=task.execution_id,
        )
        queryset = Trade.objects.filter(
            task_type=task_type_label,
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
        if query.cycle_id:
            queryset = queryset.filter(cycle_id=query.cycle_id)
        if query.trade_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.trade_id)

        ordering = ("-timestamp", "-sequence_number")
        if query.ordering == "asc":
            ordering = ("timestamp", "sequence_number")
        queryset = queryset.order_by(*ordering)

        total_count = queryset.count()
        page = query.execution.pagination.page
        page_size = query.execution.pagination.page_size
        start = (page - 1) * page_size
        rows = queryset.values(
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
        return self._normalize_trade_rows(rows), total_count, page, page_size

    @staticmethod
    def positions_queryset(*, request: Request, task, task_type_label: str):
        query = PositionQuery.from_request(
            request,
            default_execution_id=task.execution_id,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )
        queryset = (
            Position.objects.filter(
                task_type=task_type_label,
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
        if query.cycle_id:
            queryset = queryset.filter(trades__cycle_id=query.cycle_id).distinct()
        if query.position_id:
            queryset = queryset.annotate(
                _id_str=Cast("id", output_field=models.CharField())
            ).filter(_id_str__istartswith=query.position_id)

        return queryset, query

    @staticmethod
    def _normalize_trade_rows(rows) -> list[dict]:
        normalized: list[dict] = []
        for trade in rows:
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
        return normalized
