"""Strategy data API orchestration for snapshot, history, and metrics."""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.trading.models.state import ExecutionState
from apps.trading.services.strategy_data_common import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    StrategyDataQuery,
    normalise_granularity,
    page_rows,
    pagination_envelope,
    parse_datetime,
    positive_int,
    string_or_none,
)
from apps.trading.services.strategy_history import apply_history_filters, load_history_rows
from apps.trading.services.strategy_metrics import (
    build_ohlc_layers,
    load_latest_metric_point,
    load_paginated_metric_points,
    metric_consistency_warnings,
)
from apps.trading.services.strategy_snapshot import build_strategy_snapshot


class StrategyDataService:
    """Build strategy-facing data payloads independent from page layout."""

    def snapshot(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        strategy_state = context["strategy_state"]
        strategy_type = context["strategy_type"]
        snapshot = build_strategy_snapshot(strategy_type, strategy_state)
        return {
            "execution_id": string_or_none(query.execution_id),
            "strategy_type": strategy_type,
            "instrument": getattr(task, "instrument", None),
            "timestamp": context["last_tick_timestamp"],
            "snapshot": snapshot,
        }

    def history(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        rows = load_history_rows(
            task=task,
            task_type_label=task_type_label,
            query=query,
            strategy_type=context["strategy_type"],
            strategy_state=context["strategy_state"],
        )
        rows = apply_history_filters(rows, query)
        rows, pagination = page_rows(request=request, rows=rows, query=query)
        return {
            "execution_id": string_or_none(query.execution_id),
            "strategy_type": context["strategy_type"],
            "instrument": getattr(task, "instrument", None),
            **pagination,
            "results": rows,
        }

    def metrics(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        points, total = load_paginated_metric_points(
            task=task, task_type_label=task_type_label, query=query
        )
        pagination = pagination_envelope(request=request, total=total, query=query)
        return {
            "execution_id": string_or_none(query.execution_id),
            "strategy_type": context["strategy_type"],
            "instrument": getattr(task, "instrument", None),
            "data_source": "strategy_metrics",
            "resume_cursor_timestamp": context["resume_cursor_timestamp"],
            "consistency_warnings": metric_consistency_warnings(
                task=task,
                task_type_label=task_type_label,
                execution_id=query.execution_id,
            ),
            "ohlc_layers": build_ohlc_layers(
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

    def latest_metric(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        return {
            "execution_id": string_or_none(query.execution_id),
            "strategy_type": context["strategy_type"],
            "instrument": getattr(task, "instrument", None),
            "data_source": "strategy_metrics",
            "resume_cursor_timestamp": context["resume_cursor_timestamp"],
            "consistency_warnings": metric_consistency_warnings(
                task=task,
                task_type_label=task_type_label,
                execution_id=query.execution_id,
            ),
            "result": load_latest_metric_point(
                task=task,
                task_type_label=task_type_label,
                query=query,
            ),
        }

    def net_chart(self, *, request: Request, task: Any, task_type_label: str) -> dict[str, Any]:
        query = _query_from_request(request, default_execution_id=task.execution_id)
        context = _load_context(task=task, task_type_label=task_type_label, query=query)
        from apps.trading.services.snowball_net_chart import build_snowball_net_chart

        return build_snowball_net_chart(
            request=request,
            task=task,
            task_type_label=task_type_label,
            execution_id=query.execution_id,
            strategy_type=context["strategy_type"],
            strategy_state=context["strategy_state"],
            last_tick_timestamp=context["last_tick_timestamp"],
        )


def _query_from_request(request: Request, *, default_execution_id: Any) -> StrategyDataQuery:
    params = request.query_params
    execution_id = params.get("execution_id") or default_execution_id
    since = parse_datetime(params.get("since") or params.get("timestamp_from"))
    until = parse_datetime(params.get("until") or params.get("timestamp_to"))
    if since and until and since > until:
        raise ValidationError("since must be earlier than until.")
    page = positive_int(params.get("page"), 1)
    page_size = min(positive_int(params.get("page_size"), DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE)
    ordering = str(params.get("ordering") or "timestamp")
    if ordering not in {"timestamp", "-timestamp"}:
        raise ValidationError("ordering must be 'timestamp' or '-timestamp'.")
    granularity = normalise_granularity(params.get("granularity") or params.get("interval"))
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
