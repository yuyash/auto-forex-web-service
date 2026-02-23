"""Tick data views for trading app."""

import logging
from datetime import datetime

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import TickData

logger = logging.getLogger(__name__)


class TickListView(APIView):
    """Return ticks for a given instrument, date range, and count.

    Query parameters:
        instrument (required): Currency pair, e.g. "USD_JPY"
        from_time (optional): ISO-8601 start timestamp
        to_time   (optional): ISO-8601 end timestamp
        count     (optional): Max number of ticks to return (1-50000, default 5000)
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="trading_ticks_list",
        tags=["Trading"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
            OpenApiParameter(name="from_time", type=str, required=False),
            OpenApiParameter(name="to_time", type=str, required=False),
            OpenApiParameter(name="count", type=int, required=False, default=5000),
        ],
        responses={
            200: inline_serializer(
                "TradingTickDataResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "instrument": serializers.CharField(),
                    "ticks": serializers.ListField(
                        child=inline_serializer(
                            "TradingTickItem",
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
        description="Return ticks for a given instrument, date range, and count.",
    )
    def get(self, request: Request) -> Response:
        instrument = request.query_params.get("instrument")
        if not instrument:
            return Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse count
        count_raw = request.query_params.get("count", "5000")
        try:
            count = int(count_raw)
            if count < 1 or count > 50000:
                return Response(
                    {"error": "count must be between 1 and 50000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "count must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            queryset = TickData.objects.filter(instrument=instrument)

            from_time = request.query_params.get("from_time")
            if from_time:
                from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                if timezone.is_naive(from_dt):
                    from_dt = timezone.make_aware(from_dt)
                queryset = queryset.filter(timestamp__gte=from_dt)

            to_time = request.query_params.get("to_time")
            if to_time:
                to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                if timezone.is_naive(to_dt):
                    to_dt = timezone.make_aware(to_dt)
                queryset = queryset.filter(timestamp__lte=to_dt)

            ticks = queryset.order_by("timestamp").values(
                "instrument", "timestamp", "bid", "ask", "mid"
            )[:count]

            results = [
                {
                    "instrument": row["instrument"],
                    "timestamp": row["timestamp"].isoformat().replace("+00:00", "Z"),
                    "bid": str(row["bid"]),
                    "ask": str(row["ask"]),
                    "mid": str(row["mid"]),
                }
                for row in ticks
            ]

            return Response(
                {
                    "count": len(results),
                    "instrument": instrument,
                    "ticks": results,
                }
            )
        except ValueError:
            return Response(
                {"error": "Invalid time format. Use ISO-8601."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error("Error fetching ticks: %s", exc, exc_info=True)
            return Response(
                {"error": f"Failed to fetch ticks: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
