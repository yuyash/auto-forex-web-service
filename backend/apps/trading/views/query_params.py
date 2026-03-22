"""Shared query parameter objects for task sub-resource endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils.dateparse import parse_datetime
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request


def _parse_datetime_value(value: str | None) -> datetime | None:
    if value:
        parsed = parse_datetime(value)
        if parsed is None:
            raise ValidationError(
                {"code": "invalid_query_param", "detail": f"Invalid datetime value: {value}"}
            )
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
    except (TypeError, ValueError):
        raise ValidationError(
            {"code": "invalid_query_param", "detail": f"Invalid {field_name} parameter"}
        )
    if parsed < 1:
        raise ValidationError(
            {"code": "invalid_query_param", "detail": f"{field_name} must be greater than 0"}
        )
    if max_value is not None and parsed > max_value:
        raise ValidationError(
            {
                "code": "invalid_query_param",
                "detail": f"{field_name} exceeds maximum allowed value of {max_value}",
            }
        )
    return parsed


def _parse_execution_id_value(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        raise ValidationError(
            {"code": "invalid_query_param", "detail": f"Invalid execution_id: {value}"}
        )


class QueryParamsSerializer(serializers.Serializer):
    """Base serializer for sub-resource query validation."""

    def validate_datetime_field(self, field_name: str, value: str | None) -> datetime | None:
        return _parse_datetime_value(value)

    def validate_execution_id_field(self, value: str | None) -> UUID | None:
        return _parse_execution_id_value(value)

    def validate_positive_int_field(
        self,
        field_name: str,
        value: str | None,
        *,
        default: int,
        max_value: int | None = None,
    ) -> int:
        return _parse_positive_int(
            value, field_name=field_name, default=default, max_value=max_value
        )


class PaginationParamsSerializer(QueryParamsSerializer):
    """Serializer for page/page_size validation."""

    def parse(
        self,
        request: Request,
        *,
        default_page_size: int = 100,
        max_page_size: int = 1000,
    ) -> PaginationParams:
        return PaginationParams(
            page=self.validate_positive_int_field(
                "page", request.query_params.get("page"), default=1
            ),
            page_size=self.validate_positive_int_field(
                "page_size",
                request.query_params.get("page_size"),
                default=default_page_size,
                max_value=max_page_size,
            ),
        )


class ExecutionScopedQuerySerializer(QueryParamsSerializer):
    """Serializer for execution-scoped query params."""

    def parse(
        self,
        request: Request,
        *,
        default_execution_id: UUID | None,
        default_page_size: int = 100,
        max_page_size: int = 1000,
    ) -> ExecutionScopedQuery:
        return ExecutionScopedQuery(
            execution_id=self.validate_execution_id_field(request.query_params.get("execution_id"))
            or default_execution_id,
            since=self.validate_datetime_field("since", request.query_params.get("since")),
            pagination=PaginationParamsSerializer().parse(
                request,
                default_page_size=default_page_size,
                max_page_size=max_page_size,
            ),
        )


class DateRangeQuerySerializer(QueryParamsSerializer):
    """Serializer for datetime range validation."""

    def parse(
        self,
        request: Request,
        *,
        start_key: str,
        end_key: str,
    ) -> DateRangeQuery:
        start = self.validate_datetime_field(start_key, request.query_params.get(start_key))
        end = self.validate_datetime_field(end_key, request.query_params.get(end_key))
        if start and end and start > end:
            raise ValidationError(
                {
                    "code": "invalid_query_param",
                    "detail": f"{start_key} must be earlier than or equal to {end_key}",
                }
            )
        return DateRangeQuery(start=start, end=end)


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
        return PaginationParamsSerializer().parse(
            request,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
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
        return ExecutionScopedQuerySerializer().parse(
            request,
            default_execution_id=default_execution_id,
            default_page_size=default_page_size,
            max_page_size=max_page_size,
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
        return DateRangeQuerySerializer().parse(
            request,
            start_key=start_key,
            end_key=end_key,
        )


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
