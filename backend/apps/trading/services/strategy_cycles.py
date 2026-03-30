"""Cycle-based strategy visualization service.

Builds cycle list from Trade.cycle_id.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
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
            return {"cycles": [], "summary": _empty_summary(), "last_tick_timestamp": None}

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
                "last_tick_timestamp": None,
            }

        # Look up metrics (volatility, margin) at each trade timestamp
        metrics_by_minute = _load_metrics_for_trades(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=str(execution_id),
            trades=rows,
        )

        by_cycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_cycle[str(row["cycle_id"])].append(row)

        cycles = [_build_cycle(cid, trades, metrics_by_minute) for cid, trades in by_cycle.items()]
        cycles.sort(key=lambda c: c["started_at"] or "")

        # Resolve the last tick timestamp from the execution state so the
        # frontend can use it as the effective "now" for active (unclosed)
        # cycles instead of the real wall-clock time.
        last_tick_ts = _resolve_last_tick_timestamp(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=str(execution_id),
        )

        return {
            "execution_id": str(execution_id),
            "cycles": cycles,
            "summary": _build_summary(cycles),
            "last_tick_timestamp": last_tick_ts,
        }


def _resolve_last_tick_timestamp(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
) -> str | None:
    """Return the ISO-formatted last_tick_timestamp from ExecutionState.

    This is the simulated "current time" for a running or completed backtest,
    used by the frontend to anchor active-cycle charts instead of wall-clock time.
    """
    from apps.trading.models.state import ExecutionState as ExecutionStateModel

    row = (
        ExecutionStateModel.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
        )
        .values_list("last_tick_timestamp", flat=True)
        .first()
    )
    if row is not None:
        return row.isoformat()
    return None


def _load_metrics_for_trades(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    trades: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Load minute-level metrics closest to each trade timestamp.

    Returns a dict keyed by ISO-formatted minute bucket → metrics dict.
    """
    from apps.trading.models.metrics import Metrics

    if not trades:
        return {}

    # Collect unique minute buckets for all trade timestamps
    minute_keys: set[str] = set()
    for t in trades:
        ts = t.get("timestamp")
        if ts:
            bucket = ts.replace(second=0, microsecond=0)
            minute_keys.add(bucket.isoformat())

    if not minute_keys:
        return {}

    # Find the time range and query metrics in one go
    timestamps = [t["timestamp"] for t in trades if t.get("timestamp")]
    min_ts = min(timestamps) - timedelta(minutes=1)
    max_ts = max(timestamps) + timedelta(minutes=1)

    rows = Metrics.objects.filter(
        task_type=task_type,
        task_id=task_id,
        execution_id=execution_id,
        timestamp__gte=min_ts,
        timestamp__lte=max_ts,
    ).values_list("timestamp", "metrics")

    result: dict[str, dict[str, Any]] = {}
    for ts, metrics in rows:
        if isinstance(metrics, dict):
            key = ts.replace(second=0, microsecond=0).isoformat()
            result[key] = metrics

    return result


def _build_cycle(
    cycle_id: str, trades: list[dict[str, Any]], metrics_by_minute: dict[str, dict[str, Any]]
) -> dict[str, Any]:
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

    _PROTECTION_METHODS = {"volatility_lock", "margin_protection", "shrink", "rebalance"}
    protection_trades = [
        t
        for t in trades
        if t["execution_method"] in _PROTECTION_METHODS
        or str(t.get("description") or "").startswith("[PROTECTION]")
    ]
    has_protection = len(protection_trades) > 0

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
        "has_protection": has_protection,
        "protection_count": len(protection_trades),
        "trades": [_serialize_trade(t, metrics_by_minute) for t in trades],
    }


def _serialize_trade(
    t: dict[str, Any], metrics_by_minute: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    direction = t.get("direction")
    if direction is not None:
        direction = (
            "buy"
            if str(direction).lower() == "long"
            else "sell"
            if str(direction).lower() == "short"
            else direction
        )

    # Look up metrics at the trade's minute bucket
    volatility = None
    margin_ratio = None
    ts = t.get("timestamp")
    if ts:
        bucket_key = ts.replace(second=0, microsecond=0).isoformat()
        metrics = metrics_by_minute.get(bucket_key, {})
        if metrics.get("current_atr") is not None:
            volatility = f"{float(metrics['current_atr']):.3f}"
        if metrics.get("margin_ratio") is not None:
            margin_ratio = f"{float(metrics['margin_ratio']):.3f}"

    return {
        "id": str(t["id"]),
        "direction": direction,
        "units": t["units"],
        "price": f"{float(t['price']):.3f}",
        "execution_method": t["execution_method"],
        "layer_index": t.get("layer_index"),
        "retracement_count": t.get("retracement_count"),
        "description": t.get("description", ""),
        "timestamp": t["timestamp"].isoformat() if t.get("timestamp") else None,
        "position_id": str(t["position_id"]) if t.get("position_id") else None,
        "volatility": volatility,
        "margin_ratio": margin_ratio,
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
