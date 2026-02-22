"""Shared utilities for the trading app."""

from decimal import Decimal

# JPY-quoted pairs use pip_size 0.01; all others use 0.0001
_JPY_QUOTE_CURRENCIES = {"JPY", "HUF"}


def pip_size_for_instrument(instrument: str) -> Decimal:
    """Derive pip size from instrument name.

    Standard forex convention:
    - JPY (and HUF) quoted pairs: 0.01
    - All other pairs: 0.0001
    """
    quote = instrument.split("_")[-1].upper() if "_" in instrument else ""
    if quote in _JPY_QUOTE_CURRENCIES:
        return Decimal("0.01")
    return Decimal("0.0001")


def is_quote_jpy(instrument: str) -> bool:
    """Return True when the quote currency is JPY (or similar high-value currencies).

    For instruments like USD_JPY, EUR_JPY the quote currency is JPY and
    price values (and therefore PnL / margin) are denominated in JPY.
    When the account is denominated in the *base* currency (e.g. USD for
    USD_JPY) we need to divide by the current mid price to convert back
    to account currency.
    """
    quote = instrument.split("_")[-1].upper() if "_" in instrument else ""
    return quote in _JPY_QUOTE_CURRENCIES


def quote_currency(instrument: str) -> str:
    """Extract the quote currency from an instrument name.

    Example: ``"USD_JPY"`` → ``"JPY"``, ``"EUR_USD"`` → ``"USD"``
    """
    return instrument.split("_")[-1].upper() if "_" in instrument else ""


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
    quote = instrument.split("_")[-1].upper() if "_" in instrument else ""

    # If the account currency is the same as the quote currency, no conversion.
    if account_currency and quote and account_currency.upper() == quote:
        return Decimal("1")

    # If the account currency is the same as the base currency, convert from
    # quote to base.
    if is_quote_jpy(instrument):
        if mid_price <= 0:
            return Decimal("1")
        return Decimal("1") / mid_price
    return Decimal("1")
