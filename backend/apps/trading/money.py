"""Currency-aware money value objects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class AccountCurrency:
    """ISO currency code value object for account-denominated values."""

    code: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "code", str(self.code or "").strip().upper())

    def __str__(self) -> str:
        """Return the normalized currency code."""
        return self.code

    @property
    def is_known(self) -> bool:
        """Return whether a non-empty currency code is available."""
        return bool(self.code)

    def matches(self, other: "AccountCurrency | str") -> bool:
        """Return whether another currency represents the same code."""
        other_code = other.code if isinstance(other, AccountCurrency) else str(other or "")
        return self.code == other_code.strip().upper()

    def require_known(self, *, field_name: str = "currency") -> "AccountCurrency":
        """Return self, raising when the code is empty."""
        if not self.is_known:
            raise ValueError(f"{field_name} must include a currency code")
        return self


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
        quant = Decimal(1).scaleb(-self.places)
        try:
            return str(value.quantize(quant))
        except Exception:  # pragma: no cover - defensive fallback
            return str(value)


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

    @property
    def currency_code(self) -> str:
        """Return the normalized currency code."""
        return self.currency.code

    def require_currency(self, *, field_name: str = "money") -> "Money":
        """Return self, raising when the money has no currency code."""
        self.currency.require_known(field_name=f"{field_name}.currency")
        return self

    def as_dict(self) -> dict[str, str]:
        """Serialize as an amount/currency pair for JSON-friendly payloads."""
        return {"amount": str(self.amount), "currency": self.currency_code}

    def add(self, other: "Money") -> "Money":
        """Add another money value with the same currency."""
        self._require_same_currency(other)
        return Money(amount=self.amount + other.amount, currency=self.currency)

    def subtract(self, other: "Money") -> "Money":
        """Subtract another money value with the same currency."""
        self._require_same_currency(other)
        return Money(amount=self.amount - other.amount, currency=self.currency)

    def convert(self, *, rate: Decimal | float | int | str, target_currency: str) -> "Money":
        """Convert money using an explicit multiplier."""
        return Money.coerce(self.amount * Decimal(str(rate)), target_currency)

    def format(self, *, places: int = 2) -> str:
        """Format the amount for human-readable logs."""
        return MoneyFormatter(places=places).format(self.amount)

    def _require_same_currency(self, other: "Money") -> None:
        if not self.currency.matches(other.currency):
            raise ValueError(
                "Money arithmetic requires matching currencies: "
                f"{self.currency_code or '<unknown>'} != {other.currency_code or '<unknown>'}"
            )


@dataclass(frozen=True, slots=True)
class CurrencyConversion:
    """Explicit conversion rate between two currency-denominated amounts."""

    source_currency: AccountCurrency
    target_currency: AccountCurrency
    rate: Decimal

    @classmethod
    def coerce(
        cls,
        *,
        source_currency: AccountCurrency | str,
        target_currency: AccountCurrency | str,
        rate: Decimal | float | int | str,
    ) -> "CurrencyConversion":
        """Build a conversion from primitive values."""
        source = (
            source_currency
            if isinstance(source_currency, AccountCurrency)
            else AccountCurrency(source_currency)
        )
        target = (
            target_currency
            if isinstance(target_currency, AccountCurrency)
            else AccountCurrency(target_currency)
        )
        return cls(source_currency=source, target_currency=target, rate=Decimal(str(rate)))

    def convert(self, money: Money) -> Money:
        """Convert a money value, validating the source currency when available."""
        if money.currency.is_known and self.source_currency.is_known:
            if not money.currency.matches(self.source_currency):
                raise ValueError(
                    "Conversion source currency does not match money currency: "
                    f"{self.source_currency.code} != {money.currency_code}"
                )
        return money.convert(rate=self.rate, target_currency=self.target_currency.code)
