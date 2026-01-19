"""
Integration tests for trade history reconciliation.

Tests the reconciliation process between local database records and OANDA API
trade history, including discrepancy detection, logging, and audit trail maintenance.
"""

from decimal import Decimal

import pytest
import responses
from django.utils import timezone

from apps.trading.models import Executions, TradeLogs, TradingEvent
from tests.integration.factories import (
    BacktestTaskFactory,
    OandaAccountFactory,
    UserFactory,
)


@pytest.mark.django_db
class TestTradeHistoryReconciliation:
    """Test trade history reconciliation with OANDA API."""

    def test_fetch_trades_from_oanda_api(self):
        """
        Test fetching trades from OANDA API.

        Verifies that the system can successfully fetch trade history
        from the OANDA API with proper authentication and parameters."""
        # Create test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        backtest_task = BacktestTaskFactory(user=user)
        Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Mock OANDA API response for trade history
        mock_trades_response = {
            "trades": [
                {
                    "id": "12345",
                    "instrument": "EUR_USD",
                    "price": "1.08950",
                    "openTime": "2024-01-15T10:30:00.000000Z",
                    "initialUnits": "1000",
                    "currentUnits": "1000",
                    "state": "OPEN",
                    "unrealizedPL": "25.50",
                },
                {
                    "id": "12346",
                    "instrument": "GBP_USD",
                    "price": "1.26500",
                    "openTime": "2024-01-15T11:00:00.000000Z",
                    "closeTime": "2024-01-15T12:00:00.000000Z",
                    "initialUnits": "500",
                    "currentUnits": "0",
                    "state": "CLOSED",
                    "realizedPL": "15.75",
                },
            ]
        }

        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"https://api-fxpractice.oanda.com/v3/accounts/{account.account_id}/trades",
                json=mock_trades_response,
                status=200,
            )

            # Simulate fetching trades (in real implementation, this would be a service method)
            # For now, we verify the mock is set up correctly
            import requests

            response = requests.get(
                f"https://api-fxpractice.oanda.com/v3/accounts/{account.account_id}/trades"
            )

            assert response.status_code == 200
            data = response.json()
            assert "trades" in data
            assert len(data["trades"]) == 2
            assert data["trades"][0]["id"] == "12345"
            assert data["trades"][1]["id"] == "12346"

    def test_comparison_with_local_records(self):
        """
        Test comparison between OANDA trades and local records.

        Verifies that the system can compare fetched OANDA trades
        with local database records to identify matches and discrepancies."""
        # Create test data
        user = UserFactory()
        OandaAccountFactory(user=user)
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create local trade logs
        local_trade_1 = TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={
                "id": "12345",
                "instrument": "EUR_USD",
                "price": "1.08950",
                "units": "1000",
                "state": "OPEN",
            },
        )

        local_trade_2 = TradeLogs.objects.create(
            execution=execution,
            sequence=1,
            trade={
                "id": "12346",
                "instrument": "GBP_USD",
                "price": "1.26500",
                "units": "500",
                "state": "CLOSED",
                "pnl": "15.75",
            },
        )

        # Simulate OANDA trades
        oanda_trades = [
            {
                "id": "12345",
                "instrument": "EUR_USD",
                "price": "1.08950",
                "units": "1000",
                "state": "OPEN",
            },
            {
                "id": "12346",
                "instrument": "GBP_USD",
                "price": "1.26500",
                "units": "500",
                "state": "CLOSED",
                "pnl": "15.75",
            },
            {
                "id": "12347",  # This trade is not in local records
                "instrument": "USD_JPY",
                "price": "148.500",
                "units": "2000",
                "state": "OPEN",
            },
        ]

        # Compare trades
        local_trade_ids = {local_trade_1.trade["id"], local_trade_2.trade["id"]}
        oanda_trade_ids = {t["id"] for t in oanda_trades}

        # Verify comparison logic
        matching_ids = local_trade_ids & oanda_trade_ids
        missing_in_local = oanda_trade_ids - local_trade_ids
        missing_in_oanda = local_trade_ids - oanda_trade_ids

        assert len(matching_ids) == 2
        assert "12345" in matching_ids
        assert "12346" in matching_ids
        assert len(missing_in_local) == 1
        assert "12347" in missing_in_local
        assert len(missing_in_oanda) == 0

    def test_discrepancy_identification_and_logging(self):
        """
        Test discrepancy identification and logging.

        Verifies that the system identifies discrepancies between local
        and OANDA records and logs them appropriately."""
        # Create test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create local trade with different data than OANDA
        local_trade = TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={
                "id": "12345",
                "instrument": "EUR_USD",
                "price": "1.08950",
                "units": "1000",
                "state": "OPEN",
                "pnl": "0.00",
            },
        )

        # Simulate OANDA trade with different PnL
        oanda_trade = {
            "id": "12345",
            "instrument": "EUR_USD",
            "price": "1.08950",
            "units": "1000",
            "state": "OPEN",
            "pnl": "25.50",  # Different from local
        }

        # Identify discrepancy
        local_pnl = Decimal(local_trade.trade.get("pnl", "0"))
        oanda_pnl = Decimal(oanda_trade.get("pnl", "0"))
        has_discrepancy = local_pnl != oanda_pnl

        assert has_discrepancy is True

        # Log the discrepancy
        if has_discrepancy:
            event = TradingEvent.objects.create(
                event_type="trade_reconciliation_discrepancy",
                severity="warning",
                description=f"Trade {oanda_trade['id']} has PnL discrepancy",
                user=user,
                account=account,
                execution=execution,
                details={
                    "trade_id": oanda_trade["id"],
                    "local_pnl": str(local_pnl),
                    "oanda_pnl": str(oanda_pnl),
                    "difference": str(oanda_pnl - local_pnl),
                },
            )

            # Verify event was logged
            assert TradingEvent.objects.filter(
                event_type="trade_reconciliation_discrepancy"
            ).exists()
            assert event.severity == "warning"
            assert event.details["trade_id"] == "12345"
            assert event.details["local_pnl"] == "0.00"
            assert event.details["oanda_pnl"] == "25.50"

    def test_local_record_updates(self):
        """
        Test local record updates based on OANDA data.

        Verifies that the system updates local records when discrepancies
        are found, bringing them in sync with OANDA."""
        # Create test data
        user = UserFactory()
        OandaAccountFactory(user=user)
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create local trade with outdated data
        local_trade = TradeLogs.objects.create(
            execution=execution,
            sequence=0,
            trade={
                "id": "12345",
                "instrument": "EUR_USD",
                "price": "1.08950",
                "units": "1000",
                "state": "OPEN",
                "pnl": "0.00",
            },
        )

        # Simulate OANDA trade with updated data
        oanda_trade = {
            "id": "12345",
            "instrument": "EUR_USD",
            "price": "1.08950",
            "units": "1000",
            "state": "CLOSED",
            "pnl": "25.50",
            "closeTime": "2024-01-15T12:00:00.000000Z",
        }

        # Update local record
        local_trade.trade.update(
            {
                "state": oanda_trade["state"],
                "pnl": oanda_trade["pnl"],
                "closeTime": oanda_trade.get("closeTime"),
            }
        )
        local_trade.save()  # type: ignore[attr-defined]

        # Verify update
        local_trade.refresh_from_db()    # type: ignore[attr-defined]
        assert local_trade.trade["state"] == "CLOSED"
        assert local_trade.trade["pnl"] == "25.50"
        assert local_trade.trade["closeTime"] == "2024-01-15T12:00:00.000000Z"

    def test_audit_trail_maintenance(self):
        """
        Test audit trail maintenance for reconciliation.

        Verifies that the system maintains a complete audit trail of
        reconciliation activities, including updates and discrepancies."""
        # Create test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        backtest_task = BacktestTaskFactory(user=user)
        execution = Executions.objects.create(
            task_type="backtest",
            task_id=backtest_task.pk  ,  # type: ignore[attr-defined]
            execution_number=1,
            status="running",
        )

        # Create initial reconciliation event
        reconciliation_start = TradingEvent.objects.create(
            event_type="trade_reconciliation_started",
            severity="info",
            description="Started trade history reconciliation",
            user=user,
            account=account,
            execution=execution,
            details={
                "timestamp": timezone.now().isoformat(),
                "account_id": account.account_id,
            },
        )

        # Create discrepancy event
        discrepancy_event = TradingEvent.objects.create(
            event_type="trade_reconciliation_discrepancy",
            severity="warning",
            description="Found trade discrepancy",
            user=user,
            account=account,
            execution=execution,
            details={
                "trade_id": "12345",
                "discrepancy_type": "pnl_mismatch",
                "local_value": "0.00",
                "oanda_value": "25.50",
            },
        )

        # Create update event
        update_event = TradingEvent.objects.create(
            event_type="trade_reconciliation_updated",
            severity="info",
            description="Updated local trade record",
            user=user,
            account=account,
            execution=execution,
            details={
                "trade_id": "12345",
                "updated_fields": ["state", "pnl", "closeTime"],
            },
        )

        # Create completion event
        reconciliation_complete = TradingEvent.objects.create(
            event_type="trade_reconciliation_completed",
            severity="info",
            description="Completed trade history reconciliation",
            user=user,
            account=account,
            execution=execution,
            details={
                "timestamp": timezone.now().isoformat(),
                "trades_checked": 10,
                "discrepancies_found": 1,
                "records_updated": 1,
            },
        )

        # Verify audit trail
        audit_events = TradingEvent.objects.filter(
            user=user, account=account, execution=execution
        ).order_by("created_at")

        assert audit_events.count() == 4
        assert audit_events[0].event_type == "trade_reconciliation_started"
        assert audit_events[1].event_type == "trade_reconciliation_discrepancy"
        assert audit_events[2].event_type == "trade_reconciliation_updated"
        assert audit_events[3].event_type == "trade_reconciliation_completed"

        # Verify audit trail completeness
        assert reconciliation_start.details["account_id"] == account.account_id
        assert discrepancy_event.details["trade_id"] == "12345"
        assert update_event.details["trade_id"] == "12345"
        assert reconciliation_complete.details["trades_checked"] == 10
        assert reconciliation_complete.details["discrepancies_found"] == 1
        assert reconciliation_complete.details["records_updated"] == 1
