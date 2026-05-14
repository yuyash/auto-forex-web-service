"""Tests for task instrument context builder."""

from decimal import Decimal
from types import SimpleNamespace

from apps.trading.services.task_instrument_context import TASK_INSTRUMENT_CONTEXT


def test_task_instrument_context_uses_instrument_default_when_unset():
    task = SimpleNamespace(instrument="EUR_USD", pip_size=None)

    context = TASK_INSTRUMENT_CONTEXT.build(task).as_dict()

    assert context["instrument"] == "EUR_USD"
    assert context["effective_pip_size"] == "0.0001"
    assert context["pip_size_source"] == "instrument_default"
    assert context["pip_size_matches_instrument"] is True


def test_task_instrument_context_marks_overrides():
    task = SimpleNamespace(instrument="EUR_USD", pip_size=Decimal("0.02"))

    context = TASK_INSTRUMENT_CONTEXT.build(task).as_dict()

    assert context["configured_pip_size"] == "0.02"
    assert context["default_pip_size"] == "0.0001"
    assert context["effective_pip_size"] == "0.02"
    assert context["pip_size_source"] == "task_override"
    assert context["pip_size_matches_instrument"] is False
