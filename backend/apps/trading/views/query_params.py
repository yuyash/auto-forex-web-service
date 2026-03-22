"""Shared query parameter validation and schema objects for task endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
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


def _page_size_spec(*, default: int, max_value: int) -> QueryFieldSpec:
    return QueryFieldSpec(
        name="page_size",
        kind="int",
        default=default,
        max_value=max_value,
        help_text=f"Results per page. Default {default}, maximum {max_value}.",
    )


def _build_query_schema_serializer(
    name: str,
    *specs: QueryFieldSpec,
    base: type[serializers.Serializer] = serializers.Serializer,
    docstring: str | None = None,
) -> type[serializers.Serializer]:
    attrs = {spec.name: spec.schema_field() for spec in specs}
    if docstring:
        attrs["__doc__"] = docstring
    return cast(type[serializers.Serializer], type(name, (base,), attrs))


def _parse_query_group(
    request: Request,
    *specs: QueryFieldSpec,
    serializer_name: str,
) -> dict[str, object]:
    del serializer_name
    return {spec.name: spec.parse(request.query_params.get(spec.name)) for spec in specs}


def _parse_date_range_group(
    request: Request,
    *,
    start_spec: QueryFieldSpec,
    end_spec: QueryFieldSpec,
    serializer_name: str,
) -> tuple[datetime | None, datetime | None]:
    parsed = _parse_query_group(
        request,
        start_spec,
        end_spec,
        serializer_name=serializer_name,
    )
    start = cast(datetime | None, parsed[start_spec.name])
    end = cast(datetime | None, parsed[end_spec.name])
    if start and end and start > end:
        raise _invalid_query_param(
            f"{start_spec.name} must be earlier than or equal to {end_spec.name}"
        )
    return start, end


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
ACTIVITY_PAGE_SIZE_SPEC = _page_size_spec(
    default=ActivityPagination.page_size,
    max_value=ActivityPagination.max_page_size,
)
METRICS_PAGE_SIZE_SPEC = _page_size_spec(
    default=MetricsPagination.page_size,
    max_value=MetricsPagination.max_page_size,
)
TRADE_POSITION_PAGE_SIZE_SPEC = _page_size_spec(
    default=TradePositionPagination.page_size,
    max_value=TradePositionPagination.max_page_size,
)
TRADES_DIRECTION_SPEC = QueryFieldSpec(
    name="direction",
    kind="string",
    allow_blank=True,
    help_text="Direction filter (buy/sell/long/short).",
)
TRADE_TIMESTAMP_FROM_SPEC = QueryFieldSpec(
    name="timestamp_from",
    kind="datetime",
    help_text="Filter trades executed at or after this RFC3339 timestamp.",
)
TRADE_TIMESTAMP_TO_SPEC = QueryFieldSpec(
    name="timestamp_to",
    kind="datetime",
    help_text="Filter trades executed at or before this RFC3339 timestamp.",
)
POSITIONS_RANGE_FROM_SPEC = QueryFieldSpec(
    name="range_from",
    kind="datetime",
    help_text="RFC3339 lower bound for positions overlapping a chart range.",
)
POSITIONS_RANGE_TO_SPEC = QueryFieldSpec(
    name="range_to",
    kind="datetime",
    help_text="RFC3339 upper bound for positions overlapping a chart range.",
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
        serializer = cls(data=request.query_params, **kwargs)
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


ExecutionScopedQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "ExecutionScopedQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    ACTIVITY_PAGE_SIZE_SPEC,
    docstring="OpenAPI serializer for execution-scoped task query parameters.",
)

MetricsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "MetricsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    METRICS_PAGE_SIZE_SPEC,
    UNTIL_SPEC,
    INTERVAL_SPEC,
    docstring="OpenAPI serializer for metrics query parameters.",
)

LogsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "LogsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    ACTIVITY_PAGE_SIZE_SPEC,
    LEVEL_SPEC,
    COMPONENT_SPEC,
    POSITION_ID_SPEC,
    TIMESTAMP_FROM_SPEC,
    TIMESTAMP_TO_SPEC,
    docstring="OpenAPI serializer for logs query parameters.",
)

LogComponentsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "LogComponentsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    base=QueryParamsSerializer,
    docstring="OpenAPI serializer for log component query parameters.",
)

EventsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "EventsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    ACTIVITY_PAGE_SIZE_SPEC,
    EVENT_TYPE_SPEC,
    SEVERITY_SPEC,
    SCOPE_SPEC,
    CREATED_FROM_SPEC,
    CREATED_TO_SPEC,
    docstring="OpenAPI serializer for task events query parameters.",
)

StrategyEventsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "StrategyEventsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    ROOT_ENTRY_ID_SPEC,
    base=QueryParamsSerializer,
    docstring="OpenAPI serializer for strategy event visualization parameters.",
)

TradesQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "TradesQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    TRADE_POSITION_PAGE_SIZE_SPEC,
    TRADES_DIRECTION_SPEC,
    TRADE_TIMESTAMP_FROM_SPEC,
    TRADE_TIMESTAMP_TO_SPEC,
    docstring="OpenAPI serializer for trades query parameters.",
)

PositionsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "PositionsQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    TRADE_POSITION_PAGE_SIZE_SPEC,
    POSITION_STATUS_SPEC,
    DIRECTION_SPEC,
    INCLUDE_TRADE_IDS_SPEC,
    POSITIONS_RANGE_FROM_SPEC,
    POSITIONS_RANGE_TO_SPEC,
    docstring="OpenAPI serializer for positions query parameters.",
)

TrendReplayQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "TrendReplayQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    TRADE_POSITION_PAGE_SIZE_SPEC,
    RANGE_FROM_SPEC,
    RANGE_TO_SPEC,
    docstring="OpenAPI serializer for trend replay parameters.",
)

OrdersQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "OrdersQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    SINCE_SPEC,
    PAGE_SPEC,
    TRADE_POSITION_PAGE_SIZE_SPEC,
    ORDER_STATUS_SPEC,
    ORDER_TYPE_SPEC,
    DIRECTION_SPEC,
    docstring="OpenAPI serializer for orders query parameters.",
)

SummaryQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "SummaryQueryParamsSchemaSerializer",
    EXECUTION_ID_SPEC,
    base=QueryParamsSerializer,
    docstring="OpenAPI serializer for summary query parameters.",
)

ExecutionsQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "ExecutionsQueryParamsSchemaSerializer",
    PAGE_SPEC,
    ACTIVITY_PAGE_SIZE_SPEC,
    INCLUDE_METRICS_SPEC,
    docstring="OpenAPI serializer for execution list query parameters.",
)

ExecutionDetailQueryParamsSchemaSerializer = _build_query_schema_serializer(
    "ExecutionDetailQueryParamsSchemaSerializer",
    INCLUDE_METRICS_SPEC,
    base=QueryParamsSerializer,
    docstring="OpenAPI serializer for execution detail query parameters.",
)

PaginationSchemaSerializer = _build_query_schema_serializer(
    "PaginationSchemaSerializer",
    PAGE_SPEC,
    ACTIVITY_PAGE_SIZE_SPEC,
    docstring="OpenAPI serializer for plain pagination parameters.",
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
        page_size_spec = _page_size_spec(
            default=default_page_size,
            max_value=max_page_size,
        )
        parsed = _parse_query_group(
            request,
            PAGE_SPEC,
            page_size_spec,
            serializer_name="PaginationParamsRuntimeSerializer",
        )
        return cls(
            page=cast(int, parsed["page"]),
            page_size=cast(int, parsed["page_size"]),
        )


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
        page_size_spec = _page_size_spec(
            default=default_page_size,
            max_value=max_page_size,
        )
        parsed = _parse_query_group(
            request,
            EXECUTION_ID_SPEC,
            SINCE_SPEC,
            PAGE_SPEC,
            page_size_spec,
            serializer_name="ExecutionScopedQueryRuntimeSerializer",
        )
        return cls(
            execution_id=cast(UUID | None, parsed["execution_id"]) or default_execution_id,
            since=cast(datetime | None, parsed["since"]),
            pagination=PaginationParams(
                page=cast(int, parsed["page"]),
                page_size=cast(int, parsed["page_size"]),
            ),
        )


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
        field_specs = {
            "range_from": RANGE_FROM_SPEC,
            "range_to": RANGE_TO_SPEC,
            "timestamp_from": TIMESTAMP_FROM_SPEC,
            "timestamp_to": TIMESTAMP_TO_SPEC,
            "created_from": CREATED_FROM_SPEC,
            "created_to": CREATED_TO_SPEC,
        }
        start_spec = field_specs.get(start_key) or QueryFieldSpec(
            name=start_key,
            kind="datetime",
            help_text=f"RFC3339 lower bound for {start_key}.",
        )
        end_spec = field_specs.get(end_key) or QueryFieldSpec(
            name=end_key,
            kind="datetime",
            help_text=f"RFC3339 upper bound for {end_key}.",
        )
        start, end = _parse_date_range_group(
            request,
            start_spec=start_spec,
            end_spec=end_spec,
            serializer_name="DateRangeQueryRuntimeSerializer",
        )
        return cls(start=start, end=end)


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
        parsed = _parse_query_group(
            request,
            POSITION_STATUS_SPEC,
            DIRECTION_SPEC,
            INCLUDE_TRADE_IDS_SPEC,
            serializer_name="PositionQueryRuntimeSerializer",
        )
        return cls(
            execution=ExecutionScopedQuery.from_request(
                request,
                default_execution_id=default_execution_id,
                default_page_size=default_page_size,
                max_page_size=max_page_size,
            ),
            position_status=cast(str, parsed["position_status"]),
            direction=cast(str, parsed["direction"]),
            include_trade_ids=cast(bool, parsed["include_trade_ids"]),
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
