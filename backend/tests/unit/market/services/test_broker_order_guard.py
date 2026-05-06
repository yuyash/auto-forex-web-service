"""Tests for broker-bound order safety guardrails."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.market.services.broker_order_guard import BrokerOrderGuard, BrokerOrderGuardError


def _account(
    *,
    api_type: str = "practice",
    is_active: bool = True,
    live_max_order_guard_enabled: bool | None = None,
    live_max_order_units: int | None = None,
) -> SimpleNamespace:
    kwargs = {"api_type": api_type, "is_active": is_active}
    if live_max_order_guard_enabled is not None:
        kwargs["live_max_order_guard_enabled"] = live_max_order_guard_enabled
    if live_max_order_units is not None:
        kwargs["live_max_order_units"] = live_max_order_units
    return SimpleNamespace(**kwargs)


def test_dry_run_bypasses_broker_order_guard(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False

    BrokerOrderGuard().validate_order(
        account=None,
        dry_run=True,
        instrument="XAU_USD",
        units=Decimal("999999"),
    )


def test_rejects_live_account_without_global_enable(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False

    with pytest.raises(BrokerOrderGuardError, match="Live OANDA accounts are disabled"):
        BrokerOrderGuard().validate_order(
            account=_account(api_type="live"),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("1000"),
        )


def test_rejects_inactive_account():
    with pytest.raises(BrokerOrderGuardError, match="inactive account"):
        BrokerOrderGuard().validate_order(
            account=_account(is_active=False),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("1000"),
        )


def test_rejects_disallowed_instrument(settings):
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = ["EUR_USD"]

    with pytest.raises(BrokerOrderGuardError, match="Instrument USD_JPY"):
        BrokerOrderGuard().validate_order(
            account=_account(),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("1000"),
        )


def test_rejects_oversized_order(settings):
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    with pytest.raises(BrokerOrderGuardError, match="Order size exceeds"):
        BrokerOrderGuard().validate_order(
            account=_account(live_max_order_guard_enabled=True),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("-1001"),
        )


def test_order_limit_defaults_to_disabled(settings):
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    BrokerOrderGuard().validate_order(
        account=_account(),
        dry_run=False,
        instrument="USD_JPY",
        units=Decimal("100000"),
    )


def test_allows_configured_order(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = True
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = ["USD_JPY"]
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    BrokerOrderGuard().validate_order(
        account=_account(api_type="live", live_max_order_guard_enabled=True),
        dry_run=False,
        instrument="USD_JPY",
        units=Decimal("1000"),
    )


def test_account_order_limit_overrides_global_setting(settings):
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    BrokerOrderGuard().validate_order(
        account=_account(live_max_order_guard_enabled=True, live_max_order_units=1200),
        dry_run=False,
        instrument="USD_JPY",
        units=Decimal("1200"),
    )

    with pytest.raises(BrokerOrderGuardError, match="Order size exceeds"):
        BrokerOrderGuard().validate_order(
            account=_account(live_max_order_guard_enabled=True, live_max_order_units=1200),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("1201"),
        )


def test_account_order_limit_can_be_disabled(settings):
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    BrokerOrderGuard().validate_order(
        account=_account(live_max_order_guard_enabled=False, live_max_order_units=1000),
        dry_run=False,
        instrument="USD_JPY",
        units=Decimal("100000"),
    )
