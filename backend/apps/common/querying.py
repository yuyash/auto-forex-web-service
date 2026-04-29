"""Shared query helpers for API filtering, sorting, and pagination."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import cmp_to_key
from typing import Any, Iterable, Mapping

from django.db.models import QuerySet
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError


@dataclass(frozen=True)
class OrderingConfig:
    """Allowed API ordering fields and their backend representation."""

    fields: Mapping[str, str]
    default: str
    tie_breakers: tuple[str, ...] = ("id",)
    legacy_direction_field: str | None = None


def invalid_query_param(detail: str) -> ValidationError:
    """Return the common validation shape used by API query parsers."""
    return ValidationError({"code": "invalid_query_param", "detail": detail})


def parse_datetime_param(value: str | None, *, field_name: str) -> datetime | None:
    """Parse one RFC3339 datetime query parameter."""
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is None:
        raise invalid_query_param(f"Invalid datetime value: {value}")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed)
    return parsed


def parse_ordering(raw: str | None, config: OrderingConfig) -> tuple[str, list[str]]:
    """Validate an API ordering value and return ORM order_by terms."""
    normalized = _normalise_ordering_value(raw, config)
    descending = normalized.startswith("-")
    api_field = normalized[1:] if descending else normalized
    model_field = config.fields[api_field]
    prefix = "-" if descending else ""
    terms = [f"{prefix}{model_field}"]

    for tie_breaker in config.tie_breakers:
        tie_descending = tie_breaker.startswith("-")
        tie_api_field = tie_breaker[1:] if tie_descending else tie_breaker
        tie_model_field = config.fields.get(tie_api_field, tie_api_field)
        if tie_model_field == model_field:
            continue
        tie_prefix = "-" if (tie_descending or descending) else ""
        terms.append(f"{tie_prefix}{tie_model_field}")

    return normalized, terms


def apply_queryset_ordering(
    queryset: QuerySet,
    raw: str | None,
    config: OrderingConfig,
) -> QuerySet:
    """Apply validated ordering to a Django queryset."""
    _normalized, terms = parse_ordering(raw, config)
    return queryset.order_by(*terms)


def normalize_ordering(raw: str | None, config: OrderingConfig) -> str:
    """Return the normalized API ordering field."""
    normalized, _terms = parse_ordering(raw, config)
    return normalized


def sort_records(
    records: Iterable[dict[str, Any]],
    raw: str | None,
    config: OrderingConfig,
) -> list[dict[str, Any]]:
    """Sort a list of API records using the same ordering model as querysets."""
    normalized, terms = parse_ordering(raw, config)
    term_fields = [_term_to_record_field(term, config) for term in terms]

    def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
        for field_name, descending in term_fields:
            result = _compare_values(left.get(field_name), right.get(field_name))
            if result:
                return -result if descending else result
        return 0

    return sorted(list(records), key=cmp_to_key(compare))


def _normalise_ordering_value(raw: str | None, config: OrderingConfig) -> str:
    value = (raw or config.default).strip() or config.default
    if value in {"asc", "desc"} and config.legacy_direction_field:
        value = (
            config.legacy_direction_field if value == "asc" else f"-{config.legacy_direction_field}"
        )

    descending = value.startswith("-")
    api_field = value[1:] if descending else value
    if api_field not in config.fields:
        allowed = ", ".join(sorted(config.fields))
        raise invalid_query_param(f"ordering must be one of: {allowed}")
    return f"-{api_field}" if descending else api_field


def _term_to_record_field(term: str, config: OrderingConfig) -> tuple[str, bool]:
    descending = term.startswith("-")
    model_field = term[1:] if descending else term
    for api_field, configured_model_field in config.fields.items():
        if configured_model_field == model_field:
            return api_field, descending
    return model_field, descending


def _compare_values(left: Any, right: Any) -> int:
    if left is None and right is None:
        return 0
    if left is None:
        return 1
    if right is None:
        return -1

    left_value = _coerce_sort_value(left)
    right_value = _coerce_sort_value(right)
    try:
        if left_value < right_value:
            return -1
        if left_value > right_value:
            return 1
        return 0
    except TypeError:
        left_str = str(left_value)
        right_str = str(right_value)
        if left_str < right_str:
            return -1
        if left_str > right_str:
            return 1
        return 0


def _coerce_sort_value(value: Any) -> Any:
    if isinstance(value, (datetime, Decimal, int, float)):
        return value
    if isinstance(value, str):
        parsed_datetime = parse_datetime(value)
        if parsed_datetime is not None:
            return parsed_datetime
        try:
            return Decimal(value)
        except (InvalidOperation, ValueError):
            return value.casefold()
    return value
