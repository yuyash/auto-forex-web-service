"""Helper functions for trading views.

This module contains shared utility functions used across multiple view modules.
"""

import logging
from typing import Any, cast

from django.core.exceptions import ObjectDoesNotExist
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class TaskExecutionPagination(PageNumberPagination):
    """Pagination for task execution history endpoints."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _normalize_strategy_event_for_api(event: object) -> dict[str, Any] | None:
    """Normalize heterogeneous strategy event payloads to a stable API shape.

    Frontend expects items like:
      { event_type: string, description: string, details: object, timestamp?: string }

    Historical strategy payloads may be emitted as:
      { type: string, details?: object, timestamp?: string }
    """
    if not isinstance(event, dict):
        return None

    ev = cast(dict[str, Any], event)

    # Already normalized by a newer backend.
    if ev.get("event_type") is not None:
        details_raw = ev.get("details")
        details: dict[str, Any] = details_raw if isinstance(details_raw, dict) else {}
        timestamp = ev.get("timestamp")
        if timestamp is None:
            timestamp = details.get("timestamp")
        return {
            **ev,
            "event_type": str(ev.get("event_type") or ""),
            "description": str(ev.get("description") or ""),
            "details": details,
            **({"timestamp": str(timestamp)} if timestamp else {}),
        }

    raw_type = str(ev.get("type") or "")
    details_raw = ev.get("details")
    details = details_raw if isinstance(details_raw, dict) else {}
    timestamp = ev.get("timestamp") or details.get("timestamp")

    # Best-effort classification so the UI can treat entries consistently.
    event_type = raw_type
    if raw_type == "open":
        event_type = "retracement" if details.get("retracement_open") else "initial_entry"
    elif raw_type in {"layer_retracement_opened"}:
        event_type = "retracement"
    elif raw_type in {"close"}:
        # UI maps this to Take Profit display.
        event_type = "strategy_close"
    elif raw_type in {"take_profit_hit"}:
        event_type = "take_profit"

    description = str(ev.get("description") or "")
    if not description:
        description = raw_type

    out: dict[str, Any] = {
        "event_type": event_type,
        "description": description,
        "details": details,
        "type": raw_type,
    }
    if timestamp:
        out["timestamp"] = str(timestamp)
    return out


def _merge_floor_strategy_events_for_api(
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge near-duplicate floor events emitted for the same retracement.

    The floor strategy commonly emits two events at the same timestamp:
      - type=open (details.retracement_open=true, includes entry_price/lot_size)
      - type=layer_retracement_opened (milestone, may include current_price)

    For frontend readability we merge them into the `open` event and drop the milestone.
    """

    def _as_int(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:  # pylint: disable=broad-exception-caught
            return None

    def _layer_key(details: dict[str, Any]) -> int | None:
        layer_number = details.get("layer_number")
        return _as_int(layer_number if layer_number is not None else details.get("layer"))

    def _retr_key(details: dict[str, Any]) -> int | None:
        retr_count = details.get("retracement_count")
        return _as_int(retr_count if retr_count is not None else details.get("retracement"))

    def _is_retracement_open(ev_type: str, details: dict[str, Any]) -> bool:
        return ev_type == "open" and bool(details.get("retracement_open"))

    merged: list[dict[str, Any]] = []

    for e in events:
        if not merged:
            merged.append(e)
            continue

        last = merged[-1]
        last_details_raw = last.get("details")
        cur_details_raw = e.get("details")
        last_details: dict[str, Any] = (
            cast(dict[str, Any], last_details_raw) if isinstance(last_details_raw, dict) else {}
        )
        cur_details: dict[str, Any] = (
            cast(dict[str, Any], cur_details_raw) if isinstance(cur_details_raw, dict) else {}
        )

        last_type = str(last.get("type") or "")
        cur_type = str(e.get("type") or "")
        last_ts = str(last.get("timestamp") or last_details.get("timestamp") or "")
        cur_ts = str(e.get("timestamp") or cur_details.get("timestamp") or "")

        layer_last = _layer_key(last_details)
        layer_cur = _layer_key(cur_details)
        retr_last = _retr_key(last_details)
        retr_cur = _retr_key(cur_details)

        # Prefer exact timestamp matching when available, but allow merging when
        # timestamps are missing (common in older persisted metrics payloads).
        both_have_ts = last_ts != "" and cur_ts != ""
        same_ts = (both_have_ts and last_ts == cur_ts) or (not both_have_ts)
        same_layer = layer_last is not None and layer_last == layer_cur
        # Older floor events may not include retracement counters on the `open`
        # event; treat missing keys as compatible for adjacency-based merging.
        retr_compatible = (retr_last is None) or (retr_cur is None) or (retr_last == retr_cur)

        # Case A: open retracement then milestone.
        if (
            same_ts
            and same_layer
            and retr_compatible
            and _is_retracement_open(last_type, last_details)
            and cur_type == "layer_retracement_opened"
        ):
            # Prefer `open` event as primary, but enrich with milestone-only fields.
            for key in (
                "current_price",
                "max_retracements_per_layer",
                "retracement",
                "retracement_count",
                "layer_number",
            ):
                if cur_details.get(key) is not None and last_details.get(key) is None:
                    last_details[key] = cur_details.get(key)
            last["details"] = last_details
            continue

        # Case B: milestone then open retracement (rare ordering).
        if (
            same_ts
            and same_layer
            and retr_compatible
            and last_type == "layer_retracement_opened"
            and _is_retracement_open(cur_type, cur_details)
        ):
            for key in (
                "current_price",
                "max_retracements_per_layer",
                "retracement",
                "retracement_count",
                "layer_number",
            ):
                if last_details.get(key) is not None and cur_details.get(key) is None:
                    cur_details[key] = last_details.get(key)
            e["details"] = cur_details
            merged[-1] = e
            continue

        merged.append(e)

    return merged


def _get_execution_metrics_or_none(execution: Any) -> Any | None:
    """Safely resolve the reverse OneToOne `execution.metrics` relation.

    Accessing a missing reverse OneToOne raises `<RelatedModel>.DoesNotExist`,
    which does *not* inherit from `AttributeError` and therefore is not safely
    handled by `getattr(..., default)` or `hasattr(...)`.
    """
    try:
        return execution.metrics
    except ObjectDoesNotExist:
        return None


def _paginate_list_by_page(
    *,
    request: Request,
    items: list,
    base_url: str,
    page_param: str = "page",
    page_size_param: str = "page_size",
    default_page_size: int = 100,
    max_page_size: int = 1000,
    extra_query: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Paginate an in-memory list using page/page_size.

    Returns a dict with keys: count, next, previous, results.
    """

    def _to_int(value: str | None, default: int) -> int:
        if value is None or value == "":
            return default
        return int(value)

    raw_page = request.query_params.get(page_param)
    raw_page_size = request.query_params.get(page_size_param)

    page = _to_int(raw_page, 1)
    page_size = _to_int(raw_page_size, default_page_size)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = default_page_size
    page_size = min(page_size, max_page_size)

    count = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    results = items[start:end]

    extra_query = extra_query or {}
    query_parts = [f"{page_size_param}={page_size}"] + [
        f"{k}={v}" for k, v in extra_query.items() if v is not None
    ]

    next_url = None
    if end < count:
        next_url = f"{base_url}?{page_param}={page + 1}&" + "&".join(query_parts)

    previous_url = None
    if page > 1:
        previous_url = f"{base_url}?{page_param}={page - 1}&" + "&".join(query_parts)

    return {
        "count": count,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }


def _paginate_queryset_by_page(
    *,
    request: Request,
    queryset: Any,
    base_url: str,
    page_param: str = "page",
    page_size_param: str = "page_size",
    default_page_size: int = 100,
    max_page_size: int = 1000,
    extra_query: dict[str, str | None] | None = None,
) -> dict[str, Any]:
    """Paginate a queryset using page/page_size.

    The queryset must support slicing and .count().
    Returns a dict with keys: count, next, previous, results.
    """

    def _to_int(value: str | None, default: int) -> int:
        if value is None or value == "":
            return default
        return int(value)

    raw_page = request.query_params.get(page_param)
    raw_page_size = request.query_params.get(page_size_param)

    page = _to_int(raw_page, 1)
    page_size = _to_int(raw_page_size, default_page_size)

    if page < 1:
        page = 1
    if page_size < 1:
        page_size = default_page_size
    page_size = min(page_size, max_page_size)

    count = int(queryset.count())
    start = (page - 1) * page_size
    end = start + page_size
    results = list(queryset[start:end])

    extra_query = extra_query or {}
    query_parts = [f"{page_size_param}={page_size}"] + [
        f"{k}={v}" for k, v in extra_query.items() if v is not None
    ]

    next_url = None
    if end < count:
        next_url = f"{base_url}?{page_param}={page + 1}&" + "&".join(query_parts)

    previous_url = None
    if page > 1:
        previous_url = f"{base_url}?{page_param}={page - 1}&" + "&".join(query_parts)

    return {
        "count": count,
        "next": next_url,
        "previous": previous_url,
        "results": results,
    }


def _collect_logs(executions_query, level: str | None) -> list[dict[str, str | int | None]]:
    """Collect and filter logs from executions."""
    all_logs = []
    for execution in executions_query:
        logs = execution.logs if isinstance(execution.logs, list) else []
        for log_entry in logs:
            if level and log_entry.get("level") != level:
                continue

            all_logs.append(
                {
                    "timestamp": log_entry.get("timestamp"),
                    "level": log_entry.get("level"),
                    "message": log_entry.get("message"),
                    "execution_id": execution.pk,
                    "execution_number": execution.execution_number,
                }
            )
    return all_logs
