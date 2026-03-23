"""Granularities views."""

from logging import Logger, getLogger

from django.core.cache import cache
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

logger: Logger = getLogger(name=__name__)
GRANULARITIES_CACHE_TTL_SECONDS = 24 * 60 * 60


class SupportedGranularitiesView(APIView):
    """
    API endpoint for retrieving supported granularities/timeframes.

    GET /api/market/candles/granularities/
    - Returns list of supported OANDA granularities
    - Data is cached for 24 hours
    - Requires authentication
    """

    permission_classes = [IsAuthenticated]

    # OANDA supported granularities (standard list, rarely changes)
    GRANULARITIES = [
        {"value": "S5", "label": "5 Seconds"},
        {"value": "S10", "label": "10 Seconds"},
        {"value": "S15", "label": "15 Seconds"},
        {"value": "S30", "label": "30 Seconds"},
        {"value": "M1", "label": "1 Minute"},
        {"value": "M2", "label": "2 Minutes"},
        {"value": "M4", "label": "4 Minutes"},
        {"value": "M5", "label": "5 Minutes"},
        {"value": "M10", "label": "10 Minutes"},
        {"value": "M15", "label": "15 Minutes"},
        {"value": "M30", "label": "30 Minutes"},
        {"value": "H1", "label": "1 Hour"},
        {"value": "H2", "label": "2 Hours"},
        {"value": "H3", "label": "3 Hours"},
        {"value": "H4", "label": "4 Hours"},
        {"value": "H6", "label": "6 Hours"},
        {"value": "H8", "label": "8 Hours"},
        {"value": "H12", "label": "12 Hours"},
        {"value": "D", "label": "Daily"},
        {"value": "W", "label": "Weekly"},
        {"value": "M", "label": "Monthly"},
    ]

    @extend_schema(
        operation_id="market_granularities",
        tags=["Market"],
        responses={
            200: inline_serializer(
                "GranularitiesResponse",
                fields={
                    "granularities": serializers.ListField(
                        child=inline_serializer(
                            "GranularityItem",
                            fields={
                                "value": serializers.CharField(),
                                "label": serializers.CharField(),
                            },
                        )
                    ),
                    "count": serializers.IntegerField(),
                    "source": serializers.CharField(),
                },
            ),
        },
        description="Retrieve supported OANDA granularities/timeframes.",
    )
    def get(self, _request: Request) -> Response:
        """
        Retrieve list of supported granularities.

        Granularities are standardized by OANDA and rarely change.

        Returns:
            Response with list of granularity objects
        """
        cache_key = "market:supported_granularities"
        granularities = cache.get(cache_key)
        if not isinstance(granularities, list):
            granularities = self.GRANULARITIES
            cache.set(cache_key, granularities, GRANULARITIES_CACHE_TTL_SECONDS)
            logger.info("Primed supported granularities cache")
        else:
            logger.debug("Using cached supported granularities list")

        return Response(
            {
                "granularities": granularities,
                "count": len(granularities),
                "source": "cache",
            }
        )
