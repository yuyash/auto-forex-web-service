"""FX conversion helpers for account and display currency values."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, Protocol

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
    path: tuple[str, ...] = ()


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
            return FxRate(
                source.code,
                target.code,
                Decimal("1"),
                as_of=as_of,
                path=(source.code, target.code),
            )
        if not instrument or mid_price is None or mid_price <= 0:
            return None

        parsed = Instrument(instrument)
        base = AccountCurrency(parsed.base_currency)
        quote = AccountCurrency(parsed.quote_currency)
        if not base.is_known or not quote.is_known:
            return None
        if source.matches(quote) and target.matches(base):
            return FxRate(
                source.code,
                target.code,
                Decimal("1") / mid_price,
                as_of=as_of,
                path=(f"{base.code}/{quote.code}", "inverse"),
            )
        if source.matches(base) and target.matches(quote):
            return FxRate(
                source.code,
                target.code,
                mid_price,
                as_of=as_of,
                path=(f"{base.code}/{quote.code}", "direct"),
            )
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
                source.code,
                target.code,
                Decimal("1"),
                as_of=as_of,
                source=self.source_name,
                path=(source.code, target.code),
            )

        return self.rates([(source.code, target.code)], as_of=as_of).get((source.code, target.code))

    def rates(
        self,
        pairs: Iterable[tuple[str, str]],
        *,
        as_of: datetime | None = None,
    ) -> dict[tuple[str, str], FxRate]:
        """Return latest direct/inverse rates for many currency pairs in one query."""
        normalized_pairs: list[tuple[str, str]] = []
        for source, target in pairs:
            source_currency = AccountCurrency(source)
            target_currency = AccountCurrency(target)
            if source_currency.is_known and target_currency.is_known:
                normalized_pairs.append((source_currency.code, target_currency.code))
        if not normalized_pairs:
            return {}

        results: dict[tuple[str, str], FxRate] = {}
        missing_pairs: list[tuple[str, str]] = []
        for source, target in normalized_pairs:
            key = (source, target)
            if source == target:
                results[key] = FxRate(
                    source,
                    target,
                    Decimal("1"),
                    as_of=as_of,
                    source=self.source_name,
                    path=(source, target),
                )
            else:
                missing_pairs.append(key)
        if not missing_pairs:
            return results

        latest_rows = self._latest_ticks(missing_pairs, as_of=as_of)
        for source, target in missing_pairs:
            for candidate in self._instrument_candidates(source, target):
                row = latest_rows.get(candidate)
                if row is None:
                    continue
                rate = self._rate_from_row(source, target, row)
                if rate is not None:
                    results[(source, target)] = rate
                    break
        return results

    def _rate_from_row(
        self,
        source_currency: str,
        target_currency: str,
        row: dict[str, Any],
    ) -> FxRate | None:
        parsed = Instrument(str(row["instrument"]))
        base = AccountCurrency(parsed.base_currency)
        quote = AccountCurrency(parsed.quote_currency)
        source = AccountCurrency(source_currency)
        target = AccountCurrency(target_currency)
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
                path=(f"{base.code}/{quote.code}", "direct"),
            )
        if source.matches(quote) and target.matches(base):
            return FxRate(
                source.code,
                target.code,
                Decimal("1") / mid,
                as_of=row.get("timestamp"),
                source=self.source_name,
                path=(f"{base.code}/{quote.code}", "inverse"),
            )
        return None

    def _latest_ticks(
        self,
        pairs: Iterable[tuple[str, str]],
        *,
        as_of: datetime | None,
    ) -> dict[str, dict[str, Any]]:
        from apps.market.models import TickData

        candidates = tuple(
            dict.fromkeys(
                candidate
                for source_currency, target_currency in pairs
                for candidate in self._instrument_candidates(
                    source_currency,
                    target_currency,
                )
            )
        )
        if not candidates:
            return {}
        qs = TickData.objects.filter(instrument__in=candidates)
        if as_of is not None:
            qs = qs.filter(timestamp__lte=as_of)
        latest: dict[str, dict[str, Any]] = {}
        for row in qs.order_by("instrument", "-timestamp").values(
            "instrument",
            "timestamp",
            "mid",
        ):
            instrument = str(row["instrument"])
            if instrument not in latest:
                latest[instrument] = row
            if len(latest) == len(candidates):
                break
        return latest

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
                path=(source.code, target.code),
            )

        rates = self._rates_by_pivot(source, target, as_of=as_of)
        for pivot in self.pivot_currencies:
            if source.matches(pivot) or target.matches(pivot):
                continue
            first = rates.get((source.code, pivot))
            if first is None:
                continue
            second = rates.get((pivot, target.code))
            if second is None:
                continue
            return FxRate(
                source.code,
                target.code,
                first.rate * second.rate,
                as_of=_older_timestamp(first.as_of, second.as_of),
                source="tick_data_triangulated",
                path=(source.code, pivot, target.code),
            )
        return None

    def _rates_by_pivot(
        self,
        source: AccountCurrency,
        target: AccountCurrency,
        *,
        as_of: datetime | None,
    ) -> dict[tuple[str, str], FxRate]:
        pairs: list[tuple[str, str]] = []
        for pivot in self.pivot_currencies:
            if source.matches(pivot) or target.matches(pivot):
                continue
            pairs.append((source.code, pivot))
            pairs.append((pivot, target.code))
        return self.direct_provider.rates(pairs, as_of=as_of)


@dataclass(frozen=True, slots=True)
class FxConversionService:
    """Convert money through an ordered list of rate providers."""

    providers: tuple[FxRateProvider, ...] = (
        InstrumentMidRateProvider(),
        TickDataFxRateProvider(),
        TriangulatedFxRateProvider(),
    )
    rate_cache: dict[tuple[str, str, str, str, str], FxRate | None] | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def with_cache(self) -> "FxConversionService":
        """Return a request-local copy that memoizes repeated rate lookups."""
        return FxConversionService(providers=self.providers, rate_cache={})

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
        cache_key = self._cache_key(
            source_currency=source_currency,
            target_currency=target_currency,
            instrument=instrument,
            mid_price=mid_price,
            as_of=as_of,
        )
        if self.rate_cache is not None and cache_key in self.rate_cache:
            return self.rate_cache[cache_key]

        for provider in self.providers:
            rate = provider.rate(
                source_currency=source_currency,
                target_currency=target_currency,
                instrument=instrument,
                mid_price=mid_price,
                as_of=as_of,
            )
            if rate is not None:
                if self.rate_cache is not None:
                    self.rate_cache[cache_key] = rate
                return rate
        if self.rate_cache is not None:
            self.rate_cache[cache_key] = None
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

    def _cache_key(
        self,
        *,
        source_currency: str,
        target_currency: str,
        instrument: str,
        mid_price: Decimal | None,
        as_of: datetime | None,
    ) -> tuple[str, str, str, str, str]:
        source = AccountCurrency(source_currency).code
        target = AccountCurrency(target_currency).code
        return (
            source,
            target,
            str(instrument or "").strip().upper(),
            str(mid_price) if mid_price is not None else "",
            as_of.isoformat() if as_of is not None else "",
        )


def _older_timestamp(first: datetime | None, second: datetime | None) -> datetime | None:
    if first is None:
        return second
    if second is None:
        return first
    return min(first, second)


FX_CONVERSION = FxConversionService()
