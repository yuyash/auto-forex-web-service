"""Equity tracker for recording balance snapshots."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.trading.models import BacktestTasks


class EquityTracker:
    """Tracks and persists equity curve points."""

    def __init__(self, task: BacktestTasks, celery_task_id: str) -> None:
        """Initialize the equity tracker.

        Args:
            task: Backtest task
            celery_task_id: Celery task ID for this execution
        """
        self.task = task
        self.celery_task_id = celery_task_id

    def record_equity_point(
        self,
        timestamp: datetime,
        balance: Decimal,
        ticks_processed: int,
    ) -> None:
        """Record an equity curve point to database.

        Args:
            timestamp: Timestamp of the equity point
            balance: Account balance at this point
            ticks_processed: Number of ticks processed
        """
        from apps.trading.models import ExecutionEquity

        ExecutionEquity.objects.update_or_create(
            task=self.task,
            celery_task_id=self.celery_task_id,
            timestamp=timestamp,
            defaults={
                "balance": balance,
                "ticks_processed": ticks_processed,
            },
        )
