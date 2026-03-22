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


@dataclass(frozen=True)
class QueryFieldSpec:
    """Shared runtime and schema definition for query parameters."""

    name: str
    help_text: str
    kind: str
    default: object | None = None
    max_value: int | None = None
    choices: tuple[str, ...] | None = None
    allow_blank: bool = False

    def schema_field(self) -> serializers.Field:
        if self.kind == "datetime":
            return serializers.DateTimeField(
                required=False,
                allow_null=True,
                help_text=self.help_text,
            )
        if self.kind == "uuid":
            return serializers.UUIDField(
                required=False,
                allow_null=True,
                help_text=self.help_text,
            )
        if self.kind == "string":
            return serializers.CharField(
                required=False,
                allow_blank=self.allow_blank,
                help_text=self.help_text,
            )
        if self.kind == "bool":
            return serializers.BooleanField(required=False, help_text=self.help_text)
        if self.kind == "choice":
            return serializers.ChoiceField(
                required=False,
                choices=self.choices or (),
                help_text=self.help_text,
            )
        if self.kind == "int":
            return serializers.IntegerField(
                required=False,
                min_value=1,
                max_value=self.max_value,
                help_text=self.help_text,
            )
        raise ValueError(f"Unsupported query field kind: {self.kind}")

    def parse(self, value: str | None):
        if self.kind == "datetime":
            return _parse_datetime_value(value)
        if self.kind == "uuid":
            return _parse_execution_id_value(value)
        if self.kind == "int":
            default = self.default if isinstance(self.default, int) else 1
            return _parse_positive_int(
                value,
                field_name=self.name,
                default=default,
                max_value=self.max_value,
            )
        if self.kind == "bool":
            return str(value or "").lower() in {"1", "true", "yes", "on"}
        if self.kind == "choice":
            normalized = (value or "").lower()
            if normalized and self.choices and normalized not in self.choices:
                raise _invalid_query_param(f"{self.name} must be one of: {', '.join(self.choices)}")
            return normalized
        if self.kind == "string":
            return value or ""
        raise ValueError(f"Unsupported query field kind: {self.kind}")


PAGE_SPEC = QueryFieldSpec(
    name="page",
    kind="int",
    default=1,
    help_text="Page number (1-based).",
)
EXECUTION_ID_SPEC = QueryFieldSpec(
    name="execution_id",
    kind="uuid",
    help_text="Filter by execution ID (UUID).",
)
SINCE_SPEC = QueryFieldSpec(
    name="since",
    kind="datetime",
    help_text="RFC3339 timestamp for incremental fetch.",
)
ROOT_ENTRY_ID_SPEC = QueryFieldSpec(
    name="root_entry_id",
    kind="int",
    help_text="Optional root entry group filter.",
)
UNTIL_SPEC = QueryFieldSpec(
    name="until",
    kind="datetime",
    help_text="RFC3339 upper-bound timestamp (exclusive).",
)
INTERVAL_SPEC = QueryFieldSpec(
    name="interval",
    kind="int",
    max_value=1440,
    help_text=(
        "Aggregation interval in minutes. Default 1. When greater than 1, "
        "returns one point per N-minute window."
    ),
)
LEVEL_SPEC = QueryFieldSpec(
    name="level",
    kind="string",
    allow_blank=True,
    help_text="Log level filter (comma-separated for multiple).",
)
COMPONENT_SPEC = QueryFieldSpec(
    name="component",
    kind="string",
    allow_blank=True,
    help_text="Logger/component name filter (comma-separated for multiple).",
)
POSITION_ID_SPEC = QueryFieldSpec(
    name="position_id",
    kind="string",
    allow_blank=True,
    help_text="Optional position ID prefix filter.",
)
TIMESTAMP_FROM_SPEC = QueryFieldSpec(
    name="timestamp_from",
    kind="datetime",
    help_text="Filter records from this RFC3339 timestamp (inclusive).",
)
TIMESTAMP_TO_SPEC = QueryFieldSpec(
    name="timestamp_to",
    kind="datetime",
    help_text="Filter records until this RFC3339 timestamp (inclusive).",
)
EVENT_TYPE_SPEC = QueryFieldSpec(
    name="event_type",
    kind="string",
    allow_blank=True,
    help_text="Event type filter.",
)
SEVERITY_SPEC = QueryFieldSpec(
    name="severity",
    kind="string",
    allow_blank=True,
    help_text="Severity filter.",
)
SCOPE_SPEC = QueryFieldSpec(
    name="scope",
    kind="choice",
    choices=("all", "trading", "task"),
    help_text="Event scope filter.",
)
CREATED_FROM_SPEC = QueryFieldSpec(
    name="created_from",
    kind="datetime",
    help_text="Filter events created at or after this RFC3339 timestamp.",
)
CREATED_TO_SPEC = QueryFieldSpec(
    name="created_to",
    kind="datetime",
    help_text="Filter events created at or before this RFC3339 timestamp.",
)
DIRECTION_SPEC = QueryFieldSpec(
    name="direction",
    kind="string",
    allow_blank=True,
    help_text="Direction filter.",
)
POSITION_STATUS_SPEC = QueryFieldSpec(
    name="position_status",
    kind="choice",
    choices=("open", "closed"),
    help_text="Position status filter.",
)
INCLUDE_TRADE_IDS_SPEC = QueryFieldSpec(
    name="include_trade_ids",
    kind="bool",
    help_text="Include position trade_ids in the response.",
)
RANGE_FROM_SPEC = QueryFieldSpec(
    name="range_from",
    kind="datetime",
    help_text="RFC3339 lower bound for the chart window.",
)
RANGE_TO_SPEC = QueryFieldSpec(
    name="range_to",
    kind="datetime",
    help_text="RFC3339 upper bound for the chart window.",
)
ORDER_STATUS_SPEC = QueryFieldSpec(
    name="status",
    kind="string",
    allow_blank=True,
    help_text="Order status filter.",
)
ORDER_TYPE_SPEC = QueryFieldSpec(
    name="order_type",
    kind="string",
    allow_blank=True,
    help_text="Order type filter.",
)
INCLUDE_METRICS_SPEC = QueryFieldSpec(
    name="include_metrics",
    kind="bool",
    help_text="Include aggregate execution metrics.",
)


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
        self.page_size_spec = QueryFieldSpec(
            name="page_size",
            kind="int",
            default=default_page_size,
            max_value=max_page_size,
            help_text=f"Results per page. Default {default_page_size}, maximum {max_page_size}.",
        )

    def to_params(self) -> PaginationParams:
        return PaginationParams(
            page=PAGE_SPEC.parse(self.request.query_params.get("page")),
            page_size=self.page_size_spec.parse(self.request.query_params.get("page_size")),
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
            execution_id=EXECUTION_ID_SPEC.parse(self.request.query_params.get("execution_id"))
            or self.default_execution_id,
            since=SINCE_SPEC.parse(self.request.query_params.get("since")),
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

    execution_id = EXECUTION_ID_SPEC.schema_field()
    since = SINCE_SPEC.schema_field()
    page = PAGE_SPEC.schema_field()
    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
        help_text=(
            f"Results per page. Default {ActivityPagination.page_size}, "
            f"maximum {ActivityPagination.max_page_size}."
        ),
    ).schema_field()


class MetricsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for metrics query parameters."""

    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=MetricsPagination.page_size,
        max_value=MetricsPagination.max_page_size,
        help_text=(
            f"Results per page. Default {MetricsPagination.page_size}, "
            f"maximum {MetricsPagination.max_page_size}."
        ),
    ).schema_field()
    until = UNTIL_SPEC.schema_field()
    interval = INTERVAL_SPEC.schema_field()


class LogsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for logs query parameters."""

    level = LEVEL_SPEC.schema_field()
    component = COMPONENT_SPEC.schema_field()
    position_id = POSITION_ID_SPEC.schema_field()
    timestamp_from = TIMESTAMP_FROM_SPEC.schema_field()
    timestamp_to = TIMESTAMP_TO_SPEC.schema_field()


class LogComponentsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for log component query parameters."""

    execution_id = EXECUTION_ID_SPEC.schema_field()


class EventsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for task events query parameters."""

    event_type = EVENT_TYPE_SPEC.schema_field()
    severity = SEVERITY_SPEC.schema_field()
    scope = SCOPE_SPEC.schema_field()
    created_from = CREATED_FROM_SPEC.schema_field()
    created_to = CREATED_TO_SPEC.schema_field()


class StrategyEventsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for strategy event visualization parameters."""

    execution_id = EXECUTION_ID_SPEC.schema_field()
    root_entry_id = ROOT_ENTRY_ID_SPEC.schema_field()


class TradesQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trades query parameters."""

    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
        help_text=(
            f"Results per page. Default {TradePositionPagination.page_size}, "
            f"maximum {TradePositionPagination.max_page_size}."
        ),
    ).schema_field()
    direction = QueryFieldSpec(
        name="direction",
        kind="string",
        allow_blank=True,
        help_text="Direction filter (buy/sell/long/short).",
    ).schema_field()
    timestamp_from = QueryFieldSpec(
        name="timestamp_from",
        kind="datetime",
        help_text="Filter trades executed at or after this RFC3339 timestamp.",
    ).schema_field()
    timestamp_to = QueryFieldSpec(
        name="timestamp_to",
        kind="datetime",
        help_text="Filter trades executed at or before this RFC3339 timestamp.",
    ).schema_field()


class PositionsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for positions query parameters."""

    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
        help_text=(
            f"Results per page. Default {TradePositionPagination.page_size}, "
            f"maximum {TradePositionPagination.max_page_size}."
        ),
    ).schema_field()
    position_status = POSITION_STATUS_SPEC.schema_field()
    direction = DIRECTION_SPEC.schema_field()
    include_trade_ids = INCLUDE_TRADE_IDS_SPEC.schema_field()
    range_from = QueryFieldSpec(
        name="range_from",
        kind="datetime",
        help_text="RFC3339 lower bound for positions overlapping a chart range.",
    ).schema_field()
    range_to = QueryFieldSpec(
        name="range_to",
        kind="datetime",
        help_text="RFC3339 upper bound for positions overlapping a chart range.",
    ).schema_field()


class TrendReplayQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trend replay parameters."""

    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
        help_text=(
            f"Results per page. Default {TradePositionPagination.page_size}, "
            f"maximum {TradePositionPagination.max_page_size}."
        ),
    ).schema_field()
    range_from = RANGE_FROM_SPEC.schema_field()
    range_to = RANGE_TO_SPEC.schema_field()


class OrdersQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for orders query parameters."""

    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=TradePositionPagination.page_size,
        max_value=TradePositionPagination.max_page_size,
        help_text=(
            f"Results per page. Default {TradePositionPagination.page_size}, "
            f"maximum {TradePositionPagination.max_page_size}."
        ),
    ).schema_field()
    status = ORDER_STATUS_SPEC.schema_field()
    order_type = ORDER_TYPE_SPEC.schema_field()
    direction = DIRECTION_SPEC.schema_field()


class SummaryQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for summary query parameters."""

    execution_id = EXECUTION_ID_SPEC.schema_field()


class ExecutionsQueryParamsSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for execution list query parameters."""

    page = PAGE_SPEC.schema_field()
    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
        help_text=(
            f"Results per page. Default {ActivityPagination.page_size}, "
            f"maximum {ActivityPagination.max_page_size}."
        ),
    ).schema_field()
    include_metrics = INCLUDE_METRICS_SPEC.schema_field()


class ExecutionDetailQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for execution detail query parameters."""

    include_metrics = INCLUDE_METRICS_SPEC.schema_field()


class PaginationSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for plain pagination parameters."""

    page = PAGE_SPEC.schema_field()
    page_size = QueryFieldSpec(
        name="page_size",
        kind="int",
        default=ActivityPagination.page_size,
        max_value=ActivityPagination.max_page_size,
        help_text=(
            f"Results per page. Default {ActivityPagination.page_size}, "
            f"maximum {ActivityPagination.max_page_size}."
        ),
    ).schema_field()


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
