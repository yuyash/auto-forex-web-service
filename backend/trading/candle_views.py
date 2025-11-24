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

            # Check if we need to paginate (for from_time + to_time requests)
            all_candles = []
            if from_time and to_time:
                # Calculate approximate number of candles needed
                # This helps us determine if we need pagination
                try:
                    from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                    to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                    time_diff_seconds = (to_dt - from_dt).total_seconds()

                    # Estimate candles based on granularity
                    granularity_seconds = self._get_granularity_seconds(granularity)
                    estimated_candles = int(time_diff_seconds / granularity_seconds)

                    logger.info(
                        "Estimated candles for range: %d (granularity: %s, range: %s to %s)",
                        estimated_candles,
                        granularity,
                        from_time,
                        to_time,
                    )

                    # If estimated candles > 5000, we need to paginate
                    if estimated_candles > 5000:
                        logger.info("Paginating candle requests (estimated: %d)", estimated_candles)
                        all_candles = self._fetch_candles_paginated(
                            api_context,
                            instrument,
                            granularity,
                            from_dt,
                            to_dt,
                        )
                    else:
                        # Single request
                        params["fromTime"] = from_time
                        params["toTime"] = to_time
                        response = api_context.instrument.candles(instrument=instrument, **params)

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

                        all_candles = response.body.get("candles", []) if response.body else []

                except (ValueError, AttributeError) as e:
                    logger.error("Failed to parse time range: %s", e)
                    return Response(
                        {"error": "Invalid time format"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            elif before_as_to_time:
                # Fetch older data: 'to' + 'count' returns candles
                # ending at 'to' (going backwards)
                params["toTime"] = before_as_to_time
                params["count"] = count_int
                response = api_context.instrument.candles(instrument=instrument, **params)

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

                all_candles = response.body.get("candles", []) if response.body else []
            elif after_as_from_time:
                # Fetch newer data: 'from' + 'count' returns candles
                # starting from 'from' (going forwards)
                params["fromTime"] = after_as_from_time
                params["count"] = count_int
                response = api_context.instrument.candles(instrument=instrument, **params)

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

                all_candles = response.body.get("candles", []) if response.body else []
            else:
                # Default: fetch most recent candles
                params["count"] = count_int
                response = api_context.instrument.candles(instrument=instrument, **params)

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

                all_candles = response.body.get("candles", []) if response.body else []

            # Parse and format candles
            candles_data: List[Dict[str, Any]] = []
            incomplete_count = 0
            invalid_mid_count = 0
            invalid_time_count = 0

            if all_candles:
                for candle in all_candles:
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

            response_data = {
                "instrument": instrument,
                "granularity": granularity,
                "candles": candles_data,
            }

            response = Response(response_data, status=status.HTTP_200_OK)
            response["X-Cache-Hit"] = "false"
            response["X-Cache-Status"] = "disabled"
            response["X-Rate-Limited"] = "false"
            return response

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching candles: %s", e, exc_info=True)
            is_rate_limit = "429" in str(e) or "rate limit" in str(e).lower()

            if is_rate_limit:
                return Response(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )

            return Response(
                {"error": f"Failed to fetch candles: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_granularity_seconds(self, granularity: str) -> int:
        """
        Convert granularity string to seconds.

        Args:
            granularity: OANDA granularity (e.g., M1, H1, D)

        Returns:
            Number of seconds per candle
        """
        granularity_map = {
            "S5": 5,
            "S10": 10,
            "S15": 15,
            "S30": 30,
            "M1": 60,
            "M2": 120,
            "M4": 240,
            "M5": 300,
            "M10": 600,
            "M15": 900,
            "M30": 1800,
            "H1": 3600,
            "H2": 7200,
            "H3": 10800,
            "H4": 14400,
            "H6": 21600,
            "H8": 28800,
            "H12": 43200,
            "D": 86400,
            "W": 604800,
            "M": 2592000,  # Approximate (30 days)
        }
        return granularity_map.get(granularity, 3600)  # Default to 1 hour

    def _fetch_candles_paginated(
        self,
        api_context: v20.Context,
        instrument: str,
        granularity: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> List[Any]:
        """
        Fetch candles in multiple requests if the range exceeds 5000 candles.

        Args:
            api_context: v20 API context
            instrument: Currency pair
            granularity: Candle granularity
            from_dt: Start datetime
            to_dt: End datetime

        Returns:
            List of all candles from paginated requests
        """
        all_candles: List[Any] = []
        current_from = from_dt
        max_candles_per_request = 5000

        granularity_seconds = self._get_granularity_seconds(granularity)

        while current_from < to_dt:
            # Calculate the end time for this batch
            # Request 5000 candles worth of time
            time_delta_seconds = max_candles_per_request * granularity_seconds
            current_to = datetime.fromtimestamp(
                min(
                    current_from.timestamp() + time_delta_seconds,
                    to_dt.timestamp(),
                ),
                tz=timezone.utc,
            )

            # Format times for OANDA API
            from_time_str = current_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_time_str = current_to.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            logger.info(
                "Fetching candle batch: %s to %s (granularity: %s)",
                from_time_str,
                to_time_str,
                granularity,
            )

            # Fetch this batch
            try:
                response = api_context.instrument.candles(
                    instrument=instrument,
                    granularity=granularity,
                    fromTime=from_time_str,
                    toTime=to_time_str,
                )

                if response.status != 200:
                    logger.error(
                        "Failed to fetch candle batch: status=%d, body=%s",
                        response.status,
                        response.body,
                    )
                    break

                batch_candles = response.body.get("candles", []) if response.body else []

                if not batch_candles:
                    logger.warning("No candles returned for batch, stopping pagination")
                    break

                all_candles.extend(batch_candles)
                logger.info(
                    "Fetched %d candles in this batch (total: %d)",
                    len(batch_candles),
                    len(all_candles),
                )

                # Move to next batch - start from the last candle's time + 1 granularity period
                # to avoid duplicates
                last_candle_time = batch_candles[-1].time
                last_candle_dt = datetime.fromisoformat(last_candle_time.replace("Z", "+00:00"))
                current_from = datetime.fromtimestamp(
                    last_candle_dt.timestamp() + granularity_seconds,
                    tz=timezone.utc,
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error fetching candle batch: %s", e, exc_info=True)
                break

        logger.info("Pagination complete: fetched %d total candles", len(all_candles))
        return all_candles
