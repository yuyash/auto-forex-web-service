"""Capacity planning and admission control for task execution."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.market.models import CeleryTaskStatus as MarketCeleryTaskStatus
from apps.trading.enums import TaskStatus
from apps.trading.models import BacktestTask, TradingTask


ACTIVE_TASK_STATUSES = (
    TaskStatus.STARTING,
    TaskStatus.RUNNING,
    TaskStatus.PAUSED,
    TaskStatus.STOPPING,
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


class TaskCapacityService:
    """Evaluate whether the system has capacity to start a task."""

    def get_task_admission(self, task: BacktestTask | TradingTask) -> TaskAdmissionDecision:
        if isinstance(task, BacktestTask):
            return self._admit_backtest()
        return self._admit_trading(task)

    def _admit_backtest(self) -> TaskAdmissionDecision:
        active_backtests = BacktestTask.objects.filter(status__in=ACTIVE_TASK_STATUSES).count()
        active_publishers = MarketCeleryTaskStatus.objects.filter(
            task_name="market.tasks.publish_ticks_for_backtest",
            status__in=ACTIVE_MARKET_STATUSES,
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
            return TaskAdmissionDecision(
                allowed=False,
                reason=(
                    "Backtest capacity exhausted for "
                    + ", ".join(shortages)
                    + ". Stop running tasks or increase worker concurrency."
                ),
                details=(backtest_snapshot, publisher_snapshot),
            )

        return TaskAdmissionDecision(
            allowed=True,
            details=(backtest_snapshot, publisher_snapshot),
        )

    def _admit_trading(self, task: TradingTask) -> TaskAdmissionDecision:
        active_trading = TradingTask.objects.filter(status__in=ACTIVE_TASK_STATUSES).count()
        trading_snapshot = QueueCapacitySnapshot(
            queue="trading",
            used=active_trading,
            limit=int(getattr(settings, "CELERY_TRADING_WORKER_CONCURRENCY", 1)),
        )

        market_limit = int(getattr(settings, "CELERY_MARKET_WORKER_CONCURRENCY", 1))
        active_publishers = MarketCeleryTaskStatus.objects.filter(
            task_name="market.tasks.publish_oanda_ticks",
            status__in=ACTIVE_MARKET_STATUSES,
        ).count()
        subscriber_running = MarketCeleryTaskStatus.objects.filter(
            task_name="market.tasks.subscribe_ticks_to_db",
            status__in=ACTIVE_MARKET_STATUSES,
        ).exists()
        account_id = getattr(task, "oanda_account_id", None)
        account_key = str(account_id) if account_id else ""
        publisher_exists_for_account = (
            MarketCeleryTaskStatus.objects.filter(
                task_name="market.tasks.publish_oanda_ticks",
                instance_key=account_key,
                status__in=ACTIVE_MARKET_STATUSES,
            ).exists()
            if account_key
            else False
        )
        projected_market_usage = active_publishers
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
            return TaskAdmissionDecision(
                allowed=False,
                reason=(
                    "Trading capacity exhausted for "
                    + ", ".join(shortages)
                    + ". Stop running tasks or increase worker concurrency."
                ),
                details=(trading_snapshot, market_snapshot),
            )

        return TaskAdmissionDecision(
            allowed=True,
            details=(trading_snapshot, market_snapshot),
        )
