from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .base import Strategy


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

    def create(self, *, identifier: str, config: dict[str, Any]) -> Strategy:
        key = str(identifier)
        if key not in self._strategies:
            raise ValueError(f"Unknown strategy '{key}'")
        return self._strategies[key].strategy_cls(config)


registry = StrategyRegistry()


def register_strategy(
    identifier: str,
    config_schema: dict[str, Any] | None = None,
    *,
    display_name: str | None = None,
    description: str = "",
) -> Callable[[type[Strategy]], type[Strategy]]:
    def _decorator(strategy_cls: type[Strategy]) -> type[Strategy]:
        registry.register(
            identifier=identifier,
            strategy_cls=strategy_cls,
            config_schema=config_schema,
            display_name=display_name,
            description=description,
        )
        return strategy_cls

    return _decorator


def register_all_strategies() -> None:
    """Idempotently register all strategy implementations."""

    if not registry.is_registered("floor"):
        # Import triggers decorator registration.
        from apps.trading.services import floor as floor_module

        _ = floor_module.FloorStrategyService


__all__ = [
    "StrategyInfo",
    "StrategyRegistry",
    "registry",
    "register_strategy",
    "register_all_strategies",
]
