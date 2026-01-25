"""Integration tests for StrategyConfigurations model database operations."""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.utils import timezone

from apps.trading.models import StrategyConfigurations

User = get_user_model()


@pytest.mark.django_db
class TestStrategyConfigurationsIntegration:
    """Integration tests for StrategyConfigurations model database operations."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_save_and_retrieve_strategy_configuration(self, user):
        """Test saving and retrieving a strategy configuration from database."""
        # Create and save
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1", "param2": 100},
            description="Test description",
        )

        # Retrieve from database
        retrieved = StrategyConfigurations.objects.get(id=config.id)

        assert retrieved.id == config.id
        assert isinstance(retrieved.id, uuid.UUID)
        assert retrieved.user == user
        assert retrieved.name == "Test Config"
        assert retrieved.strategy_type == "floor"
        assert retrieved.parameters == {"param1": "value1", "param2": 100}
        assert retrieved.description == "Test description"

    def test_update_strategy_configuration(self, user):
        """Test updating a strategy configuration in database."""
        # Create
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1"},
        )

        # Update
        config.name = "Updated Config"
        config.parameters = {"param1": "updated_value", "param2": 200}
        config.save()

        # Retrieve and verify
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.name == "Updated Config"
        assert retrieved.parameters == {"param1": "updated_value", "param2": 200}

    def test_delete_strategy_configuration(self, user):
        """Test deleting a strategy configuration from database."""
        # Create
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )
        config_id = config.id

        # Delete
        config.delete()

        # Verify deletion
        assert not StrategyConfigurations.objects.filter(id=config_id).exists()

    def test_query_by_user(self, user):
        """Test querying configurations by user."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        # Create configs for different users
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        config2 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user2,
            name="Config 3",
            strategy_type="floor",
            parameters={},
        )

        # Query by user
        user_configs = StrategyConfigurations.objects.filter(user=user)
        assert user_configs.count() == 2
        assert set(user_configs.values_list("id", flat=True)) == {config1.id, config2.id}

    def test_query_by_strategy_type(self, user):
        """Test querying configurations by strategy type."""
        # Create configs with different strategy types
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )
        config3 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 3",
            strategy_type="floor",
            parameters={},
        )

        # Query by strategy type
        floor_configs = StrategyConfigurations.objects.filter(strategy_type="floor")
        assert floor_configs.count() == 2
        assert set(floor_configs.values_list("id", flat=True)) == {config1.id, config3.id}

    def test_unique_constraint_enforcement(self, user):
        """Test that unique constraint on (user, name) is enforced."""
        # Create first config
        StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Attempt to create duplicate
        with pytest.raises(IntegrityError):
            StrategyConfigurations.objects.create(
                user=user,
                name="Test Config",  # Same name
                strategy_type="momentum",
                parameters={},
            )

    def test_ordering_by_created_at(self, user):
        """Test that configurations are ordered by created_at descending."""
        # Create configs in sequence
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        config2 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )
        config3 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 3",
            strategy_type="floor",
            parameters={},
        )

        # Query all configs
        configs = list(StrategyConfigurations.objects.filter(user=user))

        # Verify ordering (newest first)
        assert configs[0].id == config3.id
        assert configs[1].id == config2.id
        assert configs[2].id == config1.id

    def test_cascade_delete_on_user_deletion(self, user):
        """Test that configurations are deleted when user is deleted."""
        # Create configs
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        config2 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )

        config_ids = [config1.id, config2.id]

        # Delete user
        user.delete()

        # Verify configs are deleted
        assert StrategyConfigurations.objects.filter(id__in=config_ids).count() == 0

    def test_json_field_persistence(self, user):
        """Test that complex JSON data is persisted correctly."""
        complex_params = {
            "nested": {
                "param1": "value1",
                "param2": [1, 2, 3],
                "param3": {"key": "value"},
            },
            "list": [1, 2, 3, 4, 5],
            "boolean": True,
            "null": None,
        }

        # Create with complex parameters
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters=complex_params,
        )

        # Retrieve and verify
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.parameters == complex_params

    def test_to_dict_method_with_database(self, user):
        """Test to_dict method with data from database."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1"},
            description="Test description",
        )

        # Retrieve from database and convert to dict
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        config_dict = retrieved.to_dict()

        assert config_dict["id"] == str(retrieved.id)
        assert config_dict["user_id"] == user.pk
        assert config_dict["name"] == "Test Config"
        assert config_dict["strategy_type"] == "floor"
        assert config_dict["parameters"] == {"param1": "value1"}
        assert config_dict["description"] == "Test description"
        assert config_dict["created_at"] is not None
        assert config_dict["updated_at"] is not None

    def test_from_dict_method_with_database(self, user):
        """Test from_dict method and save to database."""
        data = {
            "name": "Test Config",
            "strategy_type": "floor",
            "parameters": {"param1": "value1", "param2": 100},
            "description": "Test description",
        }

        # Create from dict
        config = StrategyConfigurations.from_dict(data, user)
        config.save()

        # Retrieve from database and verify
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.name == "Test Config"
        assert retrieved.strategy_type == "floor"
        assert retrieved.parameters == {"param1": "value1", "param2": 100}
        assert retrieved.description == "Test description"
        assert retrieved.user == user

    def test_is_in_use_with_no_tasks(self, user):
        """Test is_in_use returns False when no tasks reference the config."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        assert config.is_in_use() is False

    def test_is_in_use_with_running_backtest_task(self, user):
        """Test is_in_use returns True when a running backtest task references the config."""
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create a running backtest task
        BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Test Backtest",
            status=TaskStatus.RUNNING,
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        assert config.is_in_use() is True

    def test_is_in_use_with_completed_backtest_task(self, user):
        """Test is_in_use returns False when only completed backtest tasks reference the config."""
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create a completed backtest task
        BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Test Backtest",
            status=TaskStatus.COMPLETED,
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        assert config.is_in_use() is False

    def test_is_in_use_with_running_trading_task(self, user):
        """Test is_in_use returns True when a running trading task references the config."""
        from apps.market.models import OandaAccounts
        from apps.trading.enums import TaskStatus
        from apps.trading.models import TradingTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create an OANDA account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="test-account-123",
            api_type="practice",
        )

        # Create a running trading task
        TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Test Trading",
            status=TaskStatus.RUNNING,
        )

        assert config.is_in_use() is True

    def test_is_in_use_with_stopped_trading_task(self, user):
        """Test is_in_use returns False when only stopped trading tasks reference the config."""
        from apps.market.models import OandaAccounts
        from apps.trading.enums import TaskStatus
        from apps.trading.models import TradingTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create an OANDA account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="test-account-123",
            api_type="practice",
        )

        # Create a stopped trading task
        TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Test Trading",
            status=TaskStatus.STOPPED,
        )

        assert config.is_in_use() is False

    def test_is_in_use_with_multiple_tasks(self, user):
        """Test is_in_use with multiple tasks in different states."""
        from apps.market.models import OandaAccounts
        from apps.trading.enums import TaskStatus
        from apps.trading.models import BacktestTasks, TradingTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create completed backtest task
        BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Completed Backtest",
            status=TaskStatus.COMPLETED,
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        # Create an OANDA account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="test-account-123",
            api_type="practice",
        )

        # Create stopped trading task
        TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Stopped Trading",
            status=TaskStatus.STOPPED,
        )

        # Should be False since no running tasks
        assert config.is_in_use() is False

        # Create a running backtest task
        BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Running Backtest",
            status=TaskStatus.RUNNING,
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        # Should now be True
        assert config.is_in_use() is True

    def test_manager_for_user_with_database(self, user):
        """Test manager for_user method with database queries."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        # Create configs for different users
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        config2 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user2,
            name="Config 3",
            strategy_type="floor",
            parameters={},
        )

        # Use manager method
        user_configs = StrategyConfigurations.objects.for_user(user)

        assert user_configs.count() == 2
        assert config1 in user_configs
        assert config2 in user_configs

    def test_manager_create_for_user_with_database(self, user):
        """Test manager create_for_user method with database."""
        config = StrategyConfigurations.objects.create_for_user(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"key": "value"},
            description="Test description",
        )

        # Verify it's in database
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.user == user
        assert retrieved.name == "Test Config"
        assert retrieved.strategy_type == "floor"
        assert retrieved.parameters == {"key": "value"}
        assert retrieved.description == "Test description"

    def test_related_name_backtest_tasks(self, user):
        """Test that backtest_tasks related name works correctly."""
        from apps.trading.models import BacktestTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create backtest tasks
        task1 = BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Backtest 1",
            start_time=timezone.now(),
            end_time=timezone.now(),
        )
        task2 = BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Backtest 2",
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        # Access via related name
        backtest_tasks = config.backtest_tasks.all()
        assert backtest_tasks.count() == 2
        assert task1 in backtest_tasks
        assert task2 in backtest_tasks

    def test_related_name_trading_tasks(self, user):
        """Test that trading_tasks related name works correctly."""
        from apps.market.models import OandaAccounts
        from apps.trading.models import TradingTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create an OANDA account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="test-account-123",
            api_type="practice",
        )

        # Create trading tasks
        task1 = TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Trading 1",
        )
        task2 = TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Trading 2",
        )

        # Access via related name
        trading_tasks = config.trading_tasks.all()
        assert trading_tasks.count() == 2
        assert task1 in trading_tasks
        assert task2 in trading_tasks

    def test_protect_on_delete_with_backtest_task(self, user):
        """Test that config cannot be deleted when backtest tasks reference it."""
        from django.db.models import ProtectedError

        from apps.trading.models import BacktestTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create a backtest task
        BacktestTasks.objects.create(
            user=user,
            config=config,
            name="Test Backtest",
            start_time=timezone.now(),
            end_time=timezone.now(),
        )

        # Attempt to delete config should raise ProtectedError
        with pytest.raises(ProtectedError):
            config.delete()

    def test_protect_on_delete_with_trading_task(self, user):
        """Test that config cannot be deleted when trading tasks reference it."""
        from django.db.models import ProtectedError

        from apps.market.models import OandaAccounts
        from apps.trading.models import TradingTasks

        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Create an OANDA account
        account = OandaAccounts.objects.create(
            user=user,
            account_id="test-account-123",
            api_type="practice",
        )

        # Create a trading task
        TradingTasks.objects.create(
            user=user,
            config=config,
            oanda_account=account,
            name="Test Trading",
        )

        # Attempt to delete config should raise ProtectedError
        with pytest.raises(ProtectedError):
            config.delete()

    def test_timestamps_are_updated_on_save(self, user):
        """Test that updated_at timestamp is updated when config is saved."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        original_updated_at = config.updated_at

        # Wait a moment
        import time

        time.sleep(0.01)

        # Update and save
        config.name = "Updated Config"
        config.save()

        # Retrieve from database
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.updated_at > original_updated_at
        assert retrieved.name == "Updated Config"

    def test_bulk_create_strategy_configurations(self, user):
        """Test bulk creating multiple strategy configurations."""
        configs = [
            StrategyConfigurations(
                user=user,
                name=f"Config {i}",
                strategy_type="floor",
                parameters={"index": i},
            )
            for i in range(5)
        ]

        created_configs = StrategyConfigurations.objects.bulk_create(configs)

        assert len(created_configs) == 5
        assert StrategyConfigurations.objects.filter(user=user).count() == 5

        # Verify all have UUIDs
        for config in created_configs:
            assert config.id is not None

    def test_filter_by_user_and_strategy_type(self, user):
        """Test filtering by both user and strategy_type using index."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        # Create configs with different users and strategy types
        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user2,
            name="Config 3",
            strategy_type="floor",
            parameters={},
        )

        # Filter by user and strategy_type (should use composite index)
        results = StrategyConfigurations.objects.filter(user=user, strategy_type="floor")

        assert results.count() == 1
        assert results.first() == config1

    def test_empty_parameters_default(self, user):
        """Test that parameters defaults to empty dict when not provided."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
        )

        # Retrieve from database
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.parameters == {}

    def test_empty_description_default(self, user):
        """Test that description defaults to empty string when not provided."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Retrieve from database
        retrieved = StrategyConfigurations.objects.get(id=config.id)
        assert retrieved.description == ""
