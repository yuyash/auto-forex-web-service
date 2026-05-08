"""Shared utilities for the trading app."""

from dataclasses import dataclass
from decimal import Decimal

# JPY-quoted pairs use pip_size 0.01; all others use 0.0001
_JPY_QUOTE_CURRENCIES = {"JPY", "HUF"}


@dataclass(frozen=True, slots=True)
class Instrument:
    """Forex instrument value object with pip and currency helpers."""

    name: str

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
        if self.is_high_value_quote:
            return Decimal("0.01")
        return Decimal("0.0001")

    def quote_to_account_rate(
        self,
        mid_price: Decimal,
        account_currency: str = "",
    ) -> Decimal:
        """Return the multiplier to convert quote-currency PnL to account currency."""
        quote = self.quote_currency

        # If the account currency is the same as the quote currency, no conversion.
        if account_currency and quote and account_currency.upper() == quote:
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
