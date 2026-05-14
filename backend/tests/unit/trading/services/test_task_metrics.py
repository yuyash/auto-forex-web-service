"""Unit tests for task metrics query services."""

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.trading.services.task_metrics import (
    ensure_metrics_dict,
    filter_metrics,
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


def test_filter_metrics_keeps_money_companions_for_requested_metric():
    metrics = {
        "current_balance": "100",
        "current_balance_money": {"amount": "100", "currency": "USD"},
        "current_balance_display_money": {"amount": "15000", "currency": "JPY"},
        "current_balance_display_conversion_context": {"conversion_policy": "runtime_fx_rate"},
        "display_conversion_context": {"conversion_policy": "runtime_fx_rate"},
        "display_currency": "JPY",
        "margin_ratio": "0.1",
    }

    filtered = filter_metrics(metrics, ("current_balance",))

    assert filtered == {
        "current_balance": "100",
        "current_balance_money": {"amount": "100", "currency": "USD"},
        "current_balance_display_money": {"amount": "15000", "currency": "JPY"},
        "current_balance_display_conversion_context": {"conversion_policy": "runtime_fx_rate"},
        "display_conversion_context": {"conversion_policy": "runtime_fx_rate"},
        "display_currency": "JPY",
    }
