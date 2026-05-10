"""FX conversion helpers for account and display currency values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from apps.trading.money import AccountCurrency, Money
from apps.trading.utils import Instrument


@dataclass(frozen=True, slots=True)
class FxRate:
    """A conversion multiplier from one currency into another."""

    source_currency: str
    target_currency: str
    rate: Decimal
    as_of: datetime | None = None
    source: str = "instrument_mid"


class FxRateProvider(Protocol):
    """Protocol for services that can return FX conversion rates."""

    def rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> FxRate | None: ...


class InstrumentMidRateProvider:
    """Resolve direct/base-quote rates from the traded instrument mid price."""

    def rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> FxRate | None:
        """Return a direct conversion rate when the instrument pair is sufficient."""
        source = AccountCurrency(source_currency)
        target = AccountCurrency(target_currency)
        if not source.is_known or not target.is_known:
            return None
        if source.matches(target):
            return FxRate(source.code, target.code, Decimal("1"), as_of=as_of)
        if not instrument or mid_price is None or mid_price <= 0:
            return None

        parsed = Instrument(instrument)
        base = AccountCurrency(parsed.base_currency)
        quote = AccountCurrency(parsed.quote_currency)
        if not base.is_known or not quote.is_known:
            return None
        if source.matches(quote) and target.matches(base):
            return FxRate(source.code, target.code, Decimal("1") / mid_price, as_of=as_of)
        if source.matches(base) and target.matches(quote):
            return FxRate(source.code, target.code, mid_price, as_of=as_of)
        return None


@dataclass(frozen=True, slots=True)
class FxConversionService:
    """Convert money through an ordered list of rate providers."""

    providers: tuple[FxRateProvider, ...] = (InstrumentMidRateProvider(),)

    def rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> FxRate | None:
        """Return the first available conversion rate."""
        for provider in self.providers:
            rate = provider.rate(
                source_currency=source_currency,
                target_currency=target_currency,
                instrument=instrument,
                mid_price=mid_price,
                as_of=as_of,
            )
            if rate is not None:
                return rate
        return None

    def convert(
        self,
        money: Money,
        *,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> Money | None:
        """Convert a money value when a rate is available."""
        fx_rate = self.rate(
            source_currency=money.currency_code,
            target_currency=target_currency,
            instrument=instrument,
            mid_price=mid_price,
            as_of=as_of,
        )
        if fx_rate is None:
            return None
        return money.convert(rate=fx_rate.rate, target_currency=fx_rate.target_currency)


FX_CONVERSION = FxConversionService()
