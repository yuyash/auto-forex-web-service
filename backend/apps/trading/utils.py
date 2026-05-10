"""Shared utilities for the trading app."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from apps.trading.money import (
    AccountCurrency as _AccountCurrency,
    CurrencyConversion as _CurrencyConversion,
    Money as _Money,
    MoneyFormatter as _MoneyFormatter,
)

# JPY-quoted pairs use pip_size 0.01; all others use 0.0001
_JPY_QUOTE_CURRENCIES = {"JPY", "HUF"}


@dataclass(frozen=True, slots=True)
class PipSize:
    """Decimal pip-size value object."""

    value: Decimal

    @classmethod
    def for_instrument(cls, instrument: "Instrument | str") -> "PipSize":
        """Return the pip-size convention for an instrument."""
        instrument_obj = (
            instrument if isinstance(instrument, Instrument) else Instrument(instrument)
        )
        if instrument_obj.is_high_value_quote:
            return cls(Decimal("0.01"))
        return cls(Decimal("0.0001"))


@dataclass(frozen=True, slots=True)
class Price:
    """Decimal price value object with small arithmetic helpers."""

    value: Decimal

    @classmethod
    def coerce(cls, value: Decimal | float | int | str) -> "Price":
        """Build a price from any Decimal-compatible primitive."""
        return cls(Decimal(str(value)))

    def distance_to(self, other: "Price") -> Decimal:
        """Return signed price distance to another price."""
        return other.value - self.value


@dataclass(frozen=True, slots=True)
class Units:
    """Trade units value object."""

    value: int

    @classmethod
    def coerce(cls, value: Decimal | float | int | str) -> "Units":
        """Build integer units from a primitive value."""
        return cls(int(Decimal(str(value))))

    @property
    def absolute(self) -> int:
        """Return absolute unit size."""
        return abs(self.value)

    @property
    def side(self) -> "TradeSide":
        """Infer the trade side from the sign of units."""
        return TradeSide.LONG if self.value >= 0 else TradeSide.SHORT


class TradeSide(StrEnum):
    """Trading side value object compatible with existing string fields."""

    LONG = "long"
    SHORT = "short"

    @classmethod
    def from_units(cls, units: Units | Decimal | float | int | str) -> "TradeSide":
        """Infer trade side from signed units."""
        unit_value = units.value if isinstance(units, Units) else int(Decimal(str(units)))
        return cls.LONG if unit_value >= 0 else cls.SHORT

    @property
    def sign(self) -> int:
        """Return the unit sign for this side."""
        return 1 if self is TradeSide.LONG else -1


@dataclass(frozen=True, slots=True)
class Instrument:
    """Forex instrument value object with pip and currency helpers."""

    name: str

    @property
    def normalized_name(self) -> str:
        """Return a normalized instrument identifier for currency parsing."""
        raw = str(self.name or "").strip().upper()
        if ":" in raw:
            raw = raw.rsplit(":", 1)[-1]
        return raw.replace("/", "_").replace("-", "_")

    @property
    def pip(self) -> PipSize:
        """Return the pip-size value object for this instrument."""
        return PipSize.for_instrument(self)

    @property
    def base_currency(self) -> str:
        """Extract the base currency from common FX instrument notations."""
        base, _quote = self._currency_pair()
        return base

    @property
    def quote_currency(self) -> str:
        """Extract the quote currency from common FX instrument notations."""
        _base, quote = self._currency_pair()
        return quote

    @property
    def is_high_value_quote(self) -> bool:
        """Return whether this quote currency uses the wider pip convention."""
        return self.quote_currency in _JPY_QUOTE_CURRENCIES

    @property
    def pip_size(self) -> Decimal:
        """Return the pip size for this instrument."""
        return self.pip.value

    def _currency_pair(self) -> tuple[str, str]:
        normalised = self.normalized_name
        if "_" in normalised:
            parts = [part for part in normalised.split("_") if part]
            if len(parts) >= 2:
                return parts[0], parts[-1]
        compact = normalised.replace("_", "")
        if len(compact) == 6 and compact.isalpha():
            return compact[:3], compact[3:]
        return normalised, ""

    def quote_to_account_rate(
        self,
        mid_price: Decimal,
        account_currency: _AccountCurrency | str = "",
    ) -> Decimal:
        """Return the multiplier to convert quote-currency PnL to account currency."""
        quote = self.quote_currency
        account = (
            account_currency
            if isinstance(account_currency, _AccountCurrency)
            else _AccountCurrency(account_currency)
        )

        # Legacy strategy unit tests and dry-run paths can omit account currency.
        # Preserve the previous high-value quote fallback until every execution
        # path supplies an explicit account currency or cross-rate provider.
        if not account.is_known:
            if self.is_high_value_quote and mid_price > 0:
                return Decimal("1") / mid_price
            return Decimal("1")

        # If the account currency is the same as the quote currency, no conversion.
        if account.is_known and quote and account.matches(quote):
            return Decimal("1")

        # If the account currency is the same as the base currency, convert from
        # quote to base.
        if account.is_known and self.base_currency and account.matches(self.base_currency):
            if mid_price <= 0:
                return Decimal("1")
            return Decimal("1") / mid_price
        return Decimal("1")

    def quote_to_account_conversion(
        self,
        mid_price: Decimal,
        account_currency: _AccountCurrency | str = "",
    ) -> _CurrencyConversion:
        """Return a value object for quote-to-account money conversion."""
        account = (
            account_currency
            if isinstance(account_currency, _AccountCurrency)
            else _AccountCurrency(account_currency)
        )
        return _CurrencyConversion.coerce(
            source_currency=self.quote_currency,
            target_currency=account.code,
            rate=self.quote_to_account_rate(mid_price, account),
        )


@dataclass(frozen=True, slots=True)
class TradingValueFactory:
    """Factory for trading value objects and compatibility calculations."""

    def instrument(self, name: str) -> Instrument:
        """Build an instrument value object."""
        return Instrument(name)

    def pip_size_for_instrument(self, instrument: str) -> Decimal:
        """Derive pip size from an instrument name."""
        return self.instrument(instrument).pip_size

    def is_quote_jpy(self, instrument: str) -> bool:
        """Return whether an instrument uses a high-value quote convention."""
        return self.instrument(instrument).is_high_value_quote

    def quote_currency(self, instrument: str) -> str:
        """Extract the quote currency from an instrument name."""
        return self.instrument(instrument).quote_currency

    def quote_to_account_rate(
        self,
        instrument: str,
        mid_price: Decimal,
        account_currency: str = "",
    ) -> Decimal:
        """Return the multiplier to convert quote-currency PnL."""
        return self.instrument(instrument).quote_to_account_rate(mid_price, account_currency)

    def quote_to_account_money(
        self,
        *,
        instrument: str,
        quote_amount: Decimal | float | int | str,
        mid_price: Decimal,
        account_currency: str,
    ) -> _Money:
        """Convert a quote-currency amount into account-currency money."""
        instrument_obj = self.instrument(instrument)
        conversion = instrument_obj.quote_to_account_conversion(mid_price, account_currency)
        return conversion.convert(_Money.coerce(quote_amount, instrument_obj.quote_currency))

    def format_money(self, value: Decimal | float | int | None, *, places: int = 2) -> str:
        """Format a monetary amount for logs."""
        return _MoneyFormatter(places=places).format(value)


TRADING_VALUES = TradingValueFactory()


def pip_size_for_instrument(instrument: str) -> Decimal:
    """Derive pip size from instrument name.

    Standard forex convention:
    - JPY (and HUF) quoted pairs: 0.01
    - All other pairs: 0.0001
    """
    return TRADING_VALUES.pip_size_for_instrument(instrument)


def is_quote_jpy(instrument: str) -> bool:
    """Return True when the quote currency is JPY (or similar high-value currencies).

    For instruments like USD_JPY, EUR_JPY the quote currency is JPY and
    price values (and therefore PnL / margin) are denominated in JPY.
    When the account is denominated in the *base* currency (e.g. USD for
    USD_JPY) we need to divide by the current mid price to convert back
    to account currency.
    """
    return TRADING_VALUES.is_quote_jpy(instrument)


def quote_currency(instrument: str) -> str:
    """Extract the quote currency from an instrument name.

    Example: ``"USD_JPY"`` → ``"JPY"``, ``"EURUSD"`` → ``"USD"``
    """
    return TRADING_VALUES.quote_currency(instrument)


def quote_to_account_rate(
    instrument: str, mid_price: Decimal, account_currency: str = ""
) -> Decimal:
    """Return the multiplier to convert a quote-currency amount to account currency.

    When *account_currency* matches the quote currency of the instrument the
    PnL is already denominated in the account currency and no conversion is
    needed (returns ``1``).

    Otherwise:
    * If the account currency is the base currency, divide by mid → 1 / mid.
    * If neither side matches, return ``1`` until a cross-rate provider is supplied.
    * If account currency is missing, retain the legacy high-value quote fallback.

    Cross-currency pairs (e.g. EUR_GBP on a USD account) need an additional FX rate.
    """
    return TRADING_VALUES.quote_to_account_rate(instrument, mid_price, account_currency)


def format_money(value: Decimal | float | int | None, *, places: int = 2) -> str:
    """Format a monetary amount for human-readable logging.

    Rounds ``value`` to ``places`` decimal places using ``Decimal.quantize``
    to avoid long fractional tails that result from internal Decimal
    arithmetic. ``None`` is rendered as the literal string ``"None"`` so
    log output remains stable for callers that pass optional balances.
    """
    return TRADING_VALUES.format_money(value, places=places)
