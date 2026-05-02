"""Tests for broker-bound order safety guardrails."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.market.services.broker_order_guard import BrokerOrderGuard, BrokerOrderGuardError


def _account(*, api_type: str = "practice", is_active: bool = True) -> SimpleNamespace:
    return SimpleNamespace(api_type=api_type, is_active=is_active)


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
            account=_account(),
            dry_run=False,
            instrument="USD_JPY",
            units=Decimal("-1001"),
        )


def test_allows_configured_order(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = True
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = ["USD_JPY"]
    settings.TRADING_LIVE_MAX_ORDER_UNITS = 1000

    BrokerOrderGuard().validate_order(
        account=_account(api_type="live"),
        dry_run=False,
        instrument="USD_JPY",
        units=Decimal("1000"),
    )
