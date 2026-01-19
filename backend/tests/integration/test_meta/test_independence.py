"""
Integration tests for test independence verification.

Tests verify that:
- Tests produce the same result regardless of execution order
- Tests are isolated from each other
- Tests can run independently without dependencies
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.market.models import OandaAccounts
from tests.integration.factories import (
    OandaAccountFactory,
    StrategyConfigurationFactory,
    TradingTaskFactory,
    UserFactory,
)

User = get_user_model()


class TestIndependenceOrderA(TestCase):
    """
    First set of tests to verify order independence.

    These tests should produce the same results regardless of
    whether they run before or after TestIndependenceOrderB.
    """

    def test_create_user_order_a1(self):
        """
        Test creating a user (order A, test 1).

        This test should produce the same result regardless of
        execution order.
        """
        initial_count = User.objects.count()
        user = UserFactory(username="order_a_user_1")

        self.assertEqual(User.objects.count(), initial_count + 1)
        self.assertEqual(user.username, "order_a_user_1")
        self.assertTrue(user.is_active)

    def test_create_account_order_a2(self):
        """
        Test creating an account (order A, test 2).

        This test should produce the same result regardless of
        execution order.
        """
        initial_count = OandaAccounts.objects.count()
        user = UserFactory()
        account = OandaAccountFactory(user=user, account_id="ORDER-A-ACCOUNT-2")

        self.assertEqual(OandaAccounts.objects.count(), initial_count + 1)
        self.assertEqual(account.account_id, "ORDER-A-ACCOUNT-2")
        self.assertEqual(account.user, user)

    def test_query_empty_results_order_a3(self):
        """
        Test querying with no matching results (order A, test 3).

        This test should always return empty results regardless of
        execution order.
        """
        # Query for non-existent data
        users = User.objects.filter(username="nonexistent_user_order_a")
        accounts = OandaAccounts.objects.filter(account_id="NONEXISTENT-ORDER-A")

        self.assertEqual(users.count(), 0)
        self.assertEqual(accounts.count(), 0)


class TestIndependenceOrderB(TestCase):
    """
    Second set of tests to verify order independence.

    These tests should produce the same results regardless of
    whether they run before or after TestIndependenceOrderA.
    """

    def test_create_user_order_b1(self):
        """
        Test creating a user (order B, test 1).

        This test should produce the same result regardless of
        execution order.
        """
        initial_count = User.objects.count()
        user = UserFactory(username="order_b_user_1")

        self.assertEqual(User.objects.count(), initial_count + 1)
        self.assertEqual(user.username, "order_b_user_1")
        self.assertTrue(user.is_active)

    def test_create_account_order_b2(self):
        """
        Test creating an account (order B, test 2).

        This test should produce the same result regardless of
        execution order.
        """
        initial_count = OandaAccounts.objects.count()
        user = UserFactory()
        account = OandaAccountFactory(user=user, account_id="ORDER-B-ACCOUNT-2")

        self.assertEqual(OandaAccounts.objects.count(), initial_count + 1)
        self.assertEqual(account.account_id, "ORDER-B-ACCOUNT-2")
        self.assertEqual(account.user, user)

    def test_query_empty_results_order_b3(self):
        """
        Test querying with no matching results (order B, test 3).

        This test should always return empty results regardless of
        execution order.
        """
        # Query for non-existent data
        users = User.objects.filter(username="nonexistent_user_order_b")
        accounts = OandaAccounts.objects.filter(account_id="NONEXISTENT-ORDER-B")

        self.assertEqual(users.count(), 0)
        self.assertEqual(accounts.count(), 0)


@pytest.mark.django_db
class TestIsolationFromOtherTests:
    """Test that tests are isolated from each other."""

    def test_isolation_test_1(self):
        """
        First isolation test.

        Creates data that should not be visible to other tests.
        """
        # Create test data
        user = UserFactory(username="isolation_user_1")
        OandaAccountFactory(user=user, account_id="ISOLATION-001")

        # Verify data exists in this test
        assert User.objects.filter(username="isolation_user_1").exists()
        assert OandaAccounts.objects.filter(account_id="ISOLATION-001").exists()

    def test_isolation_test_2(self):
        """
        Second isolation test.

        Should not see data from test_isolation_test_1.
        """
        # Verify data from previous test is not visible
        assert not User.objects.filter(username="isolation_user_1").exists()
        assert not OandaAccounts.objects.filter(account_id="ISOLATION-001").exists()

        # Create new data with different identifiers
        user = UserFactory(username="isolation_user_2")
        account = OandaAccountFactory(user=user, account_id="ISOLATION-002")

        assert user.pk is not None  # ty:ignore[unresolved-attribute]
        assert account.pk is not None  # ty:ignore[unresolved-attribute]

    def test_isolation_test_3(self):
        """
        Third isolation test.

        Should not see data from previous tests.
        """
        # Verify no data from previous tests
        assert not User.objects.filter(username="isolation_user_1").exists()
        assert not User.objects.filter(username="isolation_user_2").exists()
        assert not OandaAccounts.objects.filter(account_id="ISOLATION-001").exists()
        assert not OandaAccounts.objects.filter(account_id="ISOLATION-002").exists()

        # Create fresh data
        user = UserFactory(username="isolation_user_3")
        assert user.pk is not None  # ty:ignore[unresolved-attribute]


@pytest.mark.django_db
class TestIndependentExecution:
    """Test that tests can run independently without dependencies."""

    def test_independent_user_creation(self):
        """
        Test that can run independently.

        Does not depend on any other test running first.
        """
        # This test should work even if run in isolation
        user = UserFactory(username="independent_user")
        assert user.pk is not None  # ty:ignore[unresolved-attribute]
        assert user.username == "independent_user"

    def test_independent_account_creation(self):
        """
        Test that can run independently.

        Does not depend on any other test running first.
        """
        # This test should work even if run in isolation
        user = UserFactory()
        account = OandaAccountFactory(user=user, account_id="INDEPENDENT-ACCOUNT")

        assert account.pk is not None  # ty:ignore[unresolved-attribute]
        assert account.account_id == "INDEPENDENT-ACCOUNT"
        assert account.user == user

    def test_independent_complex_operation(self):
        """
        Test complex operation that can run independently.

        Creates multiple related objects without depending on other tests.
        """
        # This test should work even if run in isolation
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)
        task = TradingTaskFactory(user=user, oanda_account=account, config=config)

        assert user.pk is not None  # ty:ignore[unresolved-attribute]
        assert account.pk is not None  # ty:ignore[unresolved-attribute]
        assert config.pk is not None  # ty:ignore[unresolved-attribute]
        assert task.pk is not None  # ty:ignore[unresolved-attribute]
        assert task.user == user
        assert task.oanda_account == account
        assert task.config == config


@pytest.mark.django_db
class TestSameResultRegardlessOfOrder:
    """Test that tests produce the same result regardless of execution order."""

    def test_count_query_result_1(self):
        """
        First test that queries counts.

        Should return consistent results regardless of order.
        """
        # Create known data
        user = UserFactory()
        OandaAccountFactory.create_batch(3, user=user)

        # Query should return consistent count
        count = OandaAccounts.objects.filter(user=user).count()
        assert count == 3

    def test_count_query_result_2(self):
        """
        Second test that queries counts.

        Should return consistent results regardless of order.
        """
        # Create known data
        user = UserFactory()
        OandaAccountFactory.create_batch(5, user=user)

        # Query should return consistent count
        count = OandaAccounts.objects.filter(user=user).count()
        assert count == 5

    def test_filter_query_result_1(self):
        """
        First test that filters data.

        Should return consistent results regardless of order.
        """
        # Create known data
        user = UserFactory()
        active_account = OandaAccountFactory(user=user, is_active=True)
        OandaAccountFactory(user=user, is_active=False)

        # Query should return consistent results
        active_accounts = OandaAccounts.objects.filter(user=user, is_active=True)
        assert active_accounts.count() == 1
        assert active_accounts.first().id == active_account.pk  # ty:ignore[possibly-missing-attribute, unresolved-attribute]

    def test_filter_query_result_2(self):
        """
        Second test that filters data.

        Should return consistent results regardless of order.
        """
        # Create known data
        user = UserFactory()
        OandaAccountFactory.create_batch(2, user=user, is_active=True)
        OandaAccountFactory.create_batch(3, user=user, is_active=False)

        # Query should return consistent results
        active_accounts = OandaAccounts.objects.filter(user=user, is_active=True)
        inactive_accounts = OandaAccounts.objects.filter(user=user, is_active=False)

        assert active_accounts.count() == 2
        assert inactive_accounts.count() == 3


@pytest.mark.django_db
class TestNoSharedState:
    """Test that tests don't share state through global variables or caches."""

    def test_no_shared_state_1(self):
        """
        First test that modifies data.

        Should not affect other tests through shared state.
        """
        # Create and modify data
        user = UserFactory(username="shared_state_test_1")
        account = OandaAccountFactory(user=user, balance=10000)

        # Modify the account
        account.balance = 20000
        account.save()  # type: ignore[attr-defined]

        # Verify modification
        updated_account = OandaAccounts.objects.get(id=account.pk)  # type: ignore[attr-defined]
        assert updated_account.balance == 20000

    def test_no_shared_state_2(self):
        """
        Second test that should not see modifications from first test.

        Verifies no shared state between tests.
        """
        # Create new data with same initial values
        user = UserFactory(username="shared_state_test_2")
        account = OandaAccountFactory(user=user, balance=10000)

        # Should have initial balance, not modified balance from previous test
        assert account.balance == 10000

        # Verify no data from previous test
        assert not User.objects.filter(username="shared_state_test_1").exists()

    def test_no_shared_state_3(self):
        """
        Third test that verifies complete isolation.

        Should not see any data from previous tests.
        """
        # Verify no data from previous tests
        assert not User.objects.filter(username="shared_state_test_1").exists()
        assert not User.objects.filter(username="shared_state_test_2").exists()

        # Create fresh data
        user = UserFactory(username="shared_state_test_3")
        account = OandaAccountFactory(user=user, balance=15000)

        assert account.balance == 15000


class TestDeterministicResults(TestCase):
    """Test that tests produce deterministic results."""

    def test_deterministic_creation(self):
        """
        Test that object creation is deterministic.

        Creating the same object should produce consistent results.
        """
        # Create user with specific attributes
        user = UserFactory(
            username="deterministic_user",
            email="deterministic@example.com",
        )

        # Verify attributes are as specified
        self.assertEqual(user.username, "deterministic_user")
        self.assertEqual(user.email, "deterministic@example.com")
        self.assertTrue(user.is_active)

    def test_deterministic_query(self):
        """
        Test that queries produce deterministic results.

        Same query should return same results.
        """
        # Create known data
        user = UserFactory(username="query_user")
        OandaAccountFactory(user=user, account_id="QUERY-001")
        OandaAccountFactory(user=user, account_id="QUERY-002")

        # Query should return consistent results
        accounts = OandaAccounts.objects.filter(user=user).order_by("account_id")
        account_ids = [acc.account_id for acc in accounts]

        self.assertEqual(account_ids, ["QUERY-001", "QUERY-002"])

    def test_deterministic_calculation(self):
        """
        Test that calculations produce deterministic results.

        Same calculation should return same result.
        """
        # Create account with known balance
        user = UserFactory()
        account = OandaAccountFactory(user=user, balance=10000, margin_used=2000)

        # Calculate available margin
        available_margin = account.margin_available

        # Should be deterministic
        self.assertEqual(available_margin, 8000)
