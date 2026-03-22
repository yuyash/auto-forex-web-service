"""Shared query parameter objects for task sub-resource endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils.dateparse import parse_datetime
from rest_framework.request import Request


def _parse_datetime_value(value: str | None) -> datetime | None:
    if value:
        return parse_datetime(value)
    return None


def _parse_execution_id_value(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class PaginationParams:
    page: int
    page_size: int

    @classmethod
    def from_request(
        cls,
        request: Request,
        *,
        default_page_size: int = 1000,
        max_page_size: int = 5000,
    ) -> PaginationParams:
        page = 1
        page_size = default_page_size
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = max(
                1,
                min(int(request.query_params.get("page_size", default_page_size)), max_page_size),
            )
        except (TypeError, ValueError):
            page_size = default_page_size
        return cls(page=page, page_size=page_size)


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
        default_page_size: int = 1000,
        max_page_size: int = 5000,
    ) -> ExecutionScopedQuery:
        return cls(
            execution_id=_parse_execution_id_value(request.query_params.get("execution_id"))
            or default_execution_id,
            since=_parse_datetime_value(request.query_params.get("since")),
            pagination=PaginationParams.from_request(
                request,
                default_page_size=default_page_size,
                max_page_size=max_page_size,
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
        return cls(
            start=_parse_datetime_value(request.query_params.get(start_key)),
            end=_parse_datetime_value(request.query_params.get(end_key)),
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
    ) -> PositionQuery:
        return cls(
            execution=ExecutionScopedQuery.from_request(
                request,
                default_execution_id=default_execution_id,
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
