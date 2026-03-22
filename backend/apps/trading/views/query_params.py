"""Shared query parameter validation and schema objects for task endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request

from apps.trading.views.pagination import (
    ActivityPagination,
    MetricsPagination,
    TradePositionPagination,
)


def _schema_datetime_field(help_text: str) -> serializers.DateTimeField:
    return serializers.DateTimeField(required=False, allow_null=True, help_text=help_text)


def _schema_string_field(help_text: str) -> serializers.CharField:
    return serializers.CharField(required=False, allow_blank=True, help_text=help_text)


def _schema_uuid_field(help_text: str) -> serializers.UUIDField:
    return serializers.UUIDField(required=False, allow_null=True, help_text=help_text)


def _schema_page_field() -> serializers.IntegerField:
    return serializers.IntegerField(required=False, min_value=1, help_text="Page number (1-based).")


def _schema_page_size_field(*, default: int, max_value: int) -> serializers.IntegerField:
    return serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=max_value,
        help_text=f"Results per page. Default {default}, maximum {max_value}.",
    )


def _schema_bool_field(help_text: str) -> serializers.BooleanField:
    return serializers.BooleanField(required=False, help_text=help_text)


def _invalid_query_param(detail: str) -> ValidationError:
    return ValidationError({"code": "invalid_query_param", "detail": detail})


def _extract_validation_detail(errors: Any) -> str:
    if isinstance(errors, dict):
        for _, value in errors.items():
            nested = _extract_validation_detail(value)
            if nested:
                return nested
    elif isinstance(errors, list) and errors:
        return _extract_validation_detail(errors[0])
    elif errors:
        return str(errors)
    return "Invalid query parameters"


class QueryParamsSerializer(serializers.Serializer):
    """Base serializer for strict query validation."""

    default_error_messages = {
        "invalid_query_param": "Invalid query parameters",
    }

    @classmethod
    def parse_query_params(cls, request: Request, **kwargs):
        serializer = cls(data=request.query_params, request=request, **kwargs)
        if not serializer.is_valid():
            raise _invalid_query_param(_extract_validation_detail(serializer.errors))
        return serializer


def _parse_datetime_value(value: str | None) -> datetime | None:
    if value:
        parsed = parse_datetime(value)
        if parsed is None:
            raise _invalid_query_param(f"Invalid datetime value: {value}")
        return parsed
    return None


def _parse_positive_int(
    value: str | None,
    *,
    field_name: str,
    default: int,
    max_value: int | None = None,
) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise _invalid_query_param(f"Invalid {field_name} parameter") from exc
    if parsed < 1:
        raise _invalid_query_param(f"{field_name} must be greater than 0")
    if max_value is not None and parsed > max_value:
        raise _invalid_query_param(f"{field_name} exceeds maximum allowed value of {max_value}")
    return parsed


def _parse_execution_id_value(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError) as exc:
        raise _invalid_query_param(f"Invalid execution_id: {value}") from exc


class PaginationParamsSerializer(QueryParamsSerializer):
    """Serializer for page/page_size validation."""

    def __init__(
        self,
        *args,
        request: Request,
        default_page_size: int = 100,
        max_page_size: int = 1000,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.request = request
        self.default_page_size = default_page_size
        self.max_page_size = max_page_size

    def to_params(self) -> PaginationParams:
        return PaginationParams(
            page=_parse_positive_int(
                self.request.query_params.get("page"),
                field_name="page",
                default=1,
            ),
            page_size=_parse_positive_int(
                self.request.query_params.get("page_size"),
                field_name="page_size",
                default=self.default_page_size,
                max_value=self.max_page_size,
            ),
        )


class ExecutionScopedQuerySerializer(PaginationParamsSerializer):
    """Serializer for execution-scoped query params."""

    def __init__(
        self,
        *args,
        request: Request,
        default_execution_id: UUID | None = None,
        default_page_size: int = 100,
        max_page_size: int = 1000,
        **kwargs,
    ) -> None:
        super().__init__(
            *args,
            request=request,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
            **kwargs,
        )
        self.default_execution_id = default_execution_id

    def to_query(self) -> ExecutionScopedQuery:
        return ExecutionScopedQuery(
            execution_id=_parse_execution_id_value(self.request.query_params.get("execution_id"))
            or self.default_execution_id,
            since=_parse_datetime_value(self.request.query_params.get("since")),
            pagination=self.to_params(),
        )


class DateRangeQuerySerializer(QueryParamsSerializer):
    """Serializer for datetime range validation."""

    def __init__(
        self,
        *args,
        request: Request,
        start_key: str,
        end_key: str,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.start_key = start_key
        self.end_key = end_key
        self.request = request

    def to_range(self) -> DateRangeQuery:
        start = _parse_datetime_value(self.request.query_params.get(self.start_key))
        end = _parse_datetime_value(self.request.query_params.get(self.end_key))
        if start and end and start > end:
            raise _invalid_query_param(
                f"{self.start_key} must be earlier than or equal to {self.end_key}"
            )
        return DateRangeQuery(start=start, end=end)


class ExecutionScopedQueryParamsSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for execution-scoped task query parameters."""

    execution_id = _schema_uuid_field("Filter by execution ID (UUID).")
    since = _schema_datetime_field("RFC3339 timestamp for incremental fetch.")
    page = _schema_page_field()
    page_size = _schema_page_size_field(
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
    )


class MetricsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for metrics query parameters."""

    page_size = _schema_page_size_field(
        default=MetricsPagination.page_size,
        max_value=MetricsPagination.max_page_size,
    )
    until = _schema_datetime_field("RFC3339 upper-bound timestamp (exclusive).")
    interval = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1440,
        help_text=(
            "Aggregation interval in minutes. Default 1. When greater than 1, "
            "returns one point per N-minute window."
        ),
    )


class LogsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for logs query parameters."""

    level = _schema_string_field("Log level filter (comma-separated for multiple).")
    component = _schema_string_field("Logger/component name filter (comma-separated for multiple).")
    position_id = _schema_string_field("Optional position ID prefix filter.")
    timestamp_from = _schema_datetime_field("Filter logs from this RFC3339 timestamp (inclusive).")
    timestamp_to = _schema_datetime_field("Filter logs until this RFC3339 timestamp (inclusive).")


class LogComponentsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for log component query parameters."""

    execution_id = _schema_uuid_field("Filter by execution ID (UUID).")


class EventsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for task events query parameters."""

    event_type = _schema_string_field("Event type filter.")
    severity = _schema_string_field("Severity filter.")
    scope = serializers.ChoiceField(
        required=False,
        choices=("all", "trading", "task"),
        help_text="Event scope filter.",
    )
    created_from = _schema_datetime_field(
        "Filter events created at or after this RFC3339 timestamp."
    )
    created_to = _schema_datetime_field(
        "Filter events created at or before this RFC3339 timestamp."
    )


class StrategyEventsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for strategy event visualization parameters."""

    execution_id = _schema_uuid_field("Filter by execution ID (UUID).")
    root_entry_id = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Optional root entry group filter.",
    )


class TradesQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trades query parameters."""

    page_size = _schema_page_size_field(
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
    )
    direction = _schema_string_field("Direction filter (buy/sell/long/short).")
    timestamp_from = _schema_datetime_field(
        "Filter trades executed at or after this RFC3339 timestamp."
    )
    timestamp_to = _schema_datetime_field(
        "Filter trades executed at or before this RFC3339 timestamp."
    )


class PositionsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for positions query parameters."""

    page_size = _schema_page_size_field(
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
    )
    position_status = serializers.ChoiceField(
        required=False,
        choices=("open", "closed"),
        help_text="Position status filter.",
    )
    direction = _schema_string_field("Direction filter.")
    include_trade_ids = _schema_bool_field("Include position trade_ids in the response.")
    range_from = _schema_datetime_field(
        "RFC3339 lower bound for positions overlapping a chart range."
    )
    range_to = _schema_datetime_field(
        "RFC3339 upper bound for positions overlapping a chart range."
    )


class TrendReplayQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trend replay parameters."""

    page_size = _schema_page_size_field(
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
    )
    range_from = _schema_datetime_field("RFC3339 lower bound for the chart window.")
    range_to = _schema_datetime_field("RFC3339 upper bound for the chart window.")


class OrdersQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for orders query parameters."""

    page_size = _schema_page_size_field(
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
    )
    status = _schema_string_field("Order status filter.")
    order_type = _schema_string_field("Order type filter.")
    direction = _schema_string_field("Direction filter.")


class SummaryQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for summary query parameters."""

    execution_id = _schema_uuid_field("Filter by execution ID (UUID).")


class ExecutionsQueryParamsSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for execution list query parameters."""

    page = _schema_page_field()
    page_size = _schema_page_size_field(
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
    )
    include_metrics = _schema_bool_field("Include aggregate execution metrics.")


class ExecutionDetailQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for execution detail query parameters."""

    include_metrics = _schema_bool_field("Include aggregate execution metrics.")


class PaginationSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for plain pagination parameters."""

    page = _schema_page_field()
    page_size = _schema_page_size_field(
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
    )


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        default_page_size: int = 100,
        max_page_size: int = 1000,
    ) -> PaginationParams:
        serializer = PaginationParamsSerializer.parse_query_params(
            request,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
        )
        return serializer.to_params()


@dataclass(frozen=True)
class ExecutionScopedQuery:
    execution_id: UUID | None
    since: datetime | None
    pagination: PaginationParams

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        default_execution_id: UUID | None,
        default_page_size: int = 100,
        max_page_size: int = 1000,
    ) -> ExecutionScopedQuery:
        serializer = ExecutionScopedQuerySerializer.parse_query_params(
            request,
            default_execution_id=default_execution_id,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
        )
        return serializer.to_query()


@dataclass(frozen=True)
class DateRangeQuery:
    start: datetime | None
    end: datetime | None

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        start_key: str,
        end_key: str,
    ) -> DateRangeQuery:
        serializer = DateRangeQuerySerializer.parse_query_params(
            request,
            start_key=start_key,
            end_key=end_key,
        )
        return serializer.to_range()


@dataclass(frozen=True)
class PositionQuery:
    execution: ExecutionScopedQuery
    position_status: str
    direction: str
    include_trade_ids: bool
    range: DateRangeQuery

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        default_execution_id: UUID | None,
        default_page_size: int = 100,
        max_page_size: int = 1000,
    ) -> PositionQuery:
        return cls(
            execution=ExecutionScopedQuery.from_request(
                request,
                default_execution_id=default_execution_id,
                default_page_size=default_page_size,
                max_page_size=max_page_size,
            ),
            position_status=(request.query_params.get("position_status") or "").lower(),
            direction=(request.query_params.get("direction") or "").lower(),
            include_trade_ids=str(request.query_params.get("include_trade_ids", "false")).lower()
            in {"1", "true", "yes", "on"},
            range=DateRangeQuery.from_request(
                request,
                start_key="range_from",
                end_key="range_to",
            ),
        )


@dataclass(frozen=True)
class TrendReplayQueryParams:
    execution: ExecutionScopedQuery
    range: DateRangeQuery

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        default_execution_id: UUID | None,
        default_page_size: int,
        max_page_size: int,
    ) -> TrendReplayQueryParams:
        return cls(
            execution=ExecutionScopedQuery.from_request(
                request,
                default_execution_id=default_execution_id,
                default_page_size=default_page_size,
                max_page_size=max_page_size,
            ),
            range=DateRangeQuery.from_request(
                request,
                start_key="range_from",
                end_key="range_to",
            ),
        )
