"""Utility functions for the trading app."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any


def pip_size_for_instrument(instrument: str) -> Decimal:
    """Calculate pip size for a given instrument.

    Args:
        instrument: Trading instrument (currency pair) like "EUR_USD" or "USD_JPY"

    Returns:
        Decimal pip size (0.01 for JPY pairs, 0.0001 for others)
    """
    inst = str(instrument).upper()
    return Decimal("0.01") if "JPY" in inst else Decimal("0.0001")


def normalize_instance_key(instance_key: str | None) -> str:
    """Normalize an instance key to a string.

    Args:
        instance_key: Optional instance key

    Returns:
        Normalized instance key string (defaults to "default" if None)
    """
    return str(instance_key) if instance_key else "default"


def parse_iso_datetime(value: Any) -> datetime | None:
    """Parse an ISO datetime string with best-effort handling.

    Accepts ISO 8601 format strings with or without timezone information.
    Handles 'Z' suffix for UTC timezone.

    Args:
        value: Value to parse (typically a string)

    Returns:
        Parsed datetime with timezone info, or None if parsing fails
    """
    if value is None:
        return None
    try:
        s = str(value)
    except Exception:
        return None
    s = s.strip()
    if not s:
        return None
    # Accept Z suffix for UTC
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        return None
    # Ensure timezone-aware datetime
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


__all__ = [
    "pip_size_for_instrument",
    "normalize_instance_key",
    "parse_iso_datetime",
]
