"""Backtest-related signal handlers."""

from __future__ import annotations

from datetime import datetime
from logging import Logger, getLogger
from uuid import uuid4

from celery import current_app

from apps.market.signals.base import (
    SignalHandler,
    backtest_tick_stream_requested,
    ensure_aware_utc,
)

logger: Logger = getLogger(name=__name__)


class BacktestSignalHandler(SignalHandler):
    """Handler for backtest-related signals."""

    def connect(self) -> None:
        """Connect backtest signal handlers."""
        backtest_tick_stream_requested.connect(
            self.enqueue_backtest_tick_publisher,
            dispatch_uid="market.signals.enqueue_backtest_tick_publisher",
        )

    def request_backtest_tick_stream(
        self,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
        request_id: str | None = None,
    ) -> str:
        """Emit a backtest tick stream request signal.

        Args:
            instrument: Currency pair
            start: Start datetime
            end: End datetime
            request_id: Optional request ID (generated if not provided)

        Returns:
            The request_id used for the stream
        """
        rid = request_id or uuid4().hex
        backtest_tick_stream_requested.send(
            sender=self.__class__,
            instrument=instrument,
            start=start,
            end=end,
            request_id=rid,
        )
        return rid

    def enqueue_backtest_tick_publisher(
        self,
        sender: object,
        signal: object,
        *,
        instrument: str,
        start: datetime,
        end: datetime,
        request_id: str,
        **_kwargs: object,
    ) -> None:
        """Handle backtest tick stream request by enqueuing publisher task."""
        start_utc = ensure_aware_utc(start)
        end_utc = ensure_aware_utc(end)

        if end_utc < start_utc:
            logger.warning(
                "Ignoring backtest tick stream request with end < start "
                "(instrument=%s, request_id=%s)",
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


# Create singleton instance
backtest_handler = BacktestSignalHandler()

# Export convenience function
request_backtest_tick_stream = backtest_handler.request_backtest_tick_stream
enqueue_backtest_tick_publisher = backtest_handler.enqueue_backtest_tick_publisher
