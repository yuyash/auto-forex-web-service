"""Supervisor task runner for managing tick pub/sub system."""

from __future__ import annotations

import contextlib
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts
from apps.market.services.celery import CeleryTaskService
from apps.market.tasks.base import acquire_lock, current_task_id, lock_value, redis_client

logger: Logger = getLogger(name=__name__)


@shared_task(bind=True, name="market.tasks.ensure_tick_pubsub_running")
def ensure_tick_pubsub_running(self: Any) -> None:
    """Ensure there is exactly one active publisher/subscriber pair.

    If either side isn't running (lock missing), re-creates the task.
    This task re-schedules itself periodically and is also triggered on:
    - worker startup
    - first LIVE OANDA account creation
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

        if self.task_service.should_stop(force=True):
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
            return

        stop_requested = False
        try:
            self.task_service.heartbeat(status_message="running", force=True)

            # Get or initialize account
            account = self._get_or_initialize_account(client)
            if account is None:
                return

            account_pk = int(account.pk)

            if account.api_type != ApiType.LIVE:
                # If the stored account was changed to non-live, do nothing.
                return

            # Check and restart publisher/subscriber if needed
            self._ensure_tasks_running(client, account_pk)

        finally:
            with contextlib.suppress(Exception):
                client.close()

            assert self.task_service is not None
            stop_requested = self.task_service.should_stop(force=True)

        if stop_requested:
            self.task_service.mark_stopped(
                status=CeleryTaskStatus.Status.STOPPED,
                status_message="Stop requested",
            )
            return

        # Self-schedule: keeps pub/sub alive even if tasks crash.
        # Import the task function to schedule it
        from apps.market.tasks import ensure_tick_pubsub_running

        ensure_tick_pubsub_running.apply_async(countdown=interval_seconds)

    def _get_or_initialize_account(self, client: Any) -> OandaAccounts | None:
        """Get or initialize the OANDA account for tick streaming."""
        account_key = getattr(settings, "MARKET_TICK_ACCOUNT_KEY", "market:tick_pubsub:account")
        init_key = getattr(settings, "MARKET_TICK_PUBSUB_INIT_KEY", "market:tick_pubsub:init")

        account_id_raw = client.get(account_key)
        account: OandaAccounts | None = None

        if account_id_raw:
            try:
                account_id = int(str(account_id_raw))
                account = OandaAccounts.objects.filter(id=account_id).first()
            except Exception:  # pylint: disable=broad-exception-caught
                account = None

        if account is None:
            account = (
                OandaAccounts.objects.filter(api_type=ApiType.LIVE).order_by("created_at").first()
            )
            if account is None:
                return None

            account_pk = int(account.pk)

            # Persist the "first live" account id exactly once.
            client.setnx(account_key, str(account_pk))
            client.setnx(init_key, "1")

        return account

    def _ensure_tasks_running(
        self,
        client: Any,
        account_pk: int,
    ) -> None:
        """Ensure publisher and subscriber tasks are running."""
        # Import here to avoid circular dependency at module level
        from apps.market.tasks import publish_oanda_ticks, subscribe_ticks_to_db

        publisher_lock = getattr(
            settings, "MARKET_TICK_PUBLISHER_LOCK_KEY", "market:tick_publisher:lock"
        )
        subscriber_lock = getattr(
            settings, "MARKET_TICK_SUBSCRIBER_LOCK_KEY", "market:tick_subscriber:lock"
        )

        if not client.exists(publisher_lock):
            logger.info(
                "Registering publisher celery task (account_id=%s)",
                account_pk,
            )
            publish_oanda_ticks.delay(account_id=account_pk)

        if not client.exists(subscriber_lock):
            logger.info("Creating subscriber celery task")
            subscribe_ticks_to_db.delay()
