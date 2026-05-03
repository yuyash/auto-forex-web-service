"""Strategy-specific snapshot projectors."""

from __future__ import annotations

from typing import Any

SNOWBALL_SNAPSHOT_CARD_KEYS = (
    "protection_level",
    "active_cycles",
    "pending_cycles",
    "completed_cycles",
    "open_entries",
    "open_long_units",
    "open_short_units",
    "account_balance",
    "account_nav",
    "lock_entered_at",
    "cooldown_until",
)

SNOWBALL_NET_SNAPSHOT_CARD_KEYS = (
    "status",
    "direction",
    "net_units",
    "average_price",
    "current_price",
    "pips_from_average",
    "target_price",
    "next_add_price",
    "next_add_distance_pips",
    "add_count",
    "exposure_pct",
    "margin_ratio_pct",
    "pending_action",
)


def build_strategy_snapshot(strategy_type: str, state: dict[str, Any]) -> dict[str, Any]:
    if strategy_type == "snowball":
        return _snowball_snapshot(state)
    if strategy_type == "snowball_net":
        return _snowball_net_snapshot(state)
    return {"status": "unknown", "cards": [], "state": {}}


def _snowball_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    try:
        from apps.trading.strategies.snowball.models import SnowballStrategyState

        parsed = SnowballStrategyState.from_strategy_state(state)
        active = len(parsed.active_cycles())
        pending = len([cycle for cycle in parsed.cycles if cycle.is_pending])
        completed = len([cycle for cycle in parsed.cycles if cycle.completed])
        entries = parsed.all_entries()
        values = {
            "protection_level": parsed.protection_level.value,
            "active_cycles": active,
            "pending_cycles": pending,
            "completed_cycles": completed,
            "open_entries": len(entries),
            "open_long_units": sum(abs(entry.units) for entry in entries if entry.is_long),
            "open_short_units": sum(abs(entry.units) for entry in entries if entry.is_short),
            "account_balance": str(parsed.account_balance),
            "account_nav": str(parsed.account_nav),
            "last_mid": str(parsed.last_mid) if parsed.last_mid is not None else None,
            "lock_entered_at": parsed.lock_entered_at,
            "cooldown_until": parsed.cooldown_until,
            "margin_ratio": parsed.metrics.get("margin_ratio"),
        }
    except Exception:  # noqa: BLE001
        values = {
            "protection_level": state.get("protection_level"),
            "active_cycles": len(state.get("cycles") or []),
            "account_nav": state.get("account_nav"),
            "last_mid": state.get("last_mid"),
        }
    return {
        "status": str(values.get("protection_level") or "unknown"),
        "cards": _cards_from_state(values, SNOWBALL_SNAPSHOT_CARD_KEYS),
        "state": values,
    }


def _snowball_net_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    try:
        from apps.trading.strategies.snowball_net.state import SnowballNetState

        parsed = SnowballNetState.from_strategy_state(state)
        metrics = parsed.metrics
        values = {
            "status": "pending_order"
            if parsed.pending_action
            else "open"
            if parsed.net_units > 0
            else "waiting_entry",
            "direction": parsed.direction,
            "net_units": parsed.net_units,
            "average_price": str(parsed.average_price)
            if parsed.average_price is not None
            else None,
            "position_id": parsed.position_id,
            "current_price": metrics.get("snowball_net_current_price"),
            "pips_from_average": metrics.get("snowball_net_pips_from_average"),
            "target_price": metrics.get("snowball_net_target_price"),
            "next_add_price": metrics.get("snowball_net_next_add_price"),
            "next_add_distance_pips": metrics.get("snowball_net_next_add_distance_pips"),
            "add_count": parsed.add_count,
            "exposure_pct": metrics.get("snowball_net_exposure_pct"),
            "margin_ratio_pct": metrics.get("snowball_net_margin_ratio_pct"),
            "pending_action": parsed.pending_action.get("kind") if parsed.pending_action else None,
            "last_action": parsed.last_action,
        }
    except Exception:  # noqa: BLE001
        raw_metrics = state.get("metrics")
        metrics: dict[str, Any] = raw_metrics if isinstance(raw_metrics, dict) else {}
        values = {
            "status": "unknown",
            "direction": state.get("direction"),
            "net_units": state.get("net_units"),
            "average_price": state.get("average_price"),
            "current_price": metrics.get("snowball_net_current_price"),
            "pips_from_average": metrics.get("snowball_net_pips_from_average"),
        }
    return {
        "status": str(values.get("status") or "unknown"),
        "cards": _cards_from_state(values, SNOWBALL_NET_SNAPSHOT_CARD_KEYS),
        "state": values,
    }


def _cards_from_state(state: dict[str, Any], keys: Any) -> list[dict[str, Any]]:
    return [
        {"id": key, "label_key": f"strategy.snapshot.{key}", "value": state.get(key)}
        for key in keys
        if state.get(key) not in (None, "")
    ]
