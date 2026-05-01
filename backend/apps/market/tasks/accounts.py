"""Celery tasks for OANDA account snapshot refreshes."""

from __future__ import annotations

from logging import getLogger

from celery import shared_task

from apps.market.models import OandaAccounts
from apps.market.services.accounts import (
    mark_oanda_account_snapshot_refresh_completed,
    mark_oanda_account_snapshot_refresh_failed,
    mark_oanda_account_snapshot_refresh_running,
    refresh_oanda_account_snapshot,
)

logger = getLogger(__name__)


@shared_task(bind=True, name="market.tasks.refresh_oanda_account_snapshots")
def refresh_oanda_account_snapshots(self, account_id: int | None = None) -> dict[str, int]:
    """Refresh cached OANDA account snapshots for active accounts."""
    queryset = OandaAccounts.objects.filter(is_active=True).order_by("id")
    if account_id is not None:
        queryset = queryset.filter(pk=account_id)

    task_id = str(getattr(getattr(self, "request", None), "id", "") or "")
    refreshed = 0
    failed = 0
    for account in queryset.iterator():
        if account_id is not None:
            mark_oanda_account_snapshot_refresh_running(account, task_id)
        try:
            refresh_oanda_account_snapshot(account)
            refreshed += 1
        except Exception:
            failed += 1
            if account_id is not None:
                mark_oanda_account_snapshot_refresh_failed(account, task_id)
            logger.warning(
                "OANDA account snapshot refresh failed for account_id=%s",
                account.pk,
                exc_info=True,
            )
        else:
            if account_id is not None:
                mark_oanda_account_snapshot_refresh_completed(account, task_id)

    return {"refreshed": refreshed, "failed": failed}
