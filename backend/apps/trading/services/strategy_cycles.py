"""Cycle-based strategy visualization service.

Builds cycle list from Trade.cycle_id.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from apps.trading.services.strategy_grid_state import build_cycle_grid_state_map


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
                "margin_ratio",
                "is_rebuild",
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

        execution_state = _load_execution_state_snapshot(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=str(execution_id),
        )
        strategy_state = (
            execution_state.get("strategy_state")
            if isinstance(execution_state.get("strategy_state"), dict)
            else None
        )
        cycle_status_map = _load_cycle_statuses(strategy_state)
        cycle_grid_state_map = build_cycle_grid_state_map(
            strategy_type=str(getattr(task.config, "strategy_type", "")),
            strategy_state=strategy_state,
        )

        cycles = [
            _build_cycle(
                cid,
                trades,
                metrics_by_minute,
                cycle_status_map.get(cid),
                cycle_grid_state_map.get(cid),
            )
            for cid, trades in by_cycle.items()
        ]
        cycles.sort(key=lambda c: c["started_at"] or "")

        last_tick_ts = _resolve_last_tick_timestamp(execution_state)

        return {
            "execution_id": str(execution_id),
            "cycles": cycles,
            "summary": _build_summary(cycles),
            "last_tick_timestamp": last_tick_ts,
        }


def _load_execution_state_snapshot(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
) -> dict[str, Any]:
    """Return the execution-state fields needed for strategy visualization."""
    from apps.trading.models.state import ExecutionState as ExecutionStateModel

    row = (
        ExecutionStateModel.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
        )
        .values("strategy_state", "last_tick_timestamp")
        .first()
    )
    return row or {}


def _resolve_last_tick_timestamp(execution_state: dict[str, Any]) -> str | None:
    """Return the ISO-formatted last_tick_timestamp from ExecutionState.

    This is the simulated "current time" for a running or completed backtest,
    used by the frontend to anchor active-cycle charts instead of wall-clock time.
    """
    row = execution_state.get("last_tick_timestamp")
    if row is not None:
        return row.isoformat()
    return None


def _load_cycle_statuses(strategy_state: dict[str, Any] | None) -> dict[str, str]:
    """Load cycle statuses from the persisted strategy_state.

    Returns a mapping of trade_cycle_id (UUID str) → status string
    ("active", "pending", "completed").  Falls back to an empty dict
    if the state is unavailable or cycles lack trade_cycle_id.
    """
    if not isinstance(strategy_state, dict):
        return {}

    result: dict[str, str] = {}
    for cycle_data in strategy_state.get("cycles", []):
        tcid = cycle_data.get("trade_cycle_id")
        if not tcid:
            continue
        status = cycle_data.get("status")
        if status is None:
            status = "completed" if cycle_data.get("completed", False) else "active"
        result[str(tcid)] = str(status)
    return result


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
    cycle_id: str,
    trades: list[dict[str, Any]],
    metrics_by_minute: dict[str, dict[str, Any]],
    authoritative_status: str | None = None,
    grid_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    first = trades[0]
    last = trades[-1]
    direction = str(first.get("direction") or "")

    _OPEN_METHODS = {"open_position", "rebuild_position"}
    opens = [t for t in trades if t["execution_method"] in _OPEN_METHODS]
    closes = [t for t in trades if t["execution_method"] not in _OPEN_METHODS]
    open_ids = {str(t["position_id"]) for t in opens if t.get("position_id")}
    close_ids = {str(t["position_id"]) for t in closes if t.get("position_id")}
    has_open_remaining = bool(open_ids - close_ids)

    # Use authoritative status from strategy_state when available;
    # otherwise fall back to event-based inference.
    if authoritative_status is not None:
        status = authoritative_status
    else:
        initial = next(
            (t for t in opens if str(t["id"]) == cycle_id),
            opens[0] if opens else first,
        )
        initial_closed = str(initial.get("position_id", "")) in close_ids

        # Check if there are rebuild trades that haven't been closed yet,
        # indicating pending stop-loss rebuilds that didn't complete.
        rebuild_open_ids = {
            str(t["position_id"])
            for t in trades
            if t.get("is_rebuild")
            and t["execution_method"] == "rebuild_position"
            and t.get("position_id")
        }
        has_unresolved_rebuilds = bool(rebuild_open_ids - close_ids)

        if initial_closed and not has_open_remaining and not has_unresolved_rebuilds:
            status = "completed"
        elif has_open_remaining:
            status = "active"
        elif not has_open_remaining and has_unresolved_rebuilds:
            # All positions closed but rebuilds pending
            status = "pending"
        else:
            status = "completed"

    _PROTECTION_METHODS = {"volatility_lock", "margin_protection", "shrink", "stop_loss"}
    protection_trades = [
        t
        for t in trades
        if t["execution_method"] in _PROTECTION_METHODS
        or str(t.get("description") or "").startswith("[PROTECTION]")
    ]
    has_protection = len(protection_trades) > 0

    rebuild_trades = [t for t in trades if t.get("is_rebuild")]
    rebuild_count = len(rebuild_trades)

    # --- PnL calculation ---
    # Realized PnL: sum of (exit_price - entry_price) * units for closed positions.
    # For SHORT: PnL = (open_price - close_price) * units.
    # We pair open trades with their close trades by position_id.
    realized_pnl = Decimal("0")
    unrealized_pnl = Decimal("0")

    # Build a map of open_price by position_id (from open/rebuild trades)
    open_price_by_pos: dict[str, Decimal] = {}
    for t in opens:
        pid = str(t["position_id"]) if t.get("position_id") else None
        if pid:
            open_price_by_pos[pid] = Decimal(str(t["price"]))

    for t in closes:
        pid = str(t["position_id"]) if t.get("position_id") else None
        if pid and pid in open_price_by_pos:
            entry_px = open_price_by_pos[pid]
            exit_px = Decimal(str(t["price"]))
            units = abs(t["units"])
            if direction.lower() == "long":
                realized_pnl += (exit_px - entry_px) * units
            else:
                realized_pnl += (entry_px - exit_px) * units

    # Unrealized PnL: sum for positions that are still open.
    # Look up current unrealized_pnl from the Position table.
    still_open_ids = open_ids - close_ids
    if still_open_ids:
        from apps.trading.models.positions import Position

        for pos in Position.objects.filter(id__in=still_open_ids).values_list(
            "unrealized_pnl", flat=True
        ):
            if pos is not None:
                unrealized_pnl += Decimal(str(pos))

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
        "rebuild_count": rebuild_count,
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl),
        "grid_state": grid_state,
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

    # Prefer the margin_ratio stored directly on the trade (captured at
    # the moment the event fired) over the metrics bucket (which reflects
    # the post-tick state).
    trade_mr = t.get("margin_ratio")
    if trade_mr is not None:
        margin_ratio = f"{float(trade_mr):.3f}"

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
        "is_rebuild": bool(t.get("is_rebuild", False)),
    }


def _empty_summary() -> dict[str, int]:
    return {
        "cycle_count": 0,
        "active_count": 0,
        "pending_count": 0,
        "completed_count": 0,
        "total_trades": 0,
    }


def _build_summary(cycles: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cycle_count": len(cycles),
        "active_count": sum(1 for c in cycles if c["status"] == "active"),
        "pending_count": sum(1 for c in cycles if c["status"] == "pending"),
        "completed_count": sum(1 for c in cycles if c["status"] == "completed"),
        "total_trades": sum(c["trade_count"] for c in cycles),
    }
