"""Pagination classes for trading views.

Provides reusable DRF pagination classes for all list endpoints.
All paginated endpoints use page/page_size query parameters and return
the standard DRF envelope: {count, next, previous, results}.
"""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Default pagination for most list endpoints (page_size=50, max=200)."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200


class ActivityPagination(PageNumberPagination):
    """Pagination for logs and event activity streams."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class TradePositionPagination(PageNumberPagination):
    """Pagination for heavier trade, order, and position payloads."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000
