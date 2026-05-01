"""Strategy-specific snapshot projectors."""

from __future__ import annotations

from typing import Any


def build_strategy_snapshot(strategy_type: str, state: dict[str, Any]) -> dict[str, Any]:
    if strategy_type == "snowball":
        return _snowball_snapshot(state)
    return {"status": "unknown", "cards": [], "state": {}}


def _snowball_snapshot(state: dict[str, Any]) -> dict[str, Any]:
    try:
        from apps.trading.strategies.snowball.models import SnowballStrategyState

        parsed = SnowballStrategyState.from_strategy_state(state)
        active = len(parsed.active_cycles())
        pending = len([cycle for cycle in parsed.cycles if cycle.is_pending])
        completed = len([cycle for cycle in parsed.cycles if cycle.completed])
        open_entries = sum(len(cycle.all_entries()) for cycle in parsed.active_cycles())
        values = {
            "protection_level": parsed.protection_level.value,
            "active_cycles": active,
            "pending_cycles": pending,
            "completed_cycles": completed,
            "open_entries": open_entries,
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
        "cards": _cards_from_state(values, tuple(values.keys())),
        "state": values,
    }


def _cards_from_state(state: dict[str, Any], keys: Any) -> list[dict[str, Any]]:
    return [
        {"id": key, "label_key": f"strategy.snapshot.{key}", "value": state.get(key)}
        for key in keys
        if state.get(key) not in (None, "")
    ]
