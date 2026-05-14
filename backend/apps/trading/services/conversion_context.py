"""Currency conversion metadata for display-money API payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from apps.trading.services.fx_rates import FxRate

ConversionPolicy = Literal["identity", "runtime_fx_rate", "unavailable"]


@dataclass(frozen=True, slots=True)
class CurrencyConversionContext:
    """Metadata describing how one currency was converted into another."""

    source_currency: str
    target_currency: str
    rate: Decimal | None
    rate_source: str
    rate_as_of: datetime | None
    rate_path: tuple[str, ...]
    conversion_available: bool
    conversion_policy: ConversionPolicy

    @classmethod
    def from_rate(cls, rate: FxRate) -> "CurrencyConversionContext":
        """Build context from a resolved FX rate."""
        source = _currency(rate.source_currency)
        target = _currency(rate.target_currency)
        return cls(
            source_currency=source,
            target_currency=target,
            rate=rate.rate,
            rate_source=rate.source,
            rate_as_of=rate.as_of,
            rate_path=rate.path,
            conversion_available=True,
            conversion_policy="identity" if source == target else "runtime_fx_rate",
        )

    @classmethod
    def unavailable(
        cls,
        *,
        source_currency: str | None,
        target_currency: str | None,
    ) -> "CurrencyConversionContext":
        """Build context for an unresolved conversion."""
        return cls(
            source_currency=_currency(source_currency),
            target_currency=_currency(target_currency),
            rate=None,
            rate_source="unavailable",
            rate_as_of=None,
            rate_path=(),
            conversion_available=False,
            conversion_policy="unavailable",
        )

    def as_dict(self) -> dict[str, Any]:
        """Serialize context as JSON-friendly primitives."""
        return {
            "source_currency": self.source_currency,
            "target_currency": self.target_currency,
            "rate": self.rate,
            "rate_source": self.rate_source,
            "rate_as_of": self.rate_as_of,
            "rate_path": list(self.rate_path),
            "conversion_available": self.conversion_available,
            "conversion_policy": self.conversion_policy,
        }


def _currency(value: str | None) -> str:
    code = str(value or "").strip().upper()
    return code if len(code) == 3 and code.isalpha() else ""
