from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from apps.trading.services.base import Strategy

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

        # Instantiate strategy directly with instrument, pip_size, and config
        return strategy_cls(instrument, pip_size, strategy_config)


registry = StrategyRegistry()


def register_strategy(
    identifier: str,
    config_schema: dict[str, Any] | str | None = None,
    *,
    display_name: str | None = None,
    description: str = "",
) -> Callable[[type[Strategy]], type[Strategy]]:
    """Register a strategy with optional schema path or dict.

    Args:
        identifier: Unique strategy identifier
        config_schema: Schema dict or path to JSON schema file (e.g., "trading/schemas/floor.json")
        display_name: Display name for the strategy
        description: Strategy description

    Returns:
        Decorator function

    Example:
        >>> @register_strategy("floor", "trading/schemas/floor.json")
        ... class FloorStrategyService(Strategy[FloorStrategyState]):
        ...     pass
    """

    def _decorator(strategy_cls: type[Strategy]) -> type[Strategy]:
        # Load schema from file if path provided
        schema: dict[str, Any] | None = None
        if isinstance(config_schema, str):
            import json
            from pathlib import Path

            from django.conf import settings

            # Resolve path relative to backend/apps/
            schema_path = Path(settings.BASE_DIR) / "apps" / config_schema
            if schema_path.exists():
                with open(schema_path, encoding="utf-8") as f:
                    schema = json.load(f)
            else:
                raise FileNotFoundError(f"Schema file not found: {schema_path}")
        elif isinstance(config_schema, dict):
            schema = config_schema

        registry.register(
            identifier=identifier,
            strategy_cls=strategy_cls,
            config_schema=schema,
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
