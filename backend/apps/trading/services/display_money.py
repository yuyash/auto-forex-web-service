"""Display-currency money conversion service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Mapping

from apps.trading.money import AccountCurrency, Money
from apps.trading.services.conversion_context import CurrencyConversionContext
from apps.trading.services.fx_rates import FX_CONVERSION, FxConversionService


@dataclass(frozen=True, slots=True)
class DisplayMoneySet:
    """Converted display-money values with shared conversion metadata."""

    values: dict[str, dict[str, str] | None]
    conversion_context: dict[str, object] | None


class DisplayMoneyConverter:
    """Convert same-currency money values to a display currency in one rate lookup."""

    def __init__(self, *, fx_conversion: FxConversionService = FX_CONVERSION) -> None:
        """Initialize the converter with an injectable FX conversion service."""
        self.fx_conversion = fx_conversion

    def convert_many(
        self,
        values: Mapping[str, Money],
        *,
        target_currency: str | None,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
        fx_conversion: FxConversionService | None = None,
    ) -> DisplayMoneySet:
        """Return display-currency values using one shared FX rate lookup."""
        source_currency = self._source_currency(values)
        target = AccountCurrency(target_currency or "")
        empty = {key: None for key in values}
        if not source_currency or not target.is_known:
            return DisplayMoneySet(
                values=empty,
                conversion_context=CurrencyConversionContext.unavailable(
                    source_currency=source_currency,
                    target_currency=target.code,
                ).as_dict(),
            )

        rate = (fx_conversion or self.fx_conversion).rate(
            source_currency=source_currency,
            target_currency=target.code,
            instrument=instrument,
            mid_price=mid_price,
            as_of=as_of,
        )
        if rate is None:
            return DisplayMoneySet(
                values=empty,
                conversion_context=CurrencyConversionContext.unavailable(
                    source_currency=source_currency,
                    target_currency=target.code,
                ).as_dict(),
            )

        return DisplayMoneySet(
            values={
                key: money.convert(
                    rate=rate.rate,
                    target_currency=rate.target_currency,
                ).as_dict()
                for key, money in values.items()
            },
            conversion_context=CurrencyConversionContext.from_rate(rate).as_dict(),
        )

    def _source_currency(self, values: Mapping[str, Money]) -> str:
        source: str | None = None
        for money in values.values():
            currency = AccountCurrency(money.currency_code)
            if not currency.is_known:
                return ""
            if source is None:
                source = currency.code
                continue
            if source != currency.code:
                raise ValueError(
                    "Display money conversion requires a single source currency: "
                    f"{source} != {currency.code}"
                )
        return source or ""


DISPLAY_MONEY = DisplayMoneyConverter()
