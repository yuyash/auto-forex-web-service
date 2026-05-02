"""Unit tests for lifecycle command adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from apps.trading.tasks.lifecycle_adapters import (
    _default_signal_pause,
    _default_signal_stop,
)
from apps.trading.tasks.lifecycle_coordination import (
    TASK_COORDINATION_STATUS_FIELD,
    TaskCoordinationStatus,
    build_task_coordination_key,
    build_task_execution_instance_key,
)


@pytest.mark.parametrize(
    ("signal_func", "expected_status"),
    [
        (_default_signal_stop, TaskCoordinationStatus.STOPPING),
        (_default_signal_pause, TaskCoordinationStatus.PAUSING),
    ],
)
def test_default_signal_writes_coordination_status(
    signal_func,
    expected_status: str,
    settings,
) -> None:
    settings.MARKET_REDIS_URL = "redis://redis.example/0"
    task_id = uuid4()
    execution_id = uuid4()
    task_name = "trading.tasks.run_trading_task"
    redis_client = MagicMock()

    with patch("redis.Redis.from_url", return_value=redis_client) as from_url:
        signal_func(task_id, task_name, execution_id)

    expected_key = build_task_coordination_key(
        task_name=task_name,
        instance_key=build_task_execution_instance_key(
            task_id=task_id,
            execution_id=execution_id,
        ),
    )
    from_url.assert_called_once_with(settings.MARKET_REDIS_URL, decode_responses=True)
    redis_client.hset.assert_called_once_with(
        expected_key,
        TASK_COORDINATION_STATUS_FIELD,
        expected_status,
    )
    redis_client.expire.assert_called_once_with(expected_key, 3600)
    redis_client.close.assert_called_once_with()
