"""Unit tests for the drain_trading_for_deploy management command."""

from __future__ import annotations

from io import StringIO
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


def _make_task(*, status: str = "running") -> MagicMock:
    task = MagicMock()
    task.pk = uuid4()
    task.name = "Live task"
    task.status = status
    task.config.strategy_type = "snowball"
    task.oanda_account.account_id = "001"
    return task


@patch("apps.trading.management.commands.drain_trading_for_deploy.TaskService")
@patch("apps.trading.management.commands.drain_trading_for_deploy.TradingTask")
def test_drain_trading_for_deploy_stops_and_waits(mock_task_model, mock_service_cls):
    task = _make_task()
    mock_qs = mock_task_model.objects.select_related.return_value.filter.return_value
    mock_qs.order_by.side_effect = [[task], []]

    out = StringIO()
    call_command("drain_trading_for_deploy", stdout=out)

    mock_service_cls.return_value.stop_task.assert_called_once_with(task.pk, mode="graceful")
    output = out.getvalue()
    assert "Draining 1 active trading task" in output
    assert "All active trading tasks drained." in output


@patch("apps.trading.management.commands.drain_trading_for_deploy.time.sleep", return_value=None)
@patch("apps.trading.management.commands.drain_trading_for_deploy.TaskService")
@patch("apps.trading.management.commands.drain_trading_for_deploy.TradingTask")
def test_drain_trading_for_deploy_raises_on_timeout(
    mock_task_model,
    _mock_service_cls,
    _mock_sleep,
):
    task = _make_task(status="stopping")
    mock_qs = mock_task_model.objects.select_related.return_value.filter.return_value
    mock_qs.order_by.return_value = [task]

    with pytest.raises(CommandError, match="Timed out draining active trading tasks"):
        call_command("drain_trading_for_deploy", timeout=1, poll_interval=0.1)
