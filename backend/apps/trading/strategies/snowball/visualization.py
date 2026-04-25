"""Snowball strategy visualization adapters."""

from __future__ import annotations

from typing import Any

from apps.trading.strategies.snowball.models import SnowballStrategyState


def build_cycle_grid_state_map(
    *,
    strategy_state: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    """Return cycle_id -> grid state mappings for Snowball cycles."""
    if not isinstance(strategy_state, dict):
        return {}

    state = SnowballStrategyState.from_dict(strategy_state)
    result: dict[str, dict[str, Any]] = {}

    for cycle in state.cycles:
        grid_state = _serialize_cycle_grid(cycle)
        cycle_keys = {
            str(key)
            for key in (cycle.trade_cycle_id, cycle.cycle_id)
            if key is not None and str(key) != ""
        }
        for cycle_key in cycle_keys:
            result[cycle_key] = grid_state

    return result


def build_cycle_status_map(
    *,
    strategy_state: dict[str, Any] | None,
) -> dict[str, str]:
    """Return trade_cycle_id -> status mappings for Snowball cycles."""
    if not isinstance(strategy_state, dict):
        return {}

    state = SnowballStrategyState.from_dict(strategy_state)
    result: dict[str, str] = {}
    for cycle in state.cycles:
        if cycle.trade_cycle_id:
            result[str(cycle.trade_cycle_id)] = str(cycle.status.value)
    return result


def _serialize_cycle_grid(cycle: Any) -> dict[str, Any]:
    layers: list[dict[str, Any]] = []
    counts = {
        "filled": 0,
        "stopped": 0,
        "rebuilt": 0,
        "empty": 0,
    }
    max_slot_index = 0

    for layer in cycle.grid.layers:
        slots: list[dict[str, Any]] = []
        for slot in layer.slots:
            state, position_id = _resolve_slot_state(slot)
            counts[state] += 1
            max_slot_index = max(max_slot_index, slot.index)
            slots.append(
                {
                    "slot": slot.index,
                    "state": state,
                    "position_id": position_id,
                }
            )

        layers.append(
            {
                "layer": layer.layer_number,
                "slots": slots,
            }
        )

    return {
        "layers": layers,
        "summary": {
            **counts,
            "layer_count": len(layers),
            "slot_count_per_layer": max_slot_index + 1 if layers else 0,
        },
    }


def _resolve_slot_state(slot: Any) -> tuple[str, str | None]:
    if slot.entry is not None:
        return (
            ("rebuilt", slot.entry.position_id)
            if slot.entry.is_rebuild
            else (
                "filled",
                slot.entry.position_id,
            )
        )

    if slot.pending_rebuild is not None:
        return "stopped", slot.pending_rebuild.position_id

    return "empty", None
