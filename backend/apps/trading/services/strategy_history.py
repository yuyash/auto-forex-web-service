"""History-row projection for strategy data endpoints."""

from __future__ import annotations

from typing import Any

from apps.trading.models.events import StrategyEventRecord, TradingEvent
from apps.trading.models.trades import Trade
from apps.trading.services.strategy_data_common import (
    StrategyDataQuery,
    granularity_seconds,
    json_value,
)


def load_history_rows(
    *,
    task: Any,
    task_type_label: str,
    query: StrategyDataQuery,
    strategy_type: str,
    strategy_state: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_trade_history_rows(task=task, task_type_label=task_type_label, query=query))
    rows.extend(
        _event_history_rows(TradingEvent, task=task, task_type_label=task_type_label, query=query)
    )
    rows.extend(
        _event_history_rows(
            StrategyEventRecord,
            task=task,
            task_type_label=task_type_label,
            query=query,
        )
    )
    return rows


def apply_history_filters(
    rows: list[dict[str, Any]], query: StrategyDataQuery
) -> list[dict[str, Any]]:
    filtered = []
    for row in rows:
        if row.get("t") is None:
            continue
        if (
            query.category != "all"
            and row.get("category") != query.category
            and row.get("source") != query.category
        ):
            continue
        filtered.append(row)
    filtered = _aggregate_history_rows(filtered, query.granularity)
    reverse = query.ordering.startswith("-")
    filtered.sort(key=lambda row: int(row.get("t") or 0), reverse=reverse)
    return filtered


def _trade_history_rows(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> list[dict[str, Any]]:
    qs = Trade.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=query.execution_id,
    )
    if query.since:
        qs = qs.filter(timestamp__gte=query.since)
    if query.until:
        qs = qs.filter(timestamp__lte=query.until)
    rows = []
    for trade in qs.order_by("timestamp").values(
        "id",
        "timestamp",
        "direction",
        "units",
        "price",
        "execution_method",
        "cycle_id",
        "position_id",
        "description",
    ):
        ts = trade["timestamp"]
        rows.append(
            {
                "id": f"trade:{trade['id']}",
                "timestamp": ts.isoformat() if ts else None,
                "t": int(ts.timestamp()) if ts else None,
                "source": "trade",
                "category": "trade",
                "action": trade["execution_method"],
                "label": trade["execution_method"],
                "details": {k: json_value(v) for k, v in trade.items()},
            }
        )
    return rows


def _event_history_rows(
    model: Any, *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> list[dict[str, Any]]:
    qs = model.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=query.execution_id,
    )
    if query.since:
        qs = qs.filter(event_timestamp__gte=query.since)
    if query.until:
        qs = qs.filter(event_timestamp__lte=query.until)
    source = "strategy_event" if model is StrategyEventRecord else "trading_event"
    rows = []
    for event in qs.order_by("event_timestamp", "sequence_number").values(
        "id",
        "event_type",
        "severity",
        "description",
        "event_timestamp",
        "details",
        "sequence_number",
        "visual_group_id",
        "root_entry_id",
        "position_id",
    ):
        ts = event["event_timestamp"]
        rows.append(
            {
                "id": f"{source}:{event['id']}",
                "timestamp": ts.isoformat() if ts else None,
                "t": int(ts.timestamp()) if ts else None,
                "source": source,
                "category": "event",
                "action": event["event_type"],
                "label": event["event_type"],
                "severity": event["severity"],
                "details": {k: json_value(v) for k, v in event.items() if k != "description"},
            }
        )
    return rows


def _aggregate_history_rows(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    seconds = granularity_seconds(granularity)
    if seconds is None:
        return rows
    bucketed: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        bucket = int(row["t"]) // seconds * seconds
        bucketed[(bucket, str(row.get("source") or ""))] = row
    return list(bucketed.values())
