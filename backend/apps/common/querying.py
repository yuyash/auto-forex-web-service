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

    def parser(self) -> "QueryOrdering":
        """Return an ordering parser bound to this config."""
        return QueryOrdering(self)

    def parse(self, raw: str | None) -> tuple[str, list[str]]:
        """Validate an API ordering value and return ORM order_by terms."""
        return self.parser().parse(raw)

    def apply_to_queryset(self, queryset: QuerySet, raw: str | None) -> QuerySet:
        """Apply validated ordering to a Django queryset."""
        return self.parser().apply_to_queryset(queryset, raw)

    def normalize(self, raw: str | None) -> str:
        """Return the normalized API ordering field."""
        return self.parser().normalize(raw)

    def sort_records(
        self,
        records: Iterable[dict[str, Any]],
        raw: str | None,
    ) -> list[dict[str, Any]]:
        """Sort API records using this ordering config."""
        return self.parser().sort_records(records, raw)


@dataclass(frozen=True, slots=True)
class QueryOrdering:
    """Object-oriented query ordering parser and in-memory sorter."""

    config: OrderingConfig

    def parse(self, raw: str | None) -> tuple[str, list[str]]:
        """Validate an API ordering value and return ORM order_by terms."""
        normalized = self._normalise_ordering_value(raw)
        descending = normalized.startswith("-")
        api_field = normalized[1:] if descending else normalized
        model_field = self.config.fields[api_field]
        prefix = "-" if descending else ""
        terms = [f"{prefix}{model_field}"]

        for tie_breaker in self.config.tie_breakers:
            tie_descending = tie_breaker.startswith("-")
            tie_api_field = tie_breaker[1:] if tie_descending else tie_breaker
            tie_model_field = self.config.fields.get(tie_api_field, tie_api_field)
            if tie_model_field == model_field:
                continue
            tie_prefix = "-" if (tie_descending or descending) else ""
            terms.append(f"{tie_prefix}{tie_model_field}")

        return normalized, terms

    def apply_to_queryset(self, queryset: QuerySet, raw: str | None) -> QuerySet:
        """Apply validated ordering to a Django queryset."""
        _normalized, terms = self.parse(raw)
        return queryset.order_by(*terms)

    def normalize(self, raw: str | None) -> str:
        """Return the normalized API ordering field."""
        normalized, _terms = self.parse(raw)
        return normalized

    def sort_records(
        self,
        records: Iterable[dict[str, Any]],
        raw: str | None,
    ) -> list[dict[str, Any]]:
        """Sort API records using the same ordering model as querysets."""
        _normalized, terms = self.parse(raw)
        term_fields = [self._term_to_record_field(term) for term in terms]

        def compare(left: dict[str, Any], right: dict[str, Any]) -> int:
            for field_name, descending in term_fields:
                result = self._compare_values(left.get(field_name), right.get(field_name))
                if result:
                    return -result if descending else result
            return 0

        return sorted(list(records), key=cmp_to_key(compare))

    def _normalise_ordering_value(self, raw: str | None) -> str:
        value = (raw or self.config.default).strip() or self.config.default
        if value in {"asc", "desc"} and self.config.legacy_direction_field:
            value = (
                self.config.legacy_direction_field
                if value == "asc"
                else f"-{self.config.legacy_direction_field}"
            )

        descending = value.startswith("-")
        api_field = value[1:] if descending else value
        if api_field not in self.config.fields:
            allowed = ", ".join(sorted(self.config.fields))
            raise invalid_query_param(f"ordering must be one of: {allowed}")
        return f"-{api_field}" if descending else api_field

    def _term_to_record_field(self, term: str) -> tuple[str, bool]:
        descending = term.startswith("-")
        model_field = term[1:] if descending else term
        for api_field, configured_model_field in self.config.fields.items():
            if configured_model_field == model_field:
                return api_field, descending
        return model_field, descending

    @staticmethod
    def _compare_values(left: Any, right: Any) -> int:
        if left is None and right is None:
            return 0
        if left is None:
            return 1
        if right is None:
            return -1

        left_value = QueryOrdering._coerce_sort_value(left)
        right_value = QueryOrdering._coerce_sort_value(right)
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

    @staticmethod
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
    return config.parse(raw)


def apply_queryset_ordering(
    queryset: QuerySet,
    raw: str | None,
    config: OrderingConfig,
) -> QuerySet:
    """Apply validated ordering to a Django queryset."""
    return config.apply_to_queryset(queryset, raw)


def normalize_ordering(raw: str | None, config: OrderingConfig) -> str:
    """Return the normalized API ordering field."""
    return config.normalize(raw)


def sort_records(
    records: Iterable[dict[str, Any]],
    raw: str | None,
    config: OrderingConfig,
) -> list[dict[str, Any]]:
    """Sort a list of API records using the same ordering model as querysets."""
    return config.sort_records(records, raw)
