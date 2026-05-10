"""Unit tests for trading serializers strategy."""

from unittest.mock import MagicMock, patch

import pytest
from rest_framework.exceptions import ValidationError

from apps.trading.serializers.strategy import (
    StrategyConfigCreateSerializer,
    StrategyConfigDetailSerializer,
    StrategyConfigListSerializer,
    StrategyConfigSerializer,
    StrategyListSerializer,
)
from apps.trading.enums import TaskStatus
from tests.integration.factories import BacktestTaskFactory, StrategyConfigurationFactory


class TestStrategyConfigDetailSerializer:
    """Test StrategyConfigDetailSerializer."""

    def test_meta_fields(self):
        fields = StrategyConfigDetailSerializer.Meta.fields
        assert "id" in fields
        assert "name" in fields
        assert "strategy_type" in fields
        assert "parameters" in fields
        assert "is_in_use" in fields
        assert "has_running_tasks" in fields

    def test_get_is_in_use(self):
        serializer = StrategyConfigDetailSerializer()
        obj = MagicMock()
        obj.is_in_use.return_value = True
        assert serializer.get_is_in_use(obj) is True

    def test_get_is_in_use_false(self):
        serializer = StrategyConfigDetailSerializer()
        obj = MagicMock()
        obj.is_in_use.return_value = False
        assert serializer.get_is_in_use(obj) is False

    def test_get_has_running_tasks(self):
        serializer = StrategyConfigDetailSerializer()
        obj = MagicMock()
        obj.has_active_tasks.return_value = True
        assert serializer.get_has_running_tasks(obj) is True


class TestStrategyConfigListSerializer:
    """Test StrategyConfigListSerializer."""

    def test_meta_fields(self):
        fields = StrategyConfigListSerializer.Meta.fields
        assert "id" in fields
        assert "name" in fields
        assert "strategy_type" in fields
        assert "has_running_tasks" in fields
        # parameters should NOT be in list view
        assert "parameters" not in fields


class TestStrategyConfigCreateSerializer:
    """Test StrategyConfigCreateSerializer."""

    def test_meta_fields(self):
        fields = StrategyConfigCreateSerializer.Meta.fields
        assert "name" in fields
        assert "strategy_type" in fields
        assert "parameters" in fields

    @patch("apps.trading.strategies.registry.registry")
    def test_validate_strategy_type_invalid(self, mock_registry):
        mock_registry.is_registered.return_value = False
        mock_registry.list_strategies.return_value = ["floor"]
        serializer = StrategyConfigCreateSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_strategy_type("invalid")

    @patch("apps.trading.strategies.registry.registry")
    def test_validate_strategy_type_valid(self, mock_registry):
        mock_registry.is_registered.return_value = True
        serializer = StrategyConfigCreateSerializer()
        result = serializer.validate_strategy_type("floor")
        assert result == "floor"

    def test_validate_parameters_not_dict(self):
        serializer = StrategyConfigCreateSerializer()

        with pytest.raises(ValidationError):
            serializer.validate_parameters("not a dict")

    def test_validate_parameters_valid(self):
        serializer = StrategyConfigCreateSerializer()
        result = serializer.validate_parameters({"key": "value"})
        assert result == {"key": "value"}

    def test_update_blocks_only_when_this_configuration_has_running_tasks(self):
        serializer = StrategyConfigCreateSerializer()
        instance = MagicMock()
        instance.has_active_tasks.return_value = True
        serializer.instance = instance

        with pytest.raises(ValidationError) as exc_info:
            serializer.update(instance, {"parameters": {"foo": "bar"}})

        assert "tasks using this configuration are running" in str(exc_info.value.detail["detail"])

    def test_update_allows_edit_when_other_tasks_are_running(self):
        serializer = StrategyConfigCreateSerializer()
        instance = MagicMock()
        instance.has_active_tasks.return_value = False
        instance.is_in_use.return_value = True

        updated = serializer.update(instance, {"parameters": {"foo": "bar"}})

        assert updated is instance
        assert instance.parameters == {"foo": "bar"}
        instance.save.assert_called_once()

    @pytest.mark.django_db
    def test_update_records_db_backed_name_and_description_changes(self):
        config = StrategyConfigurationFactory(name="Original", description="Old")
        serializer = StrategyConfigCreateSerializer()

        updated = serializer.update(
            config,
            {"name": "Updated", "description": "New"},
        )

        updated.refresh_from_db()
        assert updated.name == "Updated"
        assert updated.description == "New"
        assert updated.revision == 1

    @pytest.mark.django_db
    def test_update_increments_revision_for_parameter_changes(self):
        config = StrategyConfigurationFactory(parameters={"base_units": 1000, "r_max": 5})
        original_hash = config.config_hash
        serializer = StrategyConfigCreateSerializer()

        updated = serializer.update(
            config,
            {"parameters": {"base_units": 2000, "r_max": 5}},
        )

        updated.refresh_from_db()
        assert updated.revision == 2
        assert updated.config_hash != original_hash

    @pytest.mark.django_db
    def test_update_blocks_when_configuration_has_paused_task(self):
        config = StrategyConfigurationFactory(parameters={"base_units": 1000, "r_max": 5})
        BacktestTaskFactory(config=config, status=TaskStatus.PAUSED)
        serializer = StrategyConfigCreateSerializer()

        with pytest.raises(ValidationError) as exc_info:
            serializer.update(config, {"parameters": {"base_units": 2000, "r_max": 5}})

        assert "tasks using this configuration are running" in str(exc_info.value.detail["detail"])

    @patch("apps.trading.strategies.registry.registry")
    def test_validate_hides_internal_value_error_details(self, mock_registry):
        mock_registry.normalize_parameters.side_effect = ValueError(
            "internal details should not be exposed"
        )
        serializer = StrategyConfigCreateSerializer()

        with pytest.raises(ValidationError) as exc_info:
            serializer.validate(
                {
                    "strategy_type": "floor",
                    "parameters": {"foo": "bar"},
                }
            )

        assert str(exc_info.value.detail["parameters"]) == "Invalid strategy parameters."


class TestStrategyListSerializer:
    """Test StrategyListSerializer."""

    def test_fields_exist(self):
        serializer = StrategyListSerializer()
        assert "id" in serializer.fields
        assert "name" in serializer.fields
        assert "config_schema" in serializer.fields


class TestStrategyConfigSerializer:
    """Test StrategyConfigSerializer."""

    def test_fields_exist(self):
        serializer = StrategyConfigSerializer()
        assert "strategy_id" in serializer.fields
        assert "config_schema" in serializer.fields
