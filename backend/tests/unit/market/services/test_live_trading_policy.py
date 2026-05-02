"""Tests for shared live-trading settings parsing."""

from __future__ import annotations

from apps.market.services.live_trading_policy import get_live_trading_policy


def test_parses_live_trading_policy_from_strings(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = "yes"
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = " usd_jpy, eur_usd "
    settings.TRADING_LIVE_MAX_INITIAL_UNITS = "123"
    settings.TRADING_LIVE_MAX_ORDER_UNITS = "456"
    settings.TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS = "789"

    policy = get_live_trading_policy()

    assert policy.allow_live_oanda is True
    assert policy.allowed_instruments == frozenset({"USD_JPY", "EUR_USD"})
    assert policy.max_initial_units == 123
    assert policy.max_order_units == 456
    assert policy.max_estimated_exposure_units == 789
    assert policy.allows_instrument("usd_jpy") is True


def test_parses_live_trading_policy_from_lists(settings):
    settings.TRADING_ALLOW_LIVE_OANDA = False
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = ["USD_JPY", "gbp_usd"]

    policy = get_live_trading_policy()

    assert policy.allow_live_oanda is False
    assert policy.allowed_instruments == frozenset({"USD_JPY", "GBP_USD"})
    assert policy.allows_instrument("GBP_USD") is True
    assert policy.allows_instrument("AUD_USD") is False


def test_policy_wildcard_allows_any_non_empty_instrument(settings):
    settings.TRADING_LIVE_ALLOWED_INSTRUMENTS = "*"

    policy = get_live_trading_policy()

    assert policy.allows_instrument("XAU_USD") is True
    assert policy.allows_instrument("") is False


def test_invalid_or_negative_limits_normalize_to_safe_values(settings):
    settings.TRADING_LIVE_MAX_INITIAL_UNITS = "bad"
    settings.TRADING_LIVE_MAX_ORDER_UNITS = -10
    settings.TRADING_LIVE_MAX_ESTIMATED_EXPOSURE_UNITS = None

    policy = get_live_trading_policy()

    assert policy.max_initial_units == 10_000
    assert policy.max_order_units == 0
    assert policy.max_estimated_exposure_units == 200_000
