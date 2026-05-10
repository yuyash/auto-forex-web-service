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
from apps.market.services.instruments import (
    OandaAccountSelector,
    OandaInstrumentCache,
    OandaInstrumentCatalogService,
)
from apps.market.services.oanda_retry import OandaApiRequestExecutor
from apps.trading import utils as trading_utils

logger: Logger = getLogger(name=__name__)

INSTRUMENTS_CACHE_TTL_SECONDS = 24 * 60 * 60
INSTRUMENT_DETAIL_CACHE_TTL_SECONDS = 60 * 60


class InstrumentMetadataSerializer(serializers.Serializer):
    """Serializer for instrument metadata derived from the instrument symbol."""

    normalized_name = serializers.CharField()
    base_currency = serializers.CharField()
    quote_currency = serializers.CharField()
    pip_size = serializers.CharField()
    is_high_value_quote = serializers.BooleanField()


class InstrumentMetadataPresenter:
    """Derive display-safe instrument metadata from canonical value objects."""

    def for_instrument(self, instrument_name: str) -> dict[str, str | bool]:
        """Return base/quote/pip metadata for one instrument."""
        return trading_utils.Instrument(instrument_name).as_metadata()

    def for_many(self, instrument_names: list[str]) -> dict[str, dict[str, str | bool]]:
        """Return metadata keyed by normalized instrument name."""
        metadata: dict[str, dict[str, str | bool]] = {}
        for instrument_name in instrument_names:
            item = self.for_instrument(instrument_name)
            normalized_name = str(item["normalized_name"])
            if item["base_currency"] and item["quote_currency"]:
                metadata[normalized_name] = item
        return metadata


class OandaInstrumentServiceMixin:
    """Build instrument services with view-level injectable collaborators."""

    request_executor = OandaApiRequestExecutor()
    metadata_presenter = InstrumentMetadataPresenter()

    def _instrument_service(self) -> OandaInstrumentCatalogService:
        """Return the service object used by instrument endpoints."""
        return OandaInstrumentCatalogService(
            account_selector=OandaAccountSelector(account_model=OandaAccounts),
            instrument_cache=OandaInstrumentCache(
                cache_backend=cache,
                instruments_ttl_seconds=INSTRUMENTS_CACHE_TTL_SECONDS,
                detail_ttl_seconds=INSTRUMENT_DETAIL_CACHE_TTL_SECONDS,
            ),
            v20_module=v20,
            request_executor=self.request_executor,
        )


class SupportedInstrumentsView(OandaInstrumentServiceMixin, APIView):
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
                    "metadata": serializers.DictField(child=InstrumentMetadataSerializer()),
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
                    "metadata": self.metadata_presenter.for_many(instruments),
                }
            )

        # Fallback to default list
        logger.warning("Using fallback instruments list")
        return Response(
            {
                "instruments": self.FALLBACK_INSTRUMENTS,
                "count": len(self.FALLBACK_INSTRUMENTS),
                "source": "fallback",
                "metadata": self.metadata_presenter.for_many(self.FALLBACK_INSTRUMENTS),
            }
        )

    def _get_cached_instruments(self, account: OandaAccounts) -> list[str] | None:
        return self._instrument_service().instrument_cache.supported_instruments(account)

    def _set_cached_instruments(self, account: OandaAccounts, instruments: list[str]) -> None:
        self._instrument_service().instrument_cache.set_supported_instruments(
            account=account,
            instruments=instruments,
        )

    def _fetch_instruments_from_oanda(self, request: Request) -> list[str] | None:
        """
        Fetch available instruments from OANDA API.

        Returns:
            List of instrument names or None if fetch fails
        """
        user_id = getattr(request.user, "id", None)
        return self._instrument_service().supported_instruments_for_user(user_id)


class InstrumentDetailView(OandaInstrumentServiceMixin, APIView):
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
                    "normalized_name": serializers.CharField(),
                    "base_currency": serializers.CharField(),
                    "quote_currency": serializers.CharField(),
                    "pip_size": serializers.CharField(),
                    "is_high_value_quote": serializers.BooleanField(),
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
            instrument_data.update(self.metadata_presenter.for_instrument(instrument))
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
        user_id = getattr(request.user, "id", None)
        return self._instrument_service().instrument_details_for_user(
            user_id=user_id,
            instrument=instrument,
        )

    def _get_cached_instrument_detail(
        self, account: OandaAccounts, instrument: str
    ) -> dict[str, Any] | None:
        return self._instrument_service().instrument_cache.detail(
            account=account,
            instrument=instrument,
        )

    def _fetch_and_cache_instrument_detail(
        self, api: v20.Context, account: OandaAccounts, instrument: str
    ) -> dict[str, Any] | None:
        return self._instrument_service().fetch_and_cache_detail(
            api=api,
            account=account,
            instrument=instrument,
        )

    def _fetch_current_pricing(
        self, api: v20.Context, account_id: str, instrument: str
    ) -> dict[str, Any] | None:
        """Fetch current pricing for spread calculation."""
        return self._instrument_service().current_pricing(
            api=api,
            account_id=account_id,
            instrument=instrument,
        )
