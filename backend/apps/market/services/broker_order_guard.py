"""Safety guardrails for broker-bound order requests."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from apps.market.services.live_trading_policy import LiveTradingPolicy, get_live_trading_policy


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

        policy = get_live_trading_policy()
        self._validate_account_mode(account, policy)
        self._validate_instrument(instrument, policy)
        self._validate_units(units, policy)

    def _validate_account_mode(self, account: Any, policy: LiveTradingPolicy) -> None:
        api_type = str(getattr(account, "api_type", "")).strip().lower()
        if api_type != "live":
            return
        if policy.allow_live_oanda:
            return
        raise BrokerOrderGuardError(
            "Live OANDA accounts are disabled. Set TRADING_ALLOW_LIVE_OANDA=true before "
            "submitting broker orders on live accounts."
        )

    def _validate_instrument(self, instrument: str, policy: LiveTradingPolicy) -> None:
        normalized = str(instrument or "").strip().upper()
        if not normalized:
            raise BrokerOrderGuardError("Instrument is required for broker order submission.")

        if policy.allows_instrument(normalized):
            return

        raise BrokerOrderGuardError(
            f"Instrument {normalized} is not enabled for broker order submission. "
            "Update TRADING_LIVE_ALLOWED_INSTRUMENTS to allow it."
        )

    def _validate_units(self, units: Decimal | int | str, policy: LiveTradingPolicy) -> None:
        abs_units = _abs_decimal(units)
        if abs_units <= 0:
            raise BrokerOrderGuardError("Order units must be non-zero.")

        max_units = policy.max_order_units
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
