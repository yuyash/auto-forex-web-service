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
        include_trades: bool | None = None,
        ledger_page: int = 1,
        ledger_page_size: int = 25,
        ledger_ordering: str = "-timestamp",
    ) -> dict[str, Any]:
        from apps.trading.models.trades import Trade

        if not execution_id:
            return {"cycles": [], "summary": _empty_summary(), "last_tick_timestamp": None}

        if include_trades is None:
            include_trades = bool(cycle_id)

        qs = Trade.objects.filter(
            task_type=task_type,
            task_id=task.pk,
            execution_id=execution_id,
            cycle_id__isnull=False,
        ).order_by("timestamp")

        if cycle_id:
            qs = qs.filter(cycle_id=cycle_id)

        value_fields = [
            "id",
            "cycle_id",
            "direction",
            "units",
            "instrument",
            "price",
            "execution_method",
            "layer_index",
            "retracement_count",
            "timestamp",
            "position_id",
            "is_rebuild",
        ]
        if include_trades:
            value_fields.extend(
                [
                    "description",
                    "updated_at",
                    "margin_ratio",
                ]
            )

        rows = list(qs.values(*value_fields))
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
        strategy_type = str(getattr(task.config, "strategy_type", "") or "")
        strategy_capabilities = _load_strategy_capabilities(strategy_type)

        if not rows:
            return {
                "execution_id": str(execution_id),
                "visualization": strategy_capabilities.get("visualization", {}),
                "strategy_state": _public_strategy_state(strategy_type, strategy_state),
                "net_grid_ledger": _build_net_grid_ledger_page(
                    strategy_type=strategy_type,
                    strategy_state=strategy_state,
                    page=ledger_page,
                    page_size=ledger_page_size,
                    ordering=ledger_ordering,
                ),
                "cycles": [],
                "summary": _empty_summary(),
                "last_tick_timestamp": _resolve_last_tick_timestamp(execution_state),
            }

        # Look up metrics (volatility, margin) at each trade timestamp
        metrics_by_minute = (
            _load_metrics_for_trades(
                task_type=task_type,
                task_id=str(task.pk),
                execution_id=str(execution_id),
                trades=rows,
            )
            if include_trades
            else {}
        )

        by_cycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_cycle[str(row["cycle_id"])].append(row)

        unrealized_pnl_by_position = _load_unrealized_pnl_map(rows)

        cycle_status_map = _load_cycle_statuses(
            strategy_type=strategy_type,
            strategy_state=strategy_state,
        )
        cycle_grid_state_map = build_cycle_grid_state_map(
            strategy_type=strategy_type,
            strategy_state=strategy_state,
        )

        cycles = [
            _build_cycle(
                cid,
                trades,
                metrics_by_minute,
                cycle_status_map.get(cid),
                cycle_grid_state_map.get(cid),
                unrealized_pnl_by_position,
                include_trades=include_trades,
            )
            for cid, trades in by_cycle.items()
        ]
        cycles.sort(key=lambda c: c["started_at"] or "")

        last_tick_ts = _resolve_last_tick_timestamp(execution_state)

        return {
            "execution_id": str(execution_id),
            "visualization": strategy_capabilities.get("visualization", {}),
            "strategy_state": _public_strategy_state(strategy_type, strategy_state),
            "net_grid_ledger": _build_net_grid_ledger_page(
                strategy_type=strategy_type,
                strategy_state=strategy_state,
                page=ledger_page,
                page_size=ledger_page_size,
                ordering=ledger_ordering,
            ),
            "cycles": cycles,
            "summary": _build_summary(cycles),
            "last_tick_timestamp": last_tick_ts,
        }


def _build_net_grid_ledger_page(
    *,
    strategy_type: str,
    strategy_state: dict[str, Any] | None,
    page: int,
    page_size: int,
    ordering: str,
) -> dict[str, Any] | None:
    if strategy_type != "net_grid" or not isinstance(strategy_state, dict):
        return None
    rows = strategy_state.get("grid_ledger")
    if not isinstance(rows, list):
        rows = []
    safe_page = max(1, int(page or 1))
    safe_page_size = min(max(1, int(page_size or 25)), 200)
    reverse = ordering.startswith("-")
    field = ordering[1:] if reverse else ordering
    allowed_fields = {
        "timestamp",
        "action",
        "reason",
        "units_delta",
        "filled_price",
        "net_units_after",
        "realized_pnl",
    }
    if field not in allowed_fields:
        field = "timestamp"
        reverse = True

    def sort_key(row: Any) -> tuple[bool, Any]:
        value = row.get(field) if isinstance(row, dict) else None
        if field in {"units_delta", "filled_price", "net_units_after", "realized_pnl"}:
            try:
                value = Decimal(str(value))
            except Exception:  # noqa: BLE001
                value = None
        return (value is None, value)

    sorted_rows = sorted(
        [row for row in rows if isinstance(row, dict)],
        key=sort_key,
        reverse=reverse,
    )
    total = len(sorted_rows)
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    return {
        "count": total,
        "page": safe_page,
        "page_size": safe_page_size,
        "ordering": f"-{field}" if reverse else field,
        "results": sorted_rows[start:end],
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


def _public_strategy_state(
    strategy_type: str,
    strategy_state: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Expose visualization-safe strategy state for non-grid strategy pages."""
    if not isinstance(strategy_state, dict):
        return None
    if strategy_type == "net_grid":
        allowed_keys = {
            "current_net_units",
            "target_net_units",
            "open_units",
            "open_direction",
            "average_entry_price",
            "anchor_price",
            "last_grid_price",
            "net_take_profit_price",
            "next_grid_price",
            "take_profit_remaining_pips",
            "profit_protection_active",
            "profit_peak_pips",
            "profit_trailing_stop_price",
            "partial_derisk_done",
            "current_atr_pips",
            "effective_grid_interval_pips",
            "effective_next_grid_distance_pips",
            "effective_take_profit_pips",
            "effective_order_size_multiplier",
            "fast_ema_price",
            "slow_ema_price",
            "trend_score_pips",
            "auto_direction_required_trend_pips",
            "regime_status",
            "adverse_trend_ticks",
            "adverse_trend_status",
            "risk_exit_price",
            "current_adverse_pips",
            "current_favorable_pips",
            "current_unrealized_pnl",
            "next_order_units",
            "max_net_units",
            "max_adverse_pips",
            "max_loss",
            "drawdown_budget_quote",
            "projected_loss_after_next_add",
            "full_grid_reached_tick",
            "step",
            "step_usage",
            "max_steps",
            "started_at",
            "open_position_id",
            "open_entry_id",
            "next_entry_id",
            "grid_ledger",
            "decision_history",
            "trend_relation_history",
            "level_history",
            "latest_decision",
            "latest_position_transition",
            "pending_execution",
            "last_bid",
            "last_ask",
            "last_mid",
            "last_tick_at",
            "broker_reconciled_at",
            "broker_reconciliation_status",
            "broker_unrealized_pnl",
            "broker_open_trade_count",
            "broker_pending_order_count",
            "broker_backfilled_fill_count",
            "broker_backfilled_fill_count_latest",
            "broker_last_backfilled_transaction_id",
            "broker_backfilled_at",
            "broker_reconciliation_warnings",
            "broker_reconciliation_blockers",
        }
        return {key: strategy_state.get(key) for key in allowed_keys if key in strategy_state}
    if strategy_type != "adaptive_net":
        return None
    allowed_keys = {
        "current_net_units",
        "target_net_units",
        "open_units",
        "open_direction",
        "open_position_id",
        "latest_decision",
        "metric_signals",
        "published_metric_signals",
        "published_metric_names",
        "last_metric_publish_tick",
        "last_metric_publish_at",
        "metric_publish_count",
        "last_decision_metric_publish_count",
        "last_decision_at",
        "latest_position_transition",
        "decision_history",
        "last_price",
        "last_spread_pips",
        "last_fill_price",
        "previous_net_units",
    }
    return {key: strategy_state.get(key) for key in allowed_keys if key in strategy_state}


def _resolve_last_tick_timestamp(execution_state: dict[str, Any]) -> str | None:
    """Return the ISO-formatted last_tick_timestamp from ExecutionState.

    This is the simulated "current time" for a running or completed backtest,
    used by the frontend to anchor active-cycle charts instead of wall-clock time.
    """
    row = execution_state.get("last_tick_timestamp")
    if row is not None:
        return row.isoformat()
    return None


def _load_strategy_capabilities(strategy_type: str) -> dict[str, Any]:
    if not strategy_type:
        return {}
    from apps.trading.strategies.registry import registry

    if not registry.is_registered(strategy_type):
        return {}
    return registry.capabilities(identifier=strategy_type)


def _load_cycle_statuses(
    *,
    strategy_type: str,
    strategy_state: dict[str, Any] | None,
) -> dict[str, str]:
    """Load cycle statuses through the strategy extension point."""
    if not strategy_type or not isinstance(strategy_state, dict):
        return {}
    from apps.trading.strategies.registry import registry

    if not registry.is_registered(strategy_type):
        return {}
    return registry.build_cycle_status_map(
        identifier=strategy_type,
        strategy_state=strategy_state,
    )


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
    unrealized_pnl_by_position: dict[str, Decimal] | None = None,
    *,
    include_trades: bool = True,
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
    still_open_ids = open_ids - close_ids
    open_units_total = 0
    if still_open_ids:
        open_units_total = sum(
            abs(int(t["units"]))
            for t in opens
            if str(t.get("position_id")) in still_open_ids and t.get("position_id")
        )
        for position_id in still_open_ids:
            unrealized_pnl += (unrealized_pnl_by_position or {}).get(position_id, Decimal("0"))

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
        "open_units_total": open_units_total,
        "has_protection": has_protection,
        "protection_count": len(protection_trades),
        "rebuild_count": rebuild_count,
        "position_ids": sorted({str(t["position_id"]) for t in trades if t.get("position_id")}),
        "realized_pnl": str(realized_pnl),
        "unrealized_pnl": str(unrealized_pnl),
        "grid_state": grid_state,
        "trades": [
            _serialize_trade(t, metrics_by_minute, open_price_by_pos, direction) for t in trades
        ]
        if include_trades
        else [],
    }


def _serialize_trade(
    t: dict[str, Any],
    metrics_by_minute: dict[str, dict[str, Any]],
    open_price_by_pos: dict[str, Decimal] | None = None,
    cycle_direction: str = "",
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

    # Compute quote-currency PnL for close trades
    pnl: str | None = None
    _OPEN_METHODS_SET = {"open_position", "rebuild_position"}
    if t["execution_method"] not in _OPEN_METHODS_SET and open_price_by_pos:
        pid = str(t["position_id"]) if t.get("position_id") else None
        if pid and pid in open_price_by_pos:
            entry_px = open_price_by_pos[pid]
            exit_px = Decimal(str(t["price"]))
            units = abs(t["units"])
            if cycle_direction.lower() in {"long", "buy"}:
                pnl = str((exit_px - entry_px) * units)
            elif cycle_direction.lower() in {"short", "sell"}:
                pnl = str((entry_px - exit_px) * units)

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
        "pnl": pnl,
    }


def _empty_summary() -> dict[str, int]:
    return {
        "cycle_count": 0,
        "active_count": 0,
        "pending_count": 0,
        "completed_count": 0,
        "total_trades": 0,
    }


def _load_unrealized_pnl_map(trades: list[dict[str, Any]]) -> dict[str, Decimal]:
    """Load unrealized pnl for any position IDs referenced by open/rebuild trades."""
    from apps.trading.models.positions import Position

    _OPEN_METHODS = {"open_position", "rebuild_position"}
    position_ids = {
        str(t["position_id"])
        for t in trades
        if t.get("position_id") and t.get("execution_method") in _OPEN_METHODS
    }
    if not position_ids:
        return {}

    return {
        str(position_id): Decimal(str(unrealized_pnl or "0"))
        for position_id, unrealized_pnl in Position.objects.filter(id__in=position_ids).values_list(
            "id", "unrealized_pnl"
        )
    }


def _build_summary(cycles: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "cycle_count": len(cycles),
        "active_count": sum(1 for c in cycles if c["status"] == "active"),
        "pending_count": sum(1 for c in cycles if c["status"] == "pending"),
        "completed_count": sum(1 for c in cycles if c["status"] == "completed"),
        "total_trades": sum(c["trade_count"] for c in cycles),
    }
