"""Strategy data APIs split by concern: snapshot, history, and metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.trading.models.events import StrategyEventRecord, TradingEvent
from apps.trading.models.metrics import ExecutionMetricAggregate, Metrics
from apps.trading.models.state import ExecutionState
from apps.trading.models.trades import Trade
from apps.trading.services.task_metrics import ensure_metrics_dict, filter_metrics


DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 5000


@dataclass(frozen=True)
class StrategyDataQuery:
    execution_id: Any
    since: datetime | None
    until: datetime | None
    page: int
    page_size: int
    ordering: str
    granularity: str
    category: str
    metric_keys: tuple[str, ...]


class StrategyDataService:
    """Build strategy-facing data payloads independent from page layout."""

    def snapshot(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        strategy_state = context["strategy_state"]
        strategy_type = context["strategy_type"]
        snapshot = _build_strategy_snapshot(strategy_type, strategy_state)
        return {
            "execution_id": _string_or_none(query.execution_id),
            "strategy_type": strategy_type,
            "instrument": getattr(task, "instrument", None),
            "timestamp": context["last_tick_timestamp"],
            "snapshot": snapshot,
        }

    def history(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        rows = _load_history_rows(
            task=task,
            task_type_label=task_type_label,
            query=query,
            strategy_type=context["strategy_type"],
            strategy_state=context["strategy_state"],
        )
        rows = _apply_history_filters(rows, query)
        rows, pagination = _page_rows(request=request, rows=rows, query=query)
        return {
            "execution_id": _string_or_none(query.execution_id),
            "strategy_type": context["strategy_type"],
            "instrument": getattr(task, "instrument", None),
            **pagination,
            "results": rows,
        }

    def metrics(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        points = _load_metric_points(task=task, task_type_label=task_type_label, query=query)
        points = _aggregate_metric_points(points, query.granularity)
        points, pagination = _page_rows(request=request, rows=points, query=query)
        return {
            "execution_id": _string_or_none(query.execution_id),
            "strategy_type": context["strategy_type"],
            "instrument": getattr(task, "instrument", None),
            "data_source": "strategy_metrics",
            "resume_cursor_timestamp": context["resume_cursor_timestamp"],
            "consistency_warnings": _metric_consistency_warnings(
                task=task,
                task_type_label=task_type_label,
                execution_id=query.execution_id,
            ),
            "ohlc_layers": _build_ohlc_layers(
                strategy_type=context["strategy_type"],
                strategy_state=context["strategy_state"],
                since=query.since.isoformat() if query.since else None,
                until=query.until.isoformat() if query.until else None,
                granularity=query.granularity,
                page=query.page,
                page_size=query.page_size,
                ordering=query.ordering,
            ),
            **pagination,
            "results": points,
        }


def _query_from_request(request: Request, *, default_execution_id: Any) -> StrategyDataQuery:
    params = request.query_params
    execution_id = params.get("execution_id") or default_execution_id
    since = _parse_datetime(params.get("since") or params.get("timestamp_from"))
    until = _parse_datetime(params.get("until") or params.get("timestamp_to"))
    if since and until and since > until:
        raise ValidationError("since must be earlier than until.")
    page = _positive_int(params.get("page"), 1)
    page_size = min(_positive_int(params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    ordering = str(params.get("ordering") or "timestamp")
    if ordering not in {"timestamp", "-timestamp"}:
        raise ValidationError("ordering must be 'timestamp' or '-timestamp'.")
    granularity = _normalise_granularity(params.get("granularity") or params.get("interval"))
    category = str(params.get("category") or "all").strip() or "all"
    metric_keys = tuple(
        key.strip() for key in str(params.get("metric_keys") or "").split(",") if key.strip()
    )
    return StrategyDataQuery(
        execution_id=execution_id,
        since=since,
        until=until,
        page=page,
        page_size=page_size,
        ordering=ordering,
        granularity=granularity,
        category=category,
        metric_keys=metric_keys,
    )


def _load_context(*, task: Any, task_type_label: str, query: StrategyDataQuery) -> dict[str, Any]:
    state = (
        ExecutionState.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=query.execution_id,
        )
        .values("strategy_state", "last_tick_timestamp", "resume_cursor_timestamp")
        .first()
    )
    strategy_state = state.get("strategy_state") if state else None
    if not isinstance(strategy_state, dict):
        strategy_state = {}
    return {
        "strategy_type": str(getattr(task.config, "strategy_type", "") or ""),
        "strategy_state": strategy_state,
        "last_tick_timestamp": state["last_tick_timestamp"].isoformat()
        if state and state.get("last_tick_timestamp")
        else None,
        "resume_cursor_timestamp": state["resume_cursor_timestamp"].isoformat()
        if state and state.get("resume_cursor_timestamp")
        else None,
    }


def _build_strategy_snapshot(strategy_type: str, state: dict[str, Any]) -> dict[str, Any]:
    if strategy_type == "net_grid":
        keys = [
            "current_net_units",
            "target_net_units",
            "open_direction",
            "average_entry_price",
            "last_grid_price",
            "next_grid_price",
            "net_take_profit_price",
            "risk_exit_price",
            "current_adverse_pips",
            "current_favorable_pips",
            "current_unrealized_pnl",
            "step",
            "step_usage",
            "max_steps",
            "broker_reconciliation_status",
            "broker_reconciliation_warnings",
            "broker_reconciliation_blockers",
        ]
        return {
            "status": _net_grid_status(state),
            "cards": _cards_from_state(state, keys),
            "state": {key: state.get(key) for key in keys if key in state},
        }
    if strategy_type == "snowball":
        return _snowball_snapshot(state)
    return {"status": "unknown", "cards": [], "state": {}}


def _net_grid_status(state: dict[str, Any]) -> str:
    if state.get("pending_execution"):
        return "pending_execution"
    if int(state.get("current_net_units") or 0) != 0:
        return "open"
    return "flat"


def _snowball_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    try:
        from apps.trading.strategies.snowball.models import SnowballStrategyState

        parsed = SnowballStrategyState.from_strategy_state(state)
        active = len(parsed.active_cycles())
        pending = len([cycle for cycle in parsed.cycles if cycle.is_pending])
        completed = len([cycle for cycle in parsed.cycles if cycle.completed])
        open_entries = sum(len(cycle.all_entries()) for cycle in parsed.active_cycles())
        values = {
            "protection_level": parsed.protection_level.value,
            "active_cycles": active,
            "pending_cycles": pending,
            "completed_cycles": completed,
            "open_entries": open_entries,
            "account_balance": str(parsed.account_balance),
            "account_nav": str(parsed.account_nav),
            "last_mid": str(parsed.last_mid) if parsed.last_mid is not None else None,
            "lock_entered_at": parsed.lock_entered_at,
            "cooldown_until": parsed.cooldown_until,
            "margin_ratio": parsed.metrics.get("margin_ratio"),
        }
    except Exception:  # noqa: BLE001
        values = {
            "protection_level": state.get("protection_level"),
            "active_cycles": len(state.get("cycles") or []),
            "account_nav": state.get("account_nav"),
            "last_mid": state.get("last_mid"),
        }
    return {
        "status": str(values.get("protection_level") or "unknown"),
        "cards": _cards_from_state(values, tuple(values.keys())),
        "state": values,
    }


def _cards_from_state(state: dict[str, Any], keys: Any) -> list[dict[str, Any]]:
    return [
        {"id": key, "label_key": f"strategy.snapshot.{key}", "value": state.get(key)}
        for key in keys
        if state.get(key) not in (None, "")
    ]


def _load_history_rows(
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
    if strategy_type == "net_grid":
        rows.extend(_net_grid_state_history_rows(strategy_state))
    return rows


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
                "details": {k: _json_value(v) for k, v in trade.items()},
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
                "details": {k: _json_value(v) for k, v in event.items() if k != "description"},
            }
        )
    return rows


def _net_grid_state_history_rows(state: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source, entries in (
        ("net_grid_ledger", state.get("grid_ledger")),
        ("net_grid_decision", state.get("decision_history")),
        ("net_grid_trend", state.get("trend_relation_history")),
    ):
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                continue
            timestamp = entry.get("timestamp")
            parsed = _parse_datetime(str(timestamp)) if timestamp else None
            rows.append(
                {
                    "id": f"{source}:{index}",
                    "timestamp": str(timestamp) if timestamp else None,
                    "t": int(parsed.timestamp()) if parsed else None,
                    "source": source,
                    "category": "calculation" if source != "net_grid_ledger" else "operation",
                    "action": str(entry.get("action") or entry.get("relation") or source),
                    "label": str(entry.get("reason") or entry.get("action") or source),
                    "details": entry,
                }
            )
    return rows


def _apply_history_filters(
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


def _aggregate_history_rows(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    seconds = _granularity_seconds(granularity)
    if seconds is None:
        return rows
    bucketed: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        bucket = int(row["t"]) // seconds * seconds
        bucketed[(bucket, str(row.get("source") or ""))] = row
    return list(bucketed.values())


def _load_metric_points(
    *, task: Any, task_type_label: str, query: StrategyDataQuery
) -> list[dict[str, Any]]:
    qs = Metrics.objects.filter(
        task_type=task_type_label,
        task_id=task.pk,
        execution_id=query.execution_id,
    )
    if query.since:
        qs = qs.filter(timestamp__gte=query.since)
    if query.until:
        qs = qs.filter(timestamp__lte=query.until)
    return [
        {
            "t": int(timestamp.timestamp()),
            "timestamp": timestamp.isoformat(),
            "metrics": filter_metrics(ensure_metrics_dict(metrics), query.metric_keys),
        }
        for timestamp, metrics in qs.order_by("timestamp").values_list("timestamp", "metrics")
    ]


def _aggregate_metric_points(rows: list[dict[str, Any]], granularity: str) -> list[dict[str, Any]]:
    seconds = _granularity_seconds(granularity)
    if seconds is None:
        return rows
    bucketed: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = int(row["t"]) // seconds * seconds
        bucketed[bucket] = row
    return [bucketed[key] for key in sorted(bucketed)]


def _build_ohlc_layers(
    *,
    strategy_type: str,
    strategy_state: dict[str, Any],
    since: str | None,
    until: str | None,
    granularity: str,
    page: int,
    page_size: int,
    ordering: str,
) -> dict[str, Any]:
    if strategy_type != "net_grid":
        return _empty_ohlc_layers()
    return _net_grid_ohlc_layers(
        strategy_state,
        since=_parse_datetime(since),
        until=_parse_datetime(until),
        granularity=granularity,
        page=page,
        page_size=page_size,
        ordering=ordering,
    )


def _empty_ohlc_layers() -> dict[str, Any]:
    return {
        "price_series": [],
        "price_band_series": [],
        "pagination": {"count": 0, "page": 1, "page_size": DEFAULT_PAGE_SIZE},
    }


def _net_grid_ohlc_layers(
    state: dict[str, Any],
    *,
    since: datetime | None,
    until: datetime | None,
    granularity: str,
    page: int,
    page_size: int,
    ordering: str,
) -> dict[str, Any]:
    history = _net_grid_level_history_with_current(state)
    filtered = []
    for item in history:
        parsed = _parse_datetime(str(item.get("timestamp") or ""))
        if parsed is None:
            continue
        if since and parsed < since:
            continue
        if until and parsed > until:
            continue
        filtered.append({**item, "_t": int(parsed.timestamp())})
    seconds = _granularity_seconds(granularity)
    if seconds is not None:
        bucketed: dict[int, dict[str, Any]] = {}
        for item in filtered:
            bucketed[int(item["_t"]) // seconds * seconds] = item
        filtered = list(bucketed.values())
    reverse = ordering.startswith("-")
    filtered.sort(key=lambda item: item["_t"], reverse=reverse)
    total = len(filtered)
    page_rows = filtered[(page - 1) * page_size : page * page_size]
    page_rows.sort(key=lambda item: item["_t"])
    return {
        "price_series": _net_grid_price_series(page_rows),
        "price_band_series": _net_grid_price_band_series(page_rows),
        "pagination": {
            "count": total,
            "page": page,
            "page_size": page_size,
            "ordering": ordering,
            "granularity": granularity,
        },
    }


def _net_grid_level_history_with_current(state: dict[str, Any]) -> list[dict[str, Any]]:
    raw = state.get("level_history")
    history = (
        [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    )
    timestamp = state.get("last_tick_at")
    if not timestamp:
        return history
    current_net_units = int(state.get("current_net_units") or 0)
    current = {
        "timestamp": timestamp,
        "current_net_units": current_net_units,
        "average_entry_price": state.get("average_entry_price"),
        "net_take_profit_price": state.get("net_take_profit_price"),
        "profit_trailing_stop_price": state.get("profit_trailing_stop_price"),
        "last_grid_price": state.get("last_grid_price"),
        "next_grid_price": state.get("next_grid_price"),
        "risk_exit_price": state.get("risk_exit_price"),
    }
    if history and history[-1].get("timestamp") == timestamp:
        history[-1] = current
    else:
        history.append(current)
    return history


def _net_grid_price_series(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        ("average_entry_price", "netGrid.chart.averageEntry", "#1976d2", "solid"),
        ("net_take_profit_price", "netGrid.chart.takeProfit", "#2e7d32", "dashed"),
        ("profit_trailing_stop_price", "netGrid.chart.trailingStop", "#00897b", "dashed"),
        ("last_grid_price", "netGrid.chart.lastGrid", "#f57c00", "dotted"),
        ("next_grid_price", "netGrid.chart.nextGrid", "#d32f2f", "dashed"),
        ("risk_exit_price", "netGrid.chart.riskExit", "#616161", "dashed"),
    ]
    result = []
    for field, label_key, color, line_style in specs:
        points = [
            {"time": item["timestamp"], "value": value}
            for item in history
            for value in [_float_or_none(item.get(field))]
            if item.get("timestamp") and value is not None
        ]
        if points:
            result.append(
                {
                    "id": field,
                    "label_key": label_key,
                    "color": color,
                    "line_style": line_style,
                    "points": points,
                }
            )
    return result


def _net_grid_price_band_series(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    specs = [
        (
            "add_zone",
            "netGrid.chartBands.addZone",
            "next_grid_price",
            "risk_exit_price",
            "rgba(211, 47, 47, 0.12)",
        ),
        (
            "recovery_zone",
            "netGrid.chartBands.recoveryZone",
            "average_entry_price",
            "net_take_profit_price",
            "rgba(46, 125, 50, 0.10)",
        ),
        (
            "trailing_zone",
            "netGrid.chartBands.trailingZone",
            "profit_trailing_stop_price",
            "net_take_profit_price",
            "rgba(0, 137, 123, 0.12)",
        ),
        (
            "risk_zone",
            "netGrid.chartBands.riskZone",
            "risk_exit_price",
            "next_grid_price",
            "rgba(97, 97, 97, 0.10)",
        ),
    ]
    result = []
    for layer_id, label_key, from_field, to_field, color in specs:
        points = []
        for item in history:
            if int(item.get("current_net_units") or 0) == 0:
                continue
            from_value = _float_or_none(item.get(from_field))
            to_value = _float_or_none(item.get(to_field))
            if from_value is not None and to_value is not None and from_value != to_value:
                points.append({"time": item["timestamp"], "from": from_value, "to": to_value})
        if len(points) > 1:
            result.append(
                {"id": layer_id, "label_key": label_key, "color": color, "points": points}
            )
    return result


def _metric_consistency_warnings(
    *, task: Any, task_type_label: str, execution_id: Any
) -> list[Any]:
    aggregate = (
        ExecutionMetricAggregate.objects.filter(
            task_type=task_type_label,
            task_id=task.pk,
            execution_id=execution_id,
        )
        .only("continuity_warnings")
        .first()
    )
    return (
        aggregate.continuity_warnings
        if aggregate and isinstance(aggregate.continuity_warnings, list)
        else []
    )


def _page_rows(
    *, request: Request, rows: list[dict[str, Any]], query: StrategyDataQuery
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    total = len(rows)
    start = (query.page - 1) * query.page_size
    results = rows[start : start + query.page_size]
    return results, {
        "count": total,
        "next": _page_url(request, query.page + 1, total, query.page_size),
        "previous": _page_url(request, query.page - 1, total, query.page_size),
        "page": query.page,
        "page_size": query.page_size,
        "ordering": query.ordering,
        "granularity": query.granularity,
    }


def _page_url(request: Request, page: int, total: int, page_size: int) -> str | None:
    total_pages = math.ceil(total / page_size) if page_size else 1
    if page < 1 or page > total_pages:
        return None
    params = request.query_params.copy()
    params["page"] = str(page)
    params["page_size"] = str(page_size)
    return f"{request.build_absolute_uri(request.path)}?{urlencode(params, doseq=True)}"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValidationError(f"Invalid datetime: {value}") from exc
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


def _normalise_granularity(value: str | None) -> str:
    raw = str(value or "raw").strip().upper()
    if raw in {"", "RAW", "TICK", "1"}:
        return "raw"
    if raw.isdigit():
        return f"M{raw}"
    if raw in {"M1", "M5", "M15", "M30", "H1", "H4", "D"}:
        return raw
    raise ValidationError("granularity must be raw, M1, M5, M15, M30, H1, H4, D, or minute count.")


def _granularity_seconds(value: str) -> int | None:
    if value == "raw":
        return None
    if value.startswith("M") and value[1:].isdigit():
        return int(value[1:]) * 60
    return {"H1": 3600, "H4": 14400, "D": 86400}.get(value)


def _positive_int(value: str | None, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Expected a positive integer.") from exc
    if parsed < 1:
        raise ValidationError("Expected a positive integer.")
    return parsed


def _float_or_none(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return str(value) if hasattr(value, "hex") and callable(value.hex) else value


def _string_or_none(value: Any) -> str | None:
    return str(value) if value is not None else None
