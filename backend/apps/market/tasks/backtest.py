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
    runner = BacktestTickPublisherRunner()
    runner.run(instrument, start, end, request_id)


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
        task_name = "market.tasks.publish_ticks_for_backtest"
        instance_key = str(request_id)
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=1.0,
            heartbeat_interval_seconds=5.0,
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
            "Starting backtest tick publisher "
            "(instrument=%s, request_id=%s, channel=%s, batch_size=%s)",
            instrument,
            request_id,
            channel,
            batch_size,
        )

        client = redis_client()
        published = 0

        try:
            published = self._publish_ticks(
                client, channel, instrument, start_dt, end_dt, batch_size, request_id
            )

            # Send EOF marker
            self._send_eof(client, channel, request_id, instrument, start, end, published)

            logger.info(
                "Finished backtest tick publish (instrument=%s, request_id=%s, published=%s)",
                instrument,
                request_id,
                published,
            )

            assert self.task_service is not None
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.COMPLETED,
                status_message=f"published={published}",
            )
        except Exception as exc:
            logger.exception(
                "Backtest tick publisher failed (instrument=%s, request_id=%s): %s",
                instrument,
                request_id,
                exc,
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
            except Exception as exc:  # nosec B110
                # Log cleanup failure but don't raise
                import logging

                logger_local = logging.getLogger(__name__)
                logger_local.debug("Failed to close Athena client: %s", exc)

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

        # iterator(chunk_size=...) fetches DB rows in bounded chunks.
        for row in qs.iterator(chunk_size=batch_size):
            if self.task_service.should_stop():
                self._send_stopped(client, channel, request_id, instrument, published)
                self.task_service.mark_stopped(
                    status=CeleryTaskStatus.Status.STOPPED,
                    status_message=f"published={published}",
                )
                return published

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

            if published % max(batch_size, 1) == 0:
                logger.info(
                    "Published %s backtest ticks so far (instrument=%s, request_id=%s)",
                    published,
                    instrument,
                    request_id,
                )
                self.task_service.heartbeat(
                    status_message=f"published={published}",
                    meta_update={"published": published},
                )

        return published

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
        client.publish(
            channel,
            json.dumps(
                {
                    "type": "eof",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "start": str(start),
                    "end": str(end),
                    "count": count,
                }
            ),
        )

    def _send_stopped(
        self, client: Any, channel: str, request_id: str, instrument: str, count: int
    ) -> None:
        """Send stopped marker to channel."""
        client.publish(
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

    def _send_error(
        self, client: Any, channel: str, request_id: str, instrument: str, message: str
    ) -> None:
        """Send error marker to channel."""
        try:
            client.publish(
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
        except Exception as exc:  # nosec B110
            # Log publish failure but don't raise
            import logging

            logger = logging.getLogger(__name__)
            logger.warning("Failed to publish error message: %s", exc)
