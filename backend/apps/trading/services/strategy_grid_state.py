"""Grid-state helpers for strategy visualization."""

from __future__ import annotations

from typing import Any


def build_cycle_grid_state_map(
    *,
    strategy_type: str,
    strategy_state: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return cycle_id -> grid state mappings for strategies that expose one."""
    if not strategy_type or not isinstance(strategy_state, dict):
        return {}

    from apps.trading.strategies.registry import registry

    if not registry.is_registered(strategy_type):
        return {}
    return registry.build_cycle_grid_state_map(
        identifier=strategy_type,
        strategy_state=strategy_state,
    )
