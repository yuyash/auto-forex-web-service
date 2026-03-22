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

    execution_id = serializers.UUIDField(required=False, allow_null=True)
    since = serializers.DateTimeField(required=False, allow_null=True)
    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000)


class MetricsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for metrics query parameters."""

    until = serializers.DateTimeField(required=False, allow_null=True)
    interval = serializers.IntegerField(required=False, min_value=1, max_value=1440)


class LogsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for logs query parameters."""

    level = serializers.CharField(required=False, allow_blank=True)
    component = serializers.CharField(required=False, allow_blank=True)
    position_id = serializers.CharField(required=False, allow_blank=True)
    timestamp_from = serializers.DateTimeField(required=False, allow_null=True)
    timestamp_to = serializers.DateTimeField(required=False, allow_null=True)


class LogComponentsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for log component query parameters."""

    execution_id = serializers.UUIDField(required=False, allow_null=True)


class EventsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for task events query parameters."""

    event_type = serializers.CharField(required=False, allow_blank=True)
    severity = serializers.CharField(required=False, allow_blank=True)
    scope = serializers.ChoiceField(
        required=False,
        choices=("all", "trading", "task"),
    )
    created_from = serializers.DateTimeField(required=False, allow_null=True)
    created_to = serializers.DateTimeField(required=False, allow_null=True)


class StrategyEventsQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for strategy event visualization parameters."""

    execution_id = serializers.UUIDField(required=False, allow_null=True)
    root_entry_id = serializers.IntegerField(required=False, min_value=1)


class TradesQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trades query parameters."""

    direction = serializers.CharField(required=False, allow_blank=True)
    timestamp_from = serializers.DateTimeField(required=False, allow_null=True)
    timestamp_to = serializers.DateTimeField(required=False, allow_null=True)


class PositionsQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for positions query parameters."""

    position_status = serializers.ChoiceField(
        required=False,
        choices=("open", "closed"),
    )
    direction = serializers.CharField(required=False, allow_blank=True)
    include_trade_ids = serializers.BooleanField(required=False)
    range_from = serializers.DateTimeField(required=False, allow_null=True)
    range_to = serializers.DateTimeField(required=False, allow_null=True)


class TrendReplayQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for trend replay parameters."""

    range_from = serializers.DateTimeField(required=False, allow_null=True)
    range_to = serializers.DateTimeField(required=False, allow_null=True)


class OrdersQueryParamsSchemaSerializer(ExecutionScopedQueryParamsSchemaSerializer):
    """OpenAPI serializer for orders query parameters."""

    status = serializers.CharField(required=False, allow_blank=True)
    order_type = serializers.CharField(required=False, allow_blank=True)
    direction = serializers.CharField(required=False, allow_blank=True)


class SummaryQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for summary query parameters."""

    execution_id = serializers.UUIDField(required=False, allow_null=True)


class ExecutionsQueryParamsSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for execution list query parameters."""

    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000)
    include_metrics = serializers.BooleanField(required=False)


class ExecutionDetailQueryParamsSchemaSerializer(QueryParamsSerializer):
    """OpenAPI serializer for execution detail query parameters."""

    include_metrics = serializers.BooleanField(required=False)


class PaginationSchemaSerializer(serializers.Serializer):
    """OpenAPI serializer for plain pagination parameters."""

    page = serializers.IntegerField(required=False, min_value=1)
    page_size = serializers.IntegerField(required=False, min_value=1, max_value=1000)


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
