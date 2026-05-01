"""Celery tasks for OANDA account snapshot refreshes."""

from __future__ import annotations

from logging import getLogger

from celery import shared_task

from apps.market.models import OandaAccounts
from apps.market.services.accounts import refresh_oanda_account_snapshot

logger = getLogger(__name__)


@shared_task(name="market.tasks.refresh_oanda_account_snapshots")
def refresh_oanda_account_snapshots(account_id: int | None = None) -> dict[str, int]:
    """Refresh cached OANDA account snapshots for active accounts."""
    queryset = OandaAccounts.objects.filter(is_active=True).order_by("id")
    if account_id is not None:
        queryset = queryset.filter(pk=account_id)

    refreshed = 0
    failed = 0
    for account in queryset.iterator():
        try:
            refresh_oanda_account_snapshot(account)
            refreshed += 1
        except Exception:
            failed += 1
            logger.warning(
                "OANDA account snapshot refresh failed for account_id=%s",
                account.pk,
                exc_info=True,
            )

    return {"refreshed": refreshed, "failed": failed}
