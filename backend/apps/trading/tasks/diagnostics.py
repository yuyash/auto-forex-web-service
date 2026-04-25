"""Execution diagnostics used by task runners."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionDiagnostics:
    """Own opt-in memory profiling for task execution."""

    def __init__(self, *, task: Any, tracemalloc_enabled: bool) -> None:
        self.task = task
        self.tracemalloc_enabled = tracemalloc_enabled
        self.tracemalloc_started = False
        self.mem_snapshot_count = 0
        self.last_rss_mb = 0

    def start_tracemalloc(self) -> None:
        import tracemalloc

        if tracemalloc.is_tracing():
            logger.info("[TRACEMALLOC] Already tracing, reusing")
        else:
            tracemalloc.start(25)
        self.tracemalloc_started = True
        logger.warning(
            "[TRACEMALLOC] Enabled for task %s - expect CPU/memory overhead",
            self.task.pk,
        )

    def stop_tracemalloc(self) -> None:
        import tracemalloc

        if tracemalloc.is_tracing():
            self.log_tracemalloc_snapshot("final")
            tracemalloc.stop()
        self.tracemalloc_started = False
        logger.info("[TRACEMALLOC] Stopped for task %s", self.task.pk)

    def check_memory(self, *, batch_count: int, ticks_processed: int) -> None:
        """Log RSS and take tracemalloc snapshot when memory grows."""
        import resource
        import sys

        rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # macOS returns bytes, Linux returns KB.
        rss_mb = rss_kb // 1024 if sys.platform == "linux" else rss_kb // (1024 * 1024)

        if batch_count % 100 == 0:
            logger.info(
                "[MEMORY] task=%s batch=%d ticks=%d rss=%dMB",
                self.task.pk,
                batch_count,
                ticks_processed,
                rss_mb,
            )

        if rss_mb - self.last_rss_mb >= 500:
            self.mem_snapshot_count += 1
            self.log_tracemalloc_snapshot(f"rss_jump_{self.mem_snapshot_count}")
            self.last_rss_mb = rss_mb

    def log_tracemalloc_snapshot(self, label: str) -> None:
        """Take a tracemalloc snapshot and log the top allocations."""
        import tracemalloc

        if not tracemalloc.is_tracing():
            return

        snapshot = tracemalloc.take_snapshot()
        stats = snapshot.statistics("lineno")

        current, peak = tracemalloc.get_traced_memory()
        logger.warning(
            "[TRACEMALLOC:%s] task=%s current=%.1fMB peak=%.1fMB",
            label,
            self.task.pk,
            current / (1024 * 1024),
            peak / (1024 * 1024),
        )
        for i, stat in enumerate(stats[:20]):
            logger.warning("[TRACEMALLOC:%s] #%d %s", label, i + 1, stat)
