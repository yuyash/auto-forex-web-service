"""Tick data views."""

from logging import Logger, getLogger

from django.db.models import Max, Min
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.querying import (
    OrderingConfig,
    invalid_query_param,
    parse_datetime_param,
)
from apps.market.models import TickData

logger: Logger = getLogger(name=__name__)

TICK_ORDERING = OrderingConfig(
    fields={"timestamp": "timestamp"},
    default="timestamp",
    tie_breakers=(),
)


class TickDataView(APIView):
    """API endpoint for fetching historical tick data from DB.

    Supports cursor-based pagination using the ``cursor`` parameter.
    Each response includes a ``next_cursor`` value that can be passed
    as ``cursor`` in the next request to fetch the following page.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="market_ticks",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
            OpenApiParameter(name="from_time", type=str, required=False),
            OpenApiParameter(name="to_time", type=str, required=False),
            OpenApiParameter(
                name="limit",
                type=int,
                required=False,
                description="Deprecated alias for page_size (1-5000, default 5000)",
            ),
            OpenApiParameter(
                name="page_size",
                type=int,
                required=False,
                description="Page size (1-5000, default 5000)",
            ),
            OpenApiParameter(
                name="cursor",
                type=str,
                required=False,
                description="Cursor returned by previous response for pagination",
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                required=False,
                description="timestamp or -timestamp",
            ),
        ],
        responses={
            200: inline_serializer(
                "MarketTickDataResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "instrument": serializers.CharField(),
                    "next_cursor": serializers.CharField(allow_null=True),
                    "ticks": serializers.ListField(
                        child=inline_serializer(
                            "MarketTickItem",
                            fields={
                                "instrument": serializers.CharField(),
                                "timestamp": serializers.CharField(),
                                "bid": serializers.CharField(),
                                "ask": serializers.CharField(),
                                "mid": serializers.CharField(),
                            },
                        )
                    ),
                },
            ),
        },
        description="Fetch historical tick data from DB with cursor-based pagination.",
    )
    def get(self, request: Request) -> Response:
        instrument = request.query_params.get("instrument")
        from_time = request.query_params.get("from_time")
        to_time = request.query_params.get("to_time")
        cursor = request.query_params.get("cursor")
        limit_raw = request.query_params.get("page_size") or request.query_params.get(
            "limit", "5000"
        )

        if not instrument:
            return Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limit = int(limit_raw)
            if limit < 1 or limit > 5000:
                return Response(
                    {"error": "limit must be between 1 and 5000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "limit must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            queryset = TickData.objects.filter(instrument=instrument)
            ordering = TICK_ORDERING.normalize(request.query_params.get("ordering"))
            descending = ordering.startswith("-")
            from_dt = parse_datetime_param(from_time, field_name="from_time")
            to_dt = parse_datetime_param(to_time, field_name="to_time")
            if from_dt and to_dt and from_dt > to_dt:
                raise invalid_query_param("from_time must be earlier than or equal to to_time")

            if from_dt:
                queryset = queryset.filter(timestamp__gte=from_dt)

            if to_dt:
                queryset = queryset.filter(timestamp__lte=to_dt)

            # Cursor-based pagination: cursor is an ISO-8601 timestamp
            if cursor:
                cursor_dt = parse_datetime_param(cursor, field_name="cursor")
                cursor_filter = "timestamp__lt" if descending else "timestamp__gt"
                queryset = queryset.filter(**{cursor_filter: cursor_dt})

            # Fetch limit+1 to determine if there is a next page
            ticks = list(
                TICK_ORDERING.apply_to_queryset(
                    queryset,
                    request.query_params.get("ordering"),
                ).values("instrument", "timestamp", "bid", "ask", "mid")[: limit + 1]
            )

            has_next = len(ticks) > limit
            page = ticks[:limit]

            next_cursor = None
            if has_next and page:
                next_cursor = page[-1]["timestamp"].isoformat().replace("+00:00", "Z")

            results = [
                {
                    "instrument": row["instrument"],
                    "timestamp": row["timestamp"].isoformat().replace("+00:00", "Z"),
                    "bid": str(row["bid"]),
                    "ask": str(row["ask"]),
                    "mid": str(row["mid"]),
                }
                for row in page
            ]

            return Response(
                {
                    "count": len(results),
                    "instrument": instrument,
                    "next_cursor": next_cursor,
                    "ticks": results,
                }
            )
        except ValidationError:
            raise
        except Exception as exc:
            logger.error("Error fetching ticks: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to fetch ticks"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class TickDataRangeView(APIView):
    """API endpoint returning the available date range of tick data per instrument."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="market_ticks_range",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
        ],
        responses={
            200: inline_serializer(
                "TickDataRangeResponse",
                fields={
                    "instrument": serializers.CharField(),
                    "has_data": serializers.BooleanField(),
                    "min_timestamp": serializers.DateTimeField(allow_null=True),
                    "max_timestamp": serializers.DateTimeField(allow_null=True),
                },
            ),
        },
        description="Get available date range of tick data per instrument.",
    )
    def get(self, request: Request) -> Response:
        instrument = request.query_params.get("instrument")
        if not instrument:
            return Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            agg = TickData.objects.filter(instrument=instrument).aggregate(
                min_timestamp=Min("timestamp"),
                max_timestamp=Max("timestamp"),
            )

            min_ts = agg["min_timestamp"]
            max_ts = agg["max_timestamp"]

            if min_ts is None or max_ts is None:
                return Response(
                    {
                        "instrument": instrument,
                        "has_data": False,
                        "min_timestamp": None,
                        "max_timestamp": None,
                    }
                )

            return Response(
                {
                    "instrument": instrument,
                    "has_data": True,
                    "min_timestamp": min_ts.isoformat().replace("+00:00", "Z"),
                    "max_timestamp": max_ts.isoformat().replace("+00:00", "Z"),
                }
            )
        except Exception as exc:
            logger.error("Error fetching tick data range: %s", exc, exc_info=True)
            return Response(
                {"error": "Failed to fetch tick data range"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
