"""In-memory metrics aggregator that flushes minute-level records to the DB.

MetricsAggregator collects per-tick strategy metrics and writes one row
per minute bucket to the Metrics table.  Within each bucket the *last*
observed value for every key is kept (snapshot semantics).
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

logger = logging.getLogger(__name__)


def _truncate_to_minute(dt: datetime) -> datetime:
    """Return *dt* with seconds and microseconds zeroed out."""
    return dt.replace(second=0, microsecond=0)


def _serialise_value(v: Any) -> Any:
    """Convert Decimal / other non-JSON-native types to float."""
    if isinstance(v, Decimal):
        return float(v)
    return v


class MetricsAggregator:
    """Collect per-tick metrics and flush minute-level snapshots to the DB.

    Usage inside ``TaskExecutor``::

        agg = MetricsAggregator(task_type="backtest", task_id=uuid, execution_id=uuid)
        # on every tick:
        agg.record(tick.timestamp, state.strategy_state.get("metrics", {}))
        # periodically (e.g. after each batch):
        agg.flush()
        # at end of execution:
        agg.flush(final=True)
    """

    def __init__(
        self,
        *,
        task_type: str,
        task_id: str,
        execution_id: str | None,
    ) -> None:
        self.task_type = task_type
        self.task_id = task_id
        self.execution_id = execution_id
        # bucket_key (datetime truncated to minute) → latest metrics dict
        self._buckets: dict[datetime, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record(self, timestamp: datetime, metrics: dict[str, Any]) -> None:
        """Record a tick's metrics into the appropriate minute bucket."""
        if not metrics:
            return
        bucket_key = _truncate_to_minute(timestamp)
        serialised = {k: _serialise_value(v) for k, v in metrics.items() if v is not None}
        if not serialised:
            return
        # Last-write-wins within the same minute
        existing = self._buckets.get(bucket_key)
        if existing is None:
            self._buckets[bucket_key] = serialised
        else:
            existing.update(serialised)

    def flush(self, *, final: bool = False) -> int:
        """Write completed minute buckets to the database.

        By default only buckets whose minute has *ended* (i.e. a newer
        bucket exists) are flushed.  When *final* is True every remaining
        bucket is flushed — call this at the end of execution.

        Returns the number of rows written.
        """
        if not self._buckets:
            return 0

        from apps.trading.models.metrics import Metrics

        sorted_keys = sorted(self._buckets)

        if final:
            keys_to_flush = sorted_keys
        else:
            # Flush all buckets except the latest (still accumulating).
            keys_to_flush = sorted_keys[:-1]

        if not keys_to_flush:
            return 0

        objs = [
            Metrics(
                task_type=self.task_type,
                task_id=self.task_id,
                execution_id=self.execution_id,
                timestamp=bucket_key,
                metrics=self._buckets[bucket_key],
            )
            for bucket_key in keys_to_flush
        ]

        created = Metrics.objects.bulk_create(objs, ignore_conflicts=True)
        count = len(created)

        logger.debug(
            "MetricsAggregator flushed %d/%d buckets (final=%s) for task %s",
            count,
            len(keys_to_flush),
            final,
            self.task_id,
        )

        for k in keys_to_flush:
            del self._buckets[k]

        return count
