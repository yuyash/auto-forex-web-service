"""Helper functions for trading views.

This module contains shared utility functions used across multiple view modules.
"""

import logging
from typing import Any

from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request

logger = logging.getLogger(__name__)


class TaskExecutionPagination(PageNumberPagination):
    """Pagination for task execution history endpoints."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


def _get_execution_metrics_or_none(execution: Any) -> Any | None:
    """Safely resolve the reverse OneToOne `execution.metrics` relation.

    Accessing a missing reverse OneToOne raises `<RelatedModel>.DoesNotExist`,
    which does *not* inherit from `AttributeError` and therefore is not safely
    handled by `getattr(..., default)` or `hasattr(...)`.
    """
    try:
        return execution.metrics
    except Exception:  # pylint: disable=broad-exception-caught
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
