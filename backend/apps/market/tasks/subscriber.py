"""Subscriber task runner for persisting ticks to database."""

from __future__ import annotations

import json
import time
from datetime import datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.services.celery import CeleryTaskService
from apps.market.tasks.base import (
    acquire_lock,
    current_task_id,
    lock_value,
    parse_iso_datetime,
    redis_client,
)

logger: Logger = getLogger(name=__name__)


class TickSubscriberRunner:
    """Runner for tick subscriber task."""

    def __init__(self) -> None:
        """Initialize the subscriber runner."""
        self.task_service: CeleryTaskService | None = None
        self.buffer: list[TickData] = []
        self.buffer_max: int = 200
        self.flush_interval_seconds: int = 2

    @shared_task(bind=True, name="market.tasks.subscribe_ticks_to_db")
    def run(self) -> None:
        """Subscribe to Redis pub/sub and persist tick messages into TickData."""
        task_name = "market.tasks.subscribe_ticks_to_db"
        instance_key = "default"
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=1.0,
            heartbeat_interval_seconds=5.0,
        )
        self.task_service.start(
            celery_task_id=current_task_id(),
            worker=lock_value(),
            meta={"kind": "subscriber"},
        )

        redis_url = settings.MARKET_REDIS_URL
        channel = settings.MARKET_TICK_CHANNEL

        logger.info(
            "Starting tick subscriber task (channel=%s, redis=%s)",
            channel,
            redis_url,
        )

        client = redis_client()
        lock_key = getattr(
            settings, "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock"
        )

        if self.task_service.should_stop(force=True):
            self._cleanup_and_stop(client, lock_key, None, "Stop requested")
            return

        if not acquire_lock(client, lock_key, ttl_seconds=60):
            logger.warning("Tick subscriber already running (lock=%s)", lock_key)
            self._cleanup_and_stop(client, lock_key, None, "Already running")
            return

        self.buffer_max = int(getattr(settings, "MARKET_TICK_SUBSCRIBER_BATCH_SIZE", 200))
        self.flush_interval_seconds = int(
            getattr(settings, "MARKET_TICK_SUBSCRIBER_FLUSH_INTERVAL", 2)
        )

        # Start subscribing
        self._subscribe_and_persist(client, lock_key, channel)

    def _subscribe_and_persist(self, client: Any, lock_key: str, channel: str) -> None:
        """Subscribe to channel and persist ticks."""
        assert self.task_service is not None

        last_flush = time.monotonic()
        pubsub = None

        try:
            while True:
                if self.task_service.should_stop():
                    logger.info("Stopping tick subscriber due to stop request")
                    break

                try:
                    # Refresh lock TTL.
                    client.expire(lock_key, 60)

                    pubsub = client.pubsub(ignore_subscribe_messages=True)
                    pubsub.subscribe(channel)
                    logger.info("Subscribed to tick channel %s", channel)

                    for message in pubsub.listen():
                        if self.task_service.should_stop():
                            break

                        if not isinstance(message, dict):
                            continue
                        if message.get("type") != "message":
                            continue

                        data_raw = message.get("data")
                        if not data_raw:
                            continue

                        # Parse and buffer tick
                        tick = self._parse_tick_message(data_raw)
                        if tick:
                            self.buffer.append(tick)

                        # Flush buffer if needed
                        now = time.monotonic()
                        if len(self.buffer) >= self.buffer_max or (
                            self.buffer and now - last_flush >= self.flush_interval_seconds
                        ):
                            self._flush_buffer()
                            last_flush = now

                        # Keep lock alive.
                        if len(self.buffer) % 50 == 0:
                            client.expire(lock_key, 60)

                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.exception("Tick subscriber crashed; will retry in 5s: %s", exc)
                    self.task_service.heartbeat(status_message=f"error={str(exc)}", force=True)

                    # Flush any buffered ticks best-effort.
                    self._flush_buffer()

                    try:
                        if pubsub is not None:
                            pubsub.close()
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                    pubsub = None

                    time.sleep(5)

                if pubsub is not None:
                    try:
                        pubsub.close()
                    except Exception:  # pylint: disable=broad-exception-caught
                        pass
                    pubsub = None

        finally:
            self._cleanup_and_stop(client, lock_key, pubsub, "Stopped")

    def _parse_tick_message(self, data_raw: Any) -> TickData | None:
        """Parse tick message from Redis."""
        try:
            payload = json.loads(str(data_raw))
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Dropping invalid tick payload: %s", data_raw)
            return None

        try:
            instrument = str(payload.get("instrument") or "")
            if not instrument:
                return None
            timestamp = parse_iso_datetime(str(payload.get("timestamp")))
            bid = Decimal(str(payload.get("bid")))
            ask = Decimal(str(payload.get("ask")))
            mid = Decimal(str(payload.get("mid")))

            return TickData(
                instrument=instrument,
                timestamp=timestamp,
                bid=bid,
                ask=ask,
                mid=mid,
            )
        except Exception:  # pylint: disable=broad-exception-caught
            logger.warning("Dropping malformed tick fields: %s", payload)
            return None

    def _flush_buffer(self) -> None:
        """Flush tick buffer to database."""
        assert self.task_service is not None

        try:
            if self.buffer:
                unique_flush: dict[tuple[str, datetime], TickData] = {}
                for obj in self.buffer:
                    unique_flush[(str(obj.instrument), obj.timestamp)] = obj
                buffer_to_flush = list(unique_flush.values())

                TickData.objects.bulk_create(
                    buffer_to_flush,
                    batch_size=min(len(buffer_to_flush), self.buffer_max),
                    update_conflicts=True,
                    update_fields=["bid", "ask", "mid"],
                    unique_fields=["instrument", "timestamp"],
                )
                self.buffer.clear()

                self.task_service.heartbeat(
                    status_message="flushed",
                    meta_update={"last_flush": time.monotonic()},
                )
        except Exception:  # pylint: disable=broad-exception-caught
            pass

    def _cleanup_and_stop(self, client: Any, lock_key: str, pubsub: Any, message: str) -> None:
        """Cleanup resources and mark task as stopped."""
        # Flush any buffered ticks best-effort.
        self._flush_buffer()

        try:
            if pubsub is not None:
                pubsub.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        try:
            client.delete(lock_key)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        if self.task_service:
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.STOPPED,
                status_message=message,
            )


# Note: Singleton instance is created in __init__.py
