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
