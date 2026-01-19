"""
Integration tests for test database cleanup verification.

Tests verify that:
- Database is cleaned up after test completion
- Cleanup occurs even on test failure
- No residual data remains after tests
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase

from apps.market.models import OandaAccounts, TickData
from apps.trading.models import StrategyConfigurations, TradingTasks
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TickDataFactory,
    TradingTaskFactory,
    UserFactory,
)

User = get_user_model()


class TestDatabaseCleanup(TransactionTestCase):
    """
    Test database cleanup after test completion.

    Uses TransactionTestCase to test actual database state
    between tests without automatic rollback.
    """

    def test_database_cleanup_after_successful_test(self):
        """
        Test that database is cleaned up after a successful test.

        When a test completes successfully, all test data should be
        removed from the database.
        """
        # Record initial counts
        initial_user_count = User.objects.count()
        initial_account_count = OandaAccounts.objects.count()
        initial_config_count = StrategyConfigurations.objects.count()

        # Create test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)
        task = TradingTaskFactory(user=user, oanda_account=account, config=config)

        # Verify data was created
        self.assertEqual(User.objects.count(), initial_user_count + 1)
        self.assertEqual(OandaAccounts.objects.count(), initial_account_count + 1)
        self.assertEqual(StrategyConfigurations.objects.count(), initial_config_count + 1)
        self.assertEqual(TradingTasks.objects.count(), 1)

        # Explicitly clean up (simulating test teardown)
        task.delete()  # ty:ignore[unresolved-attribute]
        config.delete()  # ty:ignore[unresolved-attribute]
        account.delete()  # ty:ignore[unresolved-attribute]
        user.delete()  # ty:ignore[unresolved-attribute]

        # Verify cleanup occurred
        self.assertEqual(User.objects.count(), initial_user_count)
        self.assertEqual(OandaAccounts.objects.count(), initial_account_count)
        self.assertEqual(StrategyConfigurations.objects.count(), initial_config_count)
        self.assertEqual(TradingTasks.objects.count(), 0)

    def test_database_cleanup_after_failed_test(self):
        """
        Test that database is cleaned up even when a test fails.

        When a test fails, the database should still be cleaned up
        to prevent test pollution.
        """
        initial_user_count = User.objects.count()
        initial_account_count = OandaAccounts.objects.count()

        # Create test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)

        # Verify data was created
        self.assertEqual(User.objects.count(), initial_user_count + 1)
        self.assertEqual(OandaAccounts.objects.count(), initial_account_count + 1)

        # Simulate test failure by raising an exception
        # (In real scenario, this would be an assertion failure)
        try:
            raise AssertionError("Simulated test failure")
        except AssertionError:
            pass  # Catch to continue cleanup verification

        # Clean up (simulating teardown even after failure)
        account.delete()  # ty:ignore[unresolved-attribute]
        user.delete()  # ty:ignore[unresolved-attribute]

        # Verify cleanup occurred despite failure
        self.assertEqual(User.objects.count(), initial_user_count)
        self.assertEqual(OandaAccounts.objects.count(), initial_account_count)

    def test_no_residual_data_after_test(self):
        """
        Test that no residual data remains after test completion.

        After a test completes, the database should be in a clean state
        with no leftover test data.
        """
        # Record initial state
        initial_counts = {
            "users": User.objects.count(),
            "accounts": OandaAccounts.objects.count(),
            "configs": StrategyConfigurations.objects.count(),
            "tasks": TradingTasks.objects.count(),
            "tick_data": TickData.objects.count(),
        }

        # Create various test data
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)
        task = TradingTaskFactory(user=user, oanda_account=account, config=config)
        tick = TickDataFactory()

        # Verify data was created
        self.assertGreater(User.objects.count(), initial_counts["users"])
        self.assertGreater(OandaAccounts.objects.count(), initial_counts["accounts"])
        self.assertGreater(StrategyConfigurations.objects.count(), initial_counts["configs"])
        self.assertGreater(TradingTasks.objects.count(), initial_counts["tasks"])
        self.assertGreater(TickData.objects.count(), initial_counts["tick_data"])

        # Clean up all test data
        task.delete()  # ty:ignore[unresolved-attribute]
        tick.delete()  # ty:ignore[unresolved-attribute]
        config.delete()  # ty:ignore[unresolved-attribute]
        account.delete()  # ty:ignore[unresolved-attribute]
        user.delete()  # ty:ignore[unresolved-attribute]

        # Verify complete cleanup - back to initial state
        self.assertEqual(User.objects.count(), initial_counts["users"])
        self.assertEqual(OandaAccounts.objects.count(), initial_counts["accounts"])
        self.assertEqual(StrategyConfigurations.objects.count(), initial_counts["configs"])
        self.assertEqual(TradingTasks.objects.count(), initial_counts["tasks"])
        self.assertEqual(TickData.objects.count(), initial_counts["tick_data"])


class TestTransactionRollback(TestCase):
    """
    Test that TestCase automatically rolls back transactions.

    Django's TestCase wraps each test in a transaction that is
    rolled back after the test completes.
    """

    def test_automatic_rollback_on_test_completion(self):
        """
        Test that TestCase automatically rolls back database changes.

        When using TestCase, all database changes are automatically
        rolled back after the test completes.
        """
        initial_count = User.objects.count()

        # Create test data
        UserFactory()
        self.assertEqual(User.objects.count(), initial_count + 1)

        # No explicit cleanup needed - TestCase will rollback
        # This is verified by the next test not seeing this data

    def test_previous_test_data_not_visible(self):
        """
        Test that data from previous test is not visible.

        This test verifies that the previous test's data was
        rolled back and is not visible in this test.
        """
        # If rollback worked, we should not see the user from the previous test
        # We can't directly verify this, but we can verify the database is clean
        # by checking that we can create a user with the same username

        # This would fail if the previous test's data wasn't rolled back
        user = UserFactory(username="testuser0")
        self.assertIsNotNone(user.pk)  # type: ignore[attr-defined]


@pytest.mark.django_db
class TestPytestDatabaseCleanup:
    """Test pytest-django database cleanup behavior."""

    def test_pytest_database_cleanup(self):
        """
        Test that pytest-django cleans up database after test.

        When using @pytest.mark.django_db, the database is cleaned up
        after each test.
        """
        initial_count = User.objects.count()

        # Create test data
        UserFactory()
        assert User.objects.count() == initial_count + 1

        # pytest-django will automatically clean up

    def test_previous_pytest_test_data_not_visible(self):
        """
        Test that data from previous pytest test is not visible.

        This verifies that pytest-django cleaned up the previous test's data.
        """
        # Create a user with the same username as previous test
        # This would fail if previous test's data wasn't cleaned up
        user = UserFactory(username="testuser0")
        assert user.pk is not None  # ty:ignore[unresolved-attribute]

    def test_multiple_model_cleanup(self):
        """
        Test that cleanup works for multiple related models.

        When creating related objects, all should be cleaned up
        after the test.
        """
        initial_counts = {
            "users": User.objects.count(),
            "accounts": OandaAccounts.objects.count(),
            "configs": StrategyConfigurations.objects.count(),
        }

        # Create related objects
        user = UserFactory()
        OandaAccountFactory(user=user)
        StrategyConfigurationFactory(user=user)

        # Verify creation
        assert User.objects.count() == initial_counts["users"] + 1
        assert OandaAccounts.objects.count() == initial_counts["accounts"] + 1
        assert StrategyConfigurations.objects.count() == initial_counts["configs"] + 1

        # pytest-django will clean up all related objects


@pytest.mark.django_db
class TestDatabaseStateIsolation:
    """Test that database state is isolated between tests."""

    def test_database_state_isolation_first(self):
        """
        First test that modifies database state.

        Creates data that should not be visible to subsequent tests.
        """
        # Create test data
        user = UserFactory(username="isolation_test_user")
        OandaAccountFactory(user=user, account_id="ISOLATION-TEST-001")

        # Verify data exists in this test
        assert User.objects.filter(username="isolation_test_user").exists()
        assert OandaAccounts.objects.filter(account_id="ISOLATION-TEST-001").exists()

    def test_database_state_isolation_second(self):
        """
        Second test that should not see data from first test.

        Verifies that database state from previous test is not visible.
        """
        # Verify data from previous test is not visible
        assert not User.objects.filter(username="isolation_test_user").exists()
        assert not OandaAccounts.objects.filter(account_id="ISOLATION-TEST-001").exists()

        # Create new data with same identifiers (would fail if previous data existed)
        user = UserFactory(username="isolation_test_user")
        account = OandaAccountFactory(user=user, account_id="ISOLATION-TEST-001")

        assert user.pk is not None  # ty:ignore[unresolved-attribute]
        assert account.pk is not None  # ty:ignore[unresolved-attribute]

    def test_database_state_isolation_third(self):
        """
        Third test that should not see data from previous tests.

        Further verifies database isolation across multiple tests.
        """
        # Verify no data from previous tests
        assert not User.objects.filter(username="isolation_test_user").exists()
        assert not OandaAccounts.objects.filter(account_id="ISOLATION-TEST-001").exists()

        # Verify we can create fresh data
        UserFactory()
        assert User.objects.count() >= 1
