"""Tick data views."""

from datetime import datetime
from logging import Logger, getLogger

from django.db.models import Max, Min
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
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
        operation_id="market_ticks",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
            OpenApiParameter(name="from_time", type=str, required=False),
            OpenApiParameter(name="to_time", type=str, required=False),
            OpenApiParameter(name="count", type=int, required=False, default=5000),
        ],
        responses={
            200: inline_serializer(
                "MarketTickDataResponse",
                fields={
                    "count": serializers.IntegerField(),
                    "instrument": serializers.CharField(),
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
        description="Fetch historical tick data from DB.",
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

            ticks = queryset.order_by("-timestamp").values(
                "instrument", "timestamp", "bid", "ask", "mid"
            )[:count]
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
