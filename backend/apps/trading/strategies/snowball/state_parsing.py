"""Strict parsing helpers for persisted Snowball strategy state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

__all__ = ["SNOWBALL_STATE_PARSER", "SnowballStateParser"]


@dataclass(frozen=True, slots=True)
class SnowballStateParser:
    """Strict parser for persisted Snowball strategy-state payloads."""

    def require(self, data: dict[str, Any], key: str) -> Any:
        """Return a required value or raise KeyError for missing fields."""
        if key not in data:
            raise KeyError(key)
        return data[key]

    def require_dict(self, value: Any, *, field_name: str) -> dict[str, Any]:
        """Return value as a dict or raise a state parse error."""
        if not isinstance(value, dict):
            raise ValueError(f"Snowball state field {field_name} must be an object")
        return value

    def require_list(self, value: Any, *, field_name: str) -> list[Any]:
        """Return value as a list or raise a state parse error."""
        if not isinstance(value, list):
            raise ValueError(f"Snowball state field {field_name} must be a list")
        return value

    def strict_decimal(self, value: Any, *, field_name: str) -> Decimal:
        """Parse a required Decimal value."""
        try:
            return Decimal(str(value))
        except Exception as exc:
            raise ValueError(f"Snowball state field {field_name} must be decimal") from exc

    def strict_int(self, value: Any, *, field_name: str) -> int:
        """Parse a required integer value while rejecting booleans."""
        if isinstance(value, bool):
            raise ValueError(f"Snowball state field {field_name} must be integer")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Snowball state field {field_name} must be integer") from exc

    def strict_bool(self, value: Any, *, field_name: str) -> bool:
        """Parse a required boolean value."""
        if not isinstance(value, bool):
            raise ValueError(f"Snowball state field {field_name} must be boolean")
        return value

    def optional_decimal(self, data: dict[str, Any], key: str) -> Decimal | None:
        """Parse an optional Decimal value from a state object."""
        value = data.get(key)
        if value in (None, ""):
            return None
        return self.strict_decimal(value, field_name=key)

    def optional_int(self, data: dict[str, Any], key: str) -> int | None:
        """Parse an optional integer value from a state object."""
        value = data.get(key)
        if value in (None, ""):
            return None
        return self.strict_int(value, field_name=key)

    def optional_str(self, data: dict[str, Any], key: str) -> str | None:
        """Parse an optional string value from a state object."""
        value = data.get(key)
        if value is None:
            return None
        return str(value)

    def parse_datetime(self, value: Any, *, field_name: str) -> datetime:
        """Parse a required ISO datetime value."""
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


SNOWBALL_STATE_PARSER = SnowballStateParser()
