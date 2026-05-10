"""FX conversion helpers for account and display currency values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol

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


class TickDataFxRateProvider:
    """Resolve direct/base-quote rates from stored market ticks."""

    source_name = "tick_data"

    def rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> FxRate | None:
        """Return the latest stored direct or inverse market rate."""
        del instrument, mid_price
        source = AccountCurrency(source_currency)
        target = AccountCurrency(target_currency)
        if not source.is_known or not target.is_known:
            return None
        if source.matches(target):
            return FxRate(
                source.code, target.code, Decimal("1"), as_of=as_of, source=self.source_name
            )

        row = self._latest_tick(source.code, target.code, as_of=as_of)
        if row is None:
            return None
        parsed = Instrument(str(row["instrument"]))
        base = AccountCurrency(parsed.base_currency)
        quote = AccountCurrency(parsed.quote_currency)
        mid = Decimal(str(row["mid"]))
        if mid <= 0:
            return None
        if source.matches(base) and target.matches(quote):
            return FxRate(
                source.code,
                target.code,
                mid,
                as_of=row.get("timestamp"),
                source=self.source_name,
            )
        if source.matches(quote) and target.matches(base):
            return FxRate(
                source.code,
                target.code,
                Decimal("1") / mid,
                as_of=row.get("timestamp"),
                source=self.source_name,
            )
        return None

    def _latest_tick(
        self,
        source_currency: str,
        target_currency: str,
        *,
        as_of: datetime | None,
    ) -> dict[str, Any] | None:
        from apps.market.models import TickData

        candidates = self._instrument_candidates(source_currency, target_currency)
        qs = TickData.objects.filter(instrument__in=candidates)
        if as_of is not None:
            qs = qs.filter(timestamp__lte=as_of)
        return qs.order_by("-timestamp").values("instrument", "timestamp", "mid").first()

    def _instrument_candidates(self, source_currency: str, target_currency: str) -> tuple[str, ...]:
        source = source_currency.strip().upper()
        target = target_currency.strip().upper()
        direct = f"{source}_{target}"
        inverse = f"{target}_{source}"
        return (direct, inverse, f"{source}{target}", f"{target}{source}")


@dataclass(frozen=True, slots=True)
class TriangulatedFxRateProvider:
    """Resolve rates through a small set of common liquidity currencies."""

    direct_provider: TickDataFxRateProvider = field(default_factory=TickDataFxRateProvider)
    pivot_currencies: tuple[str, ...] = ("USD", "EUR", "JPY", "GBP", "AUD", "CAD", "CHF", "NZD")

    def rate(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str = "",
        mid_price: Decimal | None = None,
        as_of: datetime | None = None,
    ) -> FxRate | None:
        """Return a two-leg conversion rate when both legs are in stored ticks."""
        del instrument, mid_price
        source = AccountCurrency(source_currency)
        target = AccountCurrency(target_currency)
        if not source.is_known or not target.is_known:
            return None
        if source.matches(target):
            return FxRate(
                source.code,
                target.code,
                Decimal("1"),
                as_of=as_of,
                source="tick_data_triangulated",
            )

        for pivot in self.pivot_currencies:
            if source.matches(pivot) or target.matches(pivot):
                continue
            first = self.direct_provider.rate(
                source_currency=source.code,
                target_currency=pivot,
                as_of=as_of,
            )
            if first is None:
                continue
            second = self.direct_provider.rate(
                source_currency=pivot,
                target_currency=target.code,
                as_of=as_of,
            )
            if second is None:
                continue
            return FxRate(
                source.code,
                target.code,
                first.rate * second.rate,
                as_of=_older_timestamp(first.as_of, second.as_of),
                source="tick_data_triangulated",
            )
        return None


@dataclass(frozen=True, slots=True)
class FxConversionService:
    """Convert money through an ordered list of rate providers."""

    providers: tuple[FxRateProvider, ...] = (
        InstrumentMidRateProvider(),
        TickDataFxRateProvider(),
        TriangulatedFxRateProvider(),
    )

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


def _older_timestamp(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


FX_CONVERSION = FxConversionService()
