"""Publisher task runner for streaming ticks to Redis."""

from __future__ import annotations

import json
import time
from logging import Logger, getLogger
from typing import Any

from celery import shared_task
from django.conf import settings

from apps.market.enums import ApiType
from apps.market.models import CeleryTaskStatus, OandaAccounts
from apps.market.services.celery import CeleryTaskService
from apps.market.services.oanda import OandaService
from apps.market.tasks.base import (
    acquire_lock,
    current_task_id,
    isoformat,
    lock_value,
    redis_client,
)

logger: Logger = getLogger(name=__name__)


@shared_task(bind=True, name="market.tasks.publish_oanda_ticks")
def publish_oanda_ticks(self: Any, account_id: int, instruments: list[str] | None = None) -> None:
    """Stream live pricing ticks from OANDA and publish to Redis pub/sub.

    Args:
        account_id: OANDA account ID
        instruments: List of instruments to stream (optional)
    """
    runner = TickPublisherRunner()
    runner.run(account_id, instruments)


class TickPublisherRunner:
    """Runner for OANDA tick publisher task."""

    def __init__(self) -> None:
        """Initialize the publisher runner."""
        self.task_service: CeleryTaskService | None = None
        self.account: OandaAccounts | None = None

    def run(self, account_id: int, instruments: list[str] | None = None) -> None:
        """Execute the tick publisher task.

        Args:
            account_id: OANDA account ID
            instruments: List of instruments to stream (optional)
        """
        task_name = "market.tasks.publish_oanda_ticks"
        instance_key = str(account_id)
        self.task_service = CeleryTaskService(
            task_name=task_name,
            instance_key=instance_key,
            stop_check_interval_seconds=1.0,
            heartbeat_interval_seconds=5.0,
        )
        self.task_service.start(
            celery_task_id=current_task_id(),
            worker=lock_value(),
            meta={"account_id": account_id},
        )

        redis_url = settings.MARKET_REDIS_URL
        channel = settings.MARKET_TICK_CHANNEL

        logger.info(
            "Starting OANDA tick publisher task (account_id=%s, channel=%s, redis=%s)",
            account_id,
            channel,
            redis_url,
        )

        client = redis_client()
        lock_key = getattr(settings, "MARKET_TICK_PUBLISHER_LOCK_KEY", "market:tick_publisher:lock")

        if self.task_service.should_stop(force=True):
            self._cleanup_and_stop(client, lock_key, "Stop requested")
            return

        if not acquire_lock(client, lock_key, ttl_seconds=60):
            logger.warning("Tick publisher already running (lock=%s)", lock_key)
            self._cleanup_and_stop(client, lock_key, "Already running")
            return

        # Validate account
        self.account = OandaAccounts.objects.filter(id=account_id).first()
        if not self._validate_account(client, lock_key, account_id):
            return

        instruments_list = instruments or getattr(settings, "MARKET_TICK_INSTRUMENTS", ["EUR_USD"])

        # Start streaming
        self._stream_ticks(client, lock_key, channel, instruments_list, account_id)

    def _validate_account(self, client: Any, lock_key: str, account_id: int) -> bool:
        """Validate account exists and is live."""
        if self.account is None:
            logger.error("Tick publisher cannot start: account %s not found", account_id)
            self._cleanup_and_stop(client, lock_key, "Account not found", failed=True)
            return False

        if self.account.api_type != ApiType.LIVE:
            logger.warning(
                "Tick publisher refusing to start for non-live account "
                "(account_id=%s, api_type=%s)",
                account_id,
                self.account.api_type,
            )
            self._cleanup_and_stop(client, lock_key, "Non-live account")
            return False

        return True

    def _stream_ticks(
        self,
        client: Any,
        lock_key: str,
        channel: str,
        instruments_list: list[str],
        account_id: int,
    ) -> None:
        """Stream ticks from OANDA to Redis."""
        assert self.account is not None
        assert self.task_service is not None

        ticks_published = 0
        try:
            while True:
                if self.task_service.should_stop():
                    logger.info(
                        "Stopping tick publisher due to stop request (account_id=%s)", account_id
                    )
                    break

                try:
                    # Refresh lock TTL periodically (best-effort).
                    client.expire(lock_key, 60)

                    service = OandaService(self.account)
                    for tick in service.stream_pricing_ticks(instruments_list, snapshot=True):
                        if self.task_service.should_stop():
                            break

                        payload = {
                            "instrument": str(tick.instrument),
                            "timestamp": isoformat(tick.timestamp),
                            "bid": str(tick.bid),
                            "ask": str(tick.ask),
                            "mid": str(tick.mid),
                        }
                        client.publish(channel, json.dumps(payload))
                        ticks_published += 1

                        if ticks_published % 1000 == 0:
                            logger.info(
                                "Published %s ticks (account_id=%s, channel=%s)",
                                ticks_published,
                                account_id,
                                channel,
                            )

                        if ticks_published % 250 == 0:
                            self.task_service.heartbeat(
                                status_message=f"published={ticks_published}",
                                meta_update={"published": ticks_published},
                            )
                            client.expire(lock_key, 60)

                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.exception("Tick publisher crashed; will retry in 5s: %s", exc)
                    self.task_service.heartbeat(status_message=f"error={str(exc)}", force=True)
                    time.sleep(5)

        finally:
            self._cleanup_and_stop(client, lock_key, f"published={ticks_published}")

    def _cleanup_and_stop(
        self, client: Any, lock_key: str, message: str, failed: bool = False
    ) -> None:
        """Cleanup resources and mark task as stopped."""
        try:
            client.delete(lock_key)
        except Exception:  # pylint: disable=broad-exception-caught
            pass
        try:
            client.close()
        except Exception:  # pylint: disable=broad-exception-caught
            pass

        if self.task_service:
            status_value = (
                CeleryTaskStatus.Status.FAILED if failed else CeleryTaskStatus.Status.STOPPED
            )
            self.task_service.mark_stopped(
                status=status_value,
                status_message=message,
            )


# Note: Singleton instance is created in __init__.py
