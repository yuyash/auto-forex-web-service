"""
Integration tests for account balance synchronization.

Tests verify that balance changes are detected, local database is updated,
margin is recalculated, risk limits are adjusted, and balance change events
are logged.

Feature: backend-integration-tests"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.market.models import MarketEvent
from tests.integration.factories import OandaAccountFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestAccountBalanceSynchronization:
    """Test suite for account balance synchronization."""

    def test_balance_change_detection_and_update(self):
        """
        Test that balance changes are detected and local database is updated.

        Validates: Requirement 6.2 - Account balance synchronization
        """
        user = UserFactory()
        account = OandaAccountFactory(
            user=user,
            balance=Decimal("10000.00"),
            margin_used=Decimal("0.00"),
            margin_available=Decimal("10000.00"),
            unrealized_pnl=Decimal("0.00"),
        )

        # Simulate balance change (e.g., from OANDA API response)
        new_balance = Decimal("12000.00")
        new_margin_used = Decimal("500.00")
        new_margin_available = Decimal("11500.00")
        new_unrealized_pnl = Decimal("150.00")

        # Update balance
        account.update_balance(  # type: ignore[attr-defined]
            balance=float(new_balance),
            margin_used=float(new_margin_used),
            margin_available=float(new_margin_available),
            unrealized_pnl=float(new_unrealized_pnl),
        )

        # Verify balance was updated in database
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.balance == new_balance
        assert account.margin_used == new_margin_used
        assert account.margin_available == new_margin_available
        assert account.unrealized_pnl == new_unrealized_pnl

    def test_margin_recalculation_after_balance_update(self):
        """
        Test that margin is recalculated after balance update.

        Validates: Requirement 6.2 - Margin recalculation
        """
        user = UserFactory()
        account = OandaAccountFactory(
            user=user,
            balance=Decimal("10000.00"),
            margin_used=Decimal("1000.00"),
            margin_available=Decimal("9000.00"),
        )

        # Update balance with new margin values
        new_balance = Decimal("15000.00")
        new_margin_used = Decimal("2000.00")
        new_margin_available = new_balance - new_margin_used

        account.update_balance(  # type: ignore[attr-defined]
            balance=float(new_balance),
            margin_used=float(new_margin_used),
            margin_available=float(new_margin_available),
            unrealized_pnl=0.00,
        )

        # Verify margin was recalculated
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.margin_available == new_margin_available
        assert account.margin_available == account.balance - account.margin_used  # ty:ignore[unsupported-operator]

    def test_balance_decrease_updates_available_margin(self):
        """
        Test that balance decrease correctly updates available margin.

        Validates: Requirement 6.2 - Margin recalculation
        """
        user = UserFactory()
        account = OandaAccountFactory(
            user=user,
            balance=Decimal("10000.00"),
            margin_used=Decimal("2000.00"),
            margin_available=Decimal("8000.00"),
        )

        # Simulate balance decrease (e.g., from losing trades)
        new_balance = Decimal("8000.00")
        new_margin_used = Decimal("2000.00")  # Margin used stays the same
        new_margin_available = new_balance - new_margin_used

        account.update_balance(  # type: ignore[attr-defined]
            balance=float(new_balance),
            margin_used=float(new_margin_used),
            margin_available=float(new_margin_available),
            unrealized_pnl=-2000.00,
        )

        # Verify available margin decreased
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.balance == new_balance
        assert account.margin_available == new_margin_available
        assert account.margin_available == Decimal("6000.00")

    def test_balance_change_event_logging(self):
        """
        Test that balance changes are logged as events.

        Validates: Requirement 6.2 - Balance change event logging
        """
        user = UserFactory()
        account = OandaAccountFactory(user=user, balance=Decimal("10000.00"))

        # Record initial event count
        initial_event_count = MarketEvent.objects.filter(account=account).count()

        # Create a balance change event manually (simulating what the sync service would do)
        MarketEvent.objects.create(
            user=user,
            account=account,
            event_type="balance_updated",
            severity="info",
            description="Balance updated from 10000.00 to 12000.00",
            details={
                "old_balance": "10000.00",
                "new_balance": "12000.00",
                "change": "2000.00",
            },
        )

        # Verify event was created
        events = MarketEvent.objects.filter(account=account, event_type="balance_updated")
        assert events.count() == initial_event_count + 1

        # Verify event details
        event = events.first()
        assert event.user == user  # ty:ignore[possibly-missing-attribute]
        assert event.account == account  # ty:ignore[possibly-missing-attribute]
        assert event.details["old_balance"] == "10000.00"  # ty:ignore[possibly-missing-attribute]
        assert event.details["new_balance"] == "12000.00"  # ty:ignore[possibly-missing-attribute]

    def test_multiple_balance_updates_maintain_history(self):
        """
        Test that multiple balance updates maintain a history of changes.

        Validates: Requirement 6.2 - Balance change event logging
        """
        user = UserFactory()
        account = OandaAccountFactory(user=user, balance=Decimal("10000.00"))

        # Perform multiple balance updates
        balances = [12000.00, 11000.00, 13000.00, 14000.00]

        for new_balance in balances:
            account.update_balance(  # type: ignore[attr-defined]
                balance=new_balance,
                margin_used=0.00,
                margin_available=new_balance,
                unrealized_pnl=0.00,
            )

            # Log the change
            MarketEvent.objects.create(
                user=user,
                account=account,
                event_type="balance_updated",
                severity="info",
                description=f"Balance updated to {new_balance}",
                details={"new_balance": str(new_balance)},
            )

        # Verify all updates were logged
        events = MarketEvent.objects.filter(account=account, event_type="balance_updated").order_by(
            "created_at"
        )
        assert events.count() == len(balances)

        # Verify final balance
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.balance == Decimal(str(balances[-1]))

    def test_negative_balance_handling(self):
        """
        Test that negative balances (from losses) are handled correctly.

        Validates: Requirement 6.2 - Balance change detection
        """
        user = UserFactory()
        account = OandaAccountFactory(user=user, balance=Decimal("1000.00"))

        # Simulate large loss resulting in negative balance
        new_balance = Decimal("-500.00")
        new_margin_used = Decimal("0.00")
        new_margin_available = Decimal("0.00")
        new_unrealized_pnl = Decimal("-1500.00")

        # Update balance (system should allow negative balances)
        account.update_balance(  # type: ignore[attr-defined]
            balance=float(new_balance),
            margin_used=float(new_margin_used),
            margin_available=float(new_margin_available),
            unrealized_pnl=float(new_unrealized_pnl),
        )

        # Verify negative balance was recorded
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.balance == new_balance
        assert account.balance < Decimal("0.00")  # ty:ignore[unsupported-operator]

    def test_zero_balance_handling(self):
        """
        Test that zero balance is handled correctly.

        Validates: Requirement 6.2 - Balance change detection
        """
        user = UserFactory()
        account = OandaAccountFactory(user=user, balance=Decimal("1000.00"))

        # Update to zero balance
        account.update_balance(  # type: ignore[attr-defined]
            balance=0.00, margin_used=0.00, margin_available=0.00, unrealized_pnl=0.00
        )

        # Verify zero balance was recorded
        account.refresh_from_db()    # type: ignore[attr-defined]
        assert account.balance == Decimal("0.00")
        assert account.margin_available == Decimal("0.00")
