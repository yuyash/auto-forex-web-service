"""Tests for FX conversion service helpers."""

from decimal import Decimal

from apps.trading.money import Money
from apps.trading.services.fx_rates import FxConversionService


def test_same_currency_conversion_does_not_require_market_price():
    service = FxConversionService()

    converted = service.convert(Money.coerce("100", "USD"), target_currency="USD")

    assert converted is not None
    assert converted.amount == Decimal("100")
    assert converted.currency_code == "USD"


def test_quote_to_base_uses_inverse_mid_price():
    service = FxConversionService()

    converted = service.convert(
        Money.coerce("15000", "JPY"),
        target_currency="USD",
        instrument="USD_JPY",
        mid_price=Decimal("150"),
    )

    assert converted is not None
    assert converted.amount == Decimal("100")
    assert converted.currency_code == "USD"


def test_cross_currency_without_provider_returns_none():
    service = FxConversionService()

    converted = service.convert(
        Money.coerce("100", "EUR"),
        target_currency="JPY",
        instrument="USD_JPY",
        mid_price=Decimal("150"),
    )

    assert converted is None
