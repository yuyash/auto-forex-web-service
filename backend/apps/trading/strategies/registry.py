from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apps.trading.strategies.base import Strategy

if TYPE_CHECKING:
    from apps.trading.models import StrategyConfiguration


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
            raise ValueError(f"Strategy '{key}' is already registered")

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

    def get(self, identifier: str) -> StrategyInfo:
        key = str(identifier).strip()
        info = self._strategies.get(key)
        if info is None:
            raise ValueError(f"Unknown strategy '{key}'")
        return info

    def list_strategies(self) -> list[str]:
        return sorted(self._strategies.keys())

    def get_all_strategies_info(self) -> dict[str, dict[str, Any]]:
        info: dict[str, dict[str, Any]] = {}
        for key, item in self._strategies.items():
            info[key] = {
                "config_schema": dict(item.config_schema),
                "display_name": item.display_name,
                "description": item.description,
                "strategy_class": getattr(
                    item.strategy_cls,
                    "__name__",
                    item.strategy_cls.__class__.__name__,
                ),
            }
        return info

    def normalize_parameters(self, *, identifier: str, parameters: dict[str, Any]) -> dict[str, Any]:
        strategy_info = self.get(identifier)
        return strategy_info.strategy_cls.normalize_parameters(dict(parameters))

    def validate_parameters(self, *, identifier: str, parameters: dict[str, Any]) -> None:
        strategy_info = self.get(identifier)
        strategy_info.strategy_cls.validate_parameters(
            parameters=parameters,
            config_schema=strategy_info.config_schema,
        )

    def get_defaults(self, *, identifier: str) -> dict[str, Any]:
        strategy_info = self.get(identifier)
        defaults: dict[str, Any] = {}
        properties = strategy_info.config_schema.get("properties")
        if isinstance(properties, dict):
            for key, prop in properties.items():
                if isinstance(prop, dict) and "default" in prop and prop.get("default") is not None:
                    defaults[key] = prop["default"]

        class_defaults = strategy_info.strategy_cls.default_parameters()
        defaults.update(class_defaults)
        return defaults

    def create(
        self,
        *,
        instrument: str,
        pip_size: Decimal,
        strategy_config: "StrategyConfiguration",
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
        strategy_info = self.get(str(strategy_config.strategy_type))
        strategy_cls = strategy_info.strategy_cls

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
    """Auto-discover and register all strategy implementations.

    Scans the ``strategies/`` directory for sub-packages that contain a
    ``strategy`` module and imports them, triggering ``@register_strategy``
    decorator registration.  This means adding a new strategy only requires
    creating ``strategies/<name>/strategy.py`` with the decorator — no
    manual import list to maintain.
    """
    strategies_dir = Path(__file__).resolve().parent
    package_prefix = "apps.trading.strategies"

    for module_info in pkgutil.iter_modules([str(strategies_dir)]):
        name = module_info.name
        if name.startswith("_") or name in {"base", "registry"}:
            continue
        try:
            importlib.import_module(f"{package_prefix}.{name}.strategy")
        except ModuleNotFoundError as exc:
            expected = f"{package_prefix}.{name}.strategy"
            if exc.name != expected:
                raise
            importlib.import_module(f"{package_prefix}.{name}")


__all__ = [
    "StrategyInfo",
    "StrategyRegistry",
    "registry",
    "register_strategy",
    "register_all_strategies",
]
