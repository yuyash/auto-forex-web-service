"""Candle data views."""

from datetime import UTC, datetime
from logging import Logger, getLogger
from typing import Any

import v20
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts
from apps.market.views.account_helpers import get_user_default_account

logger: Logger = getLogger(name=__name__)

# Granularity → seconds lookup (module-level constant).
_GRANULARITY_SECONDS: dict[str, int] = {
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
    "M": 2592000,
}


class OandaCandleFetchError(Exception):
    """Raised when OANDA candle API returns a non-success status."""

    def __init__(self, status_code: int, body: Any = None):
        super().__init__(f"OANDA candles request failed (status={status_code})")
        self.status_code = status_code
        self.body = body


def _parse_candles(raw_candles: list[Any]) -> list[dict[str, Any]]:
    """Convert raw v20 Candlestick objects into JSON-serialisable dicts."""
    result: list[dict[str, Any]] = []
    for candle in raw_candles:
        if not candle.complete:
            continue
        mid = candle.mid
        if not mid or not all([mid.o, mid.h, mid.l, mid.c]):
            continue
        try:
            time_obj = datetime.fromisoformat(candle.time.replace("Z", "+00:00"))
            timestamp = int(time_obj.timestamp())
        except (ValueError, AttributeError):
            continue
        result.append(
            {
                "time": timestamp,
                "open": float(mid.o),
                "high": float(mid.h),
                "low": float(mid.l),
                "close": float(mid.c),
                "volume": int(candle.volume),
            }
        )
    return result


def _fetch_oanda_candles(
    api_context: v20.Context,
    instrument: str,
    **params: Any,
) -> list[Any]:
    """Single OANDA candle request with error handling."""
    response = api_context.instrument.candles(instrument=instrument, **params)
    if response.status != 200:
        raise OandaCandleFetchError(status_code=int(response.status), body=response.body)
    return response.body.get("candles", []) if response.body else []


class CandleDataView(APIView):
    """API endpoint for fetching candle data."""

    permission_classes = [IsAuthenticated]
    throttle_classes: list = []

    @extend_schema(
        operation_id="market_candles",
        tags=["Market"],
        parameters=[
            OpenApiParameter(name="instrument", type=str, required=True),
            OpenApiParameter(name="granularity", type=str, required=False, default="H1"),
            OpenApiParameter(name="count", type=int, required=False, default=100),
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
        count_raw = request.query_params.get("count", "100")
        try:
            count_int = int(count_raw)
            if count_int < 1 or count_int > 5000:
                return {}, Response(
                    {"error": "count must be between 1 and 5000"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except ValueError:
            return {}, Response(
                {"error": "count must be a valid integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from_time = request.query_params.get("from_time")
        to_time = request.query_params.get("to_time")

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
            )

            raw_candles = self._dispatch_fetch(api_context, params)
            candles_data = _parse_candles(raw_candles)

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
            return _fetch_oanda_candles(
                api_context, instrument, toTime=cursor_time, count=count_int, **base
            )

        # Cursor: newer data
        cursor_time = self._unix_to_rfc3339(after, offset=1)
        if cursor_time and not from_time and not to_time and not before:
            return _fetch_oanda_candles(
                api_context, instrument, fromTime=cursor_time, count=count_int, **base
            )

        # Default: most recent
        return _fetch_oanda_candles(api_context, instrument, count=count_int, **base)

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
        try:
            from_dt = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
            to_dt = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            logger.error("Failed to parse time range: %s", e)
            return []

        granularity_seconds = _GRANULARITY_SECONDS.get(granularity, 3600)
        estimated = int((to_dt - from_dt).total_seconds() / granularity_seconds)

        if estimated > 5000:
            return self._fetch_candles_paginated(
                api_context, instrument, granularity, from_dt, to_dt
            )

        return _fetch_oanda_candles(
            api_context, instrument, fromTime=from_time, toTime=to_time, **base
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
        upstream_message = ""
        if isinstance(body, dict):
            upstream_message = str(body.get("errorMessage") or body.get("message") or "")

        if oanda_status in (401, 403):
            return Response(
                {
                    "error": "OANDA authentication/authorization failed",
                    "error_code": "OANDA_AUTH_FAILED",
                    "oanda_status": oanda_status,
                    "details": upstream_message or None,
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
                    "details": upstream_message or None,
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
        all_candles: list[Any] = []
        current_from = from_dt
        granularity_seconds = _GRANULARITY_SECONDS.get(granularity, 3600)

        while current_from < to_dt:
            current_to = datetime.fromtimestamp(
                min(current_from.timestamp() + 5000 * granularity_seconds, to_dt.timestamp()),
                tz=UTC,
            )

            from_str = current_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            to_str = current_to.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

            try:
                batch = _fetch_oanda_candles(
                    api_context,
                    instrument,
                    granularity=granularity,
                    fromTime=from_str,
                    toTime=to_str,
                )
            except OandaCandleFetchError:
                raise
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.error("Error fetching candle batch: %s", e, exc_info=True)
                break

            if not batch:
                break

            all_candles.extend(batch)

            last_time = batch[-1].time
            last_dt = datetime.fromisoformat(last_time.replace("Z", "+00:00"))
            current_from = datetime.fromtimestamp(last_dt.timestamp() + granularity_seconds, tz=UTC)

        logger.info("Pagination complete: fetched %d total candles", len(all_candles))
        return all_candles
