"""Unit tests for SnowballNet chart payload helpers."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.models.metrics import Metrics
from apps.trading.services.snowball_net_chart import (
    NetChartWindow,
    _current_state,
    _load_oscillator_lines,
    _load_price_lines,
    _margin_threshold_lines,
    _strategy_data_until,
    _window_from_request,
)


def _chart_request(query_string: str = "") -> Request:
    return Request(APIRequestFactory().get(f"/strategy/net-chart/{query_string}"))


def test_window_from_request_defaults_to_m1_following_day_each_side():
    center = "2026-01-15T12:00:00Z"

    window = _window_from_request(
        _chart_request(),
        last_tick_timestamp=center,
    )

    assert window.granularity == "M1"
    assert window.granularity_seconds == 60
    assert window.follow is True
    assert window.center == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert window.since == datetime(2026, 1, 14, 12, 0, tzinfo=UTC)
    assert window.until == datetime(2026, 1, 16, 12, 0, tzinfo=UTC)


def test_window_from_request_allows_m1_two_week_range():
    window = _window_from_request(
        _chart_request("?granularity=M1&since=2026-01-01T00:00:00Z&until=2026-01-15T00:00:00Z"),
        last_tick_timestamp=None,
    )

    assert window.granularity == "M1"
    assert window.since == datetime(2026, 1, 1, tzinfo=UTC)
    assert window.until == datetime(2026, 1, 15, tzinfo=UTC)


def test_window_from_request_rejects_m1_range_over_two_weeks():
    with pytest.raises(ValidationError):
        _window_from_request(
            _chart_request("?granularity=M1&since=2026-01-01T00:00:00Z&until=2026-01-16T00:00:00Z"),
            last_tick_timestamp=None,
        )


def test_strategy_data_until_stops_follow_lines_at_sequence_center():
    since = datetime(2026, 1, 1, 11, 0, tzinfo=UTC)
    center = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    until = datetime(2026, 1, 1, 13, 0, tzinfo=UTC)

    follow_window = NetChartWindow(
        granularity="M1",
        granularity_seconds=60,
        center=center,
        since=since,
        until=until,
        follow=True,
        merge_markers=True,
    )
    fixed_window = NetChartWindow(
        granularity="M1",
        granularity_seconds=60,
        center=center,
        since=since,
        until=until,
        follow=False,
        merge_markers=True,
    )

    assert _strategy_data_until(follow_window) == center
    assert _strategy_data_until(fixed_window) == until


@pytest.mark.django_db
def test_load_oscillator_lines_returns_net_units_series():
    task_id = uuid4()
    execution_id = uuid4()
    timestamp = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    Metrics.objects.create(
        task_type="backtest",
        task_id=task_id,
        execution_id=execution_id,
        timestamp=timestamp,
        metrics={
            "snowball_net_net_units": "2000",
            "snowball_net_pips_from_average": "12.5",
            "snowball_net_margin_ratio_pct": "34",
            "snowball_net_current_price": "150",
            "realized_pnl": "8",
            "realized_pnl_quote": "1200.5",
            "unrealized_pnl": "-2.135",
        },
    )

    task = SimpleNamespace(
        pk=task_id,
        instrument="USD_JPY",
        account_currency="USD",
        config=SimpleNamespace(config_dict={}),
    )

    lines = _load_oscillator_lines(
        task=task,
        task_type_label="backtest",
        execution_id=execution_id,
        since=timestamp - timedelta(minutes=1),
        until=timestamp + timedelta(minutes=1),
        granularity_seconds=60,
    )

    net_units_line = next(line for line in lines if line["id"] == "net_units")
    assert net_units_line["label_key"] == "snowballNet.chart.netUnits"
    assert net_units_line["points"] == [{"time": int(timestamp.timestamp()), "value": 2000.0}]
    realized_pnl_line = next(line for line in lines if line["id"] == "realized_pnl")
    unrealized_pnl_line = next(line for line in lines if line["id"] == "unrealized_pnl")
    assert realized_pnl_line["label_key"] == "snowballNet.chart.realizedPnl"
    assert realized_pnl_line["points"] == [{"time": int(timestamp.timestamp()), "value": 1200.5}]
    assert unrealized_pnl_line["label_key"] == "snowballNet.chart.unrealizedPnl"
    assert unrealized_pnl_line["points"] == [{"time": int(timestamp.timestamp()), "value": -320.25}]


def test_current_state_uses_quote_pnl_values_and_currency():
    task = SimpleNamespace(account_currency="USD")
    state = {
        "metrics": {
            "snowball_net_current_price": "150",
            "realized_pnl": "8",
            "realized_pnl_quote": "1200.5",
            "unrealized_pnl": "-2.135",
        }
    }

    current = _current_state(
        state,
        "2026-01-01T12:05:00Z",
        task=task,
        instrument="USD_JPY",
        pnl_currency="JPY",
        quote_currency="JPY",
    )

    assert current["realized_pnl"] == "1200.5"
    assert Decimal(current["unrealized_pnl"]) == Decimal("-320.25")
    assert current["pnl_currency"] == "JPY"


@pytest.mark.django_db
def test_load_price_lines_returns_directional_current_tick_price_series():
    task_id = uuid4()
    execution_id = uuid4()
    timestamp = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    Metrics.objects.create(
        task_type="backtest",
        task_id=task_id,
        execution_id=execution_id,
        timestamp=timestamp,
        metrics={
            "snowball_net_average_price": "156.100",
            "snowball_net_current_price": "156.075",
            "snowball_net_target_price": "156.300",
        },
    )

    task = SimpleNamespace(
        pk=task_id,
        config=SimpleNamespace(config_dict={}),
    )

    lines = _load_price_lines(
        task=task,
        task_type_label="backtest",
        execution_id=execution_id,
        since=timestamp - timedelta(minutes=1),
        until=timestamp + timedelta(minutes=1),
        granularity_seconds=60,
    )

    current_price_line = next(line for line in lines if line["id"] == "current_price")
    assert current_price_line["label_key"] == "snowballNet.chart.currentPrice"
    assert current_price_line["line_style"] == "dashed"
    assert current_price_line["points"] == [{"time": int(timestamp.timestamp()), "value": 156.075}]


@pytest.mark.django_db
def test_load_price_lines_labels_disabled_next_add_separately():
    task_id = uuid4()
    execution_id = uuid4()
    timestamp = datetime(2026, 1, 1, 12, 5, tzinfo=UTC)
    Metrics.objects.create(
        task_type="backtest",
        task_id=task_id,
        execution_id=execution_id,
        timestamp=timestamp,
        metrics={
            "snowball_net_net_units": "1000",
            "snowball_net_average_price": "156.100",
            "snowball_net_add_count": "0",
        },
    )

    task = SimpleNamespace(
        pk=task_id,
        instrument="USD_JPY",
        config=SimpleNamespace(config_dict={"max_add_count": 0}),
    )

    lines = _load_price_lines(
        task=task,
        task_type_label="backtest",
        execution_id=execution_id,
        since=timestamp - timedelta(minutes=1),
        until=timestamp + timedelta(minutes=1),
        granularity_seconds=60,
    )

    disabled_line = next(line for line in lines if line["id"] == "next_add_price_disabled")
    assert disabled_line["label_key"] == "snowballNet.chart.nextAddDisabled"


def test_margin_threshold_lines_include_emergency_and_reduce_when_enabled():
    since = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    until = since + timedelta(hours=1)
    task = SimpleNamespace(
        config=SimpleNamespace(
            config_dict={
                "margin_reduce_enabled": True,
                "margin_reduce_threshold_pct": "72",
                "margin_reduce_target_pct": "48",
                "emergency_enabled": True,
                "emergency_threshold_pct": "93",
            }
        )
    )

    lines = _margin_threshold_lines(task=task, since=since, until=until)
    by_id = {line["id"]: line for line in lines}

    assert set(by_id) == {
        "margin_reduce_threshold_pct",
        "margin_reduce_target_pct",
        "emergency_threshold_pct",
    }
    assert by_id["margin_reduce_threshold_pct"]["points"] == [
        {"time": int(since.timestamp()), "value": 72.0},
        {"time": int(until.timestamp()), "value": 72.0},
    ]
    assert by_id["margin_reduce_target_pct"]["points"] == [
        {"time": int(since.timestamp()), "value": 48.0},
        {"time": int(until.timestamp()), "value": 48.0},
    ]
    assert by_id["emergency_threshold_pct"]["points"] == [
        {"time": int(since.timestamp()), "value": 93.0},
        {"time": int(until.timestamp()), "value": 93.0},
    ]
