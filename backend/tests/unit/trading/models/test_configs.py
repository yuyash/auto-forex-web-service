"""Unit tests for StrategyConfiguration model - field configuration and methods.

This test module focuses on testing model field configuration, model methods,
and validation logic WITHOUT database operations where possible.
"""

import uuid
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import models

from apps.trading.enums import StrategyType
from apps.trading.models import StrategyConfigurations
from apps.trading.models.base import UUIDModel

User = get_user_model()


class TestStrategyConfigurationFieldConfiguration:
    """Test field configuration without database operations."""

    def test_model_inherits_from_uuid_model(self):
        """Test that StrategyConfigurations inherits from UUIDModel."""
        assert issubclass(StrategyConfigurations, UUIDModel)

    def test_model_has_correct_fields(self):
        """Test that model has all required fields with correct types."""
        # Get all field names
        field_names = [f.name for f in StrategyConfigurations._meta.get_fields()]

        # Check required fields exist
        assert "id" in field_names
        assert "created_at" in field_names
        assert "updated_at" in field_names
        assert "user" in field_names
        assert "name" in field_names
        assert "strategy_type" in field_names
        assert "parameters" in field_names
        assert "description" in field_names

    def test_id_field_configuration(self):
        """Test id field is configured as UUID primary key."""
        id_field = StrategyConfigurations._meta.get_field("id")

        assert isinstance(id_field, models.UUIDField)
        assert id_field.primary_key is True
        assert id_field.default == uuid.uuid4
        assert id_field.editable is False

    def test_user_field_configuration(self):
        """Test user field is configured as ForeignKey."""
        user_field = StrategyConfigurations._meta.get_field("user")

        assert isinstance(user_field, models.ForeignKey)
        assert user_field.remote_field.on_delete == models.CASCADE
        assert user_field.remote_field.related_name == "strategy_configs"

    def test_name_field_configuration(self):
        """Test name field is configured correctly."""
        name_field = StrategyConfigurations._meta.get_field("name")

        assert isinstance(name_field, models.CharField)
        assert name_field.max_length == 255

    def test_strategy_type_field_configuration(self):
        """Test strategy_type field is configured correctly."""
        strategy_type_field = StrategyConfigurations._meta.get_field("strategy_type")

        assert isinstance(strategy_type_field, models.CharField)
        assert strategy_type_field.max_length == 50

    def test_parameters_field_configuration(self):
        """Test parameters field is configured as JSONField."""
        parameters_field = StrategyConfigurations._meta.get_field("parameters")

        assert isinstance(parameters_field, models.JSONField)
        assert parameters_field.default is dict

    def test_description_field_configuration(self):
        """Test description field is configured correctly."""
        description_field = StrategyConfigurations._meta.get_field("description")

        assert isinstance(description_field, models.TextField)
        assert description_field.blank is True
        assert description_field.default == ""

    def test_created_at_field_configuration(self):
        """Test created_at field is configured correctly."""
        created_at_field = StrategyConfigurations._meta.get_field("created_at")

        assert isinstance(created_at_field, models.DateTimeField)
        assert created_at_field.auto_now_add is True
        assert created_at_field.db_index is True  # type: ignore[union-attr]

    def test_updated_at_field_configuration(self):
        """Test updated_at field is configured correctly."""
        updated_at_field = StrategyConfigurations._meta.get_field("updated_at")

        assert isinstance(updated_at_field, models.DateTimeField)
        assert updated_at_field.auto_now is True
        assert updated_at_field.db_index is True  # type: ignore[union-attr]

    def test_model_meta_configuration(self):
        """Test model Meta configuration."""
        meta = StrategyConfigurations._meta

        assert meta.db_table == "strategy_configurations"
        assert meta.verbose_name == "Strategy Configuration"
        assert meta.verbose_name_plural == "Strategy Configurations"
        assert meta.ordering == ["-created_at"]

    def test_model_has_indexes(self):
        """Test model has correct indexes."""
        indexes = StrategyConfigurations._meta.indexes

        # Check that indexes exist
        assert len(indexes) >= 2

        # Check for user + strategy_type index
        index_fields = [tuple(idx.fields) for idx in indexes]
        assert ("user", "strategy_type") in index_fields
        assert ("created_at",) in index_fields

    def test_model_has_unique_constraint(self):
        """Test model has unique constraint on user and name."""
        constraints = StrategyConfigurations._meta.constraints

        # Find the unique constraint
        unique_constraints = [c for c in constraints if isinstance(c, models.UniqueConstraint)]
        assert len(unique_constraints) >= 1

        # Check the constraint fields
        constraint = unique_constraints[0]
        assert set(constraint.fields) == {"user", "name"}
        assert constraint.name == "unique_user_config_name"


class TestStrategyConfigurationMethods:
    """Test model methods without database operations."""

    def test_str_method_format(self):
        """Test __str__ method returns correct format."""
        # Create a mock instance without database
        config = StrategyConfigurations(
            name="Test Strategy",
            strategy_type="floor",
        )

        result = str(config)
        assert "Test Strategy" in result
        assert "floor" in result
        assert "(" in result and ")" in result

    def test_config_dict_property_returns_parameters(self):
        """Test config_dict property returns parameters."""
        params = {"key1": "value1", "key2": 123}
        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters=params,
        )

        assert config.config_dict == params

    def test_config_dict_property_with_none_parameters(self):
        """Test config_dict property handles None parameters."""
        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters=None,
        )

        assert config.config_dict == {}

    def test_config_dict_property_with_empty_dict(self):
        """Test config_dict property with empty dict."""
        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters={},
        )

        assert config.config_dict == {}

    def test_strategy_type_enum_property(self):
        """Test strategy_type_enum property returns StrategyType enum."""
        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters={},
        )

        result = config.strategy_type_enum
        assert isinstance(result, StrategyType)
        assert result == StrategyType.FLOOR

    def test_strategy_type_enum_property_with_custom(self):
        """Test strategy_type_enum property with custom type."""
        config = StrategyConfigurations(
            name="Test",
            strategy_type="custom",
            parameters={},
        )

        result = config.strategy_type_enum
        assert isinstance(result, StrategyType)
        assert result == StrategyType.CUSTOM


class TestStrategyConfigurationValidation:
    """Test validation logic without database operations."""

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_with_registered_strategy(self, mock_registry):
        """Test validate_parameters with registered strategy."""
        mock_registry.is_registered.return_value = True

        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters={"param": "value"},
        )

        is_valid, error = config.validate_parameters()

        assert is_valid is True
        assert error is None
        mock_registry.is_registered.assert_called_once_with("floor")

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_with_unregistered_strategy(self, mock_registry):
        """Test validate_parameters with unregistered strategy."""
        mock_registry.is_registered.return_value = False

        config = StrategyConfigurations(
            name="Test",
            strategy_type="nonexistent",
            parameters={},
        )

        is_valid, error = config.validate_parameters()

        assert is_valid is False
        assert error is not None
        assert "not registered" in error
        assert "nonexistent" in error

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_with_non_dict_parameters(self, mock_registry):
        """Test validate_parameters with non-dict parameters."""
        mock_registry.is_registered.return_value = True

        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters="invalid_string",  # type: ignore[arg-type]
        )

        is_valid, error = config.validate_parameters()

        assert is_valid is False
        assert error is not None
        assert "must be a JSON object" in error

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_with_list_parameters(self, mock_registry):
        """Test validate_parameters with list parameters."""
        mock_registry.is_registered.return_value = True

        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters=[1, 2, 3],  # type: ignore[arg-type]
        )

        is_valid, error = config.validate_parameters()

        assert is_valid is False
        assert error is not None
        assert "must be a JSON object" in error

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_with_empty_dict(self, mock_registry):
        """Test validate_parameters with empty dict is valid."""
        mock_registry.is_registered.return_value = True

        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters={},
        )

        is_valid, error = config.validate_parameters()

        assert is_valid is True
        assert error is None

    @patch("apps.trading.services.registry.registry")
    def test_validate_parameters_returns_tuple(self, mock_registry):
        """Test validate_parameters returns tuple of (bool, str|None)."""
        mock_registry.is_registered.return_value = True

        config = StrategyConfigurations(
            name="Test",
            strategy_type="floor",
            parameters={},
        )

        result = config.validate_parameters()

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert isinstance(result[0], bool)
        assert result[1] is None or isinstance(result[1], str)


class TestStrategyConfigurationManager:
    """Test custom manager methods without database operations."""

    def test_manager_class_exists(self):
        """Test that custom manager class exists."""
        from apps.trading.models.configs import StrategyConfigurationsManager

        assert StrategyConfigurationsManager is not None

    def test_manager_is_assigned_to_objects(self):
        """Test that custom manager is assigned to objects."""
        from apps.trading.models.configs import StrategyConfigurationsManager

        assert isinstance(StrategyConfigurations.objects, StrategyConfigurationsManager)

    def test_manager_has_create_for_user_method(self):
        """Test manager has create_for_user method."""
        assert hasattr(StrategyConfigurations.objects, "create_for_user")
        assert callable(StrategyConfigurations.objects.create_for_user)

    def test_manager_has_for_user_method(self):
        """Test manager has for_user method."""
        assert hasattr(StrategyConfigurations.objects, "for_user")
        assert callable(StrategyConfigurations.objects.for_user)


@pytest.mark.django_db
class TestStrategyConfigurationDatabaseOperations:
    """Test database operations that require database access."""

    @pytest.fixture
    def user(self):
        """Create a test user."""
        return User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_is_in_use_returns_false_when_no_tasks(self, user):
        """Test is_in_use returns False when no tasks reference the config."""
        config = StrategyConfigurations.objects.create(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={},
        )

        assert config.is_in_use() is False

    def test_manager_create_for_user(self, user):
        """Test manager create_for_user method."""
        config = StrategyConfigurations.objects.create_for_user(
            user=user,
            name="Test Config",
            strategy_type="floor",
            parameters={"key": "value"},
        )

        assert config.user == user
        assert config.name == "Test Config"
        assert config.strategy_type == "floor"
        assert config.parameters == {"key": "value"}

    def test_manager_for_user(self, user):
        """Test manager for_user method."""
        user2 = User.objects.create_user(  # type: ignore[attr-defined]
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
        )

        config1 = StrategyConfigurations.objects.create(
            user=user,
            name="Config 1",
            strategy_type="floor",
            parameters={},
        )
        config2 = StrategyConfigurations.objects.create(
            user=user2,
            name="Config 2",
            strategy_type="custom",
            parameters={},
        )

        user_configs = StrategyConfigurations.objects.for_user(user)

        assert user_configs.count() == 1
        assert config1 in user_configs
        assert config2 not in user_configs
