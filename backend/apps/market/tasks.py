from __future__ import annotations

import contextlib
import json
import os
import socket
import time
from datetime import UTC, datetime
from decimal import Decimal
from logging import Logger, getLogger
from typing import Any, cast

import redis
from celery import current_task, shared_task
from django.conf import settings

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts, TickData
from apps.market.services.celery import CeleryTaskService
from apps.market.services.oanda import OandaService

logger: Logger = getLogger(name=__name__)


def _current_task_id() -> str | None:
    try:
        return str(getattr(getattr(current_task, "request", None), "id", None) or "") or None
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)


def _isoformat(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_iso_datetime(value: str) -> datetime:
    value_str = str(value)
    if value_str.endswith("Z"):
        value_str = value_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(value_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _backtest_channel_for_request(request_id: str) -> str:
    prefix = getattr(settings, "MARKET_BACKTEST_TICK_CHANNEL_PREFIX", "market:backtest:ticks:")
    return f"{prefix}{request_id}"


def _lock_value() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"


def _acquire_lock(client: redis.Redis, key: str, ttl_seconds: int) -> bool:
    # Best-effort single-run guard for long-running tasks.
    return bool(client.set(key, _lock_value(), nx=True, ex=ttl_seconds))


@shared_task(name="market.tasks.ensure_tick_pubsub_running")
def ensure_tick_pubsub_running() -> None:
    """Supervisor task.

    Ensures there is exactly one active publisher/subscriber pair. If either side
    isn't running (lock missing), re-creates the task.

    This task re-schedules itself periodically and is also triggered on:
    - worker startup
    - first LIVE OANDA account creation
    """

    task_name = "market.tasks.ensure_tick_pubsub_running"
    instance_key = "supervisor"
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=5.0,
        heartbeat_interval_seconds=10.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"kind": "supervisor"},
    )

    if task_service.should_stop(force=True):
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Stop requested",
        )
        return

    client = _redis_client()

    interval_seconds = int(getattr(settings, "MARKET_TICK_SUPERVISOR_INTERVAL", 30))
    supervisor_lock = getattr(
        settings, "MARKET_TICK_SUPERVISOR_LOCK_KEY", "market:tick_supervisor:lock"
    )
    if not _acquire_lock(client, supervisor_lock, ttl_seconds=interval_seconds + 30):
        return

    stop_requested = False
    try:
        task_service.heartbeat(status_message="running", force=True)

        account_key = getattr(settings, "MARKET_TICK_ACCOUNT_KEY", "market:tick_pubsub:account")
        init_key = getattr(settings, "MARKET_TICK_PUBSUB_INIT_KEY", "market:tick_pubsub:init")

        account_id_raw = client.get(account_key)
        account: OandaAccounts | None = None
        if account_id_raw:
            try:
                account_id = int(str(account_id_raw))
                account = OandaAccounts.objects.filter(id=account_id).first()
            except Exception:  # pylint: disable=broad-exception-caught
                account = None

        if account is None:
            account = (
                OandaAccounts.objects.filter(api_type=ApiType.LIVE).order_by("created_at").first()
            )
            if account is None:
                return

            account_pk = int(account.pk)

            # Persist the "first live" account id exactly once.
            client.setnx(account_key, str(account_pk))
            client.setnx(init_key, "1")

        account_pk = int(account.pk)

        if account.api_type != ApiType.LIVE:
            # If the stored account was changed to non-live, do nothing.
            return

        publisher_lock = getattr(
            settings, "MARKET_TICK_PUBLISHER_LOCK_KEY", "market:tick_publisher:lock"
        )
        subscriber_lock = getattr(
            settings, "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock"
        )

        if not client.exists(publisher_lock):
            logger.info(
                "Registering publisher celery task (account_id=%s)",
                account_pk,
            )
            cast(Any, publish_oanda_ticks.delay)(account_id=account_pk)

        if not client.exists(subscriber_lock):
            logger.info("Creating subscriber celery task")
            cast(Any, subscribe_ticks_to_db.delay)()

    finally:
        with contextlib.suppress(Exception):
            client.close()

        stop_requested = task_service.should_stop(force=True)

    if stop_requested:
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Stop requested",
        )
        return

    # Self-schedule: keeps pub/sub alive even if tasks crash.
    cast(Any, ensure_tick_pubsub_running.apply_async)(countdown=interval_seconds)


@shared_task(name="market.tasks.publish_oanda_ticks")
def publish_oanda_ticks(*, account_id: int, instruments: list[str] | None = None) -> None:
    """Stream live pricing ticks from OANDA and publish to Redis pub/sub."""

    task_name = "market.tasks.publish_oanda_ticks"
    instance_key = str(account_id)
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=1.0,
        heartbeat_interval_seconds=5.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"account_id": account_id},
    )

    redis_url = settings.MARKET_REDIS_URL
    channel = settings.MARKET_TICK_CHANNEL

    logger.info(
        "Starting OANDA tick publisher task (account_id=%s, channel=%s, redis=%s)",
        account_id,
        channel,
        redis_url,
    )

    client = _redis_client()
    lock_key = getattr(settings, "MARKET_TICK_PUBLISHER_LOCK_KEY", "market:tick_publisher:lock")

    if task_service.should_stop(force=True):
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Stop requested",
        )
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return

    if not _acquire_lock(client, lock_key, ttl_seconds=60):
        logger.warning("Tick publisher already running (lock=%s)", lock_key)
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Already running",
        )
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return

    account = OandaAccounts.objects.filter(id=account_id).first()
    if account is None:
        logger.error("Tick publisher cannot start: account %s not found", account_id)
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED,
            status_message="Account not found",
        )
        try:
            client.delete(lock_key)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return
    if account.api_type != ApiType.LIVE:
        logger.warning(
            "Tick publisher refusing to start for non-live account (account_id=%s, api_type=%s)",
            account_id,
            account.api_type,
        )
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Non-live account",
        )
        try:
            client.delete(lock_key)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return

    instruments_list = instruments or getattr(settings, "MARKET_TICK_INSTRUMENTS", ["EUR_USD"])

    ticks_published = 0
    try:
        while True:
            if task_service.should_stop():
                logger.info(
                    "Stopping tick publisher due to stop request (account_id=%s)", account_id
                )
                break

            try:
                # Refresh lock TTL periodically (best-effort).
                client.expire(lock_key, 60)

                service = OandaService(account)
                for tick in service.stream_pricing_ticks(instruments_list, snapshot=True):
                    if task_service.should_stop():
                        break

                    payload = {
                        "instrument": str(tick.instrument),
                        "timestamp": _isoformat(tick.timestamp),
                        "bid": str(tick.bid),
                        "ask": str(tick.ask),
                        "mid": str(tick.mid),
                    }
                    client.publish(channel, json.dumps(payload))
                    ticks_published += 1

                    if ticks_published % 1000 == 0:
                        logger.info(
                            "Published %s ticks (account_id=%s, channel=%s)",
                            ticks_published,
                            account_id,
                            channel,
                        )

                    if ticks_published % 250 == 0:
                        task_service.heartbeat(
                            status_message=f"published={ticks_published}",
                            meta_update={"published": ticks_published},
                        )
                        client.expire(lock_key, 60)

            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.exception("Tick publisher crashed; will retry in 5s: %s", exc)
                task_service.heartbeat(status_message=f"error={str(exc)}", force=True)
                time.sleep(5)

    finally:
        try:
            client.delete(lock_key)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message=f"published={ticks_published}",
        )


@shared_task(name="market.tasks.subscribe_ticks_to_db")
def subscribe_ticks_to_db() -> None:
    """Subscribe to Redis pub/sub and persist tick messages into TickData."""

    task_name = "market.tasks.subscribe_ticks_to_db"
    instance_key = "default"
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=1.0,
        heartbeat_interval_seconds=5.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"kind": "subscriber"},
    )

    redis_url = settings.MARKET_REDIS_URL
    channel = settings.MARKET_TICK_CHANNEL

    logger.info(
        "Starting tick subscriber task (channel=%s, redis=%s)",
        channel,
        redis_url,
    )

    client = _redis_client()
    lock_key = getattr(settings, "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock")

    if task_service.should_stop(force=True):
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Stop requested",
        )
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return

    if not _acquire_lock(client, lock_key, ttl_seconds=60):
        logger.warning("Tick subscriber already running (lock=%s)", lock_key)
        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Already running",
        )
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        return

    buffer: list[TickData] = []
    buffer_max = int(getattr(settings, "MARKET_TICK_SUBSCRIBER_BATCH_SIZE", 200))
    flush_interval_seconds = int(getattr(settings, "MARKET_TICK_SUBSCRIBER_FLUSH_INTERVAL", 2))
    last_flush = time.monotonic()

    pubsub = None
    try:
        while True:
            if task_service.should_stop():
                logger.info("Stopping tick subscriber due to stop request")
                break

            try:
                # Refresh lock TTL.
                client.expire(lock_key, 60)

                pubsub = client.pubsub(ignore_subscribe_messages=True)
                pubsub.subscribe(channel)
                logger.info("Subscribed to tick channel %s", channel)

                for message in pubsub.listen():
                    if task_service.should_stop():
                        break

                    if not isinstance(message, dict):
                        continue
                    if message.get("type") != "message":
                        continue

                    data_raw = message.get("data")
                    if not data_raw:
                        continue

                    try:
                        payload = json.loads(str(data_raw))
                    except Exception:  # pylint: disable=broad-exception-caught
                        logger.warning("Dropping invalid tick payload: %s", data_raw)
                        continue

                    try:
                        instrument = str(payload.get("instrument") or "")
                        if not instrument:
                            continue
                        timestamp = _parse_iso_datetime(str(payload.get("timestamp")))
                        bid = Decimal(str(payload.get("bid")))
                        ask = Decimal(str(payload.get("ask")))
                        mid = Decimal(str(payload.get("mid")))
                    except Exception:  # pylint: disable=broad-exception-caught
                        logger.warning("Dropping malformed tick fields: %s", payload)
                        continue

                    buffer.append(
                        TickData(
                            instrument=instrument,
                            timestamp=timestamp,
                            bid=bid,
                            ask=ask,
                            mid=mid,
                        )
                    )

                    now = time.monotonic()
                    if len(buffer) >= buffer_max or (
                        buffer and now - last_flush >= flush_interval_seconds
                    ):
                        unique_flush: dict[tuple[str, datetime], TickData] = {}
                        for obj in buffer:
                            unique_flush[(str(obj.instrument), obj.timestamp)] = obj
                        buffer_to_flush = list(unique_flush.values())

                        TickData.objects.bulk_create(
                            buffer_to_flush,
                            batch_size=min(len(buffer_to_flush), buffer_max),
                            update_conflicts=True,
                            update_fields=["bid", "ask", "mid"],
                            unique_fields=["instrument", "timestamp"],
                        )
                        buffer.clear()
                        last_flush = now

                        task_service.heartbeat(
                            status_message="flushed",
                            meta_update={"last_flush": last_flush},
                        )

                    # Keep lock alive.
                    if len(buffer) % 50 == 0:
                        client.expire(lock_key, 60)

                    # Throttled (DB-backed) heartbeat/stop checks handled by task_service.

            except Exception as exc:  # pylint: disable=broad-exception-caught
                logger.exception("Tick subscriber crashed; will retry in 5s: %s", exc)
                task_service.heartbeat(status_message=f"error={str(exc)}", force=True)

                # Flush any buffered ticks best-effort.
                try:
                    if buffer:
                        unique_flush_retry: dict[tuple[str, datetime], TickData] = {}
                        for obj in buffer:
                            unique_flush_retry[(str(obj.instrument), obj.timestamp)] = obj
                        buffer_to_flush = list(unique_flush_retry.values())

                        TickData.objects.bulk_create(
                            buffer_to_flush,
                            batch_size=min(len(buffer_to_flush), buffer_max),
                            update_conflicts=True,
                            update_fields=["bid", "ask", "mid"],
                            unique_fields=["instrument", "timestamp"],
                        )
                        buffer.clear()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass

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
        # Flush any buffered ticks best-effort.
        try:
            if buffer:
                unique_flush_final: dict[tuple[str, datetime], TickData] = {}
                for obj in buffer:
                    unique_flush_final[(str(obj.instrument), obj.timestamp)] = obj
                buffer_to_flush = list(unique_flush_final.values())

                TickData.objects.bulk_create(
                    buffer_to_flush,
                    batch_size=min(len(buffer_to_flush), buffer_max),
                    update_conflicts=True,
                    update_fields=["bid", "ask", "mid"],
                    unique_fields=["instrument", "timestamp"],
                )
                buffer.clear()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

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

        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.STOPPED,
            status_message="Stopped",
        )


@shared_task(name="market.tasks.publish_ticks_for_backtest")
def publish_ticks_for_backtest(*, instrument: str, start: str, end: str, request_id: str) -> None:
    """Publish historical ticks from DB to Redis for a backtest run.

    Each signal creates a new Celery task. This task streams TickData rows in
    bounded chunks (doesn't load all ticks at once), publishes each tick to a
    dedicated per-request Redis channel, emits an EOF marker, then exits.
    """

    task_name = "market.tasks.publish_ticks_for_backtest"
    instance_key = str(request_id)
    task_service = CeleryTaskService(
        task_name=task_name,
        instance_key=instance_key,
        stop_check_interval_seconds=1.0,
        heartbeat_interval_seconds=5.0,
    )
    task_service.start(
        celery_task_id=_current_task_id(),
        worker=_lock_value(),
        meta={"instrument": str(instrument), "start": str(start), "end": str(end)},
    )

    channel = _backtest_channel_for_request(str(request_id))
    batch_size = int(getattr(settings, "MARKET_BACKTEST_PUBLISH_BATCH_SIZE", 1000))

    start_dt = _parse_iso_datetime(start)
    end_dt = _parse_iso_datetime(end)

    logger.info(
        "Starting backtest tick publisher (instrument=%s, request_id=%s, channel=%s, batch_size=%s)",
        instrument,
        request_id,
        channel,
        batch_size,
    )

    client = _redis_client()
    published = 0

    try:
        qs = (
            TickData.objects.filter(
                instrument=str(instrument),
                timestamp__gte=start_dt,
                timestamp__lte=end_dt,
            )
            .order_by("timestamp")
            .values("timestamp", "bid", "ask", "mid")
        )

        # iterator(chunk_size=...) fetches DB rows in bounded chunks.
        for row in qs.iterator(chunk_size=batch_size):
            if task_service.should_stop():
                client.publish(
                    channel,
                    json.dumps(
                        {
                            "type": "stopped",
                            "request_id": str(request_id),
                            "instrument": str(instrument),
                            "count": published,
                        }
                    ),
                )
                task_service.mark_stopped(
                    status=CeleryTaskStatus.Status.STOPPED,
                    status_message=f"published={published}",
                )
                return

            ts = row.get("timestamp")
            if not isinstance(ts, datetime):
                continue

            client.publish(
                channel,
                json.dumps(
                    {
                        "type": "tick",
                        "request_id": str(request_id),
                        "instrument": str(instrument),
                        "timestamp": _isoformat(ts),
                        "bid": str(row.get("bid")),
                        "ask": str(row.get("ask")),
                        "mid": str(row.get("mid")),
                    }
                ),
            )
            published += 1

            if published % max(batch_size, 1) == 0:
                logger.info(
                    "Published %s backtest ticks so far (instrument=%s, request_id=%s)",
                    published,
                    instrument,
                    request_id,
                )
                task_service.heartbeat(
                    status_message=f"published={published}",
                    meta_update={"published": published},
                )

        client.publish(
            channel,
            json.dumps(
                {
                    "type": "eof",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "start": str(start),
                    "end": str(end),
                    "count": published,
                }
            ),
        )

        logger.info(
            "Finished backtest tick publish (instrument=%s, request_id=%s, published=%s)",
            instrument,
            request_id,
            published,
        )

        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.COMPLETED,
            status_message=f"published={published}",
        )

    except Exception as exc:  # pylint: disable=broad-exception-caught
        logger.exception(
            "Backtest tick publisher failed (instrument=%s, request_id=%s): %s",
            instrument,
            request_id,
            exc,
        )
        try:
            client.publish(
                channel,
                json.dumps(
                    {
                        "type": "error",
                        "request_id": str(request_id),
                        "instrument": str(instrument),
                        "message": str(exc),
                    }
                ),
            )
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        task_service.mark_stopped(
            status=CeleryTaskStatus.Status.FAILED,
            status_message=str(exc),
        )
        raise

    finally:
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass
