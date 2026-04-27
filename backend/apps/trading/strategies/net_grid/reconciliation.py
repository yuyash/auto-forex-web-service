from __future__ import annotations

from decimal import Decimal
from typing import Any


def reconcile_broker_positions(
    *,
    state: Any,
    open_positions: list[Any],
    report: Any,
    strategy_config: Any | None = None,
) -> None:
    """Align Net Grid state with broker-reconciled open positions.

    The generic reconciliation service has already synchronized local
    ``Position`` rows against OANDA open trades.  Net Grid then treats those
    rows as the broker-backed source of truth and records any strategy-state
    adjustment in the grid ledger.
    """
    strategy_state = (
        dict(state.strategy_state or {}) if isinstance(state.strategy_state, dict) else {}
    )
    before_net = int(strategy_state.get("current_net_units", 0) or 0)
    before_avg = strategy_state.get("average_entry_price")
    broker_net = _net_units(open_positions)
    broker_avg = _weighted_average(open_positions)

    strategy_state["current_net_units"] = broker_net
    strategy_state["target_net_units"] = broker_net
    strategy_state["open_units"] = abs(broker_net)
    strategy_state["open_direction"] = _direction_value(broker_net)
    strategy_state["average_entry_price"] = str(broker_avg) if broker_avg is not None else None
    strategy_state["open_position_id"] = (
        str(open_positions[-1].id) if open_positions and broker_net != 0 else None
    )
    if broker_net == 0:
        strategy_state["step"] = 0
        strategy_state["anchor_price"] = None
        strategy_state["last_grid_price"] = None
        strategy_state["net_take_profit_price"] = None
        strategy_state["next_grid_price"] = None
        strategy_state["take_profit_remaining_pips"] = None
        strategy_state["step_usage"] = "0"
        config_dict = dict(getattr(strategy_config, "config_dict", {}) or {})
        strategy_state["max_steps"] = int(config_dict.get("max_steps", 5) or 5)
    else:
        _update_derived_levels(strategy_state, strategy_config, open_positions)

    if before_net != broker_net or str(before_avg or "") != str(
        strategy_state["average_entry_price"] or ""
    ):
        entry = {
            "timestamp": None,
            "action": "broker_reconciliation",
            "reason": "broker_position_state_sync",
            "units_delta": broker_net - before_net,
            "filled_price": None,
            "net_units_before": before_net,
            "net_units_after": broker_net,
            "avg_price_before": str(before_avg) if before_avg is not None else None,
            "avg_price_after": strategy_state["average_entry_price"],
            "realized_pnl": "0",
            "realized_pnl_quote": "0",
            "source": "broker_reconciliation",
        }
        raw_ledger = strategy_state.get("grid_ledger")
        ledger: list[Any] = raw_ledger if isinstance(raw_ledger, list) else []
        strategy_state["grid_ledger"] = [*ledger, entry][-500:]
        strategy_state["latest_position_transition"] = entry
        if hasattr(report, "messages"):
            report.messages.append("Net Grid strategy state synchronized with broker positions.")

    state.strategy_state = strategy_state


def _net_units(open_positions: list[Any]) -> int:
    total = 0
    for position in open_positions:
        units = int(getattr(position, "units", 0) or 0)
        if str(getattr(position, "direction", "")).lower() == "short" and units > 0:
            units = -units
        total += units
    return total


def _weighted_average(open_positions: list[Any]) -> Decimal | None:
    total_units = 0
    weighted = Decimal("0")
    for position in open_positions:
        units = abs(int(getattr(position, "units", 0) or 0))
        if units <= 0:
            continue
        total_units += units
        weighted += Decimal(str(getattr(position, "entry_price"))) * Decimal(str(units))
    if total_units <= 0:
        return None
    return weighted / Decimal(str(total_units))


def _direction_value(net_units: int) -> str:
    if net_units > 0:
        return "long"
    if net_units < 0:
        return "short"
    return ""


def _update_derived_levels(
    strategy_state: dict[str, Any],
    strategy_config: Any | None,
    open_positions: list[Any],
) -> None:
    avg = strategy_state.get("average_entry_price")
    if avg in (None, ""):
        strategy_state["net_take_profit_price"] = None
        return
    config_dict = dict(getattr(strategy_config, "config_dict", {}) or {})
    take_profit_pips = Decimal(str(config_dict.get("take_profit_pips", "5")))
    grid_interval_pips = Decimal(str(config_dict.get("grid_interval_pips", "30")))
    max_steps = int(config_dict.get("max_steps", 5) or 5)
    max_net_units = int(config_dict.get("max_net_units", 10000) or 10000)
    min_order_units = int(config_dict.get("min_order_units", 1) or 1)
    strategy_state["max_steps"] = max_steps
    instrument = str(getattr(open_positions[0], "instrument", "") or "") if open_positions else ""
    if instrument:
        from apps.trading.utils import pip_size_for_instrument

        pip_size = pip_size_for_instrument(instrument)
    else:
        pip_size = Decimal(str(config_dict.get("pip_size", "0.01")))
    current_net = int(strategy_state.get("current_net_units", 0) or 0)
    distance = take_profit_pips * pip_size
    average = Decimal(str(avg))
    strategy_state["net_take_profit_price"] = str(
        average + distance if current_net > 0 else average - distance
    )
    step = int(strategy_state.get("step", 0) or 0)
    strategy_state["step_usage"] = (
        str(Decimal(str(step)) / Decimal(str(max_steps))) if max_steps > 0 else "0"
    )
    room = max_net_units - abs(current_net)
    last_grid_price = (
        Decimal(str(strategy_state.get("last_grid_price")))
        if strategy_state.get("last_grid_price") not in (None, "")
        else average
    )
    if step < max_steps and room >= min_order_units:
        grid_distance = grid_interval_pips * pip_size
        strategy_state["next_grid_price"] = str(
            last_grid_price - grid_distance if current_net > 0 else last_grid_price + grid_distance
        )
    else:
        strategy_state["next_grid_price"] = None
