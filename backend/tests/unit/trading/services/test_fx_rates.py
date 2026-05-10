"""Tests for FX conversion service helpers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from apps.market.models import TickData
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
    service = FxConversionService(providers=())

    converted = service.convert(
        Money.coerce("100", "EUR"),
        target_currency="JPY",
        instrument="USD_JPY",
        mid_price=Decimal("150"),
    )

    assert converted is None


@pytest.mark.django_db
def test_tick_data_provider_uses_latest_direct_pair():
    base_time = datetime(2026, 1, 1, 12, tzinfo=UTC)
    TickData.objects.create(
        instrument="EUR_JPY",
        timestamp=base_time,
        bid=Decimal("160"),
        ask=Decimal("161"),
        mid=Decimal("160.5"),
    )
    TickData.objects.create(
        instrument="EUR_JPY",
        timestamp=base_time + timedelta(minutes=1),
        bid=Decimal("162"),
        ask=Decimal("163"),
        mid=Decimal("162.5"),
    )
    service = FxConversionService()

    converted = service.convert(Money.coerce("10", "EUR"), target_currency="JPY")

    assert converted is not None
    assert converted.amount == Decimal("1625.0")
    assert converted.currency_code == "JPY"


@pytest.mark.django_db
def test_tick_data_provider_respects_as_of_for_inverse_pair():
    base_time = datetime(2026, 1, 1, 12, tzinfo=UTC)
    TickData.objects.create(
        instrument="EUR_JPY",
        timestamp=base_time,
        bid=Decimal("160"),
        ask=Decimal("161"),
        mid=Decimal("160"),
    )
    TickData.objects.create(
        instrument="EUR_JPY",
        timestamp=base_time + timedelta(minutes=5),
        bid=Decimal("200"),
        ask=Decimal("201"),
        mid=Decimal("200"),
    )
    service = FxConversionService()

    converted = service.convert(
        Money.coerce("320", "JPY"),
        target_currency="EUR",
        as_of=base_time + timedelta(minutes=1),
    )

    assert converted is not None
    assert converted.amount == Decimal("2")
    assert converted.currency_code == "EUR"


@pytest.mark.django_db
def test_triangulated_tick_data_provider_uses_common_pivot_currency():
    timestamp = datetime(2026, 1, 1, 12, tzinfo=UTC)
    TickData.objects.create(
        instrument="EUR_USD",
        timestamp=timestamp,
        bid=Decimal("1.09"),
        ask=Decimal("1.11"),
        mid=Decimal("1.10"),
    )
    TickData.objects.create(
        instrument="USD_JPY",
        timestamp=timestamp,
        bid=Decimal("149.9"),
        ask=Decimal("150.1"),
        mid=Decimal("150"),
    )
    service = FxConversionService()

    converted = service.convert(Money.coerce("10", "EUR"), target_currency="JPY")

    assert converted is not None
    assert converted.amount == Decimal("1650.00")
    assert converted.currency_code == "JPY"
