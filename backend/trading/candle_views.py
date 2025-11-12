"""
Candle data views for historical OHLC data.

This module provides API endpoints for fetching historical candle data
from OANDA for charting and analysis.
"""

import logging
from datetime import datetime, timezone
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

    # pylint: disable=too-many-locals,too-many-return-statements
    # pylint: disable=too-many-branches,too-many-statements
    def get(self, request: Request) -> Response:  # noqa: C901
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
        before = request.query_params.get("before")  # Unix timestamp - for older data
        after = request.query_params.get("after")  # Unix timestamp - for newer data
        account_id = request.query_params.get("account_id")

        logger.info(
            "📥 Candle request: instrument=%s, granularity=%s, count=%s, "
            "before=%s, after=%s, from_time=%s, to_time=%s",
            instrument,
            granularity,
            count,
            before,
            after,
            from_time,
            to_time,
        )

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

        # Convert 'before'/'after' timestamps to RFC3339 format for OANDA API
        # OANDA API behavior (verified with curl tests):
        # - 'to' + 'count': Returns 'count' candles ENDING AT 'to'
        #   (going backwards) - for OLDER data
        # - 'from' + 'count': Returns 'count' candles STARTING FROM 'from'
        #   (going forwards) - for NEWER data
        # - 'from' + 'to': Returns ALL candles in range
        #   (cannot use with 'count')

        before_as_to_time = None
        after_as_from_time = None

        # Handle 'before' parameter for fetching older data
        if before and not from_time and not to_time and not after:
            try:
                before_timestamp = int(before)
                # Subtract 1 second to exclude the boundary candle (which we already have)
                to_timestamp = before_timestamp - 1

                before_as_to_time = datetime.fromtimestamp(to_timestamp, tz=timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
                )

                logger.info(
                    "Fetching older data: to=%s (%d), count=%d, excluding boundary at %d",
                    before_as_to_time,
                    to_timestamp,
                    count_int,
                    before_timestamp,
                )
            except (ValueError, OSError) as e:
                logger.warning("Failed to parse 'before' timestamp: %s", e)

        # Handle 'after' parameter for fetching newer data
        elif after and not from_time and not to_time and not before:
            try:
                after_timestamp = int(after)
                # Add 1 second to exclude the boundary candle (which we already have)
                from_timestamp = after_timestamp + 1

                after_as_from_time = datetime.fromtimestamp(
                    from_timestamp, tz=timezone.utc
                ).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

                logger.info(
                    "Fetching newer data: from=%s (%d), count=%d, excluding boundary at %d",
                    after_as_from_time,
                    from_timestamp,
                    count_int,
                    after_timestamp,
                )
            except (ValueError, OSError) as e:
                logger.warning("Failed to parse 'after' timestamp: %s", e)

        # Get user's OANDA account
        account: OandaAccount | None
        try:
            if account_id:
                account = OandaAccount.objects.get(account_id=account_id, user=request.user.id)
            else:
                # Use default account if not specified, otherwise use first account
                account = (
                    OandaAccount.objects.filter(user=request.user.id, is_default=True).first()
                    or OandaAccount.objects.filter(user=request.user.id).first()
                )

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

        # CACHING DISABLED - Always fetch fresh data from OANDA
        # This ensures we always get the correct data for different before/after parameters
        # Cache was causing issues where different requests returned the same cached data
        logger.info("🔄 Cache disabled - fetching fresh data from OANDA API")

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
                # Explicit time range (no count)
                params["fromTime"] = from_time
                params["toTime"] = to_time
            elif before_as_to_time:
                # Fetch older data: 'to' + 'count' returns candles
                # ending at 'to' (going backwards)
                params["toTime"] = before_as_to_time
                params["count"] = count_int
            elif after_as_from_time:
                # Fetch newer data: 'from' + 'count' returns candles
                # starting from 'from' (going forwards)
                params["fromTime"] = after_as_from_time
                params["count"] = count_int
            else:
                # Default: fetch most recent candles
                params["count"] = count_int

            # Fetch candles
            logger.info("🌐 Calling OANDA API with params: %s", params)
            logger.info("🔍 OANDA request details: instrument=%s, params=%s", instrument, params)

            response = api_context.instrument.candles(
                instrument=instrument,
                **params,
            )

            logger.info("📡 OANDA response status: %d", response.status)

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
            raw_candles_count = len(response.body.get("candles", [])) if response.body else 0
            logger.info("📊 Raw candles from OANDA: %d", raw_candles_count)

            incomplete_count = 0
            invalid_mid_count = 0
            invalid_time_count = 0

            if response.body and "candles" in response.body:
                for candle in response.body["candles"]:
                    # v20 library returns Candlestick objects, not dicts
                    if not candle.complete:
                        # Skip incomplete candles
                        incomplete_count += 1
                        continue

                    mid = candle.mid
                    # Skip candles without mid price data
                    if not mid or not all([mid.o, mid.h, mid.l, mid.c]):
                        invalid_mid_count += 1
                        continue

                    # Convert RFC3339 time to Unix timestamp for charting libraries
                    try:
                        time_obj = datetime.fromisoformat(candle.time.replace("Z", "+00:00"))
                        timestamp = int(time_obj.timestamp())
                    except (ValueError, AttributeError):
                        # Skip candles with invalid time format
                        invalid_time_count += 1
                        continue

                    candles_data.append(
                        {
                            "time": timestamp,
                            "open": float(mid.o),
                            "high": float(mid.h),
                            "low": float(mid.l),
                            "close": float(mid.c),
                            "volume": int(candle.volume),
                        }
                    )

            logger.info(
                "✅ Processed candles: %d valid, %d incomplete, %d invalid_mid, %d invalid_time",
                len(candles_data),
                incomplete_count,
                invalid_mid_count,
                invalid_time_count,
            )

            if candles_data:
                first_candle = candles_data[0]
                last_candle = candles_data[-1]
                first_time_str = datetime.fromtimestamp(
                    first_candle["time"], tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                last_time_str = datetime.fromtimestamp(
                    last_candle["time"], tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M:%S")
                logger.info(
                    "📅 Time range: %s (%d) to %s (%d)",
                    first_time_str,
                    first_candle["time"],
                    last_time_str,
                    last_candle["time"],
                )

            response_data = {
                "instrument": instrument,
                "granularity": granularity,
                "candles": candles_data,
            }

            # CACHING DISABLED - No longer storing in cache
            # This ensures each request gets fresh data from OANDA
            logger.info("✅ Returning %d candles to client (no caching)", len(candles_data))

            response = Response(response_data, status=status.HTTP_200_OK)
            response["X-Cache-Hit"] = "false"
            response["X-Cache-Status"] = "disabled"
            response["X-Rate-Limited"] = "false"
            return response

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("❌ Error fetching candles: %s", e, exc_info=True)
            logger.error("❌ Error type: %s", type(e).__name__)
            logger.error("❌ Error details: %s", str(e))

            # CACHING DISABLED - No stale cache fallback
            # Rate limiting errors will be returned to the client
            is_rate_limit = "429" in str(e) or "rate limit" in str(e).lower()

            if is_rate_limit:
                logger.error("❌ Rate limit detected - no cached data available (caching disabled)")
                return Response(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            logger.error("❌ Returning error to client")
            return Response(
                {"error": f"Failed to fetch candles: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
