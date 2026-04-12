"""Unit tests ensuring task mixin endpoints delegate to typed query objects."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.views.mixins import TaskSubResourceMixin

factory = APIRequestFactory()


class DummyTaskSubResourceView(TaskSubResourceMixin):
    task_type_label = "backtest"

    def __init__(self):
        self._task = SimpleNamespace(pk=1, execution_id="exec-1")

    def get_object(self):
        return self._task


def _request(path: str = "/api/tasks/1/") -> Request:
    return Request(factory.get(path))


def test_log_components_uses_log_components_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/log-components")

    with (
        patch("apps.trading.views.mixins.LogComponentsQueryParams.from_request") as from_request,
        patch("apps.trading.models.logs.TaskLog.objects.filter") as task_log_filter,
    ):
        from_request.return_value = SimpleNamespace(execution_id="exec-1")
        task_log_filter.return_value.values_list.return_value.distinct.return_value.order_by.return_value = [
            "executor",
            "strategy",
        ]

        response = view.log_components(request, pk=1)

    from_request.assert_called_once_with(request, default_execution_id="exec-1")
    assert response.data == {"components": ["executor", "strategy"]}


def test_strategy_events_uses_strategy_events_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/strategy-events")

    with (
        patch("apps.trading.views.mixins.StrategyEventsQueryParams.from_request") as from_request,
        patch("apps.trading.services.strategy_cycles.StrategyCyclesService.build") as build,
    ):
        from_request.return_value = SimpleNamespace(
            execution_id="exec-1",
        )
        build.return_value = {"cycles": [], "summary": {}}

        response = view.strategy_events(request, pk=1)

    from_request.assert_called_once_with(request, default_execution_id="exec-1")
    build.assert_called_once_with(
        task=view.get_object(),
        task_type="backtest",
        execution_id="exec-1",
        cycle_id=None,
    )
    assert response.data == {"cycles": [], "summary": {}}


def test_summary_uses_summary_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/summary")

    with (
        patch("dataclasses.asdict", return_value={"task": {"status": "created"}}),
        patch("apps.trading.views.mixins.SummaryQueryParams.from_request") as from_request,
        patch("apps.trading.services.summary.compute_cached_task_summary") as compute,
        patch("apps.trading.views.mixins.TaskSummarySerializer") as serializer_cls,
    ):
        from_request.return_value = SimpleNamespace(execution_id="exec-1")
        compute.return_value = SimpleNamespace()
        serializer_cls.return_value.data = {"task": {"status": "created"}}

        response = view.summary(request, pk=1)

    from_request.assert_called_once_with(request, default_execution_id="exec-1")
    assert response.data == {"task": {"status": "created"}}


def test_position_lifecycle_uses_position_lifecycle_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/position-lifecycle")

    with (
        patch(
            "apps.trading.views.mixins.PositionLifecycleQueryParams.from_request"
        ) as from_request,
        patch("apps.trading.services.position_lifecycle.PositionLifecycleService.build") as build,
    ):
        from_request.return_value = SimpleNamespace(
            execution_id="exec-1",
            position_id="abcd1234",
        )
        build.return_value = {
            "requested_position_id": "abcd1234",
            "matched_position_id": "abcd1234-abcd-abcd-abcd-abcdabcdabcd",
            "position_ids": [],
            "positions": [],
        }

        response = view.position_lifecycle(request, pk=1)

    from_request.assert_called_once_with(request, default_execution_id="exec-1")
    assert response.status_code == 200


def test_executions_uses_executions_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/executions")

    with (
        patch("apps.trading.views.mixins.ExecutionsQueryParams.from_request") as from_request,
        patch("apps.trading.services.executions.list_task_executions") as list_executions,
    ):
        from_request.return_value = SimpleNamespace(
            include_metrics=True,
            pagination=SimpleNamespace(page=2, page_size=25),
        )
        list_executions.return_value = (0, [])

        response = view.executions(request, pk=1)

    from_request.assert_called_once()
    assert response.status_code == 200


def test_execution_detail_uses_execution_detail_query_params():
    view = DummyTaskSubResourceView()
    request = _request("/api/tasks/1/executions/exec-1")

    with (
        patch("apps.trading.views.mixins.ExecutionDetailQueryParams.from_request") as from_request,
        patch("apps.trading.services.executions.get_task_execution") as get_execution,
    ):
        from_request.return_value = SimpleNamespace(include_metrics=True)
        get_execution.return_value = {
            "id": "exec-1",
            "task_type": "backtest",
            "task_id": "1",
            "execution_number": "exec-1",
            "status": "completed",
            "progress": 100,
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:05:00Z",
            "error_message": None,
            "error_traceback": None,
            "duration": 300,
            "created_at": "2026-01-01T00:00:00Z",
        }

        response = view.execution_detail(request, pk=1, execution_id="exec-1")

    from_request.assert_called_once_with(request)
    assert response.status_code == 200
