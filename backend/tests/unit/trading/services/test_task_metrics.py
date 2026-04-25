"""Unit tests for task metrics query services."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.enums import TaskType
from apps.trading.models.metrics import ExecutionMetricAggregate, Metrics
from apps.trading.models.state import ExecutionState
from apps.trading.services.task_metrics import (
    TaskMetricsQueryService,
    ensure_metrics_dict,
    paginated_envelope,
)
from tests.integration.factories import BacktestTaskFactory


def _request(path: str) -> Request:
    return Request(APIRequestFactory().get(path))


def test_ensure_metrics_dict_handles_dict_json_string_and_invalid_values():
    assert ensure_metrics_dict({"balance": 1}) == {"balance": 1}
    assert ensure_metrics_dict('{"balance": 1}') == {"balance": 1}
    assert ensure_metrics_dict("not json") == {}
    assert ensure_metrics_dict(["not", "dict"]) == {}


def test_paginated_envelope_builds_navigation_links():
    request = _request("/tasks/1/metrics/?page=2&page_size=5")

    envelope = paginated_envelope(request, [{"t": 1}], total=11, page=2, page_size=5)

    assert envelope["count"] == 11
    assert "page=3" in envelope["next"]
    assert "page=1" in envelope["previous"]


@pytest.mark.django_db
def test_latest_metric_includes_metadata_and_latest_row():
    task = BacktestTaskFactory()
    execution_id = task.execution_id
    ExecutionState.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        current_balance=Decimal("10000"),
        ticks_processed=1,
        resume_cursor_timestamp=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
    )
    ExecutionMetricAggregate.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        continuity_warnings=[{"kind": "gap"}],
    )
    Metrics.objects.create(
        task_type=TaskType.BACKTEST,
        task_id=task.pk,
        execution_id=execution_id,
        timestamp=datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
        metrics={"balance": "10000"},
    )

    payload = TaskMetricsQueryService().latest_metric(
        request=_request("/tasks/1/latest-metrics/"),
        task=task,
        task_type_label=TaskType.BACKTEST,
    )

    assert payload["data_source"] == "db_latest"
    assert payload["consistency_warnings"] == [{"kind": "gap"}]
    assert payload["resume_cursor_timestamp"] == "2026-01-01T00:01:00+00:00"
    assert payload["result"]["metrics"] == {"balance": "10000"}
