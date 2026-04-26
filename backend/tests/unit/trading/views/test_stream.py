"""Unit tests for task event stream views."""

import asyncio
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.http import Http404
from rest_framework.test import APIRequestFactory

from apps.trading.enums import TaskStatus, TaskType
from apps.trading.views.stream import TaskEventStreamView


async def _collect_async_stream(stream):
    return [item async for item in stream]


def test_normalize_task_type_rejects_unknown_values():
    with pytest.raises(Http404):
        TaskEventStreamView._normalize_task_type("<script>")


def test_get_uses_normalized_task_type_and_disables_sniffing():
    request = APIRequestFactory().get("/stream/")
    request.user = MagicMock(pk=1)
    task_id = uuid4()
    task_model = MagicMock()
    task_model.objects.filter.return_value.first.return_value = MagicMock()

    async def stream():
        if False:
            yield ""

    with (
        patch.object(TaskEventStreamView, "_task_model", return_value=task_model) as task_model_for,
        patch.object(TaskEventStreamView, "_event_stream", return_value=stream()) as event_stream,
    ):
        response = TaskEventStreamView().get(request, TaskType.BACKTEST.value, task_id)

    task_model_for.assert_called_once_with(TaskType.BACKTEST.value)
    event_stream.assert_called_once_with(
        task_type=TaskType.BACKTEST.value,
        task_model=task_model,
        task_id=task_id,
        user_id=request.user.pk,
    )
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response.is_async


def test_event_stream_swallows_runtime_errors():
    task_model = MagicMock()

    with patch.object(
        TaskEventStreamView,
        "_fetch_snapshot",
        side_effect=RuntimeError("database unavailable"),
    ):
        stream = TaskEventStreamView()._event_stream(
            task_type=TaskType.BACKTEST.value,
            task_model=task_model,
            task_id=uuid4(),
            user_id=1,
        )

        assert asyncio.run(_collect_async_stream(stream)) == []


def test_event_stream_closes_after_terminal_snapshot():
    task_model = MagicMock()
    task_id = uuid4()
    snapshot = {
        "id": str(task_id),
        "task_type": TaskType.BACKTEST.value,
        "status": TaskStatus.COMPLETED,
        "progress": 100,
        "execution_id": None,
        "started_at": None,
        "completed_at": None,
        "error_message": None,
        "updated_at": None,
    }

    with patch.object(TaskEventStreamView, "_fetch_snapshot", return_value=snapshot) as fetch:
        stream = TaskEventStreamView()._event_stream(
            task_type=TaskType.BACKTEST.value,
            task_model=task_model,
            task_id=task_id,
            user_id=1,
        )

        events = asyncio.run(_collect_async_stream(stream))

    assert len(events) == 1
    assert "event: snapshot" in events[0]
    fetch.assert_called_once()
