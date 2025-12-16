from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from apps.market.models import CeleryTaskStatus
from apps.market.signals import (
    _handle_market_task_cancel_requested,
    request_backtest_tick_stream,
    request_market_task_cancel,
)


class TestMarketSignalsUnit:
    def test_request_market_task_cancel_defaults_instance_key(self, monkeypatch) -> None:
        sent = {}

        def _fake_send(*_args, **kwargs):
            sent.update(kwargs)

        import apps.market.signals as signals_module

        monkeypatch.setattr(signals_module.market_task_cancel_requested, "send", _fake_send)

        request_market_task_cancel(task_name="t1")
        assert sent["task_name"] == "t1"
        assert sent["instance_key"] == "default"

    def test_request_backtest_tick_stream_returns_request_id(self, monkeypatch) -> None:
        sent = {}

        def _fake_send(*_args, **kwargs):
            sent.update(kwargs)

        import apps.market.signals as signals_module

        monkeypatch.setattr(signals_module.backtest_tick_stream_requested, "send", _fake_send)

        rid = request_backtest_tick_stream(
            instrument="EUR_USD",
            start=MagicMock(),
            end=MagicMock(),
        )
        assert isinstance(rid, str)
        assert sent["instrument"] == "EUR_USD"
        assert sent["request_id"] == rid


@pytest.mark.django_db
class TestMarketSignalsDB:
    def test_cancel_handler_sets_stop_requested(self) -> None:
        CeleryTaskStatus.objects.create(task_name="t2", instance_key="default")

        _handle_market_task_cancel_requested(
            _sender=object(),
            task_name="t2",
            instance_key="default",
            reason="please stop",
        )

        row = CeleryTaskStatus.objects.get(task_name="t2", instance_key="default")
        assert row.status == CeleryTaskStatus.Status.STOP_REQUESTED
        assert row.status_message == "please stop"
