"""Shared parsing utilities for event deserialization.

Eliminates the repeated try/except datetime and Decimal parsing blocks
that were duplicated across every ``from_dict`` class method in base.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation


def parse_datetime(value: object) -> datetime | None:
    """Parse a datetime from a dict value (str, datetime, or None)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def parse_decimal(value: object, default: str = "0") -> Decimal:
    """Parse a Decimal from a dict value, with fallback."""
    if not value:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(default)


def parse_optional_decimal(value: object) -> Decimal | None:
    """Parse an optional Decimal — returns None if absent/falsy."""
    if not value:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None
