"""Shared utilities for the trading app."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

# JPY-quoted pairs use pip_size 0.01; all others use 0.0001
_JPY_QUOTE_CURRENCIES = {"JPY", "HUF"}


@dataclass(frozen=True, slots=True)
class AccountCurrency:
    """ISO currency code value object for account-denominated values."""

    code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip().upper())

    @property
    def is_known(self) -> bool:
        """Return whether a non-empty currency code is available."""
        return bool(self.code)

    def matches(self, other: "AccountCurrency | str") -> bool:
        """Return whether another currency represents the same code."""
        other_code = other.code if isinstance(other, AccountCurrency) else str(other or "")
        return self.code == other_code.strip().upper()


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
class Money:
    """Money value object with amount and account currency."""

    amount: Decimal
    currency: AccountCurrency = AccountCurrency()

    @classmethod
    def coerce(
        cls,
        amount: Decimal | float | int | str,
        currency: AccountCurrency | str = "",
    ) -> "Money":
        """Build a money object from primitive amount/currency values."""
        currency_obj = (
            currency if isinstance(currency, AccountCurrency) else AccountCurrency(currency)
        )
        return cls(amount=Decimal(str(amount)), currency=currency_obj)

    def format(self, *, places: int = 2) -> str:
        """Format the amount for human-readable logs."""
        return MoneyFormatter(places=places).format(self.amount)


@dataclass(frozen=True, slots=True)
class Instrument:
    """Forex instrument value object with pip and currency helpers."""

    name: str

    @property
    def pip(self) -> PipSize:
        """Return the pip-size value object for this instrument."""
        return PipSize.for_instrument(self)

    @property
    def quote_currency(self) -> str:
        """Extract the quote currency from an OANDA instrument name."""
        return self.name.split("_")[-1].upper() if "_" in self.name else ""

    @property
    def is_high_value_quote(self) -> bool:
        """Return whether this quote currency uses the wider pip convention."""
        return self.quote_currency in _JPY_QUOTE_CURRENCIES

    @property
    def pip_size(self) -> Decimal:
        """Return the pip size for this instrument."""
        return self.pip.value

    def quote_to_account_rate(
        self,
        mid_price: Decimal,
        account_currency: AccountCurrency | str = "",
    ) -> Decimal:
        """Return the multiplier to convert quote-currency PnL to account currency."""
        quote = self.quote_currency
        account = (
            account_currency
            if isinstance(account_currency, AccountCurrency)
            else AccountCurrency(account_currency)
        )

        # If the account currency is the same as the quote currency, no conversion.
        if account.is_known and quote and account.matches(quote):
            return Decimal("1")

        # If the account currency is the same as the base currency, convert from
        # quote to base.
        if self.is_high_value_quote:
            if mid_price <= 0:
                return Decimal("1")
            return Decimal("1") / mid_price
        return Decimal("1")


@dataclass(frozen=True, slots=True)
class MoneyFormatter:
    """Format Decimal-compatible money values for stable logs."""

    places: int = 2

    def format(self, value: Decimal | float | int | None) -> str:
        """Format a monetary amount for human-readable logging."""
        if value is None:
            return "None"
        if not isinstance(value, Decimal):
            value = Decimal(str(value))
        quant = Decimal(1).scaleb(-self.places)  # e.g. Decimal("0.01") when places=2
        try:
            return str(value.quantize(quant))
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)


def pip_size_for_instrument(instrument: str) -> Decimal:
    """Derive pip size from instrument name.

    Standard forex convention:
    - JPY (and HUF) quoted pairs: 0.01
    - All other pairs: 0.0001
    """
    return Instrument(instrument).pip_size


def is_quote_jpy(instrument: str) -> bool:
    """Return True when the quote currency is JPY (or similar high-value currencies).

    For instruments like USD_JPY, EUR_JPY the quote currency is JPY and
    price values (and therefore PnL / margin) are denominated in JPY.
    When the account is denominated in the *base* currency (e.g. USD for
    USD_JPY) we need to divide by the current mid price to convert back
    to account currency.
    """
    return Instrument(instrument).is_high_value_quote


def quote_currency(instrument: str) -> str:
    """Extract the quote currency from an instrument name.

    Example: ``"USD_JPY"`` → ``"JPY"``, ``"EUR_USD"`` → ``"USD"``
    """
    return Instrument(instrument).quote_currency


def quote_to_account_rate(
    instrument: str, mid_price: Decimal, account_currency: str = ""
) -> Decimal:
    """Return the multiplier to convert a quote-currency amount to account currency.

    When *account_currency* matches the quote currency of the instrument the
    PnL is already denominated in the account currency and no conversion is
    needed (returns ``1``).

    Otherwise we fall back to the original heuristic:
    * For JPY-quoted pairs (e.g. USD_JPY on a USD account): divide by mid → 1 / mid
    * For USD-quoted pairs (e.g. EUR_USD on a USD account): already in quote=USD → 1

    Cross-currency pairs (e.g. EUR_GBP on a USD account) would need an
    additional FX rate, but that is out of scope for now.
    """
    return Instrument(instrument).quote_to_account_rate(mid_price, account_currency)


def format_money(value: Decimal | float | int | None, *, places: int = 2) -> str:
    """Format a monetary amount for human-readable logging.

    Rounds ``value`` to ``places`` decimal places using ``Decimal.quantize``
    to avoid long fractional tails that result from internal Decimal
    arithmetic. ``None`` is rendered as the literal string ``"None"`` so
    log output remains stable for callers that pass optional balances.
    """
    return MoneyFormatter(places=places).format(value)
