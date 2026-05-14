"""Candle data views."""

from datetime import UTC, datetime
from logging import Logger, getLogger
from typing import Any

import v20
from v20.errors import V20Timeout
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.querying import OrderingConfig
from apps.market.models import OandaAccounts
from apps.market.services.oanda_candles import (
    OANDA_GRANULARITY_SECONDS,
    OandaCandleFetchError,
    OandaCandleGateway,
    OandaCandleHistoryService,
    OandaCandleParser,
)
from apps.market.views.account_helpers import get_user_default_account

logger: Logger = getLogger(name=__name__)

_GRANULARITY_SECONDS = OANDA_GRANULARITY_SECONDS

CANDLE_ORDERING = OrderingConfig(
    fields={"time": "time", "timestamp": "time"},
    default="time",
    tie_breakers=(),
)


class CandleDataView(APIView):
    """API endpoint for fetching candle data."""

    permission_classes = [IsAuthenticated]
    throttle_classes: list = []
    candle_parser = OandaCandleParser()
    candle_history = OandaCandleHistoryService(
        gateway=OandaCandleGateway(),
        parser=candle_parser,
        granularity_seconds=_GRANULARITY_SECONDS,
    )

    @extend_schema(
        operation_id="market_candles",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
            OpenApiParameter(name="granularity", type=str, required=False, default="H1"),
            OpenApiParameter(
                name="count",
                type=int,
                required=False,
                default=100,
                description="Deprecated alias for page_size.",
            ),
            OpenApiParameter(name="page_size", type=int, required=False, default=100),
            OpenApiParameter(name="ordering", type=str, required=False),
            OpenApiParameter(name="from_time", type=str, required=False),
            OpenApiParameter(name="to_time", type=str, required=False),
            OpenApiParameter(name="before", type=str, required=False),
            OpenApiParameter(name="after", type=str, required=False),
            OpenApiParameter(name="account_id", type=str, required=False),
        ],
        responses={
            200: inline_serializer(
                "CandleDataResponse",
                fields={
                    "instrument": serializers.CharField(),
                    "granularity": serializers.CharField(),
                    "candles": serializers.ListField(
                        child=inline_serializer(
                            "CandleItem",
                            fields={
                                "time": serializers.IntegerField(),
                                "open": serializers.FloatField(),
                                "high": serializers.FloatField(),
                                "low": serializers.FloatField(),
                                "close": serializers.FloatField(),
                                "volume": serializers.IntegerField(),
                            },
                        )
                    ),
                },
            ),
        },
        description="Fetch historical candle data from OANDA.",
    )
    def get(self, request: Request) -> Response:
        """Fetch historical candle data from OANDA."""
        # --- validate params ---
        params, err = self._validate_params(request)
        if err is not None:
            return err

        # --- resolve account ---
        account, err = self._resolve_account(request, params.get("account_id"))
        if err is not None:
            return err
        assert account is not None

        # --- fetch & return ---
        return self._fetch_and_respond(account, params)

    # ------------------------------------------------------------------
    # Parameter validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_params(request: Request) -> tuple[dict[str, Any], Response | None]:
        """Parse and validate query parameters.  Returns (params_dict, error_response)."""
        instrument = request.query_params.get("instrument")
        if not instrument:
            return {}, Response(
                {"error": "instrument parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        granularity = request.query_params.get("granularity", "H1")
        count_raw = request.query_params.get("page_size") or request.query_params.get(
            "count", "100"
        )
        try:
            count_int = int(count_raw)
            if count_int < 1 or count_int >= 10000:
                return {}, Response(
                    {"error": "count/page_size must be between 1 and 9999"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return {}, Response(
                {"error": "count must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_time = request.query_params.get("from_time")
        to_time = request.query_params.get("to_time")
        ordering = CANDLE_ORDERING.normalize(request.query_params.get("ordering"))

        if from_time or to_time:
            try:
                from_dt = (
                    datetime.fromisoformat(from_time.replace("Z", "+00:00")) if from_time else None
                )
                to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00")) if to_time else None
            except ValueError:
                return {}, Response(
                    {"error": "Invalid time format"}, status=status.HTTP_400_BAD_REQUEST
                )

            now = datetime.now(UTC)
            if to_dt is not None and to_dt > now:
                to_dt = now
                to_time = to_dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            if from_dt is not None and to_dt is not None and from_dt > to_dt:
                return {}, Response(
                    {"error": "from_time must be before or equal to to_time"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        return {
            "instrument": instrument,
            "granularity": granularity,
            "count": count_int,
            "from_time": from_time,
            "to_time": to_time,
            "before": request.query_params.get("before"),
            "after": request.query_params.get("after"),
            "account_id": request.query_params.get("account_id"),
            "ordering": ordering,
        }, None

    # ------------------------------------------------------------------
    # Account resolution
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_account(
        request: Request, account_id: str | None
    ) -> tuple[OandaAccounts | None, Response | None]:
        if account_id:
            try:
                return OandaAccounts.objects.get(account_id=account_id, user=request.user.id), None
            except ObjectDoesNotExist:
                return None, Response(
                    {"error": "OANDA account not found", "error_code": "NO_OANDA_ACCOUNT"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        return get_user_default_account(request)

    # ------------------------------------------------------------------
    # Fetch candles
    # ------------------------------------------------------------------

    def _fetch_and_respond(self, account: OandaAccounts, params: dict[str, Any]) -> Response:
        instrument = params["instrument"]
        granularity = params["granularity"]

        try:
            api_context = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                application="auto-forex-trading",
                poll_timeout=int(getattr(settings, "OANDA_REST_TIMEOUT", 10)),
            )

            raw_candles = self._dispatch_fetch(api_context, params)
            candles_data = CANDLE_ORDERING.sort_records(
                self.candle_parser.parse_many(raw_candles),
                params.get("ordering"),
            )

            return Response(
                {"instrument": instrument, "granularity": granularity, "candles": candles_data},
                status=status.HTTP_200_OK,
                headers={
                    "X-Cache-Hit": "false",
                    "X-Cache-Status": "disabled",
                    "X-Rate-Limited": "false",
                },
            )

        except OandaCandleFetchError as e:
            logger.error("Failed to fetch candles: status=%d, body=%s", e.status_code, e.body)
            return self._build_oanda_error_response(oanda_status=e.status_code, body=e.body)
        except V20Timeout as e:
            logger.warning("OANDA candle request timed out: %s", e)
            return Response(
                {
                    "error": "OANDA API request timed out. Please try a smaller date range or try again later.",
                    "error_code": "OANDA_TIMEOUT",
                },
                status=status.HTTP_504_GATEWAY_TIMEOUT,
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error("Error fetching candles: %s", e, exc_info=True)
            if "429" in str(e) or "rate limit" in str(e).lower():
                return Response(
                    {"error": "Rate limit exceeded. Please try again later."},
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            return Response(
                {"error": "Failed to fetch candles"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _dispatch_fetch(self, api_context: v20.Context, params: dict[str, Any]) -> list[Any]:
        """Choose the right OANDA fetch strategy based on query params."""
        instrument = params["instrument"]
        granularity = params["granularity"]
        count_int = params["count"]
        from_time = params["from_time"]
        to_time = params["to_time"]
        before = params["before"]
        after = params["after"]

        base = {"granularity": granularity}

        # Range query
        if from_time and to_time:
            return self._fetch_range(api_context, instrument, granularity, from_time, to_time, base)

        # Cursor: older data
        cursor_time = self._unix_to_rfc3339(before, offset=-1)
        if cursor_time and not from_time and not to_time and not after:
            return self._fetch_count_paginated(
                api_context,
                instrument,
                granularity,
                count_int,
                direction="backward",
                cursor_time=cursor_time,
            )

        # Cursor: newer data
        cursor_time = self._unix_to_rfc3339(after, offset=1)
        if cursor_time and not from_time and not to_time and not before:
            return self._fetch_count_paginated(
                api_context,
                instrument,
                granularity,
                count_int,
                direction="forward",
                cursor_time=cursor_time,
            )

        # Default: most recent
        return self._fetch_count_paginated(
            api_context,
            instrument,
            granularity,
            count_int,
            direction="backward",
        )

    def _fetch_range(
        self,
        api_context: v20.Context,
        instrument: str,
        granularity: str,
        from_time: str,
        to_time: str,
        base: dict[str, Any],
    ) -> list[Any]:
        """Fetch candles for a from/to range, paginating if needed."""
        return self.candle_history.fetch_range(
            api_context,
            instrument,
            granularity,
            from_time,
            to_time,
            base,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _unix_to_rfc3339(raw: str | None, offset: int = 0) -> str | None:
        """Convert a Unix timestamp string to RFC3339, applying *offset* seconds."""
        if not raw:
            return None
        try:
            ts = int(raw) + offset
            return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except (ValueError, OSError) as e:
            logger.warning("Failed to parse timestamp '%s': %s", raw, e)
            return None

    def _build_oanda_error_response(self, *, oanda_status: int, body: Any) -> Response:
        """Translate OANDA error status to API response."""
        logger.warning(
            "OANDA candles request failed",
            extra={"oanda_status": oanda_status, "upstream_body_type": type(body).__name__},
        )

        if oanda_status in (401, 403):
            return Response(
                {
                    "error": "OANDA authentication/authorization failed",
                    "error_code": "OANDA_AUTH_FAILED",
                    "oanda_status": oanda_status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if oanda_status == 429:
            return Response(
                {"error": "Rate limit exceeded. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        if 400 <= oanda_status < 500:
            return Response(
                {
                    "error": "Invalid request to OANDA candles endpoint",
                    "error_code": "OANDA_BAD_REQUEST",
                    "oanda_status": oanda_status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                "error": "Failed to fetch candles from OANDA",
                "error_code": "OANDA_UPSTREAM_ERROR",
                "oanda_status": oanda_status,
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    def _fetch_candles_paginated(
        self,
        api_context: v20.Context,
        instrument: str,
        granularity: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[Any]:
        """Fetch candles in batches when the range exceeds 5000."""
        return self.candle_history.fetch_paginated(
            api_context,
            instrument,
            granularity,
            from_dt,
            to_dt,
        )

    def _fetch_count_paginated(
        self,
        api_context: v20.Context,
        instrument: str,
        granularity: str,
        total_count: int,
        *,
        direction: str,
        cursor_time: str | None = None,
    ) -> list[Any]:
        """Fetch candles in batches when count-based requests exceed OANDA's 5000 cap."""
        return self.candle_history.fetch_count_paginated(
            api_context,
            instrument,
            granularity,
            total_count,
            direction=direction,
            cursor_time=cursor_time,
        )
