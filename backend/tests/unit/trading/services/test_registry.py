from __future__ import annotations

from typing import Any

import pytest

from apps.trading.services.base import Strategy
from apps.trading.services.registry import StrategyRegistry, register_all_strategies


class _DummyStrategy(Strategy):
    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)

    def on_tick(
        self, *, tick: dict[str, Any], state: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return state, []


class TestStrategyRegistry:
    def test_register_requires_non_empty_identifier(self):
        reg = StrategyRegistry()
        with pytest.raises(ValueError):
            reg.register(identifier="", strategy_cls=_DummyStrategy)

    def test_register_is_idempotent(self):
        reg = StrategyRegistry()
        reg.register(identifier="x", strategy_cls=_DummyStrategy, config_schema={"a": 1})
        reg.register(identifier="x", strategy_cls=_DummyStrategy, config_schema={"a": 2})
        assert reg.is_registered("x") is True
        assert reg.list_strategies() == ["x"]

    def test_get_all_strategies_info_returns_copy(self):
        reg = StrategyRegistry()
        reg.register(identifier="x", strategy_cls=_DummyStrategy, config_schema={"a": 1})
        info = reg.get_all_strategies_info()
        assert info["x"]["config_schema"]["a"] == 1
        info["x"]["config_schema"]["a"] = 999
        info2 = reg.get_all_strategies_info()
        assert info2["x"]["config_schema"]["a"] == 1

    def test_create_unknown_raises(self):
        reg = StrategyRegistry()
        with pytest.raises(ValueError):
            reg.create(identifier="missing", config={})


def test_register_all_strategies_registers_floor():
    # Uses the module-level singleton registry and should be idempotent.
    register_all_strategies()

    from apps.trading.services.registry import registry

    assert registry.is_registered("floor") is True
