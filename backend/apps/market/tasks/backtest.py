"""Backtest tick publisher task runner."""

from __future__ import annotations

import time
from datetime import datetime
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.models import CeleryTaskStatus, TickData
from apps.market.services.backtest_ticks import iter_aggregated_backtest_ticks
from apps.market.services.celery import CeleryTaskService
from apps.market.tasks.base import (
    backtest_stream_key_for_request,
    current_task_id,
    isoformat,
    lock_value,
    parse_iso_datetime,
    redis_client,
)

logger: Logger = getLogger(name=__name__)


@shared_task(bind=True, name="market.tasks.publish_ticks_for_backtest")
def publish_ticks_for_backtest(
    self: Any,
    instrument: str,
    start: str,
    end: str,
    request_id: str,
    tick_granularity: str = "tick",
    tick_window_value_mode: str = "last",
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
        f"tick_granularity={tick_granularity}, "
        f"tick_window_value_mode={tick_window_value_mode}, "
        f"celery_task_id={self.request.id}, worker={self.request.hostname}"
    )
    runner = BacktestTickPublisherRunner()
    runner.run(
        instrument,
        start,
        end,
        request_id,
        tick_granularity=tick_granularity,
        tick_window_value_mode=tick_window_value_mode,
    )
    logger.info(
        f"[CELERY:PUBLISHER] Task completed - request_id={request_id}, "
        f"celery_task_id={self.request.id}"
    )


class BacktestTickPublisherRunner:
    """Runner for backtest tick publisher task."""

    def __init__(self) -> None:
        """Initialize the backtest publisher runner."""
        self.task_service: CeleryTaskService | None = None

    def run(
        self,
        instrument: str,
        start: str,
        end: str,
        request_id: str,
        *,
        tick_granularity: str = "tick",
        tick_window_value_mode: str = "last",
    ) -> None:
        """Execute the backtest tick publishing task.

        Args:
            instrument: Currency pair
            start: Start time (ISO format)
            end: End time (ISO format)
            request_id: Unique request identifier
        """
        logger.info(
            f"[PUBLISHER:RUN] Starting publisher runner - request_id={request_id}, "
            f"instrument={instrument}, start={start}, end={end}, "
            f"tick_granularity={tick_granularity}, "
            f"tick_window_value_mode={tick_window_value_mode}"
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
            meta={
                "instrument": str(instrument),
                "start": str(start),
                "end": str(end),
                "tick_granularity": str(tick_granularity),
                "tick_window_value_mode": str(tick_window_value_mode),
            },
        )

        channel = backtest_stream_key_for_request(str(request_id))
        batch_size = int(getattr(settings, "MARKET_BACKTEST_PUBLISH_BATCH_SIZE", 1000))
        stream_maxlen = int(getattr(settings, "MARKET_BACKTEST_STREAM_MAXLEN", 200_000))
        high_watermark = int(
            getattr(settings, "MARKET_BACKTEST_BACKPRESSURE_HIGH_WATERMARK", 100_000)
        )
        low_watermark = int(getattr(settings, "MARKET_BACKTEST_BACKPRESSURE_LOW_WATERMARK", 50_000))
        backpressure_sleep = float(
            getattr(settings, "MARKET_BACKTEST_BACKPRESSURE_SLEEP_SECONDS", 0.5)
        )

        start_dt = parse_iso_datetime(start)
        end_dt = parse_iso_datetime(end)

        logger.info(
            f"[PUBLISHER:RUN] Configuration - request_id={request_id}, "
            f"stream={channel}, batch_size={batch_size}, "
            f"stream_maxlen={stream_maxlen}, "
            f"backpressure_high={high_watermark}, backpressure_low={low_watermark}, "
            f"start_dt={start_dt}, end_dt={end_dt}, "
            f"tick_granularity={tick_granularity}, "
            f"tick_window_value_mode={tick_window_value_mode}"
        )

        client = redis_client()
        published = 0

        # Ensure no stale entries from a previous run leak into the new stream.
        try:
            deleted = client.delete(channel)
            if deleted:
                logger.info(
                    f"[PUBLISHER:RUN] Cleared stale stream - request_id={request_id}, "
                    f"stream={channel}"
                )
        except Exception as exc:  # nosec B110
            logger.debug(
                f"[PUBLISHER:RUN] Failed to clear stale stream (non-fatal) - "
                f"request_id={request_id}, error={exc}"
            )

        try:
            logger.info(f"[PUBLISHER:RUN] Starting tick publishing - request_id={request_id}")
            published, last_tick_ts, stopped_early = self._publish_ticks(
                client,
                channel,
                instrument,
                start_dt,
                end_dt,
                batch_size,
                request_id,
                tick_granularity=tick_granularity,
                tick_window_value_mode=tick_window_value_mode,
                stream_maxlen=stream_maxlen,
                high_watermark=high_watermark,
                low_watermark=low_watermark,
                backpressure_sleep=backpressure_sleep,
            )

            if stopped_early:
                logger.info(
                    f"[PUBLISHER:RUN] Publishing stopped before completion - request_id={request_id}, "
                    f"published={published}, last_tick_ts={last_tick_ts}"
                )
                return

            # Check for insufficient data coverage
            data_gap = self._check_data_coverage(
                instrument, start_dt, end_dt, published, last_tick_ts, request_id
            )

            if data_gap:
                # Data does not cover the requested range — mark as failed
                logger.error(
                    f"[PUBLISHER:RUN] INSUFFICIENT_DATA - request_id={request_id}, "
                    f"published={published}, last_tick_ts={last_tick_ts}, "
                    f"end_dt={end_dt}, gap={data_gap}"
                )
                self._send_error(
                    client,
                    channel,
                    request_id,
                    instrument,
                    f"Insufficient tick data: {data_gap}",
                )
                assert self.task_service is not None
                self.task_service.mark_stopped(
                    status=CeleryTaskStatus.Status.FAILED,
                    status_message=f"Insufficient tick data: {data_gap}",
                )
                # Also mark the BacktestTask as failed
                self._mark_backtest_task_failed(request_id, data_gap)
                return

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
        *,
        tick_granularity: str = "tick",
        tick_window_value_mode: str = "last",
        stream_maxlen: int = 200_000,
        high_watermark: int = 100_000,
        low_watermark: int = 50_000,
        backpressure_sleep: float = 0.5,
    ) -> tuple[int, datetime | None, bool]:
        """Publish ticks to the per-request Redis Stream.

        Uses ``XADD`` with ``MAXLEN`` trimming for a bounded stream and
        ``XLEN``-based backpressure: when the queue grows beyond
        ``high_watermark`` the publisher pauses until the subscriber has
        drained below ``low_watermark``.  This keeps the publisher in step
        with the slower consumer without losing messages, which is exactly
        what Redis Pub/Sub could not do.

        Returns:
            Tuple of (published_count, last_tick_timestamp, stopped_early).
        """
        assert self.task_service is not None

        logger.info(
            f"[PUBLISHER:PUBLISH] Starting tick query - request_id={request_id}, "
            f"instrument={instrument}, start_dt={start_dt}, end_dt={end_dt}, "
            f"tick_granularity={tick_granularity}, "
            f"tick_window_value_mode={tick_window_value_mode}"
        )

        published = 0
        last_ts: datetime | None = None
        backpressure_waiting = False

        logger.info(
            f"[PUBLISHER:PUBLISH] Query created, starting iteration - request_id={request_id}"
        )

        if tick_granularity == "tick":
            rows_iter = self._iter_raw_ticks(
                instrument=instrument,
                start_dt=start_dt,
                end_dt=end_dt,
                batch_size=batch_size,
            )
        else:
            rows_iter = self._iter_aggregated_ticks(
                instrument=instrument,
                start_dt=start_dt,
                end_dt=end_dt,
                granularity=tick_granularity,
                mode=tick_window_value_mode,
                batch_size=batch_size,
            )

        for row in rows_iter:
            # Check stop signal before every tick.
            if self._should_stop_publishing(request_id):
                logger.info(
                    f"[PUBLISHER:PUBLISH] Stop signal received - request_id={request_id}, "
                    f"instrument={instrument}, published={published}"
                )
                self._send_stopped(client, channel, request_id, instrument, published)
                self.task_service.mark_stopped(
                    status=CeleryTaskStatus.Status.STOPPED,
                    status_message=f"published={published}",
                )
                return published, last_ts, True

            ts = row["timestamp"]
            if not isinstance(ts, datetime):
                continue

            # Backpressure: pause when the subscriber is falling behind.
            # ``XLEN`` reflects the number of entries currently buffered in
            # the stream.  Combined with ``MAXLEN`` trimming below, this
            # prevents both unbounded memory use and silent tick loss.
            if high_watermark > 0:
                backpressure_waiting = self._apply_backpressure(
                    client=client,
                    channel=channel,
                    request_id=request_id,
                    high_watermark=high_watermark,
                    low_watermark=low_watermark,
                    sleep_seconds=backpressure_sleep,
                    already_waiting=backpressure_waiting,
                )
                # If a stop signal arrived while we were waiting, bail out.
                if self._should_stop_publishing(request_id):
                    logger.info(
                        f"[PUBLISHER:PUBLISH] Stop signal received during backpressure - "
                        f"request_id={request_id}, published={published}"
                    )
                    self._send_stopped(client, channel, request_id, instrument, published)
                    self.task_service.mark_stopped(
                        status=CeleryTaskStatus.Status.STOPPED,
                        status_message=f"published={published}",
                    )
                    return published, last_ts, True

            try:
                client.xadd(
                    channel,
                    {
                        "type": "tick",
                        "request_id": str(request_id),
                        "instrument": str(instrument),
                        "timestamp": isoformat(ts),
                        "bid": str(row["bid"]),
                        "ask": str(row["ask"]),
                        "mid": str(row["mid"]),
                    },
                    maxlen=stream_maxlen,
                    approximate=True,
                )
            except Exception as exc:
                logger.exception(
                    f"[PUBLISHER:PUBLISH] XADD failed - request_id={request_id}, "
                    f"published={published}, error={exc}"
                )
                raise

            published += 1
            last_ts = ts

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
            f"total_published={published}, last_ts={last_ts}"
        )
        return published, last_ts, False

    @staticmethod
    def _apply_backpressure(
        *,
        client: Any,
        channel: str,
        request_id: str,
        high_watermark: int,
        low_watermark: int,
        sleep_seconds: float,
        already_waiting: bool,
    ) -> bool:
        """Sleep while the stream contains more pending entries than allowed.

        Returns the updated ``waiting`` flag so the caller can avoid
        spamming the log.  We only log once at the start and end of each
        back-pressure episode.
        """
        try:
            pending = int(client.xlen(channel))
        except Exception as exc:  # nosec B110
            logger.debug(
                f"[PUBLISHER:BACKPRESSURE] XLEN failed, skipping - "
                f"request_id={request_id}, error={exc}"
            )
            return already_waiting

        if pending < high_watermark:
            if already_waiting and pending <= low_watermark:
                logger.info(
                    f"[PUBLISHER:BACKPRESSURE] Subscriber caught up, resuming - "
                    f"request_id={request_id}, pending={pending}"
                )
                return False
            return already_waiting

        if not already_waiting:
            logger.info(
                f"[PUBLISHER:BACKPRESSURE] Subscriber falling behind, pausing - "
                f"request_id={request_id}, pending={pending}, "
                f"high_watermark={high_watermark}, low_watermark={low_watermark}"
            )

        # Block here until the stream drains below the low watermark or the
        # subscriber disappears.  We re-check periodically so a stop signal
        # isn't delayed for more than ``sleep_seconds``.
        while True:
            time.sleep(max(sleep_seconds, 0.01))
            try:
                pending = int(client.xlen(channel))
            except Exception as exc:  # nosec B110
                logger.debug(
                    f"[PUBLISHER:BACKPRESSURE] XLEN failed while waiting - "
                    f"request_id={request_id}, error={exc}"
                )
                return True
            if pending <= low_watermark:
                logger.info(
                    f"[PUBLISHER:BACKPRESSURE] Drained below low watermark - "
                    f"request_id={request_id}, pending={pending}"
                )
                return False

    @staticmethod
    def _iter_raw_ticks(
        *,
        instrument: str,
        start_dt: datetime,
        end_dt: datetime,
        batch_size: int,
    ) -> Any:
        qs = (
            TickData.objects.filter(
                instrument=str(instrument),
                timestamp__gte=start_dt,
                timestamp__lte=end_dt,
            )
            .order_by("timestamp")
            .values("timestamp", "bid", "ask", "mid")
        )
        return qs.iterator(chunk_size=batch_size)

    @staticmethod
    def _iter_aggregated_ticks(
        *,
        instrument: str,
        start_dt: datetime,
        end_dt: datetime,
        granularity: str,
        mode: str,
        batch_size: int,
    ) -> Any:
        for row in iter_aggregated_backtest_ticks(
            instrument=instrument,
            start_dt=start_dt,
            end_dt=end_dt,
            granularity=granularity,
            mode=mode,
            batch_size=batch_size,
        ):
            yield {
                "timestamp": row.timestamp,
                "bid": row.bid,
                "ask": row.ask,
                "mid": row.mid,
            }

    @staticmethod
    def _check_data_coverage(
        instrument: str,
        start_dt: datetime,
        end_dt: datetime,
        published: int,
        last_tick_ts: datetime | None,
        request_id: str,
    ) -> str | None:
        """Check whether published ticks adequately cover the requested range.

        Returns a human-readable gap description if coverage is insufficient,
        or ``None`` when the data looks fine.
        """
        if published == 0:
            return (
                f"No tick data found for {instrument} "
                f"between {start_dt.isoformat()} and {end_dt.isoformat()}"
            )

        if last_tick_ts is None:
            return None  # shouldn't happen when published > 0

        # Allow a tolerance of 2 hours for the gap between the last tick and
        # end_dt.  Forex market close (Fri 21:00 → Sun 21:00 UTC) creates a
        # natural ~48 h gap, but if end_dt falls *within* a trading session and
        # the last tick is more than 2 h before it, data is likely missing.
        from datetime import timedelta

        gap = end_dt - last_tick_ts
        # Tolerance: if the gap is larger than 2 hours AND the end_dt does not
        # fall inside a known market-close window, flag it.
        tolerance = timedelta(hours=2)

        if gap <= tolerance:
            return None

        # Check whether the gap is explained by a weekend market close.
        # Forex closes Fri 21:00 UTC → Sun 21:00 UTC.
        if _gap_spans_only_market_close(last_tick_ts, end_dt):
            return None

        logger.warning(
            f"[PUBLISHER:COVERAGE] Data gap detected - request_id={request_id}, "
            f"last_tick_ts={last_tick_ts}, end_dt={end_dt}, gap={gap}"
        )
        return (
            f"Tick data for {instrument} ends at {last_tick_ts.isoformat()} "
            f"but the requested end_time is {end_dt.isoformat()} "
            f"(gap: {gap})"
        )

    @staticmethod
    def _mark_backtest_task_failed(request_id: str, reason: str) -> None:
        """Mark the BacktestTask as FAILED with an error message."""
        try:
            from django.utils import timezone as dj_timezone

            from apps.trading.enums import TaskStatus
            from apps.trading.models import BacktestTask

            rows = BacktestTask.objects.filter(
                pk=request_id,
                status=TaskStatus.RUNNING,
            ).update(
                status=TaskStatus.FAILED,
                completed_at=dj_timezone.now(),
                error_message=f"Insufficient tick data: {reason}",
            )
            if rows:
                logger.info(
                    f"[PUBLISHER:FAIL_TASK] BacktestTask marked FAILED - request_id={request_id}"
                )
            else:
                logger.warning(
                    f"[PUBLISHER:FAIL_TASK] Could not mark BacktestTask FAILED "
                    f"(not in RUNNING state) - request_id={request_id}"
                )
        except Exception as exc:
            logger.error(
                f"[PUBLISHER:FAIL_TASK] Error marking BacktestTask FAILED - "
                f"request_id={request_id}, error={exc}",
                exc_info=True,
            )

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
        """Append EOF marker to the stream.

        EOF is written as a regular stream entry so it cannot be dropped
        mid-flight like a pub/sub message.  ``maxlen`` is not applied here —
        the marker is small and we want to guarantee it reaches the
        subscriber even if the stream is near capacity.
        """
        logger.info(
            f"[PUBLISHER:EOF] Sending EOF marker - request_id={request_id}, "
            f"stream={channel}, count={count}"
        )

        try:
            entry_id = client.xadd(
                channel,
                {
                    "type": "eof",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "start": str(start),
                    "end": str(end),
                    "count": str(count),
                },
            )
        except Exception as exc:
            logger.exception(
                f"[PUBLISHER:EOF] XADD EOF failed - request_id={request_id}, error={exc}"
            )
            raise

        logger.info(
            f"[PUBLISHER:EOF] EOF sent - request_id={request_id}, "
            f"stream={channel}, count={count}, entry_id={entry_id}"
        )

    def _send_stopped(
        self, client: Any, channel: str, request_id: str, instrument: str, count: int
    ) -> None:
        """Append stopped marker to the stream."""
        logger.info(
            f"[PUBLISHER:STOPPED] Sending stopped marker - request_id={request_id}, "
            f"stream={channel}, count={count}"
        )
        try:
            entry_id = client.xadd(
                channel,
                {
                    "type": "stopped",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "count": str(count),
                },
            )
            logger.info(
                f"[PUBLISHER:STOPPED] Stopped marker sent - request_id={request_id}, "
                f"stream={channel}, count={count}, entry_id={entry_id}"
            )
        except Exception as exc:  # nosec B110
            logger.warning(
                f"[PUBLISHER:STOPPED] Failed to append stopped marker - "
                f"request_id={request_id}, error={exc}"
            )

    def _send_error(
        self, client: Any, channel: str, request_id: str, instrument: str, message: str
    ) -> None:
        """Append error marker to the stream."""
        logger.info(
            f"[PUBLISHER:ERROR] Sending error marker - request_id={request_id}, "
            f"stream={channel}, message={message}"
        )
        try:
            entry_id = client.xadd(
                channel,
                {
                    "type": "error",
                    "request_id": str(request_id),
                    "instrument": str(instrument),
                    "message": message,
                },
            )
            logger.info(
                f"[PUBLISHER:ERROR] Error marker sent - request_id={request_id}, "
                f"stream={channel}, entry_id={entry_id}"
            )
        except Exception as exc:  # nosec B110
            logger.warning(
                f"[PUBLISHER:ERROR] Failed to append error marker - request_id={request_id}, "
                f"error={exc}"
            )


def _gap_spans_only_market_close(last_tick: datetime, end_dt: datetime) -> bool:
    """Return True if the gap between *last_tick* and *end_dt* is fully
    explained by a forex weekend market closure (Fri 21:00 → Sun 21:00 UTC).

    The check is intentionally generous: if *last_tick* falls on Friday after
    20:00 UTC and *end_dt* falls anywhere during the weekend (Saturday,
    Sunday before reopen) or after the Sunday reopen / on a weekday, the gap
    is considered a normal weekend closure.
    """
    from datetime import timedelta

    lt_weekday = last_tick.weekday()  # 0=Mon … 6=Sun
    et_weekday = end_dt.weekday()

    # last_tick on Friday (4) evening
    if lt_weekday == 4 and last_tick.hour >= 20:
        # end_dt on Saturday (5), Sunday before/after reopen (6), or weekday
        if et_weekday == 5 or (et_weekday == 6) or et_weekday in (0, 1, 2, 3, 4):
            # Sanity: gap should be less than ~3 days
            if (end_dt - last_tick) < timedelta(days=3, hours=6):
                return True

    return False
