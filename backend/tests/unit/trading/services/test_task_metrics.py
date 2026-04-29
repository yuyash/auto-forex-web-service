"""Unit tests for task metrics query services."""

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.services.task_metrics import (
    ensure_metrics_dict,
    paginated_envelope,
)


def _request(path: str) -> Request:
    return Request(APIRequestFactory().get(path))


def test_ensure_metrics_dict_handles_dict_json_string_and_invalid_values():
    assert ensure_metrics_dict({"balance": 1}) == {"balance": 1}
    assert ensure_metrics_dict('{"balance": 1}') == {"balance": 1}
    assert ensure_metrics_dict("not json") == {}
    assert ensure_metrics_dict(["not", "dict"]) == {}


def test_paginated_envelope_builds_navigation_links():
    request = _request("/tasks/1/strategy/metrics/?page=2&page_size=5")

    envelope = paginated_envelope(request, [{"t": 1}], total=11, page=2, page_size=5)

    assert envelope["count"] == 11
    assert "page=3" in envelope["next"]
    assert "page=1" in envelope["previous"]
