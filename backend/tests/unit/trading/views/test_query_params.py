"""Unit tests for typed trading view query params."""

from __future__ import annotations

from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.views.pagination import (
    ActivityPagination,
    TradePositionPagination,
)
from apps.trading.views.query_params import (
    EventsQueryParams,
    ExecutionDetailQueryParams,
    ExecutionsQueryParams,
    ExecutionsQueryParamsSchemaSerializer,
    LogComponentsQueryParams,
    LogsQueryParams,
    OrdersQueryParams,
    PositionQuery,
    StrategyEventsQueryParams,
    SummaryQueryParams,
    SummaryQueryParamsSchemaSerializer,
    TradesQueryParams,
)

factory = APIRequestFactory()


def _request(query: str = "") -> Request:
    django_request = factory.get(f"/api/tasks/1/{query}")
    return Request(django_request)


def test_logs_query_params_splits_levels_components_and_range():
    execution_id = uuid4()
    request = _request(
        f"?execution_id={execution_id}&level=info,error&component=strategy,executor"
        "&message=started&message_match=partial"
        "&position_id=pos-1&timestamp_from=2026-01-01T00:00:00Z"
        "&timestamp_to=2026-01-01T01:00:00Z&ordering=component"
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
    assert query.message == "started"
    assert query.message_match == "partial"
    assert query.position_id == "pos-1"
    assert query.timestamp_range.start is not None
    assert query.timestamp_range.end is not None
    assert query.ordering == "component"


def test_logs_query_params_reject_invalid_message_regex():
    request = _request("?message=%5Binvalid&message_match=regex")

    with pytest.raises(ValidationError) as exc_info:
        LogsQueryParams.from_request(
            request,
            default_execution_id=None,
            default_page_size=ActivityPagination.page_size,
            max_page_size=ActivityPagination.max_page_size,
        )

    assert "Invalid message regex" in str(exc_info.value.detail)


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
    cycle_id = uuid4()
    request = _request(
        f"?direction=buy&cycle_id={cycle_id}&timestamp_from=2026-01-01T00:00:00Z"
        "&timestamp_to=2026-01-01T02:00:00Z"
    )

    query = TradesQueryParams.from_request(
        request,
        default_execution_id=None,
        default_page_size=TradePositionPagination.page_size,
        max_page_size=TradePositionPagination.max_page_size,
    )

    assert query.cycle_id == cycle_id
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


def test_position_query_parses_filters_and_overlap_range():
    cycle_id = uuid4()
    request = _request(
        f"?position_status=open&direction=long&include_trade_ids=true&cycle_id={cycle_id}"
        "&range_from=2026-01-01T00:00:00Z&range_to=2026-01-01T03:00:00Z"
    )

    query = PositionQuery.from_request(
        request,
        default_execution_id=None,
        default_page_size=TradePositionPagination.page_size,
        max_page_size=TradePositionPagination.max_page_size,
    )

    assert query.position_status == "open"
    assert query.direction == "long"
    assert query.include_trade_ids is True
    assert query.cycle_id == cycle_id
    assert query.range.start is not None
    assert query.range.end is not None


def test_strategy_events_query_params_uses_default_execution_id():
    default_execution_id = uuid4()
    cycle_id = uuid4()
    request = _request(
        f"?cycle_id={cycle_id}"
        "&cycle_page=3&cycle_page_size=75&cycle_sort=desc"
        "&cycle_status=active&position_id=abc123&trade_id=def456"
    )

    query = StrategyEventsQueryParams.from_request(
        request,
        default_execution_id=default_execution_id,
    )

    assert query.execution_id == default_execution_id
    assert query.cycle_id == cycle_id
    assert query.cycle_page == 3
    assert query.cycle_page_size == 75
    assert query.cycle_sort == "desc"
    assert query.cycle_status == "active"
    assert query.position_id == "abc123"
    assert query.trade_id == "def456"


def test_strategy_events_query_params_defaults_are_safe():
    default_execution_id = uuid4()
    query = StrategyEventsQueryParams.from_request(
        _request(),
        default_execution_id=default_execution_id,
    )

    assert query.execution_id == default_execution_id
    assert query.cycle_id is None
    assert query.cycle_page == 1
    assert query.cycle_page_size == 50
    assert query.cycle_sort == "asc"
    assert query.cycle_status == "all"
    assert query.position_id == ""
    assert query.trade_id == ""


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


def test_trades_query_params_reject_invalid_cycle_id():
    request = _request("?cycle_id=not-a-uuid")

    with pytest.raises(ValidationError) as exc_info:
        TradesQueryParams.from_request(
            request,
            default_execution_id=None,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )

    assert "Invalid cycle_id" in str(exc_info.value.detail)


def test_position_query_reject_invalid_cycle_id():
    request = _request("?cycle_id=not-a-uuid")

    with pytest.raises(ValidationError) as exc_info:
        PositionQuery.from_request(
            request,
            default_execution_id=None,
            default_page_size=TradePositionPagination.page_size,
            max_page_size=TradePositionPagination.max_page_size,
        )

    assert "Invalid cycle_id" in str(exc_info.value.detail)


@pytest.mark.parametrize(
    ("query_class", "kwargs", "query"),
    [
        (
            LogsQueryParams,
            {
                "default_execution_id": None,
                "default_page_size": ActivityPagination.page_size,
                "max_page_size": ActivityPagination.max_page_size,
            },
            "?timestamp_from=2026-01-02T00:00:00Z&timestamp_to=2026-01-01T00:00:00Z",
        ),
        (
            PositionQuery,
            {
                "default_execution_id": None,
                "default_page_size": TradePositionPagination.page_size,
                "max_page_size": TradePositionPagination.max_page_size,
            },
            "?range_from=2026-01-02T00:00:00Z&range_to=2026-01-01T00:00:00Z",
        ),
    ],
)
def test_query_params_reject_reversed_ranges(query_class, kwargs, query):
    with pytest.raises(ValidationError) as exc_info:
        query_class.from_request(_request(query), **kwargs)

    assert "must be earlier than or equal to" in str(exc_info.value.detail)
