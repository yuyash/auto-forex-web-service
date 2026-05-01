"""Tests for market account snapshot Celery tasks."""

import logging
from unittest.mock import patch

import pytest

from apps.market.enums import ApiType
from apps.market.models import OandaAccounts
from apps.market.tasks.accounts import refresh_oanda_account_snapshots


@pytest.mark.django_db
class TestRefreshOandaAccountSnapshots:
    def test_refreshes_active_accounts_only(self, user) -> None:
        active = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-001",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-002",
            api_type=ApiType.PRACTICE,
            is_active=False,
        )

        with patch("apps.market.tasks.accounts.refresh_oanda_account_snapshot") as refresh:
            result = refresh_oanda_account_snapshots()

        assert result == {"refreshed": 1, "failed": 0}
        refresh.assert_called_once()
        assert refresh.call_args.args[0].pk == active.pk

    def test_counts_refresh_failures(self, user) -> None:
        OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-003",
            api_type=ApiType.PRACTICE,
            is_active=True,
        )

        with patch(
            "apps.market.tasks.accounts.refresh_oanda_account_snapshot",
            side_effect=RuntimeError("fail"),
        ):
            result = refresh_oanda_account_snapshots()

        assert result == {"refreshed": 0, "failed": 1}

    def test_single_account_refresh_marks_completed(self, user, caplog) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-004",
            api_type=ApiType.PRACTICE,
            is_active=True,
            snapshot_refresh_task_id="task-123",
            snapshot_refresh_status=OandaAccounts.SnapshotRefreshStatus.QUEUED,
        )

        with caplog.at_level(logging.INFO, logger="apps.market.services.accounts"):
            with patch("apps.market.tasks.accounts.refresh_oanda_account_snapshot"):
                result = refresh_oanda_account_snapshots(account_id=account.pk)

        account.refresh_from_db()
        assert result == {"refreshed": 1, "failed": 0}
        assert account.snapshot_refresh_status == OandaAccounts.SnapshotRefreshStatus.COMPLETED
        completed_events = [
            record
            for record in caplog.records
            if getattr(record, "event", "") == "oanda_account_snapshot_refresh_completed"
        ]
        assert len(completed_events) == 1
        assert completed_events[0].task_id

    def test_single_account_refresh_marks_failed(self, user, caplog) -> None:
        account = OandaAccounts.objects.create(
            user=user,
            account_id="101-001-1234567-005",
            api_type=ApiType.PRACTICE,
            is_active=True,
            snapshot_refresh_task_id="task-123",
            snapshot_refresh_status=OandaAccounts.SnapshotRefreshStatus.QUEUED,
        )

        with caplog.at_level(logging.INFO, logger="apps.market.services.accounts"):
            with patch(
                "apps.market.tasks.accounts.refresh_oanda_account_snapshot",
                side_effect=RuntimeError("fail"),
            ):
                result = refresh_oanda_account_snapshots(account_id=account.pk)

        account.refresh_from_db()
        assert result == {"refreshed": 0, "failed": 1}
        assert account.snapshot_refresh_status == OandaAccounts.SnapshotRefreshStatus.FAILED
        failed_events = [
            record
            for record in caplog.records
            if getattr(record, "event", "") == "oanda_account_snapshot_refresh_failed"
        ]
        assert len(failed_events) == 1
        assert failed_events[0].task_id
