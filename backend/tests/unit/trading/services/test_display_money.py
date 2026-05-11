"""Tests for display-currency money conversion service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from apps.trading.money import Money
from apps.trading.services.display_money import DisplayMoneyConverter
from apps.trading.services.fx_rates import FxRate


class StaticFxConversion:
    """Small test double that records rate calls."""

    def __init__(self) -> None:
        self.calls = 0

    def rate(self, **kwargs) -> FxRate:
        self.calls += 1
        return FxRate(
            kwargs["source_currency"],
            kwargs["target_currency"],
            Decimal("150"),
            as_of=kwargs["as_of"],
            source="test",
            path=("USD", "JPY"),
        )


def test_display_money_converter_converts_many_values_with_one_rate_lookup():
    fx_conversion = StaticFxConversion()
    as_of = datetime(2026, 1, 1, tzinfo=UTC)

    result = DisplayMoneyConverter(fx_conversion=fx_conversion).convert_many(
        {
            "current": Money.coerce("100", "USD"),
            "adjustment": Money.coerce("5", "USD"),
        },
        target_currency="JPY",
        instrument="USD_JPY",
        as_of=as_of,
    )

    assert fx_conversion.calls == 1
    assert result.values == {
        "current": {"amount": "15000", "currency": "JPY"},
        "adjustment": {"amount": "750", "currency": "JPY"},
    }
    assert result.conversion_context == {
        "source_currency": "USD",
        "target_currency": "JPY",
        "rate": Decimal("150"),
        "rate_source": "test",
        "rate_as_of": as_of,
        "rate_path": ["USD", "JPY"],
        "conversion_available": True,
        "conversion_policy": "runtime_fx_rate",
    }
