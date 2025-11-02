"""
Unit tests for StrategyRegistry.

Tests strategy registration, lookup, and configuration schema retrieval.

Requirements: 5.1
"""

import pytest

from trading.base_strategy import BaseStrategy
from trading.strategy_registry import StrategyRegistry, register_strategy, registry
from trading.tick_data_models import TickData


class MockStrategy(BaseStrategy):
    """Mock strategy for testing."""

    def on_tick(self, tick_data: TickData) -> list:
        """Mock on_tick implementation."""
        return []

    def on_position_update(self, position) -> None:
        """Mock on_position_update implementation."""
        pass

    def validate_config(self, config: dict) -> bool:
        """Mock validate_config implementation."""
        return True


class AnotherMockStrategy(BaseStrategy):
    """Another mock strategy for testing."""

    def on_tick(self, tick_data: TickData) -> list:
        """Mock on_tick implementation."""
        return []

    def on_position_update(self, position) -> None:
        """Mock on_position_update implementation."""
        pass

    def validate_config(self, config: dict) -> bool:
        """Mock validate_config implementation."""
        return True


class NotAStrategy:
    """Class that does not inherit from BaseStrategy."""

    pass


@pytest.fixture
def clean_registry():
    """Fixture to provide a clean registry for each test."""
    # Clear the registry before each test
    registry.clear()
    yield registry
    # Clear again after test
    registry.clear()


class TestStrategyRegistry:
    """Test suite for StrategyRegistry class."""

    def test_singleton_pattern(self, clean_registry):
        """Test that StrategyRegistry implements singleton pattern."""
        registry1 = StrategyRegistry()
        registry2 = StrategyRegistry()

        assert registry1 is registry2
        assert registry1 is clean_registry

    def test_register_strategy(self, clean_registry):
        """Test registering a strategy class."""
        config_schema = {
            "type": "object",
            "properties": {"lot_size": {"type": "number"}},
        }

        clean_registry.register("mock", MockStrategy, config_schema)

        assert clean_registry.is_registered("mock")
        assert "mock" in clean_registry.list_strategies()

    def test_register_strategy_without_schema(self, clean_registry):
        """Test registering a strategy without explicit schema generates default."""
        clean_registry.register("mock", MockStrategy)

        schema = clean_registry.get_config_schema("mock")
        assert schema["type"] == "object"
        assert "title" in schema
        assert "properties" in schema

    def test_register_duplicate_strategy_raises_error(self, clean_registry):
        """Test that registering duplicate strategy name raises ValueError."""
        clean_registry.register("mock", MockStrategy)

        with pytest.raises(ValueError, match="already registered"):
            clean_registry.register("mock", AnotherMockStrategy)

    def test_register_non_strategy_class_raises_error(self, clean_registry):
        """Test that registering non-BaseStrategy class raises TypeError."""
        with pytest.raises(TypeError, match="must inherit from BaseStrategy"):
            clean_registry.register("invalid", NotAStrategy)

    def test_unregister_strategy(self, clean_registry):
        """Test unregistering a strategy."""
        clean_registry.register("mock", MockStrategy)
        assert clean_registry.is_registered("mock")

        clean_registry.unregister("mock")
        assert not clean_registry.is_registered("mock")

    def test_unregister_nonexistent_strategy_raises_error(self, clean_registry):
        """Test that unregistering non-existent strategy raises KeyError."""
        with pytest.raises(KeyError, match="not registered"):
            clean_registry.unregister("nonexistent")

    def test_get_strategy_class(self, clean_registry):
        """Test retrieving a strategy class by name."""
        clean_registry.register("mock", MockStrategy)

        strategy_class = clean_registry.get_strategy_class("mock")
        assert strategy_class is MockStrategy

    def test_get_nonexistent_strategy_raises_error(self, clean_registry):
        """Test that getting non-existent strategy raises KeyError."""
        with pytest.raises(KeyError, match="not registered"):
            clean_registry.get_strategy_class("nonexistent")

    def test_list_strategies(self, clean_registry):
        """Test listing all registered strategies."""
        clean_registry.register("mock1", MockStrategy)
        clean_registry.register("mock2", AnotherMockStrategy)

        strategies = clean_registry.list_strategies()
        assert len(strategies) == 2
        assert "mock1" in strategies
        assert "mock2" in strategies

    def test_list_strategies_empty(self, clean_registry):
        """Test listing strategies when none are registered."""
        strategies = clean_registry.list_strategies()
        assert strategies == []

    def test_get_config_schema(self, clean_registry):
        """Test retrieving configuration schema for a strategy."""
        config_schema = {
            "type": "object",
            "properties": {
                "lot_size": {"type": "number", "default": 1.0},
                "scaling_mode": {"type": "string", "enum": ["additive", "multiplicative"]},
            },
            "required": ["lot_size"],
        }

        clean_registry.register("mock", MockStrategy, config_schema)

        retrieved_schema = clean_registry.get_config_schema("mock")
        assert retrieved_schema == config_schema
        assert "lot_size" in retrieved_schema["properties"]
        assert "scaling_mode" in retrieved_schema["properties"]

    def test_get_config_schema_nonexistent_raises_error(self, clean_registry):
        """Test that getting schema for non-existent strategy raises KeyError."""
        with pytest.raises(KeyError, match="not registered"):
            clean_registry.get_config_schema("nonexistent")

    def test_get_all_strategies_info(self, clean_registry):
        """Test retrieving information about all registered strategies."""
        schema1 = {"type": "object", "properties": {"param1": {"type": "number"}}}
        schema2 = {"type": "object", "properties": {"param2": {"type": "string"}}}

        clean_registry.register("mock1", MockStrategy, schema1)
        clean_registry.register("mock2", AnotherMockStrategy, schema2)

        all_info = clean_registry.get_all_strategies_info()

        assert len(all_info) == 2
        assert "mock1" in all_info
        assert "mock2" in all_info

        assert all_info["mock1"]["name"] == "mock1"
        assert all_info["mock1"]["class_name"] == "MockStrategy"
        assert all_info["mock1"]["config_schema"] == schema1

        assert all_info["mock2"]["name"] == "mock2"
        assert all_info["mock2"]["class_name"] == "AnotherMockStrategy"
        assert all_info["mock2"]["config_schema"] == schema2

    def test_is_registered(self, clean_registry):
        """Test checking if a strategy is registered."""
        assert not clean_registry.is_registered("mock")

        clean_registry.register("mock", MockStrategy)
        assert clean_registry.is_registered("mock")

    def test_clear_registry(self, clean_registry):
        """Test clearing all registered strategies."""
        clean_registry.register("mock1", MockStrategy)
        clean_registry.register("mock2", AnotherMockStrategy)

        assert len(clean_registry.list_strategies()) == 2

        clean_registry.clear()
        assert len(clean_registry.list_strategies()) == 0

    def test_repr(self, clean_registry):
        """Test string representation of registry."""
        clean_registry.register("mock", MockStrategy)

        repr_str = repr(clean_registry)
        assert "StrategyRegistry" in repr_str
        assert "strategies=1" in repr_str
        assert "mock" in repr_str


class TestRegisterStrategyDecorator:
    """Test suite for register_strategy decorator."""

    def test_decorator_registers_strategy(self, clean_registry):
        """Test that decorator successfully registers a strategy."""

        @register_strategy("decorated_mock")
        class DecoratedStrategy(BaseStrategy):
            """Decorated strategy."""

            def on_tick(self, tick_data: TickData) -> list:
                return []

            def on_position_update(self, position) -> None:
                pass

            def validate_config(self, config: dict) -> bool:
                return True

        assert clean_registry.is_registered("decorated_mock")
        assert clean_registry.get_strategy_class("decorated_mock") is DecoratedStrategy

    def test_decorator_with_schema(self, clean_registry):
        """Test decorator with explicit configuration schema."""
        schema = {
            "type": "object",
            "properties": {"test_param": {"type": "string"}},
        }

        @register_strategy("decorated_with_schema", config_schema=schema)
        class DecoratedStrategyWithSchema(BaseStrategy):
            """Decorated strategy with schema."""

            def on_tick(self, tick_data: TickData) -> list:
                return []

            def on_position_update(self, position) -> None:
                pass

            def validate_config(self, config: dict) -> bool:
                return True

        retrieved_schema = clean_registry.get_config_schema("decorated_with_schema")
        assert retrieved_schema == schema

    def test_decorator_returns_unmodified_class(self, clean_registry):
        """Test that decorator returns the original class unmodified."""

        @register_strategy("unmodified_mock")
        class UnmodifiedStrategy(BaseStrategy):
            """Unmodified strategy."""

            test_attribute = "test_value"

            def on_tick(self, tick_data: TickData) -> list:
                return []

            def on_position_update(self, position) -> None:
                pass

            def validate_config(self, config: dict) -> bool:
                return True

        # Verify the class is unmodified
        assert hasattr(UnmodifiedStrategy, "test_attribute")
        assert UnmodifiedStrategy.test_attribute == "test_value"

        # Verify it's still registered
        assert clean_registry.get_strategy_class("unmodified_mock") is UnmodifiedStrategy
