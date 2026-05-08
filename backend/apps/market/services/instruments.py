"""OANDA instrument catalog services."""

from __future__ import annotations

from logging import Logger, getLogger
from typing import Any

from apps.market.models import OandaAccounts
from apps.market.services.cache import (
    build_instrument_detail_cache_key,
    build_supported_instruments_cache_key,
)
from apps.market.services.oanda_retry import OandaApiRequestExecutor

logger: Logger = getLogger(name=__name__)


class OandaAccountSelector:
    """Select a user's active OANDA account for market-data lookups."""

    def __init__(self, *, account_model: type[OandaAccounts] = OandaAccounts) -> None:
        self.account_model = account_model

    def active_for_user(self, user_id: int | None) -> OandaAccounts | None:
        """Return the default active account, falling back to any active account."""
        if not user_id:
            return None
        return (
            self.account_model.objects.filter(
                user_id=user_id,
                is_active=True,
                is_default=True,
            ).first()
            or self.account_model.objects.filter(user_id=user_id, is_active=True).first()
        )


class OandaInstrumentCache:
    """Cache OANDA instrument catalog responses."""

    def __init__(
        self,
        *,
        cache_backend: Any,
        instruments_ttl_seconds: int,
        detail_ttl_seconds: int,
    ) -> None:
        self.cache = cache_backend
        self.instruments_ttl_seconds = instruments_ttl_seconds
        self.detail_ttl_seconds = detail_ttl_seconds

    def supported_instruments(self, account: OandaAccounts) -> list[str] | None:
        """Return cached supported instruments for an account hostname."""
        cached = self.cache.get(build_supported_instruments_cache_key(account.api_hostname))
        if isinstance(cached, list) and all(isinstance(item, str) for item in cached):
            return cached
        return None

    def set_supported_instruments(
        self,
        *,
        account: OandaAccounts,
        instruments: list[str],
    ) -> None:
        """Cache supported instruments for an account hostname."""
        self.cache.set(
            build_supported_instruments_cache_key(account.api_hostname),
            instruments,
            self.instruments_ttl_seconds,
        )

    def detail(self, *, account: OandaAccounts, instrument: str) -> dict[str, Any] | None:
        """Return cached instrument detail when available."""
        cached = self.cache.get(build_instrument_detail_cache_key(account.api_hostname, instrument))
        return cached if isinstance(cached, dict) else None

    def set_detail(
        self,
        *,
        account: OandaAccounts,
        instrument: str,
        detail: dict[str, Any],
    ) -> None:
        """Cache instrument detail."""
        self.cache.set(
            build_instrument_detail_cache_key(account.api_hostname, instrument),
            detail,
            self.detail_ttl_seconds,
        )


class OandaInstrumentCatalogService:
    """Fetch and shape OANDA supported instruments and instrument details."""

    def __init__(
        self,
        *,
        account_selector: OandaAccountSelector,
        instrument_cache: OandaInstrumentCache,
        v20_module: Any,
        request_executor: OandaApiRequestExecutor | None = None,
    ) -> None:
        self.account_selector = account_selector
        self.instrument_cache = instrument_cache
        self.v20 = v20_module
        self.request_executor = request_executor or OandaApiRequestExecutor()

    def supported_instruments_for_user(self, user_id: int | None) -> list[str] | None:
        """Fetch supported forex instruments for a user account."""
        try:
            account = self.account_selector.active_for_user(user_id)
            if not account:
                logger.warning("No active OANDA account found for user %s", user_id)
                return None

            cached = self.instrument_cache.supported_instruments(account)
            if cached is not None:
                return cached

            api = self._api_context(account)
            response = self.request_executor.request(
                api.account.instruments,
                account.account_id,
                label="Fetch OANDA instruments",
                failure_message="Failed to fetch OANDA instruments",
            )
            instruments = self._forex_instrument_names(response.body.get("instruments", []))
            self.instrument_cache.set_supported_instruments(
                account=account,
                instruments=instruments,
            )
            return instruments
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to fetch instruments from OANDA: %s", exc)
            return None

    def instrument_details_for_user(
        self,
        *,
        user_id: int | None,
        instrument: str,
    ) -> dict[str, Any] | None:
        """Fetch instrument detail and current pricing for a user account."""
        try:
            account = self.account_selector.active_for_user(user_id)
            if not account:
                logger.warning("No active OANDA account found for user %s", user_id)
                return None

            api = self._api_context(account)
            pricing_data = self.current_pricing(
                api=api,
                account_id=account.account_id,
                instrument=instrument,
            )
            detail = self.instrument_cache.detail(account=account, instrument=instrument)
            if detail is None:
                detail = self.fetch_and_cache_detail(
                    api=api, account=account, instrument=instrument
                )
                if detail is None:
                    return None
            return {**detail, "current_pricing": pricing_data}
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Failed to fetch instrument details for %s: %s", instrument, exc)
            return None

    def fetch_and_cache_detail(
        self,
        *,
        api: Any,
        account: OandaAccounts,
        instrument: str,
    ) -> dict[str, Any] | None:
        """Fetch one instrument detail from OANDA and cache it."""
        response = self.request_executor.request(
            api.account.instruments,
            account.account_id,
            label="Fetch OANDA instrument detail",
            failure_message="Failed to fetch OANDA instrument detail",
            instruments=instrument,
        )
        instruments_list = response.body.get("instruments", [])
        if not instruments_list:
            logger.warning("Instrument %s not found", instrument)
            return None
        detail = self._detail_from_oanda(instruments_list[0])
        self.instrument_cache.set_detail(account=account, instrument=instrument, detail=detail)
        return detail

    def current_pricing(
        self,
        *,
        api: Any,
        account_id: str,
        instrument: str,
    ) -> dict[str, Any] | None:
        """Fetch current pricing for spread calculation."""
        try:
            response = self.request_executor.request(
                api.pricing.get,
                account_id,
                label="Fetch OANDA pricing",
                failure_message="Failed to fetch OANDA pricing",
                instruments=instrument,
            )
            prices = response.body.get("prices", [])
            if not prices:
                return None
            return self._pricing_from_oanda(prices[0])
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.warning("Failed to fetch pricing for %s: %s", instrument, exc)
            return None

    def _api_context(self, account: OandaAccounts) -> Any:
        return self.v20.Context(
            hostname=account.api_hostname,
            token=account.get_api_token(),
            poll_timeout=10,
        )

    def _forex_instrument_names(self, instruments: list[Any]) -> list[str]:
        names: list[str] = []
        for instrument in instruments:
            name = instrument.name
            if "_" in name and len(name) == 7:
                names.append(name)
        return sorted(names)

    def _detail_from_oanda(self, instrument: Any) -> dict[str, Any]:
        margin_rate = float(instrument.marginRate)
        return {
            "instrument": instrument.name,
            "display_name": instrument.displayName,
            "type": instrument.type,
            "pip_location": instrument.pipLocation,
            "pip_value": 10**instrument.pipLocation,
            "display_precision": instrument.displayPrecision,
            "trade_units_precision": instrument.tradeUnitsPrecision,
            "minimum_trade_size": str(instrument.minimumTradeSize),
            "maximum_trade_units": str(instrument.maximumTradeUnits),
            "maximum_position_size": str(instrument.maximumPositionSize),
            "maximum_order_units": str(instrument.maximumOrderUnits),
            "margin_rate": str(instrument.marginRate),
            "leverage": f"1:{int(1 / margin_rate)}" if margin_rate > 0 else "N/A",
            "guaranteed_stop_loss_order_mode": str(
                getattr(instrument, "guaranteedStopLossOrderMode", "DISABLED")
            ),
            "tags": [tag.name for tag in getattr(instrument, "tags", [])],
            "financing": (
                {
                    "long_rate": str(getattr(instrument.financing, "longRate", "0")),
                    "short_rate": str(getattr(instrument.financing, "shortRate", "0")),
                }
                if hasattr(instrument, "financing") and instrument.financing
                else None
            ),
        }

    def _pricing_from_oanda(self, price: Any) -> dict[str, Any]:
        bids = price.bids if hasattr(price, "bids") and price.bids else []
        asks = price.asks if hasattr(price, "asks") and price.asks else []
        best_bid = float(bids[0].price) if bids else None
        best_ask = float(asks[0].price) if asks else None

        spread = None
        spread_pips = None
        if best_bid and best_ask:
            spread = best_ask - best_bid
            spread_pips = spread * 10000

        return {
            "bid": str(best_bid) if best_bid else None,
            "ask": str(best_ask) if best_ask else None,
            "spread": f"{spread:.5f}" if spread else None,
            "spread_pips": f"{spread_pips:.1f}" if spread_pips else None,
            "tradeable": price.tradeable if hasattr(price, "tradeable") else None,
            "time": price.time if hasattr(price, "time") else None,
        }
