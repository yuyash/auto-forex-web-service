"""Instruments views."""

from logging import Logger, getLogger
from typing import Any

import v20
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.market.models import OandaAccounts

logger: Logger = getLogger(name=__name__)


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
        summary="GET /api/market/instruments/",
        description="Retrieve list of supported currency pairs from OANDA API",
        operation_id="list_supported_instruments",
        tags=["market"],
        responses={200: dict},
    )
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
            account = OandaAccounts.objects.filter(is_active=True).first()
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
        summary="GET /api/market/instruments/{instrument}/",
        description="Fetch detailed information about a specific currency pair",
        operation_id="get_instrument_detail",
        tags=["market"],
        parameters=[
            OpenApiParameter(
                name="instrument",
                type=str,
                location=OpenApiParameter.PATH,
                required=True,
                description="Currency pair (e.g., EUR_USD)",
            ),
        ],
        responses={200: dict},
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
            user_id = request.user.id
            if not user_id:
                return None
            # Get user's OANDA account or any active account
            account = (
                OandaAccounts.objects.filter(user_id=user_id, is_active=True).first()
                or OandaAccounts.objects.filter(is_active=True).first()
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
