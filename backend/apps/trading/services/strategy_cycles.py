"""Cycle-based strategy visualization service.

Builds cycle list from Trade.cycle_id.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID


class StrategyCyclesService:
    """Build cycle response from Trade records grouped by cycle_id."""

    def build(
        self,
        *,
        task: Any,
        task_type: str,
        execution_id: UUID | str | None,
        cycle_id: str | None = None,
    ) -> dict[str, Any]:
        from apps.trading.models.trades import Trade

        if not execution_id:
            return {"cycles": [], "summary": _empty_summary()}

        qs = Trade.objects.filter(
            task_type=task_type,
            task_id=task.pk,
            execution_id=execution_id,
            cycle_id__isnull=False,
        ).order_by("timestamp")

        if cycle_id:
            qs = qs.filter(cycle_id=cycle_id)

        rows = list(
            qs.values(
                "id",
                "cycle_id",
                "direction",
                "units",
                "instrument",
                "price",
                "execution_method",
                "layer_index",
                "retracement_count",
                "description",
                "timestamp",
                "position_id",
                "updated_at",
            )
        )

        if not rows:
            return {
                "execution_id": str(execution_id),
                "cycles": [],
                "summary": _empty_summary(),
            }

        by_cycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_cycle[str(row["cycle_id"])].append(row)

        cycles = [_build_cycle(cid, trades) for cid, trades in by_cycle.items()]
        cycles.sort(key=lambda c: c["started_at"] or "")

        return {
            "execution_id": str(execution_id),
            "cycles": cycles,
            "summary": _build_summary(cycles),
        }


def _build_cycle(cycle_id: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    first = trades[0]
    last = trades[-1]
    direction = str(first.get("direction") or "")

    opens = [t for t in trades if t["execution_method"] == "open_position"]
    closes = [t for t in trades if t["execution_method"] == "close_position"]
    open_ids = {str(t["position_id"]) for t in opens if t.get("position_id")}
    close_ids = {str(t["position_id"]) for t in closes if t.get("position_id")}
    has_open_remaining = bool(open_ids - close_ids)

    # The initial entry is the first open trade in the cycle (cycle_id == trade.id)
    initial = next(
        (t for t in opens if str(t["id"]) == cycle_id),
        opens[0] if opens else first,
    )
    initial_closed = str(initial.get("position_id", "")) in close_ids

    if initial_closed:
        status = "completed"
    elif has_open_remaining:
        status = "active"
    else:
        status = "completed"

    return {
        "cycle_id": cycle_id,
        "direction": direction,
        "status": status,
        "started_at": first["timestamp"].isoformat() if first.get("timestamp") else None,
        "ended_at": last["timestamp"].isoformat()
        if status == "completed" and last.get("timestamp")
        else None,
        "trade_count": len(trades),
        "open_count": len(opens),
        "close_count": len(closes),
        "trades": [_serialize_trade(t) for t in trades],
    }


def _serialize_trade(t: dict[str, Any]) -> dict[str, Any]:
    direction = t.get("direction")
    if direction is not None:
        direction = (
            "buy"
            if str(direction).lower() == "long"
            else "sell"
            if str(direction).lower() == "short"
            else direction
        )
    return {
        "id": str(t["id"]),
        "direction": direction,
        "units": t["units"],
        "price": str(t["price"]),
        "execution_method": t["execution_method"],
        "layer_index": t.get("layer_index"),
        "retracement_count": t.get("retracement_count"),
        "description": t.get("description", ""),
        "timestamp": t["timestamp"].isoformat() if t.get("timestamp") else None,
        "position_id": str(t["position_id"]) if t.get("position_id") else None,
    }


def _empty_summary() -> dict[str, int]:
    return {
        "cycle_count": 0,
        "active_count": 0,
        "completed_count": 0,
        "total_trades": 0,
    }


def _build_summary(cycles: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cycle_count": len(cycles),
        "active_count": sum(1 for c in cycles if c["status"] == "active"),
        "completed_count": sum(1 for c in cycles if c["status"] == "completed"),
        "total_trades": sum(c["trade_count"] for c in cycles),
    }
