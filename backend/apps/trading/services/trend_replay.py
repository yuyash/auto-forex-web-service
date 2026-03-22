"""Trend replay read-model for chart-oriented task views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db.models import Q, QuerySet

from apps.trading.models.positions import Position
from apps.trading.models.trades import Trade


DEFAULT_TREND_REPLAY_PAGE_SIZE = 500
MAX_TREND_REPLAY_PAGE_SIZE = 2000


@dataclass(frozen=True)
class TrendReplayQuery:
    """Query parameters for trend replay payload generation."""

    task_type: str
    task_id: str
    execution_id: str | None
    range_from: datetime | None
    range_to: datetime | None
    since: datetime | None
    page: int
    page_size: int


def build_trend_replay_payload(query: TrendReplayQuery) -> dict[str, Any]:
    """Return a combined trades/positions payload for the trend panel."""
    trades_qs = _build_trades_queryset(query)
    total_trades = trades_qs.count()
    offset = max(query.page - 1, 0) * query.page_size

    if query.range_from or query.range_to or query.since:
        paged_trades = list(trades_qs[offset : offset + query.page_size])
        mode = "windowed"
    else:
        paged_trades = list(
            reversed(list(trades_qs.order_by("-timestamp")[offset : offset + query.page_size]))
        )
        mode = "latest"

    latest_trade_updated_at = None
    for trade in paged_trades:
        if trade.updated_at and (
            latest_trade_updated_at is None or trade.updated_at > latest_trade_updated_at
        ):
            latest_trade_updated_at = trade.updated_at

    positions_qs = _build_positions_queryset(query)

    return {
        "trades": [_serialize_trade(trade) for trade in paged_trades],
        "positions": [_serialize_position(position) for position in positions_qs],
        "trade_markers": [_serialize_trade_marker(trade) for trade in paged_trades],
        "meta": {
            "mode": mode,
            "page": query.page,
            "page_size": query.page_size,
            "total_trades": total_trades,
            "returned_trades": len(paged_trades),
            "has_more_trades": offset + len(paged_trades) < total_trades,
            "latest_trade_updated_at": latest_trade_updated_at,
            "range_from": query.range_from,
            "range_to": query.range_to,
        },
    }


def _build_trades_queryset(query: TrendReplayQuery) -> QuerySet[Trade]:
    queryset = Trade.objects.filter(
        task_type=query.task_type,
        task_id=query.task_id,
        execution_id=query.execution_id,
    ).order_by("timestamp")
    if query.since:
        queryset = queryset.filter(updated_at__gt=query.since)
    if query.range_from:
        queryset = queryset.filter(timestamp__gte=query.range_from)
    if query.range_to:
        queryset = queryset.filter(timestamp__lte=query.range_to)
    return queryset


def _build_positions_queryset(query: TrendReplayQuery) -> QuerySet[Position]:
    queryset = (
        Position.objects.filter(
            task_type=query.task_type,
            task_id=query.task_id,
            execution_id=query.execution_id,
        )
        .order_by("-entry_time")
        .prefetch_related("trades")
    )
    if query.range_to:
        queryset = queryset.filter(entry_time__lte=query.range_to)
    if query.range_from:
        queryset = queryset.filter(Q(exit_time__isnull=True) | Q(exit_time__gte=query.range_from))
    if query.since:
        queryset = queryset.filter(updated_at__gt=query.since)
    return queryset


def _serialize_trade(trade: Trade) -> dict[str, Any]:
    direction = trade.direction
    if direction == "long":
        direction = "buy"
    elif direction == "short":
        direction = "sell"

    return {
        "id": trade.id,
        "direction": direction,
        "units": trade.units,
        "instrument": trade.instrument,
        "price": trade.price,
        "execution_method": trade.execution_method,
        "layer_index": trade.layer_index,
        "retracement_count": trade.retracement_count,
        "description": trade.description,
        "timestamp": trade.timestamp,
        "position_id": trade.position.pk if trade.position else None,
        "updated_at": trade.updated_at,
    }


def _serialize_position(position: Position) -> dict[str, Any]:
    return {
        "id": position.id,
        "instrument": position.instrument,
        "direction": position.direction,
        "units": position.units,
        "entry_price": position.entry_price,
        "entry_time": position.entry_time,
        "exit_price": position.exit_price,
        "exit_time": position.exit_time,
        "is_open": position.is_open,
        "layer_index": position.layer_index,
        "retracement_count": position.retracement_count,
        "planned_exit_price": position.planned_exit_price,
        "planned_exit_price_formula": position.planned_exit_price_formula,
        "trade_ids": list(Trade.objects.filter(position=position).values_list("id", flat=True)),
        "updated_at": position.updated_at,
    }


def _serialize_trade_marker(trade: Trade) -> dict[str, Any]:
    units = int(trade.units)
    execution_method = str(trade.execution_method or "").lower()
    is_close = execution_method in {
        "take_profit",
        "margin_protection",
        "volatility_lock",
        "close_position",
        "volatility_hedge_neutralize",
    }
    if trade.direction in {"long", "short"}:
        direction = trade.direction
    else:
        direction = "short" if units < 0 else "long"
    lots = abs(units) // 1000 if units else None
    lot_label = "" if lots is None else f"{lots}L"
    direction_label = direction.upper()
    label = (
        f"CLOSE {direction_label} {lot_label}".strip()
        if is_close
        else f"OPEN {direction_label} {lot_label}".strip()
    )
    return {
        "trade_id": trade.id,
        "timestamp": trade.timestamp,
        "direction": direction,
        "action": "close" if is_close else "open",
        "lots": lots,
        "label": label,
    }
