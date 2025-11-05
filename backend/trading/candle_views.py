"""
Candle data views for historical OHLC data.

This module provides API endpoints for fetching historical candle data
from OANDA for charting and analysis.
"""

import logging
from typing import Any, Dict, List

from django.core.exceptions import ObjectDoesNotExist

import v20
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class CandleDataView(APIView):
    """
    API endpoint for fetching historical candle data.

    GET /api/candles/?instrument=EUR_USD&granularity=H1&count=100

    Query Parameters:
    - instrument: Currency pair (e.g., EUR_USD, GBP_USD)
    - granularity: Candle granularity (S5, S10, S15, S30, M1, M2, M4,
      M5, M10, M15, M30, H1, H2, H3, H4, H6, H8, H12, D, W, M)
    - count: Number of candles to fetch (default: 100, max: 5000)
    - from_time: Start time in RFC3339 format (optional)
    - to_time: End time in RFC3339 format (optional)
    - account_id: OANDA account ID (optional, uses first if not provided)
    """

    permission_classes = [IsAuthenticated]

    # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches
    def get(self, request: Request) -> Response:
        """
        Fetch historical candle data from OANDA.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with candle data or error message
        """
        # Get query parameters
        instrument = request.query_params.get("instrument")
        granularity = request.query_params.get("granularity", "H1")
        count = request.query_params.get("count", "100")
        from_time = request.query_params.get("from_time")
        to_time = request.query_params.get("to_time")
        account_id = request.query_params.get("account_id")

        # Validate required parameters
        if not instrument:
            return Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate count
        try:
            count_int = int(count)
            if count_int < 1 or count_int > 5000:
                return Response(
                    {"error": "count must be between 1 and 5000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return Response(
                {"error": "count must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get user's OANDA account
        account: OandaAccount | None
        try:
            if account_id:
                account = OandaAccount.objects.get(account_id=account_id, user=request.user.id)
            else:
                # Use first account if not specified
                account = OandaAccount.objects.filter(user=request.user.id).first()

            if account is None:
                return Response(
                    {
                        "error": "No OANDA account found. Please configure an account first.",
                        "error_code": "NO_OANDA_ACCOUNT",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

        except ObjectDoesNotExist:
            return Response(
                {
                    "error": "OANDA account not found",
                    "error_code": "NO_OANDA_ACCOUNT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch candles from OANDA
        try:
            # Initialize v20 API context
            api_context = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                application="auto-forex-trading",
            )

            # Build request parameters
            params: Dict[str, Any] = {
                "granularity": granularity,
            }

            if from_time and to_time:
                params["from"] = from_time
                params["to"] = to_time
            else:
                params["count"] = count_int

            # Fetch candles
            response = api_context.instrument.candles(
                instrument=instrument,
                **params,
            )

            if response.status != 200:
                logger.error(
                    "Failed to fetch candles: status=%d, body=%s",
                    response.status,
                    response.body,
                )
                return Response(
                    {"error": "Failed to fetch candles from OANDA"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # Parse and format candles
            candles_data: List[Dict[str, Any]] = []
            if response.body and "candles" in response.body:
                for candle in response.body["candles"]:
                    if not candle.get("complete"):
                        # Skip incomplete candles
                        continue

                    mid = candle.get("mid", {})
                    candles_data.append(
                        {
                            "time": candle.get("time"),
                            "open": float(mid.get("o", 0)),
                            "high": float(mid.get("h", 0)),
                            "low": float(mid.get("l", 0)),
                            "close": float(mid.get("c", 0)),
                            "volume": int(candle.get("volume", 0)),
                        }
                    )

            logger.info(
                "Fetched %d candles for %s with granularity %s",
                len(candles_data),
                instrument,
                granularity,
            )

            return Response(
                {
                    "instrument": instrument,
                    "granularity": granularity,
                    "candles": candles_data,
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching candles: %s", e, exc_info=True)
            return Response(
                {"error": f"Failed to fetch candles: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
