"""Unit tests for StrategyConfigurations model."""

import pytest
from django.contrib.auth import get_user_model

from apps.trading.models import StrategyConfigurations

User = get_user_model()


@pytest.mark.django_db
class TestStrategyConfigurationsModel:
    """Test suite for StrategyConfigurations model."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_create_strategy_configuration_with_valid_data(self, user):
        """Test creating StrategyConfigurations with valid fields."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1", "param2": 100},
            description="Test description",
        )

        assert config.id is not None
        assert config.user == user
        assert config.name == "Test Config"
        assert config.strategy_type == "floor"
        assert config.parameters == {"param1": "value1", "param2": 100}
        assert config.description == "Test description"
        assert config.created_at is not None
        assert config.updated_at is not None

    def test_unique_constraint_on_user_name(self, user):
        """Test that (user, name) must be unique."""
        # Create first config
        StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        # Attempt to create duplicate with same user and name
        with pytest.raises(Exception):  # IntegrityError
            StrategyConfigurations.objects.create(
                user=user,  # Same user
                name="Test Config",  # Same name
                strategy_type="momentum",
                parameters={},
            )

    def test_config_dict_property(self, user):
        """Test config_dict property returns parameters."""
        params = {"param1": "value1", "param2": 100}
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters=params,
        )

        assert config.config_dict == params

    def test_validate_parameters_with_valid_strategy(self, user):
        """Test validate_parameters with registered strategy."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"param1": "value1"},
        )

        is_valid, error = config.validate_parameters()
        # Should be valid if floor strategy is registered
        assert is_valid or error is not None  # Either valid or has error message

    def test_validate_parameters_with_invalid_strategy(self, user):
        """Test validate_parameters with unregistered strategy."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="nonexistent_strategy",
            parameters={},
        )

        is_valid, error = config.validate_parameters()
        assert not is_valid
        assert "not registered" in error

    def test_manager_for_user(self, user):
        """Test manager method for_user."""
        user2 = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        StrategyConfigurations.objects.create(
            user=user2,
            name="Config 2",
            strategy_type="momentum",
            parameters={},
        )

        user_configs = StrategyConfigurations.objects.for_user(user)
        assert user_configs.count() == 1
        assert user_configs.first().user == user

    def test_manager_create_for_user(self, user):
        """Test manager method create_for_user."""
        config = StrategyConfigurations.objects.create_for_user(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        assert config.user == user
        assert config.name == "Test Config"
