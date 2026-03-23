"""Unit tests for typed trading view query params."""

from __future__ import annotations

from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.views.pagination import (
    ActivityPagination,
    MetricsPagination,
    TradePositionPagination,
)
from apps.trading.views.query_params import (
    EventsQueryParams,
    ExecutionDetailQueryParams,
    ExecutionsQueryParams,
    ExecutionsQueryParamsSchemaSerializer,
    LogComponentsQueryParams,
    LogsQueryParams,
    MetricsQueryParams,
    OrdersQueryParams,
    StrategyEventsQueryParams,
    SummaryQueryParams,
    SummaryQueryParamsSchemaSerializer,
    TradesQueryParams,
)

factory = APIRequestFactory()


def _request(query: str = "") -> Request:
    django_request = factory.get(f"/api/tasks/1/{query}")
    return Request(django_request)


def test_metrics_query_params_parses_execution_pagination_and_interval():
    execution_id = uuid4()
    request = _request(
        f"?execution_id={execution_id}&since=2026-01-01T00:00:00Z&until=2026-01-02T00:00:00Z"
        "&interval=15&page=2&page_size=25"
    )

    query = MetricsQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=MetricsPagination.page_size,
        max_page_size=MetricsPagination.max_page_size,
    )

    assert query.execution.execution_id == execution_id
    assert query.execution.pagination.page == 2
    assert query.execution.pagination.page_size == 25
    assert query.interval == 15
    assert query.until is not None


def test_logs_query_params_splits_levels_components_and_range():
    execution_id = uuid4()
    request = _request(
        f"?execution_id={execution_id}&level=info,error&component=strategy,executor"
        "&position_id=pos-1&timestamp_from=2026-01-01T00:00:00Z"
        "&timestamp_to=2026-01-01T01:00:00Z"
    )

    query = LogsQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=ActivityPagination.page_size,
        max_page_size=ActivityPagination.max_page_size,
    )

    assert query.execution.execution_id == execution_id
    assert query.levels == ["INFO", "ERROR"]
    assert query.components == ["strategy", "executor"]
    assert query.position_id == "pos-1"
    assert query.timestamp_range.start is not None
    assert query.timestamp_range.end is not None


def test_events_query_params_defaults_scope_to_all():
    request = _request("?event_type=state_change&severity=warning")

    query = EventsQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=ActivityPagination.page_size,
        max_page_size=ActivityPagination.max_page_size,
    )

    assert query.scope == "all"
    assert query.event_type == "state_change"
    assert query.severity == "warning"


def test_trades_query_params_parses_direction_and_timestamp_range():
    request = _request(
        "?direction=buy&timestamp_from=2026-01-01T00:00:00Z&timestamp_to=2026-01-01T02:00:00Z"
    )

    query = TradesQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=TradePositionPagination.page_size,
        max_page_size=TradePositionPagination.max_page_size,
    )

    assert query.direction == "buy"
    assert query.timestamp_range.start is not None
    assert query.timestamp_range.end is not None


def test_orders_query_params_parses_filters():
    request = _request("?status=filled&order_type=market&direction=buy")

    query = OrdersQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=TradePositionPagination.page_size,
        max_page_size=TradePositionPagination.max_page_size,
    )

    assert query.status == "filled"
    assert query.order_type == "market"
    assert query.direction == "buy"


def test_strategy_events_query_params_uses_default_execution_id():
    default_execution_id = uuid4()
    request = _request("?root_entry_id=42")

    query = StrategyEventsQueryParams.from_request(
        request,
        default_execution_id=default_execution_id,
    )

    assert query.execution_id == default_execution_id
    assert query.root_entry_id == 42


def test_log_components_query_params_uses_default_execution_id():
    default_execution_id = uuid4()

    query = LogComponentsQueryParams.from_request(
        _request(),
        default_execution_id=default_execution_id,
    )

    assert query.execution_id == default_execution_id


def test_summary_query_params_parses_execution_id():
    execution_id = uuid4()
    request = _request(f"?execution_id={execution_id}")

    query = SummaryQueryParams.from_request(
        request,
        default_execution_id=None,
    )

    assert query.execution_id == execution_id


def test_executions_query_params_parses_include_metrics_and_pagination():
    request = _request("?include_metrics=true&page=3&page_size=50")

    query = ExecutionsQueryParams.from_request(
        request,
        default_page_size=ActivityPagination.page_size,
        max_page_size=ActivityPagination.max_page_size,
    )

    assert query.include_metrics is True
    assert query.pagination.page == 3
    assert query.pagination.page_size == 50


def test_execution_detail_query_params_defaults_metrics_false():
    query = ExecutionDetailQueryParams.from_request(_request())

    assert query.include_metrics is False


def test_summary_schema_serializer_exposes_execution_id_field_metadata():
    serializer = SummaryQueryParamsSchemaSerializer()

    field = serializer.fields["execution_id"]

    assert field.help_text == "Filter by execution ID (UUID)."
    assert field.required is False


def test_executions_schema_serializer_exposes_page_size_constraints():
    serializer = ExecutionsQueryParamsSchemaSerializer()

    field = serializer.fields["page_size"]

    assert field.help_text == "Results per page. Default 100, maximum 1000."
    assert field.max_value == 1000


def test_trades_query_params_rejects_invalid_page_size():
    request = _request("?page_size=999999")

    with pytest.raises(ValidationError) as exc_info:
        TradesQueryParams.from_request(
            request,
            default_execution_id=None,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )

    assert "maximum allowed value" in str(exc_info.value.detail)
