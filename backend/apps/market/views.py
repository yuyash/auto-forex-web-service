"""
Market data views for OANDA accounts, candles, and configuration.

This module provides API endpoints for:
- OANDA account management (CRUD operations)
- Historical candle data for charting and analysis
- Supported currency pairs/instruments
- Supported granularities/timeframes
"""

from datetime import UTC, datetime
from decimal import Decimal
from logging import getLogger
from typing import Any

import v20
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccount
from apps.market.serializers import (
    OandaAccountSerializer,
    OandaApiHealthStatusSerializer,
    PositionSerializer,
)
from apps.market.services.compliance import ComplianceViolationError
from apps.market.services.health import OandaHealthCheckService
from apps.market.services.oanda import (
    LimitOrderRequest,
    MarketOrderRequest,
    OandaAPIError,
    OandaService,
    OcoOrderRequest,
    OpenTrade,
    Order,
    StopOrderRequest,
)

logger = getLogger(__name__)


class OandaAccountView(APIView):
    """
    API endpoint for OANDA accounts.

    GET /api/accounts
    - List all OANDA accounts for the authenticated user

    POST /api/accounts
    - Add a new OANDA account
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountSerializer

    def get(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        accounts = OandaAccount.objects.filter(user_id=request.user.id).order_by("-created_at")
        serializer = self.serializer_class(accounts, many=True)
        logger.info(
            "User %s retrieved %s OANDA accounts",
            request.user.email,
            accounts.count(),
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "count": accounts.count(),
            },
        )
        response_data = {
            "count": accounts.count(),
            "next": None,
            "previous": None,
            "results": serializer.data,
        }
        return Response(response_data, status=status.HTTP_200_OK)

    def post(self, request: Request) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )

        serializer = self.serializer_class(data=request.data, context={"request": request})
        if serializer.is_valid():
            account = serializer.save()
            logger.info(
                "User %s created OANDA account %s",
                request.user.email,
                account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OandaAccountDetailView(APIView):
    """
    API endpoint for retrieving, updating, and deleting a specific OANDA account.

    GET /api/accounts/{id}
    - Retrieve details of a specific OANDA account

    PUT /api/accounts/{id}
    - Update a specific OANDA account

    DELETE /api/accounts/{id}
    - Delete a specific OANDA account
    """

    permission_classes = [IsAuthenticated]
    serializer_class = OandaAccountSerializer

    def get_object(self, request: Request, account_id: int) -> OandaAccount | None:
        if not request.user.is_authenticated:
            return None
        try:
            account = OandaAccount.objects.get(id=account_id, user_id=request.user.id)
            return account
        except OandaAccount.DoesNotExist:
            return None

    def get(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(account)
        response_data = serializer.data
        try:
            client = OandaService(account)
            live_data = client.get_account_details()

            account_resource = client.get_account_resource()
            hedging_enabled = bool(account_resource.get("hedgingEnabled", False))

            response_data["balance"] = str(live_data.balance)
            response_data["margin_used"] = str(live_data.margin_used)
            response_data["margin_available"] = str(live_data.margin_available)
            response_data["unrealized_pnl"] = str(live_data.unrealized_pl)
            response_data["nav"] = str(live_data.nav)
            response_data["open_trade_count"] = live_data.open_trade_count
            response_data["open_position_count"] = live_data.open_position_count
            response_data["pending_order_count"] = live_data.pending_order_count

            response_data["hedging_enabled"] = hedging_enabled
            response_data["position_mode"] = "hedging" if hedging_enabled else "netting"
            response_data["oanda_account"] = client.make_jsonable(account_resource)
            response_data["live_data"] = True
        except Exception as e:
            logger.warning(
                "Failed to fetch live data from OANDA for account %s: %s",
                account.account_id,
                str(e),
            )
            response_data["live_data"] = False
            response_data["live_data_error"] = str(e)
        logger.info(
            "User %s retrieved OANDA account %s",
            request.user.email,
            account.account_id,
            extra={
                "user_id": request.user.id,
                "email": request.user.email,
                "account_id": account.account_id,
            },
        )
        return Response(response_data, status=status.HTTP_200_OK)

    def put(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = self.serializer_class(
            account, data=request.data, partial=True, context={"request": request}
        )
        if serializer.is_valid():
            updated_account = serializer.save()
            logger.info(
                "User %s updated OANDA account %s",
                request.user.email,
                updated_account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": updated_account.account_id,
                    "updated_fields": list(request.data.keys()),
                },
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request: Request, account_id: int) -> Response:
        if not request.user.is_authenticated:
            return Response(
                {"error": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED
            )
        account = self.get_object(request, account_id)
        if account is None:
            return Response(
                {"error": "Account not found or you don't have permission to access it."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if account.is_used:
            error_message = (
                "Cannot delete this OANDA account because it is marked as in use. "
                "Please stop the process using this account first."
            )
            logger.warning(
                "User %s attempted to delete OANDA account %s that is in use",
                request.user.email,
                account.account_id,
                extra={
                    "user_id": request.user.id,
                    "email": request.user.email,
                    "account_id": account.account_id,
                    "is_used": True,
                },
            )
            return Response({"error": error_message}, status=status.HTTP_400_BAD_REQUEST)
        account_id_str = account.account_id
        account.delete()
        logger.info(
            "User %s deleted OANDA account %s",
            request.user.email,
            account_id_str,
            extra={
                "user_id": request.user.pk,
                "email": request.user.email,
                "account_id": account_id_str,
            },
        )
        return Response({"message": "Account deleted successfully."}, status=status.HTTP_200_OK)


class CandleDataView(APIView):
    """
    API endpoint for fetching candle data.

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

                before_as_to_time = datetime.fromtimestamp(to_timestamp, tz=UTC).strftime(
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

                after_as_from_time = datetime.fromtimestamp(from_timestamp, tz=UTC).strftime(
                    "%Y-%m-%dT%H:%M:%S.%fZ"
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

        # Fetch candles from OANDA
        try:
            # Initialize v20 API context
            api_context = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                application="auto-forex-trading",
            )

            # Build request parameters
            params: dict[str, Any] = {
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
                        oanda_response = api_context.instrument.candles(
                            instrument=instrument, **params
                        )

                        if oanda_response.status != 200:
                            logger.error(
                                "Failed to fetch candles: status=%d, body=%s",
                                oanda_response.status,
                                oanda_response.body,
                            )
                            return Response(
                                {"error": "Failed to fetch candles from OANDA"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )

                        all_candles = (
                            oanda_response.body.get("candles", []) if oanda_response.body else []
                        )

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
                oanda_response = api_context.instrument.candles(instrument=instrument, **params)

                if oanda_response.status != 200:
                    logger.error(
                        "Failed to fetch candles: status=%d, body=%s",
                        oanda_response.status,
                        oanda_response.body,
                    )
                    return Response(
                        {"error": "Failed to fetch candles from OANDA"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                all_candles = oanda_response.body.get("candles", []) if oanda_response.body else []
            elif after_as_from_time:
                # Fetch newer data: 'from' + 'count' returns candles
                # starting from 'from' (going forwards)
                params["fromTime"] = after_as_from_time
                params["count"] = count_int
                oanda_response = api_context.instrument.candles(instrument=instrument, **params)

                if oanda_response.status != 200:
                    logger.error(
                        "Failed to fetch candles: status=%d, body=%s",
                        oanda_response.status,
                        oanda_response.body,
                    )
                    return Response(
                        {"error": "Failed to fetch candles from OANDA"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                all_candles = oanda_response.body.get("candles", []) if oanda_response.body else []
            else:
                # Default: fetch most recent candles
                params["count"] = count_int
                oanda_response = api_context.instrument.candles(instrument=instrument, **params)

                if oanda_response.status != 200:
                    logger.error(
                        "Failed to fetch candles: status=%d, body=%s",
                        oanda_response.status,
                        oanda_response.body,
                    )
                    return Response(
                        {"error": "Failed to fetch candles from OANDA"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )

                all_candles = oanda_response.body.get("candles", []) if oanda_response.body else []

            # Parse and format candles
            candles_data: list[dict[str, Any]] = []
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

            return Response(
                response_data,
                status=status.HTTP_200_OK,
                headers={
                    "X-Cache-Hit": "false",
                    "X-Cache-Status": "disabled",
                    "X-Rate-Limited": "false",
                },
            )

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
    ) -> list[Any]:
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
        all_candles: list[Any] = []
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
                tz=UTC,
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
                    tz=UTC,
                )

            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error fetching candle batch: %s", e, exc_info=True)
                break

        logger.info("Pagination complete: fetched %d total candles", len(all_candles))
        return all_candles


class SupportedInstrumentsView(APIView):
    """
    API endpoint for retrieving supported currency pairs/instruments.

    GET /api/trading/instruments/
    - Returns list of supported currency pairs from OANDA API
    - Data is cached for 24 hours
    - Requires authentication
    """

    permission_classes = [IsAuthenticated]

    # Fallback list if OANDA API is unavailable
    FALLBACK_INSTRUMENTS = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "USD_CAD",
        "NZD_USD",
        "EUR_GBP",
        "EUR_JPY",
        "GBP_JPY",
        "EUR_CHF",
        "AUD_JPY",
        "GBP_CHF",
        "EUR_AUD",
        "EUR_CAD",
    ]

    def get(self, _request: Request) -> Response:
        """
        Retrieve list of supported instruments from OANDA API.

        Returns:
            Response with list of instrument codes
        """
        # Fetch from OANDA API
        instruments = self._fetch_instruments_from_oanda()

        if instruments:
            logger.info(f"Fetched {len(instruments)} instruments from OANDA")
            return Response(
                {
                    "instruments": instruments,
                    "count": len(instruments),
                    "source": "oanda",
                }
            )

        # Fallback to default list
        logger.warning("Using fallback instruments list")
        return Response(
            {
                "instruments": self.FALLBACK_INSTRUMENTS,
                "count": len(self.FALLBACK_INSTRUMENTS),
                "source": "fallback",
            }
        )

    def _fetch_instruments_from_oanda(self) -> list[str] | None:
        """
        Fetch available instruments from OANDA API.

        Returns:
            List of instrument names or None if fetch fails
        """
        try:
            # Get any active OANDA account to use for API call
            account = OandaAccount.objects.filter(is_active=True).first()
            if not account:
                logger.warning("No active OANDA account found")
                return None

            # Create API context
            api = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                poll_timeout=10,
            )

            # Fetch account instruments
            response = api.account.instruments(account.account_id)

            if response.status != 200:
                logger.error(f"OANDA API error: {response.status}")
                return None

            # Extract instrument names
            instruments = []
            for instrument in response.body.get("instruments", []):
                name = instrument.name
                # Filter to forex pairs only (format: XXX_YYY)
                if "_" in name and len(name) == 7:
                    instruments.append(name)

            return sorted(instruments)

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to fetch instruments from OANDA: {e}")
            return None


class SupportedGranularitiesView(APIView):
    """
    API endpoint for retrieving supported granularities/timeframes.

    GET /api/trading/granularities/
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

    def get(self, _request: Request) -> Response:
        """
        Retrieve list of supported granularities.

        Granularities are standardized by OANDA and rarely change.

        Returns:
            Response with list of granularity objects
        """
        # Fetch from OANDA API to validate
        granularities = self._fetch_granularities_from_oanda()

        if granularities:
            logger.info(f"Validated {len(granularities)} granularities from OANDA")
            return Response(
                {
                    "granularities": granularities,
                    "count": len(granularities),
                    "source": "oanda",
                }
            )

        # Use standard list as fallback
        logger.info("Using standard granularities list")
        return Response(
            {
                "granularities": self.GRANULARITIES,
                "count": len(self.GRANULARITIES),
                "source": "standard",
            }
        )

    def _fetch_granularities_from_oanda(self) -> list[dict[str, str]] | None:
        """
        Fetch available granularities from OANDA API.

        Returns:
            List of granularity objects or None if fetch fails
        """
        try:
            # Get any active OANDA account to use for API call
            account = OandaAccount.objects.filter(is_active=True).first()
            if not account:
                logger.warning("No active OANDA account found")
                return None

            # Create API context
            api = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                poll_timeout=10,
            )

            # Fetch candle specifications for any instrument to get granularities
            response = api.account.instruments(account.account_id)

            if response.status != 200:
                logger.error(f"OANDA API error: {response.status}")
                return None

            # OANDA doesn't provide a direct granularities endpoint,
            # but the granularities are standardized, so we validate
            # that we can fetch candles with our standard list
            instruments = response.body.get("instruments", [])
            if instruments:
                # If we can fetch instruments, our granularities list is valid
                return self.GRANULARITIES

            return None

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to validate granularities from OANDA: {e}")
            return None


class MarketStatusView(APIView):
    """
    API endpoint for fetching forex market open/close status.

    GET /api/market/status/
    - Returns current market status (open/closed)
    - Includes trading session information
    - Requires authentication
    """

    permission_classes = [IsAuthenticated]

    # Forex market sessions (in UTC)
    MARKET_SESSIONS = {
        "sydney": {"open": 21, "close": 6},  # 21:00 - 06:00 UTC
        "tokyo": {"open": 0, "close": 9},  # 00:00 - 09:00 UTC
        "london": {"open": 7, "close": 16},  # 07:00 - 16:00 UTC
        "new_york": {"open": 12, "close": 21},  # 12:00 - 21:00 UTC
    }

    def get(self, _request: Request) -> Response:
        """
        Get current forex market status.

        Returns:
            Response with market status and active sessions
        """
        now = datetime.now(UTC)
        current_hour = now.hour
        current_weekday = now.weekday()  # 0=Monday, 6=Sunday

        # Forex market is closed from Friday 21:00 UTC to Sunday 21:00 UTC
        is_weekend_closed = (
            (current_weekday == 4 and current_hour >= 21)  # Friday after 21:00
            or current_weekday == 5  # Saturday
            or (current_weekday == 6 and current_hour < 21)  # Sunday before 21:00
        )

        # Determine active sessions
        active_sessions = []
        for session_name, hours in self.MARKET_SESSIONS.items():
            if self._is_session_active(current_hour, hours["open"], hours["close"]):
                active_sessions.append(session_name)

        # Market is open if not weekend and at least one session is active
        is_market_open = not is_weekend_closed and len(active_sessions) > 0

        # Calculate next market open/close
        next_event = self._get_next_market_event(now, is_market_open)

        response_data = {
            "is_open": is_market_open,
            "current_time_utc": now.isoformat(),
            "active_sessions": active_sessions,
            "sessions": {
                name: {
                    "open_hour_utc": hours["open"],
                    "close_hour_utc": hours["close"],
                    "is_active": name in active_sessions,
                }
                for name, hours in self.MARKET_SESSIONS.items()
            },
            "next_event": next_event,
            "is_weekend": is_weekend_closed,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    def _is_session_active(self, current_hour: int, open_hour: int, close_hour: int) -> bool:
        """Check if a trading session is currently active."""
        if open_hour < close_hour:
            return open_hour <= current_hour < close_hour
        else:  # Session spans midnight (e.g., Sydney)
            return current_hour >= open_hour or current_hour < close_hour

    def _get_next_market_event(self, now: datetime, is_open: bool) -> dict[str, Any]:
        """Calculate the next market open or close event."""
        current_weekday = now.weekday()
        current_hour = now.hour

        if is_open:
            # Market is open, find next close (Friday 21:00 UTC)
            days_until_friday = (4 - current_weekday) % 7
            if current_weekday == 4 and current_hour < 21:
                days_until_friday = 0

            next_close = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if days_until_friday > 0 or (days_until_friday == 0 and current_hour >= 21):
                from datetime import timedelta

                next_close = next_close + timedelta(days=days_until_friday)

            return {
                "event": "close",
                "time_utc": next_close.isoformat(),
                "description": "Market closes for the weekend",
            }
        else:
            # Market is closed, find next open (Sunday 21:00 UTC)
            days_until_sunday = (6 - current_weekday) % 7
            if current_weekday == 6 and current_hour >= 21:
                days_until_sunday = 7  # Next Sunday

            from datetime import timedelta

            next_open = now.replace(hour=21, minute=0, second=0, microsecond=0)
            next_open = next_open + timedelta(days=days_until_sunday)

            return {
                "event": "open",
                "time_utc": next_open.isoformat(),
                "description": "Market opens for the week",
            }


class OandaApiHealthView(APIView):
    """API endpoint for OANDA API health checks.

    GET /api/market/health/oanda/
    - Returns latest persisted status for the selected account (or null if none yet)

    POST /api/market/health/oanda/
    - Performs a live check against OANDA and persists/returns the result
    """

    permission_classes = [IsAuthenticated]

    def _get_account(self, request: Request) -> OandaAccount | None:
        account_id = request.query_params.get("account_id")

        if account_id:
            return OandaAccount.objects.filter(
                account_id=account_id,
                user=request.user.id,
            ).first()

        return (
            OandaAccount.objects.filter(user=request.user.id, is_default=True).first()
            or OandaAccount.objects.filter(user=request.user.id).first()
        )

    def get(self, request: Request) -> Response:
        account = self._get_account(request)
        if account is None:
            return Response(
                {
                    "error": "No OANDA account found. Please configure an account first.",
                    "error_code": "NO_OANDA_ACCOUNT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        latest = account.api_health_statuses.order_by("-checked_at").first()  # type: ignore[attr-defined]

        return Response(
            {
                "account": {
                    "id": account.pk,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
                "status": OandaApiHealthStatusSerializer(latest).data if latest else None,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request: Request) -> Response:
        account = self._get_account(request)
        if account is None:
            return Response(
                {
                    "error": "No OANDA account found. Please configure an account first.",
                    "error_code": "NO_OANDA_ACCOUNT",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        row = OandaHealthCheckService(account).check()
        return Response(
            {
                "account": {
                    "id": account.pk,
                    "account_id": account.account_id,
                    "api_type": account.api_type,
                },
                "status": OandaApiHealthStatusSerializer(row).data,
            },
            status=status.HTTP_200_OK,
        )


class InstrumentDetailView(APIView):
    """
    API endpoint for fetching detailed information about a specific currency pair.

    GET /api/market/instruments/<instrument>/
    - Returns pip value, tick size, margin requirements, etc.
    - Requires authentication
    - Data is cached for 1 hour
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, instrument: str) -> Response:
        """
        Get detailed information about a specific instrument.

        Args:
            request: HTTP request
            instrument: Currency pair (e.g., EUR_USD)

        Returns:
            Response with instrument details
        """
        # Normalize instrument name
        instrument = instrument.upper().replace("-", "_")

        # Fetch from OANDA API
        instrument_data = self._fetch_instrument_details(request, instrument)

        if instrument_data:
            instrument_data["source"] = "oanda"
            return Response(instrument_data, status=status.HTTP_200_OK)

        return Response(
            {"error": f"Instrument '{instrument}' not found or API error"},
            status=status.HTTP_404_NOT_FOUND,
        )

    def _fetch_instrument_details(self, request: Request, instrument: str) -> dict[str, Any] | None:
        """
        Fetch instrument details from OANDA API.

        Args:
            request: HTTP request (for user's OANDA account)
            instrument: Currency pair

        Returns:
            Dictionary with instrument details or None if fetch fails
        """
        try:
            user_id = request.user.id
            if not user_id:
                return None
            # Get user's OANDA account or any active account
            account = (
                OandaAccount.objects.filter(user_id=user_id, is_active=True).first()
                or OandaAccount.objects.filter(is_active=True).first()
            )

            if not account:
                logger.warning("No active OANDA account found")
                return None

            # Create API context
            api = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                poll_timeout=10,
            )

            # Fetch instrument details
            response = api.account.instruments(
                account.account_id,
                instruments=instrument,
            )

            if response.status != 200:
                logger.error(f"OANDA API error: {response.status}")
                return None

            instruments_list = response.body.get("instruments", [])
            if not instruments_list:
                logger.warning(f"Instrument {instrument} not found")
                return None

            instr = instruments_list[0]

            # Also fetch current pricing for spread calculation
            pricing_data = self._fetch_current_pricing(api, account.account_id, instrument)

            # Build response data
            return {
                "instrument": instr.name,
                "display_name": instr.displayName,
                "type": instr.type,
                # Pip and tick information
                "pip_location": instr.pipLocation,
                "pip_value": 10**instr.pipLocation,  # e.g., 0.0001 for most pairs
                "display_precision": instr.displayPrecision,
                "trade_units_precision": instr.tradeUnitsPrecision,
                "minimum_trade_size": str(instr.minimumTradeSize),
                "maximum_trade_units": str(instr.maximumTradeUnits),
                "maximum_position_size": str(instr.maximumPositionSize),
                "maximum_order_units": str(instr.maximumOrderUnits),
                # Margin requirements
                "margin_rate": str(instr.marginRate),
                "leverage": (
                    f"1:{int(1 / float(instr.marginRate))}"
                    if float(instr.marginRate) > 0
                    else "N/A"
                ),
                # Trading hours and status
                "guaranteed_stop_loss_order_mode": str(
                    getattr(instr, "guaranteedStopLossOrderMode", "DISABLED")
                ),
                "tags": [tag.name for tag in getattr(instr, "tags", [])],
                # Financing (swap) information
                "financing": (
                    {
                        "long_rate": str(getattr(instr.financing, "longRate", "0")),
                        "short_rate": str(getattr(instr.financing, "shortRate", "0")),
                    }
                    if hasattr(instr, "financing") and instr.financing
                    else None
                ),
                # Current pricing (if available)
                "current_pricing": pricing_data,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to fetch instrument details for {instrument}: {e}")
            return None

    def _fetch_current_pricing(
        self, api: v20.Context, account_id: str, instrument: str
    ) -> dict[str, Any] | None:
        """Fetch current pricing for spread calculation."""
        try:
            response = api.pricing.get(account_id, instruments=instrument)

            if response.status != 200:
                return None

            prices = response.body.get("prices", [])
            if not prices:
                return None

            price = prices[0]

            # Get best bid/ask
            bids = price.bids if hasattr(price, "bids") and price.bids else []
            asks = price.asks if hasattr(price, "asks") and price.asks else []

            best_bid = float(bids[0].price) if bids else None
            best_ask = float(asks[0].price) if asks else None

            spread = None
            spread_pips = None
            if best_bid and best_ask:
                spread = best_ask - best_bid
                # Assume standard pip location for forex
                spread_pips = spread * 10000  # Convert to pips for most pairs

            return {
                "bid": str(best_bid) if best_bid else None,
                "ask": str(best_ask) if best_ask else None,
                "spread": f"{spread:.5f}" if spread else None,
                "spread_pips": f"{spread_pips:.1f}" if spread_pips else None,
                "tradeable": price.tradeable if hasattr(price, "tradeable") else None,
                "time": price.time if hasattr(price, "time") else None,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning(f"Failed to fetch pricing for {instrument}: {e}")
            return None


class PositionView(APIView):
    """
    API endpoint for position listing directly from OANDA API.

    GET /api/positions
    - Retrieve positions directly from OANDA API
    - Filter by account, instrument, status (open/closed)

    PUT /api/positions
    - Open a new position by submitting a market order via OANDA

    Query Parameters:
        - account_id: OANDA account database ID (optional)
        - instrument: Currency pair (e.g., 'EUR_USD')
        - status: Position status ('open' or 'closed', default: 'open')
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        Retrieve positions directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with position data
        """
        return self._get_positions_from_oanda(request)

    def put(self, request: Request) -> Response:
        """
        Open a new position via OANDA by submitting a market order.

        Body:
            - account_id: OANDA account database ID (required)
            - instrument: Currency pair (e.g., 'EUR_USD') (required)
            - direction: 'long' or 'short' (required)
            - units: number of units (required)
            - take_profit: optional TP price
            - stop_loss: optional SL price

        Returns:
            Response with created order details
        """

        serializer = PositionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        account_id = request.data.get("account_id")
        if not account_id:
            return Response({"error": "account_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.pk)
        except (ValueError, TypeError, OandaAccount.DoesNotExist):
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        validated = serializer.validated_data
        instrument = validated["instrument"]
        direction = validated["direction"]
        units = validated["units"]
        take_profit = validated.get("take_profit")
        stop_loss = validated.get("stop_loss")

        signed_units = units if direction == "long" else -units

        try:
            client = OandaService(account)
            result = client.create_market_order(
                MarketOrderRequest(
                    instrument=instrument,
                    units=signed_units,
                    take_profit=take_profit,
                    stop_loss=stop_loss,
                )
            )

            return Response(
                {
                    "id": result.order_id,
                    "instrument": result.instrument,
                    "type": result.order_type.value,
                    "units": str(result.units),
                    "price": str(result.price) if result.price is not None else None,
                    "state": result.state.value,
                    "create_time": result.create_time.isoformat() if result.create_time else None,
                    "account_name": account.account_id,
                    "account_db_id": account.pk,
                },
                status=status.HTTP_201_CREATED,
            )
        except (OandaAPIError, ComplianceViolationError) as e:
            logger.error("Position open (market order) failed: %s", e)
            return Response(
                {"error": f"Order execution failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error opening position: %s", e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_positions_from_oanda(self, request: Request) -> Response:
        """
        Retrieve positions directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with position data from OANDA
        """
        account_id = request.query_params.get("account_id")
        instrument = request.query_params.get("instrument")
        position_status = request.query_params.get("status", "open").lower()

        # Validate status parameter
        if position_status not in ["open", "closed", "all"]:
            return Response(
                {"error": "Invalid status. Must be 'open', 'closed', or 'all'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get accounts to query
        if account_id:
            try:
                accounts = [OandaAccount.objects.get(id=int(account_id), user=request.user.id)]
            except OandaAccount.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccount.objects.filter(user=request.user.id, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_positions = []

        for account in accounts:
            try:
                client = OandaService(account)

                if position_status in ["open", "all"]:
                    # Get open trades (individual position entries)
                    trades = client.get_open_trades(instrument=instrument)
                    for trade in trades:
                        all_positions.append(
                            {
                                "id": trade.trade_id,
                                "instrument": trade.instrument,
                                "direction": trade.direction.value,
                                "units": str(trade.units),
                                "entry_price": str(trade.entry_price),
                                "unrealized_pnl": str(trade.unrealized_pnl),
                                "open_time": (
                                    trade.open_time.isoformat() if trade.open_time else None
                                ),
                                "state": trade.state,
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                                "status": "open",
                            }
                        )

                # Note: OANDA doesn't provide a direct "closed positions" API
                # Closed positions must be retrieved from transaction history
                # For now, we only show open positions from OANDA

            except OandaAPIError as e:
                logger.error(
                    "Failed to fetch positions from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                # Continue with other accounts

        # Sort by open time (newest first)
        all_positions.sort(key=lambda x: str(x.get("open_time") or ""), reverse=True)

        logger.info(
            "Positions retrieved from OANDA",
            extra={
                "user_id": request.user.id,
                "account_id": account_id,
                "instrument": instrument,
                "status": position_status,
                "count": len(all_positions),
            },
        )

        return Response(
            {
                "results": all_positions,
                "count": len(all_positions),
            }
        )


class PositionDetailView(APIView):
    """
    API endpoint for position detail retrieval from OANDA API.

    GET /api/positions/{trade_id}
    - Retrieve detailed information for a specific trade/position from OANDA
    - trade_id is the OANDA trade ID
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, position_id: str) -> Response:
        """
        Retrieve position details from OANDA API.

        Args:
            request: HTTP request
            position_id: OANDA Trade ID

        Returns:
            Response with position data from OANDA
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            trades = client.get_open_trades()
            trade: OpenTrade | None = next((t for t in trades if t.trade_id == position_id), None)

            if not trade:
                return Response(
                    {"error": "Position not found or already closed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            trade_data = {
                "id": trade.trade_id,
                "instrument": trade.instrument,
                "direction": trade.direction.value,
                "units": str(trade.units),
                "entry_price": str(trade.entry_price),
                "unrealized_pnl": str(trade.unrealized_pnl),
                "open_time": trade.open_time.isoformat() if trade.open_time else None,
                "state": trade.state,
                "account_name": account.account_id,
                "account_db_id": account.pk,
            }

            logger.info(
                "Position details retrieved from OANDA",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                },
            )

            return Response(trade_data, status=status.HTTP_200_OK)

        except OandaAPIError as e:
            logger.error("Failed to fetch position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to fetch position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request: Request, position_id: str) -> Response:
        """
        Close a position via OANDA API.

        PATCH /api/positions/{trade_id}

        Body (optional):
            - account_id: OANDA account database ID (required)
            - units: Number of units to close (optional, closes all if not provided)
        """
        account_id = request.data.get("account_id") or request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.id)
        except (ValueError, TypeError):
            return Response(
                {"error": "Invalid account_id"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        units_str = request.data.get("units")
        units = Decimal(str(units_str)) if units_str else None

        try:
            client = OandaService(account)
            trades = client.get_open_trades()
            trade = next((t for t in trades if t.trade_id == position_id), None)
            if not trade:
                return Response(
                    {"error": "Position not found or already closed"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            result = client.close_trade(trade, units=units)

            logger.info(
                "Position closed via OANDA API",
                extra={
                    "user_id": request.user.id,
                    "position_id": position_id,
                    "units": str(units) if units else "ALL",
                },
            )

            return Response(
                {
                    "message": "Position closed successfully",
                    "details": {
                        "id": result.order_id,
                        "instrument": result.instrument,
                        "type": result.order_type.value,
                        "direction": result.direction.value,
                        "units": str(result.units),
                        "price": str(result.price) if result.price is not None else None,
                        "state": result.state.value,
                        "fill_time": result.fill_time.isoformat() if result.fill_time else None,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to close position %s: %s", position_id, str(e))
            return Response(
                {"error": f"Failed to close position: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrderView(APIView):
    """
    API endpoint for order listing and creation.

    GET /api/orders
    - List user's orders directly from OANDA API
    - Filter by account, instrument, status

    POST /api/orders
    - Submit new order (market, limit, stop, OCO)
    - Validate order parameters
    - Execute via OANDA API with retry logic

    Query Parameters (GET):
        - account_id: Filter by OANDA account ID (required)
        - instrument: Filter by currency pair (e.g., 'EUR_USD')
        - status: Filter by order status (pending, all)
        - count: Number of orders to return (default: 50)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """
        List user's orders directly from OANDA API.

        Args:
            request: HTTP request with query parameters

        Returns:
            Response with order list from OANDA
        """
        account_id = request.query_params.get("account_id")
        instrument = request.query_params.get("instrument")
        order_status = request.query_params.get("status", "all").lower()
        count = int(request.query_params.get("count", "50"))

        # If no account_id specified, get orders from all user accounts
        if account_id:
            try:
                accounts = [OandaAccount.objects.get(id=int(account_id), user=request.user.pk)]
            except OandaAccount.DoesNotExist:
                return Response(
                    {"error": "Account not found or access denied"},
                    status=status.HTTP_404_NOT_FOUND,
                )
        else:
            accounts = list(OandaAccount.objects.filter(user=request.user.pk, is_active=True))

        if not accounts:
            return Response({"results": [], "count": 0})

        all_orders = []

        for account in accounts:
            try:
                client = OandaService(account)

                if order_status == "pending":
                    # Get only pending orders
                    for pending_order in client.get_pending_orders(instrument=instrument):
                        all_orders.append(
                            {
                                "id": pending_order.order_id,
                                "instrument": pending_order.instrument,
                                "type": pending_order.order_type.value,
                                "direction": pending_order.direction.value,
                                "units": str(pending_order.units),
                                "price": (
                                    str(pending_order.price)
                                    if pending_order.price is not None
                                    else None
                                ),
                                "state": pending_order.state.value,
                                "time_in_force": pending_order.time_in_force,
                                "create_time": (
                                    pending_order.create_time.isoformat()
                                    if pending_order.create_time
                                    else None
                                ),
                                "fill_time": (
                                    pending_order.fill_time.isoformat()
                                    if pending_order.fill_time
                                    else None
                                ),
                                "cancel_time": (
                                    pending_order.cancel_time.isoformat()
                                    if pending_order.cancel_time
                                    else None
                                ),
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                            }
                        )
                else:
                    # Get order history (includes all states)
                    for order in client.get_order_history(
                        instrument=instrument,
                        count=count,
                        state="ALL",
                    ):
                        all_orders.append(
                            {
                                "id": order.order_id,
                                "instrument": order.instrument,
                                "type": order.order_type.value,
                                "direction": order.direction.value,
                                "units": str(order.units),
                                "price": str(order.price) if order.price is not None else None,
                                "state": order.state.value,
                                "time_in_force": order.time_in_force,
                                "create_time": (
                                    order.create_time.isoformat() if order.create_time else None
                                ),
                                "fill_time": (
                                    order.fill_time.isoformat() if order.fill_time else None
                                ),
                                "cancel_time": (
                                    order.cancel_time.isoformat() if order.cancel_time else None
                                ),
                                "account_name": account.account_id,
                                "account_db_id": account.pk,
                            }
                        )

            except OandaAPIError as e:
                logger.error(
                    "Failed to fetch orders from OANDA for account %s: %s",
                    account.account_id,
                    str(e),
                )
                # Continue with other accounts

        # Sort by create_time (newest first)
        all_orders.sort(key=lambda x: str(x.get("create_time") or ""), reverse=True)

        # Limit total results
        all_orders = all_orders[:count]

        return Response(
            {
                "results": all_orders,
                "count": len(all_orders),
            }
        )

    def post(  # pylint: disable=too-many-locals,too-many-return-statements
        self, request: Request
    ) -> Response:
        """
        Submit a new order.

        Args:
            request: HTTP request with order data

        Returns:
            Response with created order details or error
        """
        from apps.market.serializers import OrderSerializer

        # Validate request data
        serializer = OrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Get account ID from request
        account_id = request.data.get("account_id")
        if not account_id:
            return Response(
                {"error": "account_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify account belongs to user
        try:
            account = OandaAccount.objects.get(id=account_id, user=request.user.pk)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Extract order parameters
        validated_data = serializer.validated_data
        instrument = validated_data["instrument"]
        order_type = validated_data["order_type"]
        direction = validated_data["direction"]
        units = validated_data["units"]

        # Convert direction to signed units (positive for long, negative for short)
        signed_units = units if direction == "long" else -units

        # Get optional parameters
        price = validated_data.get("price")
        take_profit = validated_data.get("take_profit")
        stop_loss = validated_data.get("stop_loss")
        limit_price = validated_data.get("limit_price")
        stop_price = validated_data.get("stop_price")

        # Execute order via OANDA API
        try:
            result: Order
            if order_type == "market":
                client = OandaService(account)
                result = client.create_market_order(
                    MarketOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "limit":
                client = OandaService(account)
                result = client.create_limit_order(
                    LimitOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        price=price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "stop":
                client = OandaService(account)
                result = client.create_stop_order(
                    StopOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        price=price,
                        take_profit=take_profit,
                        stop_loss=stop_loss,
                    )
                )
            elif order_type == "oco":
                client = OandaService(account)
                oco_order = client.create_oco_order(
                    OcoOrderRequest(
                        instrument=instrument,
                        units=signed_units,
                        limit_price=limit_price,
                        stop_price=stop_price,
                    )
                )
                # Return both order responses for OCO
                return Response(
                    {
                        "oco_order": self._format_order_response(oco_order),
                        "limit_order": (
                            self._format_order_response(oco_order.limit_order)
                            if oco_order.limit_order
                            else None
                        ),
                        "stop_order": (
                            self._format_order_response(oco_order.stop_order)
                            if oco_order.stop_order
                            else None
                        ),
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                return Response(
                    {"error": f"Unsupported order type: {order_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Return created order
            return Response(
                self._format_order_response(result),
                status=status.HTTP_201_CREATED,
            )

        except (OandaAPIError, ComplianceViolationError) as e:
            logger.error("Order execution failed: %s", e)
            return Response(
                {"error": f"Order execution failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Unexpected error during order submission: %s", e)
            return Response(
                {"error": "An unexpected error occurred"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _format_order_response(self, order_result: Order) -> dict:
        """Format an Order object for API response."""
        return {
            "id": order_result.order_id,
            "instrument": order_result.instrument,
            "type": order_result.order_type.value,
            "direction": order_result.direction.value,
            "units": str(order_result.units),
            "price": str(order_result.price) if order_result.price is not None else None,
            "state": order_result.state.value,
            "time_in_force": order_result.time_in_force,
            "create_time": (
                order_result.create_time.isoformat() if order_result.create_time else None
            ),
            "fill_time": order_result.fill_time.isoformat() if order_result.fill_time else None,
            "cancel_time": (
                order_result.cancel_time.isoformat() if order_result.cancel_time else None
            ),
        }

    def _format_order_from_model(self, order: Any) -> dict:
        """Format Order model instance for API response."""
        return {
            "id": order.order_id,
            "instrument": order.instrument,
            "type": order.order_type,
            "units": str(order.units),
            "price": str(order.price) if order.price else None,
            "state": order.status.upper() if order.status else "PENDING",
            "create_time": order.created_at.isoformat() if order.created_at else None,
        }


class OrderDetailView(APIView):
    """
    API endpoint for order details and cancellation.

    GET /api/orders/{order_id}
    - Retrieve order details from OANDA API
    - order_id is the OANDA order ID

    DELETE /api/orders/{order_id}
    - Cancel a pending order via OANDA API
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request, order_id: str) -> Response:
        """
        Retrieve order details from OANDA API.

        Args:
            request: HTTP request
            order_id: OANDA Order ID

        Returns:
            Response with order details or error
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            order = client.get_order(order_id)

            return Response(
                {
                    "id": order.order_id,
                    "instrument": order.instrument,
                    "type": order.order_type.value,
                    "direction": order.direction.value,
                    "units": str(order.units),
                    "price": str(order.price) if order.price is not None else None,
                    "state": order.state.value,
                    "time_in_force": order.time_in_force,
                    "create_time": order.create_time.isoformat() if order.create_time else None,
                    "fill_time": order.fill_time.isoformat() if order.fill_time else None,
                    "cancel_time": order.cancel_time.isoformat() if order.cancel_time else None,
                }
            )

        except OandaAPIError as e:
            logger.error("Failed to fetch order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to fetch order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def delete(self, request: Request, order_id: str) -> Response:
        """
        Cancel a pending order via OANDA API.

        Args:
            request: HTTP request
            order_id: OANDA Order ID

        Returns:
            Response with success message or error
        """
        account_id = request.query_params.get("account_id")

        if not account_id:
            return Response(
                {"error": "account_id query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            account = OandaAccount.objects.get(id=int(account_id), user=request.user.pk)
        except OandaAccount.DoesNotExist:
            return Response(
                {"error": "Account not found or access denied"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            client = OandaService(account)
            order = client.get_order(order_id)
            result = client.cancel_order(order)

            return Response(
                {
                    "message": "Order cancelled successfully",
                    "details": {
                        "order_id": result.order_id,
                        "transaction_id": result.transaction_id,
                        "time": result.cancel_time.isoformat() if result.cancel_time else None,
                        "state": result.state.value,
                    },
                },
                status=status.HTTP_200_OK,
            )

        except OandaAPIError as e:
            logger.error("Failed to cancel order %s: %s", order_id, str(e))
            return Response(
                {"error": f"Failed to cancel order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
