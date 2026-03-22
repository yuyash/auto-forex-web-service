"""Instruments views."""

from logging import Logger, getLogger
from typing import Any

import v20
from django.core.cache import cache
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts

logger: Logger = getLogger(name=__name__)

INSTRUMENTS_CACHE_TTL_SECONDS = 24 * 60 * 60
INSTRUMENT_DETAIL_CACHE_TTL_SECONDS = 60 * 60


def _get_user_active_account(user_id: int | None) -> OandaAccounts | None:
    """Return the requesting user's default active account when available."""
    if not user_id:
        return None

    return (
        OandaAccounts.objects.filter(user_id=user_id, is_active=True, is_default=True).first()
        or OandaAccounts.objects.filter(user_id=user_id, is_active=True).first()
    )


class SupportedInstrumentsView(APIView):
    """
    API endpoint for retrieving supported currency pairs/instruments.

    GET /api/market/instruments/
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

    @extend_schema(
        operation_id="market_instruments_list",
        tags=["Market"],
        responses={
            200: inline_serializer(
                "InstrumentsListResponse",
                fields={
                    "instruments": serializers.ListField(child=serializers.CharField()),
                    "count": serializers.IntegerField(),
                    "source": serializers.CharField(),
                },
            ),
        },
        description="Retrieve list of supported currency pairs from OANDA.",
    )
    def get(self, request: Request) -> Response:
        """
        Retrieve list of supported instruments from OANDA API.

        Returns:
            Response with list of instrument codes
        """
        # Fetch from OANDA API
        instruments = self._fetch_instruments_from_oanda(request)

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

    def _get_cached_instruments(self, account: OandaAccounts) -> list[str] | None:
        cache_key = f"market:supported_instruments:{account.api_hostname}"
        cached = cache.get(cache_key)
        if isinstance(cached, list) and all(isinstance(item, str) for item in cached):
            return cached
        return None

    def _set_cached_instruments(self, account: OandaAccounts, instruments: list[str]) -> None:
        cache_key = f"market:supported_instruments:{account.api_hostname}"
        cache.set(cache_key, instruments, INSTRUMENTS_CACHE_TTL_SECONDS)

    def _fetch_instruments_from_oanda(self, request: Request) -> list[str] | None:
        """
        Fetch available instruments from OANDA API.

        Returns:
            List of instrument names or None if fetch fails
        """
        try:
            user_id = getattr(request.user, "id", None)
            account = _get_user_active_account(user_id)
            if not account:
                logger.warning("No active OANDA account found for user %s", user_id)
                return None

            cached = self._get_cached_instruments(account)
            if cached is not None:
                return cached

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

            sorted_instruments = sorted(instruments)
            self._set_cached_instruments(account, sorted_instruments)
            return sorted_instruments

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to fetch instruments from OANDA: {e}")
            return None


class InstrumentDetailView(APIView):
    """
    API endpoint for fetching detailed information about a specific currency pair.

    GET /api/market/instruments/<instrument>/
    - Returns pip value, tick size, margin requirements, etc.
    - Requires authentication
    - Data is cached for 1 hour
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(
        operation_id="market_instrument_detail",
        tags=["Market"],
        responses={
            200: inline_serializer(
                "InstrumentDetailResponse",
                fields={
                    "instrument": serializers.CharField(),
                    "display_name": serializers.CharField(),
                    "type": serializers.CharField(),
                    "pip_location": serializers.IntegerField(),
                    "pip_value": serializers.FloatField(),
                    "display_precision": serializers.IntegerField(),
                    "trade_units_precision": serializers.IntegerField(),
                    "minimum_trade_size": serializers.CharField(),
                    "maximum_trade_units": serializers.CharField(),
                    "maximum_position_size": serializers.CharField(),
                    "maximum_order_units": serializers.CharField(),
                    "margin_rate": serializers.CharField(),
                    "leverage": serializers.CharField(),
                    "source": serializers.CharField(),
                },
            ),
            404: inline_serializer(
                "InstrumentNotFound",
                fields={"error": serializers.CharField()},
            ),
        },
        description="Get detailed information about a specific currency pair.",
    )
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
            user_id = getattr(request.user, "id", None)
            if not user_id:
                return None
            account = _get_user_active_account(user_id)

            if not account:
                logger.warning("No active OANDA account found for user %s", user_id)
                return None

            cached_detail = self._get_cached_instrument_detail(account, instrument)

            api = v20.Context(
                hostname=account.api_hostname,
                token=account.get_api_token(),
                poll_timeout=10,
            )

            # Also fetch current pricing for spread calculation
            pricing_data = self._fetch_current_pricing(api, account.account_id, instrument)

            if cached_detail is None:
                cached_detail = self._fetch_and_cache_instrument_detail(api, account, instrument)
                if cached_detail is None:
                    return None

            # Build response data
            return {
                **cached_detail,
                "current_pricing": pricing_data,
            }

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to fetch instrument details for {instrument}: {e}")
            return None

    def _get_cached_instrument_detail(
        self, account: OandaAccounts, instrument: str
    ) -> dict[str, Any] | None:
        cache_key = f"market:instrument_detail:{account.api_hostname}:{instrument}"
        cached = cache.get(cache_key)
        return cached if isinstance(cached, dict) else None

    def _fetch_and_cache_instrument_detail(
        self, api: v20.Context, account: OandaAccounts, instrument: str
    ) -> dict[str, Any] | None:
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
        detail = {
            "instrument": instr.name,
            "display_name": instr.displayName,
            "type": instr.type,
            "pip_location": instr.pipLocation,
            "pip_value": 10**instr.pipLocation,
            "display_precision": instr.displayPrecision,
            "trade_units_precision": instr.tradeUnitsPrecision,
            "minimum_trade_size": str(instr.minimumTradeSize),
            "maximum_trade_units": str(instr.maximumTradeUnits),
            "maximum_position_size": str(instr.maximumPositionSize),
            "maximum_order_units": str(instr.maximumOrderUnits),
            "margin_rate": str(instr.marginRate),
            "leverage": (
                f"1:{int(1 / float(instr.marginRate))}" if float(instr.marginRate) > 0 else "N/A"
            ),
            "guaranteed_stop_loss_order_mode": str(
                getattr(instr, "guaranteedStopLossOrderMode", "DISABLED")
            ),
            "tags": [tag.name for tag in getattr(instr, "tags", [])],
            "financing": (
                {
                    "long_rate": str(getattr(instr.financing, "longRate", "0")),
                    "short_rate": str(getattr(instr.financing, "shortRate", "0")),
                }
                if hasattr(instr, "financing") and instr.financing
                else None
            ),
        }
        cache_key = f"market:instrument_detail:{account.api_hostname}:{instrument}"
        cache.set(cache_key, detail, INSTRUMENT_DETAIL_CACHE_TTL_SECONDS)
        return detail

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
