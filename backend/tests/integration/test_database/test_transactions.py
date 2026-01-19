"""
Integration tests for database transaction handling.

Tests verify that:
- Successful operations commit data correctly
- Failed operations rollback without persisting partial data
- Transaction atomicity is maintained across multiple operations
"""

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.market.models import OandaAccounts
from apps.trading.models import StrategyConfigurations, TradingTasks
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)


class TransactionHandlingTestCase(TestCase):
    """Test database transaction handling and rollback behavior."""

    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.account = OandaAccountFactory(user=self.user)
        self.config = StrategyConfigurationFactory(user=self.user)

    def test_successful_operation_commits_data(self):
        """
        Test that successful database operations commit data correctly.

        When a database operation completes successfully, all changes
        should be persisted to the database.
        """
        # Create a trading task
        task = TradingTaskFactory(
            user=self.user,
            oanda_account=self.account,
            config=self.config,
            name="Test Task",
            status="created",
        )

        # Verify the task was persisted
        persisted_task = TradingTasks.objects.get(id=task.id)  # ty:ignore[unresolved-attribute]
        self.assertEqual(persisted_task.name, "Test Task")
        self.assertEqual(persisted_task.status, "created")
        self.assertEqual(persisted_task.user, self.user)
        self.assertEqual(persisted_task.oanda_account, self.account)

    def test_failed_operation_rollback(self):
        """
        Test that failed operations rollback without persisting data.

        When a database operation fails (e.g., due to constraint violation),
        no partial data should be persisted.
        """
        initial_count = TradingTasks.objects.count()

        # Attempt to create a task with invalid data that will fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # Create a valid task first
                TradingTaskFactory(
                    user=self.user,
                    oanda_account=self.account,
                    config=self.config,
                    name="Valid Task",
                )

                # Force a constraint violation by creating duplicate
                # This will fail and should rollback the entire transaction
                task = TradingTasks(
                    user=self.user,
                    oanda_account=self.account,
                    config=self.config,
                    name="Invalid Task",
                    status="created",
                )
                task.save()  # type: ignore[attr-defined]

                # Force integrity error by violating a constraint
                # Create another account with same account_id and api_type
                OandaAccounts.objects.create(
                    user=self.user,
                    account_id=self.account.account_id,
                    api_type=self.account.api_type,
                    currency="USD",
                )

        # Verify no data was persisted (rollback occurred)
        final_count = TradingTasks.objects.count()
        self.assertEqual(initial_count, final_count)

    def test_no_partial_data_persistence_on_failure(self):
        """
        Test that multi-step operations don't persist partial data on failure.

        When a transaction involves multiple operations and one fails,
        none of the operations should persist.
        """
        initial_account_count = OandaAccounts.objects.count()
        initial_config_count = StrategyConfigurations.objects.count()
        initial_task_count = TradingTasks.objects.count()

        # Attempt a multi-step operation that will fail
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                # Step 1: Create a new account (should rollback)
                new_account = OandaAccountFactory(
                    user=self.user,
                    account_id="NEW-ACCOUNT-123",
                )

                # Step 2: Create a new config (should rollback)
                new_config = StrategyConfigurationFactory(
                    user=self.user,
                    name="New Config",
                )

                # Step 3: Create a task (should rollback)
                TradingTaskFactory(
                    user=self.user,
                    oanda_account=new_account,
                    config=new_config,
                    name="New Task",
                )

                # Step 4: Force a failure with duplicate account
                OandaAccounts.objects.create(
                    user=self.user,
                    account_id=self.account.account_id,
                    api_type=self.account.api_type,
                    currency="USD",
                )

        # Verify no partial data was persisted
        self.assertEqual(OandaAccounts.objects.count(), initial_account_count)
        self.assertEqual(StrategyConfigurations.objects.count(), initial_config_count)
        self.assertEqual(TradingTasks.objects.count(), initial_task_count)

    def test_nested_transaction_rollback(self):
        """
        Test that nested transactions rollback correctly.

        When an inner transaction fails, it should rollback without
        affecting the outer transaction's ability to commit.
        """
        initial_count = OandaAccounts.objects.count()

        # Outer transaction succeeds
        with transaction.atomic():
            # Create an account in outer transaction
            outer_account = OandaAccountFactory(
                user=self.user,
                account_id="OUTER-ACCOUNT",
            )

            # Inner transaction fails
            try:
                with transaction.atomic():
                    # Create account in inner transaction
                    OandaAccountFactory(
                        user=self.user,
                        account_id="INNER-ACCOUNT",
                    )

                    # Force failure
                    raise IntegrityError("Simulated failure")
            except IntegrityError:
                pass  # Expected failure

            # Outer transaction continues and commits
            outer_account.balance = 20000
            outer_account.save()  # type: ignore[attr-defined]

        # Verify outer transaction committed, inner rolled back
        self.assertEqual(OandaAccounts.objects.count(), initial_count + 1)
        self.assertTrue(OandaAccounts.objects.filter(account_id="OUTER-ACCOUNT").exists())
        self.assertFalse(OandaAccounts.objects.filter(account_id="INNER-ACCOUNT").exists())

    def test_transaction_isolation(self):
        """
        Test that transactions are properly isolated.

        Changes made in one transaction should not be visible to
        other transactions until committed.
        """
        # This test verifies basic transaction isolation
        # In a real concurrent scenario, we'd need multiple database connections

        initial_balance = self.account.balance

        with transaction.atomic():
            # Modify account balance
            self.account.balance = 50000
            self.account.save()  # type: ignore[attr-defined]

            # Within the transaction, changes are visible
            updated_account = OandaAccounts.objects.get(id=self.account.pk)  # type: ignore[attr-defined]
            self.assertEqual(updated_account.balance, 50000)

        # After commit, changes are persisted
        final_account = OandaAccounts.objects.get(id=self.account.pk)  # type: ignore[attr-defined]
        self.assertEqual(final_account.balance, 50000)
        self.assertNotEqual(final_account.balance, initial_balance)


@pytest.mark.django_db
class TestTransactionAtomicity:
    """Pytest-style tests for transaction atomicity."""

    def test_atomic_decorator_rollback(self, test_user):
        """Test that @transaction.atomic decorator rolls back on exception."""
        initial_count = OandaAccounts.objects.count()

        @transaction.atomic
        def create_accounts_with_failure():
            OandaAccountFactory(user=test_user, account_id="ATOMIC-1")
            OandaAccountFactory(user=test_user, account_id="ATOMIC-2")
            # Force failure
            raise ValueError("Simulated error")

        with pytest.raises(ValueError):
            create_accounts_with_failure()

        # Verify rollback occurred
        assert OandaAccounts.objects.count() == initial_count

    def test_atomic_context_manager_commit(self, test_user):
        """Test that atomic context manager commits on success."""
        initial_count = OandaAccounts.objects.count()

        with transaction.atomic():
            OandaAccountFactory(user=test_user, account_id="CONTEXT-1")
            OandaAccountFactory(user=test_user, account_id="CONTEXT-2")

        # Verify commit occurred
        assert OandaAccounts.objects.count() == initial_count + 2

    def test_savepoint_rollback(self, test_user):
        """Test that savepoints allow partial rollback within a transaction."""
        initial_count = OandaAccounts.objects.count()

        with transaction.atomic():
            # Create first account
            OandaAccountFactory(user=test_user, account_id="SAVEPOINT-1")

            # Create savepoint
            sid = transaction.savepoint()

            # Create second account
            OandaAccountFactory(user=test_user, account_id="SAVEPOINT-2")

            # Rollback to savepoint (removes second account)
            transaction.savepoint_rollback(sid)

            # Create third account
            OandaAccountFactory(user=test_user, account_id="SAVEPOINT-3")

        # Verify: first and third accounts exist, second doesn't
        assert OandaAccounts.objects.count() == initial_count + 2
        assert OandaAccounts.objects.filter(account_id="SAVEPOINT-1").exists()
        assert not OandaAccounts.objects.filter(account_id="SAVEPOINT-2").exists()
        assert OandaAccounts.objects.filter(account_id="SAVEPOINT-3").exists()
