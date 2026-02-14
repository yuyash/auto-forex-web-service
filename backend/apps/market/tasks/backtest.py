"""Backtest tick publisher task runner."""

from __future__ import annotations

import json
from datetime import datetime
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.services.celery import CeleryTaskService
from apps.market.tasks.base import (
    backtest_channel_for_request,
    current_task_id,
    isoformat,
    lock_value,
    parse_iso_datetime,
    redis_client,
)

logger: Logger = getLogger(name=__name__)


@shared_task(bind=True, name="market.tasks.publish_ticks_for_backtest")
def publish_ticks_for_backtest(
    self: Any, instrument: str, start: str, end: str, request_id: str
) -> None:
    """Publish historical ticks from DB to Redis for a backtest run.

    Each signal creates a new Celery task. This task streams TickData rows in
    bounded chunks (doesn't load all ticks at once), publishes each tick to a
    dedicated per-request Redis channel, emits an EOF marker, then exits.

    Args:
        instrument: Currency pair
        start: Start time (ISO format)
        end: End time (ISO format)
        request_id: Unique request identifier
    """
    logger.info(
        f"[CELERY:PUBLISHER] Task started - request_id={request_id}, "
        f"instrument={instrument}, start={start}, end={end}, "
        f"celery_task_id={self.request.id}, worker={self.request.hostname}"
    )
    runner = BacktestTickPublisherRunner()
    runner.run(instrument, start, end, request_id)
    logger.info(
        f"[CELERY:PUBLISHER] Task completed - request_id={request_id}, "
        f"celery_task_id={self.request.id}"
    )


class BacktestTickPublisherRunner:
    """Runner for backtest tick publisher task."""

    def __init__(self) -> None:
        """Initialize the backtest publisher runner."""
        self.task_service: CeleryTaskService | None = None

    def run(self, instrument: str, start: str, end: str, request_id: str) -> None:
        """Execute the backtest tick publishing task.

        Args:
            instrument: Currency pair
            start: Start time (ISO format)
            end: End time (ISO format)
            request_id: Unique request identifier
        """
        logger.info(
            f"[PUBLISHER:RUN] Starting publisher runner - request_id={request_id}, "
            f"instrument={instrument}, start={start}, end={end}"
        )

        task_name = "market.tasks.publish_ticks_for_backtest"
        instance_key = str(request_id)
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=1.0,
            heartbeat_interval_seconds=5.0,
        )

        logger.info(
            f"[PUBLISHER:RUN] Starting task service - request_id={request_id}, "
            f"task_name={task_name}, instance_key={instance_key}"
        )

        self.task_service.start(
            celery_task_id=current_task_id(),
            worker=lock_value(),
            meta={"instrument": str(instrument), "start": str(start), "end": str(end)},
        )

        channel = backtest_channel_for_request(str(request_id))
        batch_size = int(getattr(settings, "MARKET_BACKTEST_PUBLISH_BATCH_SIZE", 1000))

        start_dt = parse_iso_datetime(start)
        end_dt = parse_iso_datetime(end)

        logger.info(
            f"[PUBLISHER:RUN] Configuration - request_id={request_id}, "
            f"channel={channel}, batch_size={batch_size}, "
            f"start_dt={start_dt}, end_dt={end_dt}"
        )

        client = redis_client()
        published = 0

        try:
            logger.info(f"[PUBLISHER:RUN] Starting tick publishing - request_id={request_id}")
            published = self._publish_ticks(
                client, channel, instrument, start_dt, end_dt, batch_size, request_id
            )

            # Send EOF marker
            logger.info(
                f"[PUBLISHER:RUN] Publishing completed, sending EOF - request_id={request_id}, "
                f"published={published}"
            )
            self._send_eof(client, channel, request_id, instrument, start, end, published)

            logger.info(
                f"[PUBLISHER:RUN] Finished successfully - request_id={request_id}, "
                f"published={published}"
            )

            assert self.task_service is not None
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.COMPLETED,
                status_message=f"published={published}",
            )
        except Exception as exc:
            logger.exception(
                f"[PUBLISHER:RUN] FAILED - request_id={request_id}, "
                f"published={published}, error={exc}"
            )
            self._send_error(client, channel, request_id, instrument, str(exc))

            assert self.task_service is not None
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.FAILED,
                status_message=str(exc),
            )
            raise

        finally:
            try:
                client.close()
                logger.info(f"[PUBLISHER:RUN] Redis client closed - request_id={request_id}")
            except Exception as exc:  # nosec B110
                # Log cleanup failure but don't raise
                logger.debug(
                    f"[PUBLISHER:RUN] Failed to close Redis client - request_id={request_id}, "
                    f"error={exc}"
                )

    def _publish_ticks(
        self,
        client: Any,
        channel: str,
        instrument: str,
        start_dt: datetime,
        end_dt: datetime,
        batch_size: int,
        request_id: str,
    ) -> int:
        """Publish ticks from database to Redis."""
        assert self.task_service is not None

        logger.info(
            f"[PUBLISHER:PUBLISH] Starting tick query - request_id={request_id}, "
            f"instrument={instrument}, start_dt={start_dt}, end_dt={end_dt}"
        )

        published = 0

        qs = (
            TickData.objects.filter(
                instrument=str(instrument),
                timestamp__gte=start_dt,
                timestamp__lte=end_dt,
            )
            .order_by("timestamp")
            .values("timestamp", "bid", "ask", "mid")
        )

        logger.info(
            f"[PUBLISHER:PUBLISH] Query created, starting iteration - request_id={request_id}"
        )

        # iterator(chunk_size=...) fetches DB rows in bounded chunks.
        tick_count = 0
        for row in qs.iterator(chunk_size=batch_size):
            # Check stop signal before every tick
            should_stop = self._should_stop_publishing(request_id)
            if should_stop:
                logger.info(
                    f"[PUBLISHER:PUBLISH] Stop signal received - request_id={request_id}, "
                    f"instrument={instrument}, published={published}, tick_count={tick_count}"
                )
                self._send_stopped(client, channel, request_id, instrument, published)
                self.task_service.mark_stopped(
                    status=CeleryTaskStatus.Status.STOPPED,
                    status_message=f"published={published}",
                )
                return published

            tick_count += 1

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
                        "timestamp": isoformat(ts),
                        "bid": str(row.get("bid")),
                        "ask": str(row.get("ask")),
                        "mid": str(row.get("mid")),
                    }
                ),
            )
            published += 1

            if published % max(batch_size * 10, 1) == 0:
                logger.info(
                    f"[PUBLISHER:PUBLISH] Progress update - request_id={request_id}, "
                    f"published={published}"
                )
                self.task_service.heartbeat(
                    status_message=f"published={published}",
                    meta_update={"published": published},
                )

        logger.info(
            f"[PUBLISHER:PUBLISH] Iteration complete - request_id={request_id}, "
            f"total_published={published}"
        )
        return published

    def _should_stop_publishing(self, request_id: str) -> bool:
        """Check if publishing should stop.

        Checks both the publisher's own stop signal and the executor's status.

        Args:
            request_id: The backtest request ID (matches BacktestTask.id)

        Returns:
            True if publishing should stop, False otherwise
        """
        assert self.task_service is not None

        # Force check to bypass throttling - we need immediate response
        if self.task_service.should_stop(force=True):
            logger.info(
                f"[PUBLISHER:STOP_CHECK] Publisher stop signal detected - request_id={request_id}"
            )
            return True

        # Check executor's status via BacktestTask
        try:
            from apps.trading.enums import TaskStatus
            from apps.trading.models import BacktestTask

            task_status = (
                BacktestTask.objects.filter(id=request_id).values_list("status", flat=True).first()
            )

            if task_status in (TaskStatus.STOPPING, TaskStatus.STOPPED, TaskStatus.FAILED):
                logger.info(
                    f"[PUBLISHER:STOP_CHECK] Executor stop detected - request_id={request_id}, "
                    f"task_status={task_status}"
                )
                return True

        except Exception as exc:
            logger.warning(
                f"[PUBLISHER:STOP_CHECK] Failed to check executor status - request_id={request_id}, "
                f"error={exc}"
            )

        return False

    def _send_eof(
        self,
        client: Any,
        channel: str,
        request_id: str,
        instrument: str,
        start: str,
        end: str,
        count: int,
    ) -> None:
        """Send EOF marker to channel."""
        logger.info(
            f"[PUBLISHER:EOF] Sending EOF marker - request_id={request_id}, "
            f"channel={channel}, count={count}"
        )

        eof_message = {
            "type": "eof",
            "request_id": str(request_id),
            "instrument": str(instrument),
            "start": str(start),
            "end": str(end),
            "count": count,
        }

        subscribers = client.publish(channel, json.dumps(eof_message))

        logger.info(
            f"[PUBLISHER:EOF] EOF sent - request_id={request_id}, "
            f"channel={channel}, count={count}, subscribers={subscribers}"
        )

    def _send_stopped(
        self, client: Any, channel: str, request_id: str, instrument: str, count: int
    ) -> None:
        """Send stopped marker to channel."""
        logger.info(
            f"[PUBLISHER:STOPPED] Sending stopped marker - request_id={request_id}, "
            f"channel={channel}, count={count}"
        )
        subscribers = client.publish(
            channel,
            json.dumps(
                {
                    "type": "stopped",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "count": count,
                }
            ),
        )
        logger.info(
            f"[PUBLISHER:STOPPED] Stopped marker sent - request_id={request_id}, "
            f"channel={channel}, count={count}, subscribers={subscribers}"
        )

    def _send_error(
        self, client: Any, channel: str, request_id: str, instrument: str, message: str
    ) -> None:
        """Send error marker to channel."""
        logger.info(
            f"[PUBLISHER:ERROR] Sending error marker - request_id={request_id}, "
            f"channel={channel}, message={message}"
        )
        try:
            subscribers = client.publish(
                channel,
                json.dumps(
                    {
                        "type": "error",
                        "request_id": str(request_id),
                        "instrument": str(instrument),
                        "message": message,
                    }
                ),
            )
            logger.info(
                f"[PUBLISHER:ERROR] Error marker sent - request_id={request_id}, "
                f"channel={channel}, subscribers={subscribers}"
            )
        except Exception as exc:  # nosec B110
            # Log publish failure but don't raise
            logger.warning(
                f"[PUBLISHER:ERROR] Failed to publish error message - request_id={request_id}, "
                f"error={exc}"
            )
