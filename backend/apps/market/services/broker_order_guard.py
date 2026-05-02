"""Safety guardrails for broker-bound order requests."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.conf import settings

_DEFAULT_ALLOWED_INSTRUMENTS = (
    "USD_JPY",
    "EUR_USD",
    "GBP_USD",
    "AUD_USD",
    "USD_CAD",
    "USD_CHF",
    "NZD_USD",
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


class BrokerOrderGuardError(ValueError):
    """Raised when an order violates broker-bound safety guardrails."""


class BrokerOrderGuard:
    """Validate order requests before they can reach a broker API."""

    def validate_order(
        self,
        *,
        account: Any | None,
        dry_run: bool,
        instrument: str,
        units: Decimal | int | str,
    ) -> None:
        """Validate account mode, instrument, and order size for a broker order."""

        if dry_run:
            return
        if account is None:
            raise BrokerOrderGuardError("Account required for broker order submission.")
        if not bool(getattr(account, "is_active", True)):
            raise BrokerOrderGuardError("Cannot submit broker orders for an inactive account.")

        self._validate_account_mode(account)
        self._validate_instrument(instrument)
        self._validate_units(units)

    def _validate_account_mode(self, account: Any) -> None:
        api_type = str(getattr(account, "api_type", "")).strip().lower()
        if api_type != "live":
            return
        if _setting_bool("TRADING_ALLOW_LIVE_OANDA", default=False):
            return
        raise BrokerOrderGuardError(
            "Live OANDA accounts are disabled. Set TRADING_ALLOW_LIVE_OANDA=true before "
            "submitting broker orders on live accounts."
        )

    def _validate_instrument(self, instrument: str) -> None:
        normalized = str(instrument or "").strip().upper()
        if not normalized:
            raise BrokerOrderGuardError("Instrument is required for broker order submission.")

        allowed = _setting_instruments(
            "TRADING_LIVE_ALLOWED_INSTRUMENTS",
            default=_DEFAULT_ALLOWED_INSTRUMENTS,
        )
        if "*" in allowed or normalized in allowed:
            return

        raise BrokerOrderGuardError(
            f"Instrument {normalized} is not enabled for broker order submission. "
            "Update TRADING_LIVE_ALLOWED_INSTRUMENTS to allow it."
        )

    def _validate_units(self, units: Decimal | int | str) -> None:
        abs_units = _abs_decimal(units)
        if abs_units <= 0:
            raise BrokerOrderGuardError("Order units must be non-zero.")

        max_units = _setting_positive_int("TRADING_LIVE_MAX_ORDER_UNITS", default=10_000)
        if max_units and abs_units > Decimal(max_units):
            raise BrokerOrderGuardError(
                "Order size exceeds the configured broker order limit "
                f"({abs_units} > {max_units}). "
                "Reduce order units or raise TRADING_LIVE_MAX_ORDER_UNITS."
            )


def _abs_decimal(value: Any) -> Decimal:
    try:
        return abs(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        raise BrokerOrderGuardError("Order units must be numeric.") from None


def _setting_bool(name: str, *, default: bool) -> bool:
    value = getattr(settings, name, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in _TRUE_VALUES


def _setting_positive_int(name: str, *, default: int) -> int:
    value = getattr(settings, name, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 0)


def _setting_instruments(name: str, *, default: tuple[str, ...]) -> set[str]:
    value = getattr(settings, name, default)
    if isinstance(value, str):
        items = value.split(",")
    else:
        items = value
    return {str(item).strip().upper() for item in items if str(item).strip()}
