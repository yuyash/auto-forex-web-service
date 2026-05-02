"""Default side-effect adapters for lifecycle commands."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from apps.trading.enums import StopMode


@dataclass(frozen=True)
class LifecycleCommandAdapters:
    """External side effects used by lifecycle commands."""

    inspect_workers: Callable[[], dict[str, object] | None]
    signal_stop: Callable[[UUID, str, object], None]
    signal_pause: Callable[[UUID, str, object], None]
    revoke_execution: Callable[[object], None]
    dispatch_stop: Callable[[UUID, bool, StopMode], None]
    sleep: Callable[[float], None]


def create_default_lifecycle_adapters() -> LifecycleCommandAdapters:
    """Build production lifecycle command adapters."""

    return LifecycleCommandAdapters(
        inspect_workers=_default_inspect_workers,
        signal_stop=_default_signal_stop,
        signal_pause=_default_signal_pause,
        revoke_execution=_default_revoke_execution,
        dispatch_stop=_default_dispatch_stop,
        sleep=time.sleep,
    )


def _default_inspect_workers() -> dict[str, object] | None:
    from celery import current_app

    return current_app.control.inspect(timeout=3.0).active()


def _default_signal_stop(task_id: UUID, task_name: str, execution_id: object) -> None:
    import redis
    from django.conf import settings

    redis_client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
    redis_instance_key = f"{task_id}:{execution_id}"
    redis_key = f"task:coord:{task_name}:{redis_instance_key}"
    redis_client.hset(redis_key, "status", "stopping")
    redis_client.expire(redis_key, 3600)
    redis_client.close()


def _default_signal_pause(task_id: UUID, task_name: str, execution_id: object) -> None:
    import redis
    from django.conf import settings

    redis_client = redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)
    redis_instance_key = f"{task_id}:{execution_id}"
    redis_key = f"task:coord:{task_name}:{redis_instance_key}"
    redis_client.hset(redis_key, "status", "pausing")
    redis_client.expire(redis_key, 3600)
    redis_client.close()


def _default_revoke_execution(celery_task_id: object) -> None:
    from celery import current_app

    current_app.control.revoke(str(celery_task_id), terminate=True, signal="SIGKILL")


def _default_dispatch_stop(task_id: UUID, is_backtest: bool, stop_mode: StopMode) -> None:
    from apps.trading.tasks import service as service_module

    if is_backtest:
        service_module.stop_backtest_task.apply_async(
            args=[task_id, stop_mode.value],
            queue="system",
        )
    else:
        service_module.stop_trading_task.apply_async(
            args=[task_id, stop_mode.value],
            queue="system",
        )
