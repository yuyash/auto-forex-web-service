"""
Views for trading data and operations.

This module contains views for:
- Tick data retrieval with filtering and pagination
- CSV export for backtesting

Requirements: 7.1, 7.2, 12.1
"""

import csv
import logging
from datetime import datetime

from django.core.cache import cache
from django.db.models import QuerySet
from django.http import StreamingHttpResponse
from django.utils import timezone

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import TickDataSerializer
from .tick_data_models import TickData

logger = logging.getLogger(__name__)


class TickDataPagination(PageNumberPagination):
    """
    Pagination class for tick data.

    Provides configurable page size with reasonable defaults and limits.

    Requirements: 7.1, 7.2, 12.1
    """

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class Echo:
    """
    Helper class for streaming CSV responses.

    Implements a write method that returns the written value for streaming.
    """

    def write(self, value: str) -> str:
        """Return the value to be written."""
        return value


class TickDataListView(APIView):
    """
    API endpoint for tick data retrieval.

    GET /api/tick-data
    - Retrieve historical tick data with filtering
    - Support pagination for large datasets
    - Filter by instrument, start_date, end_date, account
    - Rate limited to prevent abuse

    Query Parameters:
        - instrument: Currency pair (e.g., 'EUR_USD')
        - start_date: Start date in ISO format (e.g., '2024-01-01T00:00:00Z')
        - end_date: End date in ISO format (e.g., '2024-01-31T23:59:59Z')
        - account_id: OANDA account ID (optional, filters to user's accounts)
        - export: Response format ('json' or 'csv', default: 'json')
        - page: Page number for pagination (default: 1)
        - page_size: Number of results per page (default: 100, max: 1000)

    Requirements: 7.1, 7.2, 12.1
    """

    permission_classes = [IsAuthenticated]
    pagination_class = TickDataPagination

    # Rate limiting configuration: 60 requests per minute per user
    RATE_LIMIT_MAX_ATTEMPTS = 60
    RATE_LIMIT_WINDOW_SECONDS = 60

    def get(self, request: Request) -> Response | StreamingHttpResponse:
        """
        Retrieve tick data with optional filtering.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with paginated tick data or CSV file
        """
        # Apply rate limiting
        user_id = str(request.user.id)
        cache_key = f"tick_data_rate_limit:{user_id}"

        # Get current request count
        request_count = cache.get(cache_key, 0)

        if request_count >= self.RATE_LIMIT_MAX_ATTEMPTS:
            logger.warning(
                "Rate limit exceeded for tick data retrieval",
                extra={
                    "user_id": user_id,
                    "ip_address": self.get_client_ip(request),
                },
            )
            return Response(
                {
                    "error": "Rate limit exceeded. Please try again later.",
                    "retry_after": self.RATE_LIMIT_WINDOW_SECONDS,
                },
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Increment request count
        cache.set(cache_key, request_count + 1, self.RATE_LIMIT_WINDOW_SECONDS)

        # Get query parameters
        instrument = request.query_params.get("instrument")
        start_date_str = request.query_params.get("start_date")
        end_date_str = request.query_params.get("end_date")
        account_id = request.query_params.get("account_id")
        # Use 'export' instead of 'format' to avoid DRF content negotiation
        export_format = request.query_params.get("export", "json").lower()

        # Validate export parameter
        if export_format not in ["json", "csv"]:
            return Response(
                {"error": "Invalid export format. Must be 'json' or 'csv'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Build queryset with filters
        filters = {
            "instrument": instrument,
            "start_date_str": start_date_str,
            "end_date_str": end_date_str,
            "account_id": account_id,
        }
        queryset = self.get_queryset(request, filters)

        # Handle validation errors
        if isinstance(queryset, Response):
            return queryset

        # Handle CSV export
        if export_format == "csv":
            return self.export_csv(queryset, instrument)

        # Handle JSON response with pagination
        paginator = self.pagination_class()
        paginated_queryset = paginator.paginate_queryset(queryset, request)

        serializer = TickDataSerializer(paginated_queryset, many=True)

        logger.info(
            "Tick data retrieved",
            extra={
                "user_id": user_id,
                "instrument": instrument,
                "start_date": start_date_str,
                "end_date": end_date_str,
                "count": len(serializer.data),
            },
        )

        return paginator.get_paginated_response(serializer.data)

    def get_queryset(
        self, request: Request, filters: dict[str, str | None]
    ) -> QuerySet[TickData] | Response:
        """
        Build queryset with filters.

        Args:
            request: HTTP request
            filters: Dict with instrument, start_date_str, end_date_str, account_id

        Returns:
            Filtered queryset or error response
        """
        instrument = filters.get("instrument")
        start_date_str = filters.get("start_date_str")
        end_date_str = filters.get("end_date_str")
        account_id = filters.get("account_id")
        # Start with base queryset filtered to user's accounts
        queryset = TickData.objects.filter(account__user=request.user.id).select_related("account")

        # Apply instrument filter
        if instrument:
            queryset = queryset.filter(instrument=instrument)

        # Apply date range filters
        if start_date_str:
            try:
                start_date = self.parse_datetime(start_date_str)
                queryset = queryset.filter(timestamp__gte=start_date)
            except ValueError as e:
                return Response(
                    {"error": f"Invalid start_date format: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if end_date_str:
            try:
                end_date = self.parse_datetime(end_date_str)
                queryset = queryset.filter(timestamp__lte=end_date)
            except ValueError as e:
                return Response(
                    {"error": f"Invalid end_date format: {str(e)}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Apply account filter
        if account_id:
            try:
                account_id_int = int(account_id)
                # Ensure the account belongs to the user
                queryset = queryset.filter(account__id=account_id_int)
            except ValueError:
                return Response(
                    {"error": "Invalid account_id. Must be an integer."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Order by timestamp (newest first)
        queryset = queryset.order_by("-timestamp")

        return queryset

    def parse_datetime(self, date_str: str) -> datetime:
        """
        Parse datetime string in ISO format.

        Args:
            date_str: Date string in ISO format

        Returns:
            Timezone-aware datetime object

        Raises:
            ValueError: If date string is invalid
        """
        try:
            # Try parsing with timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt)
            return dt
        except Exception as e:
            raise ValueError(
                f"Date must be in ISO format " f"(e.g., '2024-01-01T00:00:00Z'): {str(e)}"
            ) from e

    def export_csv(
        self,
        queryset: QuerySet[TickData],
        instrument: str | None = None,
    ) -> StreamingHttpResponse:
        """
        Export tick data as CSV file.

        Args:
            queryset: Filtered queryset
            instrument: Instrument name for filename

        Returns:
            Streaming CSV response
        """
        # Generate filename
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        instrument_str = instrument if instrument else "all_instruments"
        filename = f"tick_data_{instrument_str}_{timestamp}.csv"

        # Create streaming response
        pseudo_buffer = Echo()
        writer = csv.writer(pseudo_buffer)

        def stream_csv():  # type: ignore[no-untyped-def]
            """Generator function for streaming CSV rows."""
            # Write header
            yield writer.writerow(
                [
                    "timestamp",
                    "instrument",
                    "bid",
                    "ask",
                    "mid",
                    "spread",
                ]
            )

            # Write data rows
            for tick in queryset.iterator(chunk_size=1000):
                yield writer.writerow(
                    [
                        tick.timestamp.isoformat(),
                        tick.instrument,
                        str(tick.bid),
                        str(tick.ask),
                        str(tick.mid),
                        str(tick.spread),
                    ]
                )

        response = StreamingHttpResponse(
            stream_csv(),
            content_type="text/csv",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        user_id = str(self.request.user.id) if hasattr(self, "request") else None
        logger.info(
            "Tick data CSV export initiated",
            extra={
                "user_id": user_id,
                "instrument": instrument,
                "export_filename": filename,
            },
        )

        return response

    def get_client_ip(self, request: Request) -> str:
        """
        Get client IP address from request.

        Args:
            request: HTTP request

        Returns:
            Client IP address
        """
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip: str = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR", "")
        return ip
