"""Minimal custom strategy skeleton.

This strategy is intentionally inert. It gives new strategy work a concrete
package shape and a non-Snowball implementation for registry/API tests without
placing trades.
"""

from __future__ import annotations

from typing import Any

from apps.trading.dataclasses import StrategyResult, Tick
from apps.trading.enums import StrategyType
from apps.trading.models.state import ExecutionState
from apps.trading.strategies.base import Strategy
from apps.trading.strategies.registry import register_strategy


@register_strategy(
    id="custom",
    schema="trading/schemas/custom.json",
    display_name="Custom Strategy",
    description="No-op strategy skeleton for custom implementations.",
)
class CustomStrategy(Strategy):
    """No-op strategy skeleton for custom implementations."""

    @staticmethod
    def parse_config(strategy_config: Any) -> dict[str, Any]:
        return dict(getattr(strategy_config, "config_dict", {}) or {})

    @classmethod
    def default_parameters(cls) -> dict[str, Any]:
        return {}

    @classmethod
    def normalize_parameters(cls, parameters: dict[str, Any]) -> dict[str, Any]:
        return dict(parameters)

    @property
    def strategy_type(self) -> StrategyType:
        return StrategyType.CUSTOM

    def on_tick(self, *, tick: Tick, state: ExecutionState) -> StrategyResult:
        state.last_tick_price = tick.mid
        state.last_tick_bid = tick.bid
        state.last_tick_ask = tick.ask
        state.last_tick_timestamp = tick.timestamp
        state.strategy_state = dict(state.strategy_state or {})
        return StrategyResult.from_state(state)
