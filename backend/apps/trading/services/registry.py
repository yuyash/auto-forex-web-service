from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.trading.strategies.base import Strategy

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfig


@dataclass(frozen=True)
class StrategyInfo:
    identifier: str
    strategy_cls: type[Strategy]
    config_schema: dict[str, Any]
    display_name: str
    description: str


class StrategyRegistry:
    def __init__(self) -> None:
        self._strategies: dict[str, StrategyInfo] = {}

    def register(
        self,
        *,
        identifier: str,
        strategy_cls: type[Strategy],
        config_schema: dict[str, Any] | None = None,
        display_name: str | None = None,
        description: str = "",
    ) -> None:
        key = str(identifier).strip()
        if not key:
            raise ValueError("Strategy identifier must be non-empty")
        if key in self._strategies:
            return

        schema = dict(config_schema or {})
        schema.setdefault("display_name", display_name or key)

        self._strategies[key] = StrategyInfo(
            identifier=key,
            strategy_cls=strategy_cls,
            config_schema=schema,
            display_name=str(display_name or schema.get("display_name") or key),
            description=str(description or ""),
        )

    def is_registered(self, identifier: str) -> bool:
        return str(identifier) in self._strategies

    def list_strategies(self) -> list[str]:
        return sorted(self._strategies.keys())

    def get_all_strategies_info(self) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for key, item in self._strategies.items():
            info[key] = {
                "config_schema": dict(item.config_schema),
                "display_name": item.display_name,
                "description": item.description,
            }
        return info

    def create(
        self, *, instrument: str, pip_size: Decimal, strategy_config: "StrategyConfig"
    ) -> Strategy:
        """Create a strategy instance.

        Args:
            instrument: Trading instrument (e.g., "USD_JPY")
            pip_size: Pip size for the instrument
            strategy_config: StrategyConfig model instance

        Returns:
            Strategy: Initialized strategy instance

        Raises:
            ValueError: If strategy identifier is unknown
        """
        key = str(strategy_config.strategy_type)
        if key not in self._strategies:
            raise ValueError(f"Unknown strategy '{key}'")

        strategy_cls = self._strategies[key].strategy_cls

        # Parse StrategyConfig to strategy-specific config object
        parsed_config = strategy_cls.parse_config(strategy_config)

        # Instantiate strategy with parsed config
        return strategy_cls(instrument, pip_size, parsed_config)


registry = StrategyRegistry()


def register_strategy(
    id: str,
    schema: dict[str, Any] | str | None = None,
    *,
    display_name: str | None = None,
    description: str = "",
) -> Callable[[type[Strategy]], type[Strategy]]:
    """Register a strategy with optional schema path or dict.

    Args:
        id: Unique strategy identifier
        schema: Schema dict or path to JSON schema file (e.g., "trading/schemas/floor.json")
        display_name: Display name for the strategy
        description: Strategy description

    Returns:
        Decorator function

    Example:
        >>> @register_strategy(id="floor", schema="trading/schemas/floor.json")
        ... class FloorStrategy(Strategy[FloorStrategyState]):
        ...     pass
    """

    def _decorator(strategy_cls: type[Strategy]) -> type[Strategy]:
        # Load schema from file if path provided
        loaded_schema: dict[str, Any] | None = None
        if isinstance(schema, str):
            import json
            from pathlib import Path

            from django.conf import settings

            # Resolve path relative to backend/apps/
            schema_path = Path(settings.BASE_DIR) / "apps" / schema
            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    loaded_schema = json.load(f)
            else:
                raise FileNotFoundError(f"Schema file not found: {schema_path}")
        elif isinstance(schema, dict):
            loaded_schema = schema

        registry.register(
            identifier=id,
            strategy_cls=strategy_cls,
            config_schema=loaded_schema,
            display_name=display_name,
            description=description,
        )
        return strategy_cls

    return _decorator


def register_all_strategies() -> None:
    """Register all strategy implementations."""

    if not registry.is_registered("floor"):
        # Import triggers decorator registration.
        from apps.trading.strategies import floor as floor_module

        _ = floor_module.FloorStrategy


__all__ = [
    "StrategyInfo",
    "StrategyRegistry",
    "registry",
    "register_strategy",
    "register_all_strategies",
]
