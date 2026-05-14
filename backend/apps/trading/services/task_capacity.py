"""Capacity planning and admission control for task execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from celery import current_app
from django.conf import settings
from django.utils import timezone

from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus
from apps.trading.models import BacktestTask, TradingTask
from apps.trading.services.task_policy import (
    CAPACITY_ACTIVE_STATUSES as ACTIVE_TASK_STATUSES,
)

ACTIVE_MARKET_STATUSES = (
    MarketCeleryTaskStatus.Status.RUNNING,
    MarketCeleryTaskStatus.Status.STOPPING,
)


@dataclass(frozen=True, slots=True)
class QueueCapacitySnapshot:
    """Current and maximum capacity for a single worker queue."""

    queue: str
    used: int
    limit: int

    @property
    def available(self) -> int:
        return max(self.limit - self.used, 0)


@dataclass(frozen=True, slots=True)
class TaskAdmissionDecision:
    """Admission result for a task start request."""

    allowed: bool
    reason: str = ""
    details: tuple[QueueCapacitySnapshot, ...] = ()
    required_stops: tuple[dict[str, object], ...] = ()


class TaskCapacityService:
    """Evaluate whether the system has capacity to start a task."""

    def _queue_inspector(self):
        return current_app.control.inspect(timeout=2.0)

    def _queue_usage(self, queue: str) -> int | None:
        """Return active task count for a dedicated queue.

        Returns ``None`` when inspection is unavailable so callers can fall
        back to persisted liveness data.
        """
        try:
            inspector = self._queue_inspector()
            active_queues = inspector.active_queues() or {}
            active = inspector.active() or {}
        except Exception:
            return None

        workers = [
            worker_name
            for worker_name, queue_entries in active_queues.items()
            if any(str(entry.get("name") or "") == queue for entry in (queue_entries or []))
        ]
        if not workers:
            return 0

        active_count = sum(len(active.get(worker_name) or []) for worker_name in workers)
        return active_count

    @staticmethod
    def _required_stop(queue: str, count: int) -> dict[str, object]:
        task_type = "task"
        if queue in {"trading", "market"}:
            task_type = "trading task"
        elif queue in {"backtest", "backtest_publisher"}:
            task_type = "backtest task"
        plural = "" if count == 1 else "s"
        return {
            "queue": queue,
            "count": count,
            "task_type": task_type,
            "message": f"Stop at least {count} {task_type}{plural}.",
        }

    def _market_task_cutoff(self):
        stale_after_seconds = int(getattr(settings, "CELERY_MARKET_TASK_STALE_AFTER_SECONDS", 90))
        return timezone.now() - timedelta(seconds=stale_after_seconds)

    def _fresh_market_tasks(self, *, task_name: str):
        return MarketCeleryTaskStatus.objects.filter(
            task_name=task_name,
            status__in=ACTIVE_MARKET_STATUSES,
            last_heartbeat_at__gte=self._market_task_cutoff(),
        )

    def get_task_admission(self, task: BacktestTask | TradingTask) -> TaskAdmissionDecision:
        if isinstance(task, BacktestTask):
            return self._admit_backtest()
        return self._admit_trading(task)

    def _admit_backtest(self) -> TaskAdmissionDecision:
        active_backtests = self._queue_usage("backtest")
        if active_backtests is None:
            active_backtests = BacktestTask.objects.filter(status__in=ACTIVE_TASK_STATUSES).count()

        active_publishers = self._queue_usage("backtest_publisher")
        if active_publishers is None:
            active_publishers = self._fresh_market_tasks(
                task_name="market.tasks.publish_ticks_for_backtest"
            ).count()

        backtest_snapshot = QueueCapacitySnapshot(
            queue="backtest",
            used=active_backtests,
            limit=int(getattr(settings, "CELERY_BACKTEST_WORKER_CONCURRENCY", 1)),
        )
        publisher_snapshot = QueueCapacitySnapshot(
            queue="backtest_publisher",
            used=active_publishers,
            limit=int(getattr(settings, "CELERY_BACKTEST_PUBLISHER_CONCURRENCY", 1)),
        )

        shortages = [
            snapshot.queue
            for snapshot in (backtest_snapshot, publisher_snapshot)
            if snapshot.used + 1 > snapshot.limit
        ]
        if shortages:
            required_stops = []
            backtest_stop_count = max(
                backtest_snapshot.used + 1 - backtest_snapshot.limit,
                publisher_snapshot.used + 1 - publisher_snapshot.limit,
                0,
            )
            if backtest_stop_count > 0:
                required_stops.append(self._required_stop("backtest", backtest_stop_count))
            return TaskAdmissionDecision(
                allowed=False,
                reason=(
                    "Backtest capacity exhausted for "
                    + ", ".join(shortages)
                    + ". Stop running tasks or increase worker concurrency."
                ),
                details=(backtest_snapshot, publisher_snapshot),
                required_stops=tuple(required_stops),
            )

        return TaskAdmissionDecision(
            allowed=True,
            details=(backtest_snapshot, publisher_snapshot),
        )

    def _admit_trading(self, task: TradingTask) -> TaskAdmissionDecision:
        active_trading = self._queue_usage("trading")
        if active_trading is None:
            active_trading = TradingTask.objects.filter(status__in=ACTIVE_TASK_STATUSES).count()
        trading_snapshot = QueueCapacitySnapshot(
            queue="trading",
            used=active_trading,
            limit=int(getattr(settings, "CELERY_TRADING_WORKER_CONCURRENCY", 1)),
        )

        market_limit = int(getattr(settings, "CELERY_MARKET_WORKER_CONCURRENCY", 1))
        market_usage = self._queue_usage("market")
        active_publishers = self._fresh_market_tasks(
            task_name="market.tasks.publish_oanda_ticks"
        ).count()
        subscriber_running = self._fresh_market_tasks(
            task_name="market.tasks.subscribe_ticks_to_db"
        ).exists()
        account_id = getattr(task, "oanda_account_id", None)
        account_key = str(account_id) if account_id else ""
        publisher_exists_for_account = (
            self._fresh_market_tasks(task_name="market.tasks.publish_oanda_ticks")
            .filter(instance_key=account_key)
            .exists()
            if account_key
            else False
        )
        if market_usage is None:
            projected_market_usage = active_publishers
            if not publisher_exists_for_account:
                projected_market_usage += 1
            if not subscriber_running:
                projected_market_usage += 1
        else:
            projected_market_usage = market_usage
            if not publisher_exists_for_account:
                projected_market_usage += 1
            if not subscriber_running:
                projected_market_usage += 1

        market_snapshot = QueueCapacitySnapshot(
            queue="market",
            used=projected_market_usage,
            limit=market_limit,
        )

        shortages = []
        if trading_snapshot.used + 1 > trading_snapshot.limit:
            shortages.append("trading")
        if market_snapshot.used > market_snapshot.limit:
            shortages.append("market")

        if shortages:
            required_stops = []
            trading_stop_count = max(trading_snapshot.used + 1 - trading_snapshot.limit, 0)
            market_stop_count = max(market_snapshot.used - market_snapshot.limit, 0)
            if trading_stop_count > 0:
                required_stops.append(self._required_stop("trading", trading_stop_count))
            if market_stop_count > 0:
                required_stops.append(self._required_stop("market", market_stop_count))
            return TaskAdmissionDecision(
                allowed=False,
                reason=(
                    "Trading capacity exhausted for "
                    + ", ".join(shortages)
                    + ". Stop running tasks or increase worker concurrency."
                ),
                details=(trading_snapshot, market_snapshot),
                required_stops=tuple(required_stops),
            )

        return TaskAdmissionDecision(
            allowed=True,
            details=(trading_snapshot, market_snapshot),
        )
