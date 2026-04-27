"""Strict parsing helpers for persisted Snowball strategy state."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any


def require(data: dict[str, Any], key: str) -> Any:
    if key not in data:
        raise KeyError(key)
    return data[key]


def require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Snowball state field {field_name} must be an object")
    return value


def require_list(value: Any, *, field_name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"Snowball state field {field_name} must be a list")
    return value


def strict_decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Snowball state field {field_name} must be decimal") from exc


def strict_int(value: Any, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"Snowball state field {field_name} must be integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Snowball state field {field_name} must be integer") from exc


def strict_bool(value: Any, *, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"Snowball state field {field_name} must be boolean")
    return value


def optional_decimal(data: dict[str, Any], key: str) -> Decimal | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    return strict_decimal(value, field_name=key)


def optional_int(data: dict[str, Any], key: str) -> int | None:
    value = data.get(key)
    if value in (None, ""):
        return None
    return strict_int(value, field_name=key)


def optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    return str(value)


def parse_datetime(value: Any, *, field_name: str) -> datetime:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Snowball state field {field_name} must be ISO datetime")
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"Snowball state field {field_name} must be ISO datetime") from exc
