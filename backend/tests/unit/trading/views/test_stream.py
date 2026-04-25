"""Unit tests for task event stream views."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.http import Http404
from rest_framework.test import APIRequestFactory

from apps.trading.enums import TaskType
from apps.trading.views.stream import TaskEventStreamView


def test_normalize_task_type_rejects_unknown_values():
    with pytest.raises(Http404):
        TaskEventStreamView._normalize_task_type("<script>")


def test_get_uses_normalized_task_type_and_disables_sniffing():
    request = APIRequestFactory().get("/stream/")
    request.user = MagicMock(pk=1)
    task_id = uuid4()
    task_model = MagicMock()
    task_model.objects.filter.return_value.first.return_value = MagicMock()
    stream = iter(())

    with (
        patch.object(TaskEventStreamView, "_task_model", return_value=task_model) as task_model_for,
        patch.object(TaskEventStreamView, "_event_stream", return_value=stream) as event_stream,
    ):
        response = TaskEventStreamView().get(request, TaskType.BACKTEST.value, task_id)

    task_model_for.assert_called_once_with(TaskType.BACKTEST.value)
    event_stream.assert_called_once_with(
        request,
        task_model=task_model,
        task_id=task_id,
    )
    assert response["X-Content-Type-Options"] == "nosniff"


def test_event_stream_swallows_runtime_errors():
    request = APIRequestFactory().get("/stream/")
    request.user = MagicMock(pk=1)
    task_model = MagicMock()
    task_model.objects.filter.side_effect = RuntimeError("database unavailable")

    stream = TaskEventStreamView()._event_stream(
        request,
        task_model=task_model,
        task_id=uuid4(),
    )

    assert list(stream) == []
