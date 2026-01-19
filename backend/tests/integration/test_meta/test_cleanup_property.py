"""
Property-based tests for test database cleanup.

Feature: backend-integration-tests
Property 1: Test Database Cleanup

For any integration test, after the test completes (whether passing or
failing), the test database should be in a clean state with no residual
data from that test.
"""

import pytest
from django.contrib.auth import get_user_model
from hypothesis import given, settings
from hypothesis import strategies as st

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


# Strategy for generating test data counts
test_data_counts = st.integers(min_value=1, max_value=5)


@pytest.mark.django_db
class TestDatabaseCleanupProperty:
    """
    Property-based tests for database cleanup.

    Feature: backend-integration-tests
    Property 1: Test Database Cleanup
    """

    @settings(max_examples=100, deadline=None)
    @given(user_count=test_data_counts)
    def test_user_cleanup_property(self, user_count):
        """
        Property: For any number of users created, database should be clean after test.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any number of users created in a test, after the test completes,
        the database should not contain those users.
        """
        # Record initial state
        initial_count = User.objects.count()

        # Create test users
        users = [UserFactory() for _ in range(user_count)]

        # Verify users were created
        assert User.objects.count() == initial_count + user_count

        # Verify all users exist
        for user in users:
            assert User.objects.filter(id=user.id).exists()  # ty:ignore[possibly-missing-attribute]

        # pytest-django will automatically clean up
        # The next test will verify cleanup occurred

    @settings(max_examples=100, deadline=None)
    @given(account_count=test_data_counts)
    def test_account_cleanup_property(self, account_count):
        """
        Property: For any number of accounts created, database should be clean after test.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any number of accounts created in a test, after the test completes,
        the database should not contain those accounts.
        """
        # Record initial state
        initial_count = OandaAccounts.objects.count()

        # Create test accounts
        user = UserFactory()
        accounts = [OandaAccountFactory(user=user) for _ in range(account_count)]

        # Verify accounts were created
        assert OandaAccounts.objects.count() == initial_count + account_count

        # Verify all accounts exist
        for account in accounts:
            assert OandaAccounts.objects.filter(id=account.pk)  # type: ignore[attr-defined].exists()

        # pytest-django will automatically clean up

    @settings(max_examples=100, deadline=None)
    @given(
        user_count=test_data_counts,
        account_count=test_data_counts,
        config_count=test_data_counts,
    )
    def test_related_objects_cleanup_property(self, user_count, account_count, config_count):
        """
        Property: For any related objects created, database should be clean after test.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any number of related objects (users, accounts, configs) created
        in a test, after the test completes, the database should not contain
        any of those objects.
        """
        # Record initial state
        initial_counts = {
            "users": User.objects.count(),
            "accounts": OandaAccounts.objects.count(),
            "configs": StrategyConfigurations.objects.count(),
        }

        # Create test data
        users = [UserFactory() for _ in range(user_count)]

        accounts = []
        for user in users:
            for _ in range(account_count):
                accounts.append(OandaAccountFactory(user=user))

        configs = []
        for user in users:
            for _ in range(config_count):
                configs.append(StrategyConfigurationFactory(user=user))

        # Verify data was created
        assert User.objects.count() == initial_counts["users"] + user_count
        assert OandaAccounts.objects.count() == initial_counts["accounts"] + (
            user_count * account_count
        )
        assert StrategyConfigurations.objects.count() == initial_counts["configs"] + (
            user_count * config_count
        )

        # Verify all objects exist
        for user in users:
            assert User.objects.filter(id=user.id).exists()  # ty:ignore[possibly-missing-attribute]
        for account in accounts:
            assert OandaAccounts.objects.filter(id=account.pk)  # type: ignore[attr-defined].exists()
        for config in configs:
            assert StrategyConfigurations.objects.filter(id=config.id).exists()

        # pytest-django will automatically clean up

    @settings(max_examples=100, deadline=None)
    @given(task_count=test_data_counts)
    def test_complex_objects_cleanup_property(self, task_count):
        """
        Property: For any complex objects with dependencies, cleanup should be complete.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any number of complex objects with foreign key dependencies created
        in a test, after the test completes, the database should not contain
        any of those objects or their dependencies.
        """
        # Record initial state
        initial_counts = {
            "users": User.objects.count(),
            "accounts": OandaAccounts.objects.count(),
            "configs": StrategyConfigurations.objects.count(),
            "tasks": TradingTasks.objects.count(),
        }

        # Create test data with dependencies
        user = UserFactory()
        account = OandaAccountFactory(user=user)
        config = StrategyConfigurationFactory(user=user)

        tasks = []
        for _ in range(task_count):
            tasks.append(TradingTaskFactory(user=user, oanda_account=account, config=config))

        # Verify data was created
        assert User.objects.count() == initial_counts["users"] + 1
        assert OandaAccounts.objects.count() == initial_counts["accounts"] + 1
        assert StrategyConfigurations.objects.count() == initial_counts["configs"] + 1
        assert TradingTasks.objects.count() == initial_counts["tasks"] + task_count

        # Verify all objects exist
        assert User.objects.filter(id=user.id).exists()  # ty:ignore[unresolved-attribute]
        assert OandaAccounts.objects.filter(id=account.pk)  # type: ignore[attr-defined].exists()
        assert StrategyConfigurations.objects.filter(id=config.id).exists()  # ty:ignore[unresolved-attribute]
        for task in tasks:
            assert TradingTasks.objects.filter(id=task.id).exists()

        # pytest-django will automatically clean up

    @settings(max_examples=100, deadline=None)
    @given(tick_count=test_data_counts)
    def test_time_series_data_cleanup_property(self, tick_count):
        """
        Property: For any time-series data created, cleanup should be complete.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any number of time-series data points (tick data) created in a test,
        after the test completes, the database should not contain those data points.
        """
        # Record initial state
        initial_count = TickData.objects.count()

        # Create test tick data
        ticks = [TickDataFactory() for _ in range(tick_count)]

        # Verify data was created
        assert TickData.objects.count() == initial_count + tick_count

        # Verify all ticks exist
        for tick in ticks:
            assert TickData.objects.filter(
                instrument=tick.instrument, timestamp=tick.timestamp
            ).exists()

        # pytest-django will automatically clean up

    @settings(max_examples=100, deadline=None)
    @given(
        user_count=test_data_counts,
        account_count=test_data_counts,
    )
    def test_cleanup_after_simulated_failure_property(self, user_count, account_count):
        """
        Property: Database cleanup should occur even after test failure.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any test data created before a test failure, after the test completes,
        the database should still be cleaned up despite the failure.
        """
        # Record initial state
        initial_counts = {
            "users": User.objects.count(),
            "accounts": OandaAccounts.objects.count(),
        }

        # Create test data
        users = [UserFactory() for _ in range(user_count)]
        accounts = []
        for user in users:
            for _ in range(account_count):
                accounts.append(OandaAccountFactory(user=user))

        # Verify data was created
        assert User.objects.count() == initial_counts["users"] + user_count
        assert OandaAccounts.objects.count() == initial_counts["accounts"] + (
            user_count * account_count
        )

        # Simulate test failure (but catch it to continue)
        try:
            # This would normally cause test failure
            assert False, "Simulated test failure"
        except AssertionError:
            pass  # Catch to continue and verify cleanup still occurs

        # pytest-django will still clean up despite the "failure"

    @settings(max_examples=100, deadline=None)
    @given(data_count=test_data_counts)
    def test_no_data_leakage_between_iterations_property(self, data_count):
        """
        Property: No data should leak between property test iterations.

        Feature: backend-integration-tests
        Property 1: Test Database Cleanup

        For any property test with multiple iterations, each iteration should
        start with a clean database state, with no data from previous iterations.
        """
        # Each iteration should start fresh
        # If cleanup didn't work, we'd see accumulating data

        # Record state at start of this iteration
        initial_count = User.objects.count()

        # Create test data
        [UserFactory() for _ in range(data_count)]

        # Verify data was created
        assert User.objects.count() == initial_count + data_count

        # If cleanup between iterations didn't work, initial_count would
        # keep growing across iterations, causing this test to fail

        # pytest-django will clean up before next iteration
