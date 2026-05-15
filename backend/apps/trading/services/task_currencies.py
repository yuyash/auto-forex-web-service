"""Currency options and defaults for task configuration."""

from __future__ import annotations

from typing import Any

from apps.trading.utils import Instrument


def instrument_currency_options(instrument: Any) -> tuple[str, ...]:
    """Return the selectable currencies for a forex instrument."""
    parsed = Instrument(str(instrument or ""))
    options: list[str] = []
    for currency in (parsed.base_currency, parsed.quote_currency):
        code = normalize_currency(currency)
        if code and code not in options:
            options.append(code)
    return tuple(options)


def default_currency_for_language(instrument: Any, language: Any) -> str:
    """Return the language-preferred currency when it is part of the pair."""
    return default_currency_from_options(
        instrument_currency_options(instrument),
        language,
    )


def default_currency_from_options(options: tuple[str, ...] | list[str], language: Any) -> str:
    """Return JPY for Japanese, USD otherwise, falling back to the quote currency."""
    normalized = tuple(code for code in (normalize_currency(item) for item in options) if code)
    if not normalized:
        return ""
    preferred = "JPY" if str(language or "").lower().startswith("ja") else "USD"
    if preferred in normalized:
        return preferred
    return normalized[-1]


def normalize_currency(value: Any) -> str:
    """Normalize a three-letter ISO currency code."""
    code = str(value or "").strip().upper()
    return code if len(code) == 3 and code.isalpha() else ""


def currency_is_instrument_option(currency: Any, instrument: Any) -> bool:
    """Return whether ``currency`` is one of the instrument currencies."""
    code = normalize_currency(currency)
    return bool(code and code in instrument_currency_options(instrument))
