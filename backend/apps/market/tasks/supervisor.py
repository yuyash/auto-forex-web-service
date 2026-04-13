"""Supervisor task runner for managing tick pub/sub system."""

from __future__ import annotations

import contextlib
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.models import CeleryTaskStatus, OandaAccounts
from apps.market.services.celery import CeleryTaskService
from apps.market.tasks.publisher import publisher_lock_key_for_account
from apps.market.tasks.base import acquire_lock, current_task_id, lock_value, redis_client

logger: Logger = getLogger(name=__name__)


@shared_task(bind=True, name="market.tasks.ensure_tick_pubsub_running")
def ensure_tick_pubsub_running(self: Any) -> None:
    """Ensure the required publisher/subscriber tasks are active.

    Publishers are maintained per active trading account. The subscriber
    remains a singleton because it persists the shared market channel.
    This task re-schedules itself periodically and is also triggered on:
    - worker startup
    - OANDA account creation
    - trading-task starts
    """
    runner = TickSupervisorRunner()
    runner.run()


class TickSupervisorRunner:
    """Runner for tick pub/sub supervisor task."""

    def __init__(self) -> None:
        """Initialize the supervisor runner."""
        self.task_service: CeleryTaskService | None = None

    def run(self) -> None:
        """Execute the supervisor task."""
        # Import here to avoid circular dependency

        task_name = "market.tasks.ensure_tick_pubsub_running"
        instance_key = "supervisor"
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=5.0,
            heartbeat_interval_seconds=10.0,
        )
        self.task_service.start(
            celery_task_id=current_task_id(),
            worker=lock_value(),
            meta={"kind": "supervisor"},
        )

        logger.info("Supervisor starting (worker=%s)", lock_value())

        if self.task_service.should_stop(force=True):
            logger.info("Supervisor exiting: stop requested before main loop")
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.STOPPED,
                status_message="Stop requested",
            )
            return

        client = redis_client()

        interval_seconds = int(getattr(settings, "MARKET_TICK_SUPERVISOR_INTERVAL", 30))
        supervisor_lock = getattr(
            settings, "MARKET_TICK_SUPERVISOR_LOCK_KEY", "market:tick_supervisor:lock"
        )
        if not acquire_lock(client, supervisor_lock, ttl_seconds=interval_seconds + 30):
            logger.info(
                "Supervisor exiting: another instance holds the lock (lock=%s)", supervisor_lock
            )
            return

        stop_requested = False
        try:
            self.task_service.heartbeat(status_message="running", force=True)

            account_pks = self._target_account_pks()
            if not account_pks:
                logger.warning(
                    "Supervisor: no active trading-task accounts found — "
                    "tick streaming will stay idle until a trading task starts"
                )
            else:
                logger.info(
                    "Supervisor: ensuring tick publishers for account_pks=%s",
                    account_pks,
                )
                self._ensure_publishers_running(client, account_pks)

            # Check and restart subscriber if needed
            self._ensure_subscriber_running(client)

            # Best-effort cleanup of stale legacy single-account cache keys.
            account_key = getattr(settings, "MARKET_TICK_ACCOUNT_KEY", "market:tick_pubsub:account")
            init_key = getattr(settings, "MARKET_TICK_PUBSUB_INIT_KEY", "market:tick_pubsub:init")
            with contextlib.suppress(Exception):
                client.delete(account_key)
                client.delete(init_key)

        finally:
            with contextlib.suppress(Exception):
                client.close()

            assert self.task_service is not None
            stop_requested = self.task_service.should_stop(force=True)

        if stop_requested:
            logger.info("Supervisor exiting: stop requested after check cycle")
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.STOPPED,
                status_message="Stop requested",
            )
            return

        # Self-schedule: keeps pub/sub alive even if tasks crash.
        # Import the task function to schedule it
        from apps.market.tasks import ensure_tick_pubsub_running

        logger.info("Supervisor: scheduling next check in %ss", interval_seconds)
        ensure_tick_pubsub_running.apply_async(countdown=interval_seconds)

    def _target_account_pks(self) -> list[int]:
        """Return active OANDA account PKs required by active trading tasks."""
        from apps.trading.enums import TaskStatus as TradingTaskStatus

        active_statuses = (
            TradingTaskStatus.STARTING,
            TradingTaskStatus.RUNNING,
            TradingTaskStatus.PAUSED,
            TradingTaskStatus.STOPPING,
        )
        return list(
            OandaAccounts.objects.filter(
                is_active=True,
                trading_tasks__status__in=active_statuses,
            )
            .distinct()
            .order_by("created_at")
            .values_list("pk", flat=True)
        )

    def _ensure_publishers_running(self, client: Any, account_pks: list[int]) -> None:
        """Ensure account-specific publisher tasks are running."""
        from apps.market.tasks import publish_oanda_ticks

        for account_pk in account_pks:
            publisher_lock = publisher_lock_key_for_account(int(account_pk))
            publisher_alive = bool(client.exists(publisher_lock))
            logger.info(
                "Supervisor: publisher status for account_pk=%s is %s",
                account_pk,
                "running" if publisher_alive else "NOT running",
            )
            if not publisher_alive:
                logger.info(
                    "Supervisor: spawning publisher task (account_pk=%s)",
                    account_pk,
                )
                publish_oanda_ticks.delay(account_id=int(account_pk))

    def _ensure_subscriber_running(self, client: Any) -> None:
        """Ensure the shared DB subscriber task is running."""
        from apps.market.tasks import subscribe_ticks_to_db

        subscriber_lock = getattr(
            settings, "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock"
        )
        subscriber_alive = bool(client.exists(subscriber_lock))
        logger.info(
            "Supervisor: subscriber status is %s",
            "running" if subscriber_alive else "NOT running",
        )
        if not subscriber_alive:
            logger.info("Supervisor: spawning subscriber task")
            subscribe_ticks_to_db.delay()
