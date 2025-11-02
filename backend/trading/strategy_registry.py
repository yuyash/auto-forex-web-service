"""
Strategy Registry for managing trading strategy registration and lookup.

This module provides a centralized registry for all trading strategies,
allowing dynamic strategy registration, lookup, and configuration schema retrieval.

Requirements: 5.1
"""

from typing import Any, Type

from .base_strategy import BaseStrategy


class StrategyRegistry:
    """
    Registry for managing trading strategy classes.

    This class provides a singleton registry pattern for registering and
    retrieving trading strategy implementations. It allows strategies to be
    registered dynamically and provides methods to list available strategies
    and retrieve their configuration schemas.

    Requirements: 5.1
    """

    _instance: "StrategyRegistry | None" = None
    _strategies: dict[str, Type[BaseStrategy]] = {}
    _config_schemas: dict[str, dict[str, Any]] = {}

    def __new__(cls) -> "StrategyRegistry":
        """
        Implement singleton pattern to ensure only one registry instance exists.

        Returns:
            The singleton StrategyRegistry instance
        """
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register(
        self,
        name: str,
        strategy_class: Type[BaseStrategy],
        config_schema: dict[str, Any] | None = None,
    ) -> None:
        """
        Register a strategy class with the registry.

        Args:
            name: Unique identifier for the strategy (e.g., 'floor', 'trend_following')
            strategy_class: The strategy class that inherits from BaseStrategy
            config_schema: Optional JSON schema describing the strategy's configuration

        Raises:
            ValueError: If strategy name is already registered
            TypeError: If strategy_class does not inherit from BaseStrategy

        Requirements: 5.1
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(
                f"Strategy class {strategy_class.__name__} must inherit from BaseStrategy"
            )

        if name in self._strategies:
            raise ValueError(f"Strategy '{name}' is already registered")

        self._strategies[name] = strategy_class

        if config_schema is None:
            config_schema = self._generate_default_schema(strategy_class)

        self._config_schemas[name] = config_schema

    def unregister(self, name: str) -> None:
        """
        Unregister a strategy from the registry.

        Args:
            name: Strategy identifier to unregister

        Raises:
            KeyError: If strategy name is not registered
        """
        if name not in self._strategies:
            raise KeyError(f"Strategy '{name}' is not registered")

        del self._strategies[name]
        del self._config_schemas[name]

    def get_strategy_class(self, name: str) -> Type[BaseStrategy]:
        """
        Get a strategy class by name.

        Args:
            name: Strategy identifier

        Returns:
            The strategy class

        Raises:
            KeyError: If strategy name is not registered

        Requirements: 5.1
        """
        if name not in self._strategies:
            raise KeyError(
                f"Strategy '{name}' is not registered. "
                f"Available strategies: {', '.join(self.list_strategies())}"
            )

        return self._strategies[name]

    def list_strategies(self) -> list[str]:
        """
        Get a list of all registered strategy names.

        Returns:
            List of strategy identifiers

        Requirements: 5.1
        """
        return list(self._strategies.keys())

    def get_config_schema(self, name: str) -> dict[str, Any]:
        """
        Get the configuration schema for a strategy.

        The schema describes the expected configuration parameters,
        their types, default values, and validation rules.

        Args:
            name: Strategy identifier

        Returns:
            Dictionary containing the configuration schema

        Raises:
            KeyError: If strategy name is not registered

        Requirements: 5.1
        """
        if name not in self._config_schemas:
            raise KeyError(
                f"Strategy '{name}' is not registered. "
                f"Available strategies: {', '.join(self.list_strategies())}"
            )

        return self._config_schemas[name]

    def get_all_strategies_info(self) -> dict[str, dict[str, Any]]:
        """
        Get information about all registered strategies.

        Returns:
            Dictionary mapping strategy names to their info including
            class name, description, and configuration schema

        Requirements: 5.1
        """
        strategies_info = {}

        for name, strategy_class in self._strategies.items():
            strategies_info[name] = {
                "name": name,
                "class_name": strategy_class.__name__,
                "description": strategy_class.__doc__ or "No description available",
                "config_schema": self._config_schemas[name],
            }

        return strategies_info

    def is_registered(self, name: str) -> bool:
        """
        Check if a strategy is registered.

        Args:
            name: Strategy identifier

        Returns:
            True if strategy is registered, False otherwise
        """
        return name in self._strategies

    def clear(self) -> None:
        """
        Clear all registered strategies.

        This method is primarily useful for testing purposes.
        """
        self._strategies.clear()
        self._config_schemas.clear()

    @staticmethod
    def _generate_default_schema(strategy_class: Type[BaseStrategy]) -> dict[str, Any]:
        """
        Generate a default configuration schema for a strategy class.

        This provides a basic schema structure when none is explicitly provided.

        Args:
            strategy_class: The strategy class

        Returns:
            Default configuration schema
        """
        return {
            "type": "object",
            "title": f"{strategy_class.__name__} Configuration",
            "description": strategy_class.__doc__ or "Strategy configuration",
            "properties": {},
            "required": [],
        }

    def __repr__(self) -> str:
        """Developer-friendly representation of the registry."""
        return (
            f"<StrategyRegistry strategies={len(self._strategies)} "
            f"registered={list(self._strategies.keys())}>"
        )


# Global registry instance
registry = StrategyRegistry()


def register_strategy(
    name: str, config_schema: dict[str, Any] | None = None
) -> Any:  # Returns decorator function
    """
    Decorator for registering a strategy class.

    This provides a convenient way to register strategies using a decorator pattern.

    Args:
        name: Unique identifier for the strategy
        config_schema: Optional JSON schema for the strategy configuration

    Returns:
        Decorator function

    Example:
        @register_strategy('floor', config_schema={...})
        class FloorStrategy(BaseStrategy):
            pass

    Requirements: 5.1
    """

    def decorator(strategy_class: Type[BaseStrategy]) -> Type[BaseStrategy]:
        """
        Inner decorator function that performs the registration.

        Args:
            strategy_class: The strategy class to register

        Returns:
            The unmodified strategy class
        """
        registry.register(name, strategy_class, config_schema)
        return strategy_class

    return decorator
