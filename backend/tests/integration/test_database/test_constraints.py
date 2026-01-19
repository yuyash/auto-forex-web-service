"""
Integration tests for database foreign key constraints.

Tests verify that:
- Foreign key constraints are enforced on invalid operations
- Orphaned records are prevented
- Cascade deletes work correctly
"""

import pytest
from django.db import IntegrityError
from django.test import TestCase

from apps.market.models import MarketEvent, OandaAccounts
from apps.trading.models import (
    BacktestTasks,
    Executions,
    StrategyConfigurations,
    TradingTasks,
)
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


class ForeignKeyConstraintTestCase(TestCase):
    """Test foreign key constraint enforcement."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.account = OandaAccountFactory(user=self.user)
        self.config = StrategyConfigurationFactory(user=self.user)

    def test_cannot_create_account_with_invalid_user(self):
        """
        Test that creating an account with non-existent user fails.

        Foreign key constraints should prevent creating records that
        reference non-existent parent records.
        """
        # Try to create account with invalid user ID
        with self.assertRaises(IntegrityError):
            OandaAccounts.objects.create(
                user_id=99999,  # Non-existent user
                account_id="INVALID-ACCOUNT",
                currency="USD",
            )

    def test_cannot_create_task_with_invalid_account(self):
        """
        Test that creating a task with non-existent account fails.

        Foreign key constraints should prevent orphaned task records.
        """
        with self.assertRaises(IntegrityError):
            TradingTasks.objects.create(
                user=self.user,
                oanda_account_id=99999,  # Non-existent account
                config=self.config,
                name="Invalid Task",
                instrument="EUR_USD",
            )

    def test_cannot_create_task_with_invalid_config(self):
        """
        Test that creating a task with non-existent config fails.

        Foreign key constraints should prevent tasks without valid configs.
        """
        with self.assertRaises(IntegrityError):
            TradingTasks.objects.create(
                user=self.user,
                oanda_account=self.account,
                config_id=99999,  # Non-existent config
                name="Invalid Task",
                instrument="EUR_USD",
            )

    def test_cascade_delete_user_deletes_accounts(self):
        """
        Test that deleting a user cascades to delete their accounts.

        When a user is deleted, all their OANDA accounts should be
        automatically deleted due to CASCADE foreign key.
        """
        # Create multiple accounts for the user
        account1 = OandaAccountFactory(user=self.user)
        account2 = OandaAccountFactory(user=self.user)
        account3 = OandaAccountFactory(user=self.user)

        account_ids = [
            account1.pk,  # type: ignore[attr-defined]
            account2.pk,  # type: ignore[attr-defined]
            account3.pk,  # type: ignore[attr-defined]
        ]

        # Delete the user
        self.user.delete()  # type: ignore[attr-defined]

        # Verify all accounts were deleted
        for account_id in account_ids:
            self.assertFalse(OandaAccounts.objects.filter(id=account_id).exists())

    def test_cascade_delete_user_deletes_configs(self):
        """
        Test that deleting a user cascades to delete their strategy configs.

        When a user is deleted, all their strategy configurations should be
        automatically deleted.
        """
        # Create multiple configs for the user
        config1 = StrategyConfigurationFactory(user=self.user)
        config2 = StrategyConfigurationFactory(user=self.user)

        config_ids = [config1.id, config2.id]  # ty:ignore[unresolved-attribute]

        # Delete the user
        self.user.delete()  # ty:ignore[possibly-missing-attribute]

        # Verify all configs were deleted
        for config_id in config_ids:
            self.assertFalse(StrategyConfigurations.objects.filter(id=config_id).exists())

    def test_cascade_delete_account_deletes_tasks(self):
        """
        Test that deleting an account cascades to delete associated tasks.

        When an OANDA account is deleted, all trading tasks using that
        account should be deleted.
        """
        # Create tasks using the account
        task1 = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.config,
        )
        task2 = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.config,
        )

        task_ids = [task1.id, task2.id]  # ty:ignore[unresolved-attribute]

        # Delete the account
        self.account.delete()  # ty:ignore[possibly-missing-attribute]

        # Verify all tasks were deleted
        for task_id in task_ids:
            self.assertFalse(TradingTasks.objects.filter(id=task_id).exists())

    def test_set_null_on_delete_for_market_event(self):
        """
        Test that deleting a user sets MarketEvent.user to NULL.

        MarketEvent uses SET_NULL for user foreign key, so deleting
        the user should not delete events but set user to NULL.
        """
        # Create a market event
        event = MarketEvent.objects.create(
            event_type="test_event",
            category="market",
            severity="info",
            description="Test event",
            user=self.user,
            account=self.account,
        )

        # Delete the user
        self.user.delete()  # ty:ignore[possibly-missing-attribute]

        # Verify event still exists but user is NULL
        event.refresh_from_db()  # type: ignore[attr-defined]
        self.assertIsNone(event.user)
        self.assertIsNotNone(event.account)

    def test_set_null_on_delete_for_market_event_account(self):
        """
        Test that deleting an account sets MarketEvent.account to NULL.

        MarketEvent uses SET_NULL for account foreign key.
        """
        # Create a market event
        event = MarketEvent.objects.create(
            event_type="test_event",
            category="market",
            severity="info",
            description="Test event",
            user=self.user,
            account=self.account,
        )

        # Delete the account
        self.account.delete()  # ty:ignore[possibly-missing-attribute]

        # Verify event still exists but account is NULL
        event.refresh_from_db()  # type: ignore[attr-defined]
        self.assertIsNotNone(event.user)
        self.assertIsNone(event.account)

    def test_prevent_orphaned_trading_task(self):
        """
        Test that orphaned trading tasks cannot be created.

        All trading tasks must have valid user, account, and config references.
        """
        # Create a valid task
        task = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.config,
        )

        # Verify task has all required foreign keys
        self.assertIsNotNone(task.user)
        self.assertIsNotNone(task.oanda_account)
        self.assertIsNotNone(task.config)

        # Try to create task without user (should fail)
        with self.assertRaises(IntegrityError):
            TradingTasks.objects.create(
                user_id=None,
                oanda_account=self.account,
                config=self.config,
                name="Orphaned Task",
                instrument="EUR_USD",
            )

    def test_prevent_orphaned_backtest_task(self):
        """
        Test that orphaned backtest tasks cannot be created.

        All backtest tasks must have valid user and config references.
        """
        # Try to create backtest without user (should fail)
        with self.assertRaises(IntegrityError):
            BacktestTasks.objects.create(
                user_id=None,
                config=self.config,
                name="Orphaned Backtest",
                instrument="EUR_USD",
                initial_balance=10000,
            )

    def test_prevent_orphaned_execution(self):
        """
        Test that orphaned executions cannot be created.

        All executions must have valid user, account, and config references.
        """
        # Try to create execution without user (should fail)
        with self.assertRaises(IntegrityError):
            Executions.objects.create(
                user_id=None,
                account=self.account,
                strategy_config=self.config,
                execution_type="backtest",
                initial_balance=10000,
            )


@pytest.mark.django_db
class TestForeignKeyConstraints:
    """Pytest-style tests for foreign key constraints."""

    def test_multiple_cascade_levels(self, test_user):
        """
        Test that cascade deletes work through multiple levels.

        User -> Account -> Task should all cascade delete.
        """
        # Create hierarchy
        account = OandaAccountFactory(user=test_user)
        config = StrategyConfigurationFactory(user=test_user)
        task = TradingTaskFactory(
            user=test_user,
            oanda_account=account,
            config=config,
        )

        task_id = task.id  # ty:ignore[unresolved-attribute]
        account_id = account.pk  # ty:ignore[unresolved-attribute]
        config_id = config.id  # ty:ignore[unresolved-attribute]

        # Delete user (should cascade to account, config, and task)
        test_user.delete()

        # Verify all were deleted
        assert not TradingTasks.objects.filter(id=task_id).exists()
        assert not OandaAccounts.objects.filter(id=account_id).exists()
        assert not StrategyConfigurations.objects.filter(id=config_id).exists()

    def test_foreign_key_validation_on_update(self, test_user):
        """
        Test that foreign key constraints are enforced on updates.

        Updating a foreign key to an invalid value should fail.
        """
        account = OandaAccountFactory(user=test_user)
        config = StrategyConfigurationFactory(user=test_user)
        task = TradingTaskFactory(
            user=test_user,
            oanda_account=account,
            config=config,
        )

        # Try to update to invalid account ID
        with pytest.raises(IntegrityError):
            task.oanda_account_id = 99999  # ty:ignore[unresolved-attribute]
            task.save()  # type: ignore[attr-defined]

    def test_foreign_key_integrity_across_transactions(self, test_user):
        """
        Test that foreign key integrity is maintained across transactions.

        Even in complex multi-step transactions, foreign key constraints
        should be enforced.
        """
        from django.db import transaction

        account = OandaAccountFactory(user=test_user)
        config = StrategyConfigurationFactory(user=test_user)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                # Create task
                TradingTaskFactory(
                    user=test_user,
                    oanda_account=account,
                    config=config,
                )

                # Try to delete account (should fail due to task reference)
                # Actually, this will succeed because CASCADE is set
                # Let's test the opposite: try to create task with deleted account

                # Delete account first
                account.delete()  # ty:ignore[unresolved-attribute]

                # Try to create another task with deleted account (should fail)
                TradingTasks.objects.create(
                    user=test_user,
                    oanda_account_id=account.pk,  # type: ignore[attr-defined]
                    config=config,
                    name="Invalid Task",
                    instrument="EUR_USD",
                )

    def test_unique_together_constraint(self, test_user):
        """
        Test that unique_together constraints are enforced.

        OandaAccounts has unique_together on (user, account_id, api_type).
        """
        account = OandaAccountFactory(user=test_user)

        # Try to create duplicate account with same user, account_id, api_type
        with pytest.raises(IntegrityError):
            OandaAccounts.objects.create(
                user=test_user,
                account_id=account.account_id,
                api_type=account.api_type,
                currency="USD",
            )

    def test_foreign_key_on_delete_protect_behavior(self):
        """
        Test PROTECT behavior if any models use it.

        Note: Current models use CASCADE or SET_NULL, but this tests
        the concept for future reference.
        """
        # This is a conceptual test - current models don't use PROTECT
        # If a model used PROTECT, deleting the parent would raise ProtectedError
        pass
