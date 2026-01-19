"""
Integration tests for multi-account data isolation.

Tests verify that operations on one account don't affect other accounts,
account-specific data queries return correct data, and trades are associated
with the correct account.

Feature: backend-integration-tests"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.market.models import OandaAccounts
from apps.trading.models import (
    TradingEvent,
    TradingTasks,
)
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)

User = get_user_model()


@pytest.mark.django_db
class TestAccountIsolation:
    """Test suite for multi-account data isolation."""

    def test_account_balance_update_does_not_affect_other_accounts(self):
        """
        Test that updating balance on one account doesn't affect other accounts.

        Validates: Requirement 6.2 - Account data isolation
        """
        # Create two accounts for the same user with explicit margin values
        user = UserFactory()
        account1 = OandaAccountFactory(
            user=user, balance=Decimal("10000.00"), margin_used=Decimal("0.00")
        )
        account2 = OandaAccountFactory(
            user=user, balance=Decimal("20000.00"), margin_used=Decimal("0.00")
        )

        # Store original account2 values
        original_balance = account2.balance
        original_margin = account2.margin_used
        original_unrealized = account2.unrealized_pnl

        # Update balance on account1
        account1.update_balance(  # type: ignore[attr-defined]
            balance=15000.00,
            margin_used=500.00,
            margin_available=14500.00,
            unrealized_pnl=100.00,
        )

        # Refresh account2 from database
        account2.refresh_from_db()    # type: ignore[attr-defined]

        # Verify account2 balance is unchanged
        assert account2.balance == original_balance
        assert account2.margin_used == original_margin
        assert account2.unrealized_pnl == original_unrealized

        # Verify account1 was updated correctly
        account1.refresh_from_db()    # type: ignore[attr-defined]
        assert account1.balance == Decimal("15000.00")
        assert account1.margin_used == Decimal("500.00")
        assert account1.unrealized_pnl == Decimal("100.00")

    def test_account_activation_does_not_affect_other_accounts(self):
        """
        Test that activating/deactivating one account doesn't affect others.

        Validates: Requirement 6.2 - Account data isolation
        """
        user = UserFactory()
        account1 = OandaAccountFactory(user=user, is_active=True)
        account2 = OandaAccountFactory(user=user, is_active=True)
        account3 = OandaAccountFactory(user=user, is_active=True)

        # Deactivate account1
        account1.deactivate()  # ty:ignore[unresolved-attribute]

        # Refresh other accounts
        account2.refresh_from_db()    # type: ignore[attr-defined]
        account3.refresh_from_db()    # type: ignore[attr-defined]

        # Verify only account1 is deactivated
        account1.refresh_from_db()    # type: ignore[attr-defined]
        assert account1.is_active is False
        assert account2.is_active is True
        assert account3.is_active is True

    def test_account_specific_data_queries(self):
        """
        Test that queries for account-specific data return only that account's data.

        Validates: Requirement 6.3 - Account-specific data queries
        """
        user = UserFactory()
        account1 = OandaAccountFactory(user=user)
        account2 = OandaAccountFactory(user=user)

        # Create trading tasks for each account
        config1 = StrategyConfigurationFactory(user=user)
        config2 = StrategyConfigurationFactory(user=user)

        task1 = TradingTaskFactory(
            user=user, oanda_account=account1, config=config1, name="Task for Account 1"
        )
        task2 = TradingTaskFactory(
            user=user, oanda_account=account2, config=config2, name="Task for Account 2"
        )
        task3 = TradingTaskFactory(
            user=user, oanda_account=account1, config=config1, name="Another Task for Account 1"
        )

        # Query tasks for account1
        account1_tasks = TradingTasks.objects.filter(oanda_account=account1)

        # Verify only account1 tasks are returned
        assert account1_tasks.count() == 2
        assert task1 in account1_tasks
        assert task3 in account1_tasks
        assert task2 not in account1_tasks

        # Query tasks for account2
        account2_tasks = TradingTasks.objects.filter(oanda_account=account2)

        # Verify only account2 tasks are returned
        assert account2_tasks.count() == 1
        assert task2 in account2_tasks
        assert task1 not in account2_tasks
        assert task3 not in account2_tasks

    def test_trade_association_with_correct_account(self):
        """
        Test that trades are correctly associated with their account.

        Validates: Requirement 6.4 - Trade association with correct account
        """
        user = UserFactory()
        account1 = OandaAccountFactory(user=user, account_id="101-001-12345")
        account2 = OandaAccountFactory(user=user, account_id="101-001-67890")

        # Create trading events for each account
        event1 = TradingEvent.objects.create(
            user=user,
            account=account1,
            event_type="trade_opened",
            severity="info",
            description="Trade opened on account 1",
            instrument="EUR_USD",
            details={"trade_id": "1001", "units": 1000},
        )

        event2 = TradingEvent.objects.create(
            user=user,
            account=account2,
            event_type="trade_opened",
            severity="info",
            description="Trade opened on account 2",
            instrument="GBP_USD",
            details={"trade_id": "2001", "units": 2000},
        )

        # Query events for account1
        account1_events = TradingEvent.objects.filter(account=account1)
        assert account1_events.count() == 1
        assert account1_events.first() == event1
        assert account1_events.first().details["trade_id"] == "1001"  # ty:ignore[possibly-missing-attribute]

        # Query events for account2
        account2_events = TradingEvent.objects.filter(account=account2)
        assert account2_events.count() == 1
        assert account2_events.first() == event2
        assert account2_events.first().details["trade_id"] == "2001"  # ty:ignore[possibly-missing-attribute]

    def test_multiple_users_account_isolation(self):
        """
        Test that accounts from different users are completely isolated.

        Validates: Requirement 6.2, 6.3 - Account data isolation across users
        """
        user1 = UserFactory(username="user1", email="user1@example.com")
        user2 = UserFactory(username="user2", email="user2@example.com")

        # Create accounts for each user
        account1_user1 = OandaAccountFactory(user=user1, balance=Decimal("10000.00"))
        account2_user1 = OandaAccountFactory(user=user1, balance=Decimal("20000.00"))
        account1_user2 = OandaAccountFactory(user=user2, balance=Decimal("30000.00"))

        # Query accounts for user1
        user1_accounts = OandaAccounts.objects.filter(user=user1)
        assert user1_accounts.count() == 2
        assert account1_user1 in user1_accounts
        assert account2_user1 in user1_accounts
        assert account1_user2 not in user1_accounts

        # Query accounts for user2
        user2_accounts = OandaAccounts.objects.filter(user=user2)
        assert user2_accounts.count() == 1
        assert account1_user2 in user2_accounts
        assert account1_user1 not in user2_accounts
        assert account2_user1 not in user2_accounts

    def test_default_account_setting_does_not_affect_other_accounts(self):
        """
        Test that setting one account as default doesn't affect other accounts.

        Validates: Requirement 6.2 - Account data isolation
        """
        user = UserFactory()
        account1 = OandaAccountFactory(user=user, is_default=False)
        account2 = OandaAccountFactory(user=user, is_default=False)
        account3 = OandaAccountFactory(user=user, is_default=True)

        # Set account1 as default
        account1.set_as_default()  # type: ignore[attr-defined]

        # Refresh all accounts
        account1.refresh_from_db()    # type: ignore[attr-defined]
        account2.refresh_from_db()    # type: ignore[attr-defined]
        account3.refresh_from_db()    # type: ignore[attr-defined]

        # Verify only account1 is default
        assert account1.is_default is True
        assert account2.is_default is False
        assert account3.is_default is False

    def test_account_deletion_does_not_affect_other_accounts(self):
        """
        Test that deleting one account doesn't affect other accounts.

        Validates: Requirement 6.2 - Account data isolation
        """
        user = UserFactory()
        account1 = OandaAccountFactory(user=user)
        account2 = OandaAccountFactory(user=user)
        account3 = OandaAccountFactory(user=user)

        account1_id = account1.pk  # ty:ignore[unresolved-attribute]

        # Delete account1
        account1.delete()  # type: ignore[attr-defined]

        # Verify account1 is deleted
        assert not OandaAccounts.objects.filter(id=account1_id).exists()

        # Verify other accounts still exist
        assert OandaAccounts.objects.filter(id=account2.pk)  # type: ignore[attr-defined].exists()
        assert OandaAccounts.objects.filter(id=account3.pk)  # type: ignore[attr-defined].exists()

    def test_strategy_configuration_isolation_across_accounts(self):
        """
        Test that strategy configurations are isolated per user, not per account.

        Validates: Requirement 6.3 - Account-specific data queries
        """
        user1 = UserFactory()
        user2 = UserFactory()

        account1_user1 = OandaAccountFactory(user=user1)
        account2_user1 = OandaAccountFactory(user=user1)
        account1_user2 = OandaAccountFactory(user=user2)

        # Create strategy configs for each user
        config1_user1 = StrategyConfigurationFactory(user=user1, name="User1 Strategy 1")
        config2_user1 = StrategyConfigurationFactory(user=user1, name="User1 Strategy 2")
        config1_user2 = StrategyConfigurationFactory(user=user2, name="User2 Strategy 1")

        # Create trading tasks linking configs to accounts
        task1 = TradingTaskFactory(user=user1, oanda_account=account1_user1, config=config1_user1)
        task2 = TradingTaskFactory(user=user1, oanda_account=account2_user1, config=config2_user1)
        task3 = TradingTaskFactory(user=user2, oanda_account=account1_user2, config=config1_user2)

        # Query tasks for user1's accounts
        user1_tasks = TradingTasks.objects.filter(user=user1)
        assert user1_tasks.count() == 2
        assert task1 in user1_tasks
        assert task2 in user1_tasks
        assert task3 not in user1_tasks

        # Query tasks for user2's accounts
        user2_tasks = TradingTasks.objects.filter(user=user2)
        assert user2_tasks.count() == 1
        assert task3 in user2_tasks
        assert task1 not in user2_tasks
        assert task2 not in user2_tasks
