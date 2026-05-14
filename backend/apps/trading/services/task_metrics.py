"""Query services for task metric API resources."""

from __future__ import annotations

import json
import math
from typing import Any
from urllib.parse import urlencode

from rest_framework.request import Request

from apps.trading.services.metric_money import (
    MONEY_COMPANION_KEYS,
    money_related_keys,
    requested_money_roots,
)


def ensure_metrics_dict(value: Any) -> dict:
    """Ensure a metrics value is a dict, including double-encoded JSON strings."""
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


def filter_metrics(metrics: dict, metric_keys: tuple[str, ...]) -> dict:
    """Return requested metric keys and their currency/money companions."""
    if not metric_keys:
        return metrics

    filtered: dict[str, Any] = {}
    requested_roots = requested_money_roots(metric_keys)
    requested_keys = set(metric_keys)
    for key in metric_keys:
        if key in metrics:
            filtered[key] = metrics[key]

    for root in requested_roots:
        for key in money_related_keys(root):
            if key in metrics:
                filtered[key] = metrics[key]

    if requested_roots:
        for key in MONEY_COMPANION_KEYS:
            if key in metrics:
                filtered[key] = metrics[key]
        for key in requested_keys:
            if key.endswith("_currency") and key in metrics:
                filtered[key] = metrics[key]

    return filtered


def paginated_envelope(
    request: Request,
    results: list,
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Build a standard paginated response envelope."""
    total_pages = math.ceil(total / page_size) if page_size else 1
    base_url = request.build_absolute_uri(request.path)
    params = request.query_params.copy()

    def build_url(p: int) -> str | None:
        if p < 1 or p > total_pages:
            return None
        params["page"] = str(p)
        params["page_size"] = str(page_size)
        qs = urlencode(params, doseq=True)
        return f"{base_url}?{qs}"

    return {
        "count": total,
        "next": build_url(page + 1),
        "previous": build_url(page - 1),
        "results": results,
    }
