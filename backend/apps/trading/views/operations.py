"""Trading operations health views."""

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.trading.services.operations import TradingOperationsMetricsService


class TradingOperationsMetricsView(APIView):
    """Return runtime metrics for live trading operations."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="trading_operations_metrics",
        tags=["Trading"],
        responses={
            200: inline_serializer(
                "TradingOperationsMetricsResponse",
                fields={
                    "broker_read_outage": serializers.DictField(),
                    "oanda_retry": serializers.DictField(),
                },
            )
        },
        description="Get broker-read outage parking and OANDA retry counters.",
    )
    def get(self, request: Request) -> Response:
        """Return operational metrics visible to the current user."""
        return Response(
            TradingOperationsMetricsService().snapshot(user=request.user),
            status=status.HTTP_200_OK,
        )
