from __future__ import annotations

from datetime import UTC, datetime
from logging import Logger, getLogger
from uuid import uuid4

import redis
from celery import current_app
from django.conf import settings
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import Signal, receiver
from django.utils.timezone import now as django_now

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts

logger: Logger = getLogger(name=__name__)


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.MARKET_REDIS_URL, decode_responses=True)


# =============================================================================
# Backtest tick stream signal
# =============================================================================

# Sent when a backtest needs a historical tick stream.
# Payload:
# - instrument: str
# - start: datetime
# - end: datetime
# - request_id: str (used to build a dedicated Redis pub/sub channel)
backtest_tick_stream_requested: Signal = Signal()


# Sent when some external owner (trading/backtest/etc) wants a market-managed
# Celery task to stop cleanly.
# Payload:
# - task_name: str
# - instance_key: str | None
# - reason: str | None
market_task_cancel_requested: Signal = Signal()


def request_market_task_cancel(
    *,
    task_name: str,
    instance_key: str | None = None,
    reason: str | None = None,
) -> None:
    key = instance_key or "default"
    market_task_cancel_requested.send(
        sender=request_market_task_cancel,
        task_name=task_name,
        instance_key=key,
        reason=reason,
    )


def request_backtest_tick_stream(
    *,
    instrument: str,
    start: datetime,
    end: datetime,
    request_id: str | None = None,
) -> str:
    """Emit a backtest tick stream request signal.

    Returns the request_id used for the stream.
    """

    rid = request_id or uuid4().hex
    backtest_tick_stream_requested.send(
        sender=request_backtest_tick_stream,
        instrument=instrument,
        start=start,
        end=end,
        request_id=rid,
    )
    return rid


def _ensure_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


@receiver(backtest_tick_stream_requested)
def _enqueue_backtest_tick_publisher(
    _sender: object,
    *,
    instrument: str,
    start: datetime,
    end: datetime,
    request_id: str,
    **_kwargs: object,
) -> None:
    start_utc = _ensure_aware_utc(start)
    end_utc = _ensure_aware_utc(end)

    if end_utc < start_utc:
        logger.warning(
            "Ignoring backtest tick stream request with end < start (instrument=%s, request_id=%s)",
            instrument,
            request_id,
        )
        return

    logger.info(
        "Enqueuing backtest tick publisher (instrument=%s, request_id=%s, start=%s, end=%s)",
        instrument,
        request_id,
        start_utc.isoformat(),
        end_utc.isoformat(),
    )

    current_app.send_task(
        "market.tasks.publish_ticks_for_backtest",
        kwargs={
            "instrument": str(instrument),
            "start": start_utc.isoformat().replace("+00:00", "Z"),
            "end": end_utc.isoformat().replace("+00:00", "Z"),
            "request_id": str(request_id),
        },
    )


@receiver(market_task_cancel_requested)
def _handle_market_task_cancel_requested(
    _sender: object,
    *,
    task_name: str,
    instance_key: str | None = None,
    reason: str | None = None,
    **_kwargs: object,
) -> None:
    # Best-effort flag flip; tasks are responsible for honoring STOP_REQUESTED.
    key = instance_key or "default"
    now = django_now()
    qs = CeleryTaskStatus.objects.filter(task_name=str(task_name), instance_key=key)

    updated = qs.exclude(status=CeleryTaskStatus.Status.STOPPED).update(
        status=CeleryTaskStatus.Status.STOP_REQUESTED,
        status_message=(reason or "Stop requested"),
        updated_at=now,
    )

    if updated:
        logger.info(
            "Stop requested for market task (task_name=%s, instance_key=%s)",
            task_name,
            key,
        )
    else:
        logger.info(
            "Stop requested for market task but no active record found (task_name=%s, instance_key=%s)",
            task_name,
            key,
        )


@receiver(post_save, sender=OandaAccounts)
def bootstrap_tick_pubsub_on_first_live_account(
    sender: type[OandaAccounts], instance: OandaAccounts, created: bool, **_kwargs: object
) -> None:
    _ = sender
    if not created:
        return

    if instance.api_type != ApiType.LIVE:
        return

    live_count = OandaAccounts.objects.filter(api_type=ApiType.LIVE).count()
    if live_count != 1:
        return

    def _start_tasks() -> None:
        try:
            logger.info(
                "First live OANDA account created; bootstrapping tick pub/sub (account_id=%s)",
                instance.id,  # type: ignore[attr-defined]
            )

            from apps.market.tasks import ensure_tick_pubsub_running

            ensure_tick_pubsub_running.delay()

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.exception("Failed to bootstrap tick pub/sub tasks: %s", exc)

    transaction.on_commit(_start_tasks)
