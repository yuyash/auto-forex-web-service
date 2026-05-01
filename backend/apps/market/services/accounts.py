"""Service helpers for OANDA account mutations and cached snapshots."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import timedelta
from logging import getLogger
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.market.models import OandaAccounts
from apps.market.serializers import OandaAccountsSerializer
from apps.market.services.oanda import OandaAPIError, OandaService

logger = getLogger(__name__)

SNAPSHOT_UPDATE_FIELDS = [
    "currency",
    "balance",
    "margin_used",
    "margin_available",
    "unrealized_pnl",
    "nav",
    "open_trade_count",
    "open_position_count",
    "pending_order_count",
    "hedging_enabled",
    "snapshot_refreshed_at",
    "snapshot_refresh_error",
    "updated_at",
]


SNAPSHOT_REFRESH_STATUS_UPDATE_FIELDS = [
    "snapshot_refresh_task_id",
    "snapshot_refresh_status",
    "snapshot_refresh_status_updated_at",
    "snapshot_refresh_error",
    "updated_at",
]


ACTIVE_SNAPSHOT_REFRESH_STATUSES = frozenset(
    {
        OandaAccounts.SnapshotRefreshStatus.QUEUED,
        OandaAccounts.SnapshotRefreshStatus.RUNNING,
    }
)


def create_oanda_account(serializer: OandaAccountsSerializer) -> OandaAccounts:
    """Persist a new OANDA account from a validated serializer."""
    return serializer.save()


def update_oanda_account(serializer: OandaAccountsSerializer) -> OandaAccounts:
    """Persist OANDA account updates from a validated serializer."""
    return serializer.save()


def delete_oanda_account(account: OandaAccounts) -> None:
    """Delete an OANDA account through a shared mutation path."""
    account.delete()


def enqueue_oanda_account_snapshot_refresh(account: OandaAccounts) -> str:
    """Queue or reuse an asynchronous refresh for a single OANDA account snapshot."""
    from apps.market.tasks.accounts import refresh_oanda_account_snapshots

    task_id = str(uuid4())
    with transaction.atomic():
        locked_account = OandaAccounts.objects.select_for_update().get(pk=account.pk)
        if has_active_oanda_account_snapshot_refresh(locked_account):
            _copy_snapshot_refresh_state(source=locked_account, target=account)
            return locked_account.snapshot_refresh_task_id

        mark_oanda_account_snapshot_refresh_queued(locked_account, task_id)
        _copy_snapshot_refresh_state(source=locked_account, target=account)

    try:
        refresh_oanda_account_snapshots.apply_async(
            kwargs={"account_id": account.pk},
            queue="market",
            task_id=task_id,
        )
    except Exception:
        account.snapshot_refresh_status = OandaAccounts.SnapshotRefreshStatus.FAILED
        account.snapshot_refresh_status_updated_at = timezone.now()
        account.snapshot_refresh_error = "Failed to queue account snapshot refresh."
        account.save(
            update_fields=[
                "snapshot_refresh_status",
                "snapshot_refresh_status_updated_at",
                "snapshot_refresh_error",
                "updated_at",
            ]
        )
        raise
    return task_id


def has_active_oanda_account_snapshot_refresh(account: OandaAccounts) -> bool:
    """Return whether a manual refresh is already queued or running."""
    return (
        bool(account.snapshot_refresh_task_id)
        and account.snapshot_refresh_status in ACTIVE_SNAPSHOT_REFRESH_STATUSES
        and not is_oanda_account_snapshot_refresh_expired(account)
    )


def is_oanda_account_snapshot_refresh_expired(account: OandaAccounts) -> bool:
    """Return whether an active manual refresh record is old enough to replace."""
    if account.snapshot_refresh_status not in ACTIVE_SNAPSHOT_REFRESH_STATUSES:
        return False

    ttl_seconds = int(getattr(settings, "OANDA_ACCOUNT_SNAPSHOT_REFRESH_ACTIVE_TTL_SECONDS", 900))
    if ttl_seconds <= 0:
        return False

    updated_at = account.snapshot_refresh_status_updated_at
    if updated_at is None:
        return True

    return updated_at < timezone.now() - timedelta(seconds=ttl_seconds)


def _copy_snapshot_refresh_state(
    *,
    source: OandaAccounts,
    target: OandaAccounts,
) -> None:
    target.snapshot_refresh_task_id = source.snapshot_refresh_task_id
    target.snapshot_refresh_status = source.snapshot_refresh_status
    target.snapshot_refresh_status_updated_at = source.snapshot_refresh_status_updated_at
    target.snapshot_refresh_error = source.snapshot_refresh_error


def mark_oanda_account_snapshot_refresh_queued(
    account: OandaAccounts,
    task_id: str,
) -> None:
    """Persist that a manual account snapshot refresh has been queued."""
    account.snapshot_refresh_task_id = task_id
    account.snapshot_refresh_status = OandaAccounts.SnapshotRefreshStatus.QUEUED
    account.snapshot_refresh_status_updated_at = timezone.now()
    account.snapshot_refresh_error = ""
    account.save(update_fields=SNAPSHOT_REFRESH_STATUS_UPDATE_FIELDS)


def mark_oanda_account_snapshot_refresh_running(
    account: OandaAccounts,
    task_id: str,
) -> None:
    """Persist that a manual account snapshot refresh has started."""
    _mark_oanda_account_snapshot_refresh_status(
        account=account,
        task_id=task_id,
        refresh_status=OandaAccounts.SnapshotRefreshStatus.RUNNING,
    )


def mark_oanda_account_snapshot_refresh_completed(
    account: OandaAccounts,
    task_id: str,
) -> None:
    """Persist that a manual account snapshot refresh finished successfully."""
    _mark_oanda_account_snapshot_refresh_status(
        account=account,
        task_id=task_id,
        refresh_status=OandaAccounts.SnapshotRefreshStatus.COMPLETED,
    )


def mark_oanda_account_snapshot_refresh_failed(
    account: OandaAccounts,
    task_id: str,
) -> None:
    """Persist that a manual account snapshot refresh finished unsuccessfully."""
    _mark_oanda_account_snapshot_refresh_status(
        account=account,
        task_id=task_id,
        refresh_status=OandaAccounts.SnapshotRefreshStatus.FAILED,
    )


def _mark_oanda_account_snapshot_refresh_status(
    *,
    account: OandaAccounts,
    task_id: str,
    refresh_status: OandaAccounts.SnapshotRefreshStatus,
) -> None:
    if task_id and account.snapshot_refresh_task_id and account.snapshot_refresh_task_id != task_id:
        return

    update_fields = [
        "snapshot_refresh_status",
        "snapshot_refresh_status_updated_at",
        "updated_at",
    ]
    if task_id and not account.snapshot_refresh_task_id:
        account.snapshot_refresh_task_id = task_id
        update_fields.append("snapshot_refresh_task_id")
    account.snapshot_refresh_status = refresh_status
    account.snapshot_refresh_status_updated_at = timezone.now()
    account.save(update_fields=update_fields)


def apply_cached_oanda_account_snapshot(
    *,
    account: OandaAccounts,
    response_data: MutableMapping[str, Any],
) -> None:
    """Populate response-only snapshot status from persisted OANDA account data."""
    has_snapshot = account.snapshot_refreshed_at is not None
    is_stale = is_oanda_account_snapshot_stale(account)

    response_data["live_data"] = has_snapshot and not bool(account.snapshot_refresh_error)
    response_data["snapshot_stale"] = is_stale

    if account.snapshot_refresh_error:
        response_data["live_data_error"] = account.snapshot_refresh_error

    if account.hedging_enabled is not None:
        response_data["position_mode"] = "hedging" if account.hedging_enabled else "netting"


def is_oanda_account_snapshot_stale(account: OandaAccounts) -> bool:
    """Return whether the cached snapshot should be considered stale."""
    if account.snapshot_refreshed_at is None:
        return True

    stale_seconds = int(getattr(settings, "OANDA_ACCOUNT_SNAPSHOT_STALE_SECONDS", 300))
    if stale_seconds <= 0:
        return False

    stale_before = timezone.now() - timedelta(seconds=stale_seconds)
    return account.snapshot_refreshed_at < stale_before


def refresh_oanda_account_snapshot(account: OandaAccounts) -> OandaAccounts:
    """Fetch OANDA account data and persist it outside the request path."""
    try:
        client = OandaService(account)
        live_data = client.get_account_details()
        account_resource = client.get_account_resource()
    except Exception as exc:
        _record_snapshot_refresh_error(account, exc)
        raise

    account.currency = live_data.currency
    account.balance = live_data.balance
    account.margin_used = live_data.margin_used
    account.margin_available = live_data.margin_available
    account.unrealized_pnl = live_data.unrealized_pl
    account.nav = live_data.nav
    account.open_trade_count = live_data.open_trade_count
    account.open_position_count = live_data.open_position_count
    account.pending_order_count = live_data.pending_order_count
    account.hedging_enabled = bool(account_resource.get("hedgingEnabled", False))
    account.snapshot_refreshed_at = timezone.now()
    account.snapshot_refresh_error = ""
    account.save(update_fields=SNAPSHOT_UPDATE_FIELDS)
    return account


def _record_snapshot_refresh_error(account: OandaAccounts, exc: Exception) -> None:
    error_message = _safe_snapshot_error_message(exc)
    account.snapshot_refresh_error = error_message
    account.save(update_fields=["snapshot_refresh_error", "updated_at"])
    logger.warning(
        "Failed to refresh OANDA account snapshot for %s: %s",
        account.account_id,
        str(exc),
    )


def _safe_snapshot_error_message(exc: Exception) -> str:
    if isinstance(exc, OandaAPIError):
        message = str(exc) or "Failed to fetch account snapshot"
    else:
        message = "Failed to fetch account snapshot"
    return message[:255]
