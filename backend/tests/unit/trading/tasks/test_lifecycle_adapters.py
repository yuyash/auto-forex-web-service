"""Unit tests for lifecycle command adapters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

from apps.trading.enums import StopMode
from apps.trading.tasks.lifecycle_adapters import (
    _default_signal_pause,
    _default_signal_stop,
)
from apps.trading.tasks.lifecycle_coordination import (
    TASK_COORDINATION_STATUS_FIELD,
    TASK_COORDINATION_STOP_MODE_FIELD,
    TaskCoordinationStatus,
    build_task_coordination_key,
    build_task_execution_instance_key,
)


def test_default_signal_stop_writes_coordination_status_and_mode(settings) -> None:
    settings.MARKET_REDIS_URL = "redis://redis.example/0"
    task_id = uuid4()
    execution_id = uuid4()
    task_name = "trading.tasks.run_trading_task"
    redis_client = MagicMock()

    with patch("redis.Redis.from_url", return_value=redis_client) as from_url:
        _default_signal_stop(task_id, task_name, execution_id, StopMode.GRACEFUL_CLOSE)

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
        mapping={
            TASK_COORDINATION_STATUS_FIELD: TaskCoordinationStatus.STOPPING,
            TASK_COORDINATION_STOP_MODE_FIELD: StopMode.GRACEFUL_CLOSE.value,
        },
    )
    redis_client.expire.assert_called_once_with(expected_key, 3600)
    redis_client.close.assert_called_once_with()


def test_default_signal_pause_writes_coordination_status(settings) -> None:
    settings.MARKET_REDIS_URL = "redis://redis.example/0"
    task_id = uuid4()
    execution_id = uuid4()
    task_name = "trading.tasks.run_trading_task"
    redis_client = MagicMock()

    with patch("redis.Redis.from_url", return_value=redis_client) as from_url:
        _default_signal_pause(task_id, task_name, execution_id)

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
        TaskCoordinationStatus.PAUSING,
    )
    redis_client.expire.assert_called_once_with(expected_key, 3600)
    redis_client.close.assert_called_once_with()
