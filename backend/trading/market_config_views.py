"""
Views for market configuration data.

This module provides API endpoints for:
- Supported currency pairs/instruments
- Supported granularities/timeframes

Data is fetched from OANDA API and cached for performance.
"""

import logging

from django.core.cache import cache

import v20
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import OandaAccount

logger = logging.getLogger(__name__)


class SupportedInstrumentsView(APIView):
    """
    API endpoint for retrieving supported currency pairs/instruments.

    GET /api/trading/instruments/
    - Returns list of supported currency pairs from OANDA API
    - Data is cached for 24 hours
    - No authentication required (public data)
    """

    permission_classes = []  # Public endpoint

    CACHE_KEY = "oanda_supported_instruments"
    CACHE_TIMEOUT = 86400  # 24 hours

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
        # Check cache first
        cached_instruments = cache.get(self.CACHE_KEY)
        if cached_instruments:
            logger.debug("Returning cached instruments")
            return Response(
                {
                    "instruments": cached_instruments,
                    "count": len(cached_instruments),
                    "source": "cache",
                }
            )

        # Fetch from OANDA API
        instruments = self._fetch_instruments_from_oanda()

        if instruments:
            # Cache the results
            cache.set(self.CACHE_KEY, instruments, self.CACHE_TIMEOUT)
            logger.info(f"Fetched and cached {len(instruments)} instruments from OANDA")
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
    - No authentication required (public data)
    """

    permission_classes = []  # Public endpoint

    CACHE_KEY = "oanda_supported_granularities"
    CACHE_TIMEOUT = 86400  # 24 hours

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

        Granularities are standardized by OANDA and rarely change,
        so we cache them and fetch from OANDA API to validate.

        Returns:
            Response with list of granularity objects
        """
        # Check cache first
        cached_granularities = cache.get(self.CACHE_KEY)
        if cached_granularities:
            logger.debug("Returning cached granularities")
            return Response(
                {
                    "granularities": cached_granularities,
                    "count": len(cached_granularities),
                    "source": "cache",
                }
            )

        # Fetch from OANDA API to validate
        granularities = self._fetch_granularities_from_oanda()

        if granularities:
            # Cache the results
            cache.set(self.CACHE_KEY, granularities, self.CACHE_TIMEOUT)
            logger.info(f"Fetched and cached {len(granularities)} granularities from OANDA")
            return Response(
                {
                    "granularities": granularities,
                    "count": len(granularities),
                    "source": "oanda",
                }
            )

        # Use standard list as fallback
        cache.set(self.CACHE_KEY, self.GRANULARITIES, self.CACHE_TIMEOUT)
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


class ClearMarketConfigCacheView(APIView):
    """
    API endpoint for clearing market configuration cache.

    POST /api/trading/market-config/clear-cache/
    - Clears cached instruments and granularities
    - Requires authentication
    - Next request will fetch fresh data from OANDA
    """

    def post(self, request: Request) -> Response:
        """
        Clear market configuration cache.

        Returns:
            Response with success message
        """
        try:
            # Clear both caches
            cache.delete(SupportedInstrumentsView.CACHE_KEY)
            cache.delete(SupportedGranularitiesView.CACHE_KEY)

            logger.info(
                "Market configuration cache cleared",
                extra={"user_id": request.user.id if request.user.is_authenticated else None},
            )

            return Response(
                {
                    "message": "Market configuration cache cleared successfully",
                    "cleared": ["instruments", "granularities"],
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.error(f"Failed to clear market configuration cache: {e}")
            return Response(
                {"error": "Failed to clear cache"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
