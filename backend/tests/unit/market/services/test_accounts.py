from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.market.services.accounts import (
    apply_cached_oanda_account_snapshot,
    create_oanda_account,
    delete_oanda_account,
    enqueue_oanda_account_snapshot_refresh,
    is_oanda_account_snapshot_stale,
    refresh_oanda_account_snapshot,
    update_oanda_account,
)
from apps.market.services.oanda import AccountDetails, OandaAPIError


class TestMarketAccountService:
    def test_create_oanda_account_uses_serializer_save(self) -> None:
        serializer = MagicMock()
        account = MagicMock()
        serializer.save.return_value = account

        result = create_oanda_account(serializer)

        serializer.save.assert_called_once_with()
        assert result is account

    def test_update_oanda_account_uses_serializer_save(self) -> None:
        serializer = MagicMock()
        account = MagicMock()
        serializer.save.return_value = account

        result = update_oanda_account(serializer)

        serializer.save.assert_called_once_with()
        assert result is account

    def test_delete_oanda_account_uses_model_delete(self) -> None:
        account = MagicMock()

        delete_oanda_account(account)

        account.delete.assert_called_once_with()

    def test_enqueue_oanda_account_snapshot_refresh_queues_market_task(self) -> None:
        account = MagicMock()
        account.pk = 123

        with (
            patch(
                "apps.market.tasks.accounts.refresh_oanda_account_snapshots.apply_async"
            ) as apply_async,
            patch("apps.market.services.accounts.uuid4", return_value="task-123"),
        ):
            task_id = enqueue_oanda_account_snapshot_refresh(account)

        assert task_id == "task-123"
        assert account.snapshot_refresh_task_id == "task-123"
        assert account.snapshot_refresh_status == "queued"
        assert account.snapshot_refresh_error == ""
        account.save.assert_called_once_with(
            update_fields=[
                "snapshot_refresh_task_id",
                "snapshot_refresh_status",
                "snapshot_refresh_error",
                "updated_at",
            ]
        )
        apply_async.assert_called_once_with(
            kwargs={"account_id": 123},
            queue="market",
            task_id="task-123",
        )

    def test_apply_cached_snapshot_marks_missing_snapshot_stale(self) -> None:
        account = MagicMock()
        account.snapshot_refreshed_at = None
        account.snapshot_refresh_error = ""
        account.hedging_enabled = None

        data: dict[str, object] = {}

        apply_cached_oanda_account_snapshot(account=account, response_data=data)

        assert data["live_data"] is False
        assert data["snapshot_stale"] is True
        assert "position_mode" not in data

    def test_apply_cached_snapshot_includes_position_mode(self) -> None:
        account = MagicMock()
        account.snapshot_refreshed_at = timezone.now()
        account.snapshot_refresh_error = ""
        account.hedging_enabled = False

        data: dict[str, object] = {}

        apply_cached_oanda_account_snapshot(account=account, response_data=data)

        assert data["live_data"] is True
        assert data["snapshot_stale"] is False
        assert data["position_mode"] == "netting"

    def test_snapshot_stale_after_configured_age(self, settings) -> None:
        settings.OANDA_ACCOUNT_SNAPSHOT_STALE_SECONDS = 60
        account = MagicMock()
        account.snapshot_refreshed_at = timezone.now() - timedelta(seconds=61)

        assert is_oanda_account_snapshot_stale(account) is True

    def test_refresh_oanda_account_snapshot_updates_cached_fields(self) -> None:
        account = MagicMock()
        details = AccountDetails(
            account_id="101-001-1234567-001",
            currency="USD",
            balance=Decimal("12000"),
            nav=Decimal("12100"),
            unrealized_pl=Decimal("100"),
            margin_used=Decimal("200"),
            margin_available=Decimal("11800"),
            position_value=Decimal("4000"),
            open_trade_count=2,
            open_position_count=1,
            pending_order_count=3,
            last_transaction_id="42",
        )

        service = MagicMock()
        service.get_account_details.return_value = details
        service.get_account_resource.return_value = {"hedgingEnabled": True}

        with patch("apps.market.services.accounts.OandaService", return_value=service):
            result = refresh_oanda_account_snapshot(account)

        assert result is account
        assert account.balance == Decimal("12000")
        assert account.nav == Decimal("12100")
        assert account.open_trade_count == 2
        assert account.hedging_enabled is True
        assert account.snapshot_refresh_error == ""
        account.save.assert_called_once()
        assert "snapshot_refreshed_at" in account.save.call_args.kwargs["update_fields"]

    def test_refresh_oanda_account_snapshot_records_safe_error(self) -> None:
        account = MagicMock()
        account.account_id = "101-001-1234567-001"

        service = MagicMock()
        service.get_account_details.side_effect = OandaAPIError("broker unavailable")

        with patch("apps.market.services.accounts.OandaService", return_value=service):
            with pytest.raises(OandaAPIError):
                refresh_oanda_account_snapshot(account)

        assert account.snapshot_refresh_error == "broker unavailable"
        account.save.assert_called_once_with(update_fields=["snapshot_refresh_error", "updated_at"])
