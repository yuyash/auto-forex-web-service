"""Tick data views."""

from datetime import datetime
from logging import Logger, getLogger

from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import TickData

logger: Logger = getLogger(name=__name__)


class TickDataView(APIView):
    """API endpoint for fetching historical tick data from DB."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary="GET /api/market/ticks/",
        description="Fetch historical tick data from local DB",
        operation_id="get_tick_data",
        tags=["market"],
        parameters=[
            OpenApiParameter(
                name="instrument",
                type=str,
                required=True,
                description="Currency pair (e.g., USD_JPY)",
            ),
            OpenApiParameter(
                name="from_time",
                type=str,
                required=False,
                description="Start time in RFC3339 format",
            ),
            OpenApiParameter(
                name="to_time",
                type=str,
                required=False,
                description="End time in RFC3339 format",
            ),
            OpenApiParameter(
                name="count",
                type=int,
                required=False,
                description="Number of ticks to return (1-20000, default: 5000)",
            ),
        ],
        responses={200: dict},
    )
    def get(self, request: Request) -> Response:
        instrument = request.query_params.get("instrument")
        from_time = request.query_params.get("from_time")
        to_time = request.query_params.get("to_time")
        count_raw = request.query_params.get("count", "5000")

        if not instrument:
            return Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            count = int(count_raw)
            if count < 1 or count > 20000:
                return Response(
                    {"error": "count must be between 1 and 20000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "count must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            queryset = TickData.objects.filter(instrument=instrument)

            if from_time:
                from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                if timezone.is_naive(from_dt):
                    from_dt = timezone.make_aware(from_dt)
                queryset = queryset.filter(timestamp__gte=from_dt)

            if to_time:
                to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                if timezone.is_naive(to_dt):
                    to_dt = timezone.make_aware(to_dt)
                queryset = queryset.filter(timestamp__lte=to_dt)

            ticks = (
                queryset.order_by("-timestamp")
                .values("instrument", "timestamp", "bid", "ask", "mid")[:count]
            )
            tick_rows = list(reversed(list(ticks)))

            results = [
                {
                    "instrument": row["instrument"],
                    "timestamp": row["timestamp"].isoformat().replace("+00:00", "Z"),
                    "bid": str(row["bid"]),
                    "ask": str(row["ask"]),
                    "mid": str(row["mid"]),
                }
                for row in tick_rows
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
                {"error": "Invalid time format"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.error("Error fetching ticks: %s", exc, exc_info=True)
            return Response(
                {"error": f"Failed to fetch ticks: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

