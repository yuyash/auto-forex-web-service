"""Cycle-based strategy visualization service.

Builds the cycle list from Trade.cycle_id with server-side pagination,
filtering, and sorting.  The service has two modes:

* **List mode** (no ``cycle_id``): returns a page of cycles with lightweight
  per-cycle aggregates (counts, PnL, grid_state) plus an overall ``summary``
  computed after filters are applied.  Individual trades are **not** included.
* **Detail mode** (``cycle_id`` supplied): returns a single cycle with its
  full trade ledger, identical in shape to the list mode entries but with
  ``trades`` populated.

Heavy full-trade serialisation is therefore avoided on every list render.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from django.db.models import Q

from apps.trading.services.strategy_grid_state import build_cycle_grid_state_map

# Execution methods we treat as opening a slot in the cycle grid.
_OPEN_METHODS: frozenset[str] = frozenset({"open_position", "rebuild_position"})

# Execution methods flagged as protection events in the cycle badge.
_PROTECTION_METHODS: frozenset[str] = frozenset(
    {"volatility_lock", "margin_protection", "shrink", "stop_loss"}
)

# Minimum number of characters required for substring filters on UUIDs to
# keep the query cheap while still being useful for search-by-prefix.
_MIN_ID_FILTER_LENGTH = 3


class StrategyCyclesService:
    """Build cycle response from Trade records grouped by cycle_id."""

    def build(
        self,
        *,
        task: Any,
        task_type: str,
        execution_id: UUID | str | None,
        cycle_id: UUID | str | None = None,
        cycle_page: int = 1,
        cycle_page_size: int = 50,
        cycle_sort: str = "asc",
        cycle_status: str = "all",
        position_id: str = "",
        trade_id: str = "",
    ) -> dict[str, Any]:
        if not execution_id:
            return self._empty_response(execution_id=None, strategy_type="")

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
        last_tick_ts = _resolve_last_tick_timestamp(execution_state)
        cycle_status_map = _load_cycle_statuses(
            strategy_type=strategy_type,
            strategy_state=strategy_state,
        )
        cycle_grid_state_map = build_cycle_grid_state_map(
            strategy_type=strategy_type,
            strategy_state=strategy_state,
        )

        if cycle_id:
            return self._build_detail_response(
                task=task,
                task_type=task_type,
                execution_id=str(execution_id),
                cycle_id=str(cycle_id),
                strategy_type=strategy_type,
                strategy_capabilities=strategy_capabilities,
                cycle_status_map=cycle_status_map,
                cycle_grid_state_map=cycle_grid_state_map,
                last_tick_ts=last_tick_ts,
            )

        return self._build_list_response(
            task=task,
            task_type=task_type,
            execution_id=str(execution_id),
            strategy_type=strategy_type,
            strategy_capabilities=strategy_capabilities,
            cycle_status_map=cycle_status_map,
            cycle_grid_state_map=cycle_grid_state_map,
            last_tick_ts=last_tick_ts,
            page=cycle_page,
            page_size=cycle_page_size,
            sort=cycle_sort,
            status_filter=cycle_status,
            position_id_filter=position_id,
            trade_id_filter=trade_id,
        )

    # ------------------------------------------------------------------
    # Detail mode (single cycle with full trade ledger)
    # ------------------------------------------------------------------

    def _build_detail_response(
        self,
        *,
        task: Any,
        task_type: str,
        execution_id: str,
        cycle_id: str,
        strategy_type: str,
        strategy_capabilities: dict[str, Any],
        cycle_status_map: dict[str, str],
        cycle_grid_state_map: dict[str, dict[str, Any]],
        last_tick_ts: str | None,
    ) -> dict[str, Any]:
        from apps.trading.models.trades import Trade

        rows = list(
            Trade.objects.filter(
                task_type=task_type,
                task_id=task.pk,
                execution_id=execution_id,
                cycle_id=cycle_id,
            )
            .order_by("timestamp")
            .values(
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
                "description",
                "updated_at",
                "margin_ratio",
            )
        )

        if not rows:
            return {
                "execution_id": execution_id,
                "visualization": strategy_capabilities.get("visualization", {}),
                "cycles": [],
                "summary": _empty_summary(),
                "pagination": None,
                "last_tick_timestamp": last_tick_ts,
                "money_context": _task_money_context_dict(task=task, task_type=task_type),
            }

        metrics_by_minute = _load_metrics_for_trades(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=execution_id,
            trades=rows,
        )
        unrealized_pnl_by_position = _load_unrealized_pnl_map(rows)

        cycle = _build_cycle(
            cycle_id=cycle_id,
            trades=rows,
            metrics_by_minute=metrics_by_minute,
            authoritative_status=cycle_status_map.get(cycle_id),
            grid_state=cycle_grid_state_map.get(cycle_id),
            unrealized_pnl_by_position=unrealized_pnl_by_position,
            include_trades=True,
        )
        _attach_cycle_display_money([cycle], task=task, task_type=task_type)

        return {
            "execution_id": execution_id,
            "visualization": strategy_capabilities.get("visualization", {}),
            "cycles": [cycle],
            "summary": _build_summary([cycle]),
            "pagination": None,
            "last_tick_timestamp": last_tick_ts,
            "strategy_type": strategy_type,
            "money_context": _task_money_context_dict(task=task, task_type=task_type),
        }

    # ------------------------------------------------------------------
    # List mode (paginated, filtered aggregates)
    # ------------------------------------------------------------------

    def _build_list_response(
        self,
        *,
        task: Any,
        task_type: str,
        execution_id: str,
        strategy_type: str,
        strategy_capabilities: dict[str, Any],
        cycle_status_map: dict[str, str],
        cycle_grid_state_map: dict[str, dict[str, Any]],
        last_tick_ts: str | None,
        page: int,
        page_size: int,
        sort: str,
        status_filter: str,
        position_id_filter: str,
        trade_id_filter: str,
    ) -> dict[str, Any]:
        # Step 1: find all cycle_ids belonging to this execution along with
        # a started_at anchor (the min timestamp in the cycle).
        cycle_meta = _load_cycle_started_at_map(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=execution_id,
        )

        # Step 2: apply id-substring filters that require scanning the
        # trades table.  These narrow the cycle_id universe *before* we
        # spend any effort serialising.  Both filters require a minimum
        # length to avoid accidentally returning every cycle.
        allowed_cycle_ids: set[str] | None = None
        if len(position_id_filter) >= _MIN_ID_FILTER_LENGTH:
            matched = _cycle_ids_with_position_id_like(
                task_type=task_type,
                task_id=str(task.pk),
                execution_id=execution_id,
                needle=position_id_filter,
            )
            allowed_cycle_ids = (
                matched if allowed_cycle_ids is None else allowed_cycle_ids & matched
            )
        if len(trade_id_filter) >= _MIN_ID_FILTER_LENGTH:
            matched = _cycle_ids_with_trade_id_like(
                task_type=task_type,
                task_id=str(task.pk),
                execution_id=execution_id,
                needle=trade_id_filter,
            )
            allowed_cycle_ids = (
                matched if allowed_cycle_ids is None else allowed_cycle_ids & matched
            )

        # Step 3: build the candidate id list (id filters + ordering only).
        candidate_cycle_ids: list[str] = []
        for cid, _started_at in cycle_meta:
            if allowed_cycle_ids is not None and cid not in allowed_cycle_ids:
                continue
            candidate_cycle_ids.append(cid)

        # Step 4: apply status filter.  Status requires aggregated trade
        # data for cycles lacking an authoritative entry in the strategy
        # state, so we resolve status lazily per cycle using the aggregate
        # fallback.  To avoid loading aggregates for every cycle when no
        # status filter is applied, we only do this work when filtering.
        if status_filter != "all":
            status_filtered_ids = _filter_cycle_ids_by_status(
                task_type=task_type,
                task_id=str(task.pk),
                execution_id=execution_id,
                cycle_ids=candidate_cycle_ids,
                cycle_status_map=cycle_status_map,
                status_filter=status_filter,
            )
        else:
            status_filtered_ids = candidate_cycle_ids

        if sort == "desc":
            status_filtered_ids = list(reversed(status_filtered_ids))

        total_count = len(status_filtered_ids)
        total_pages = (total_count + page_size - 1) // page_size if total_count else 0
        safe_page = max(1, page)
        start_index = (safe_page - 1) * page_size
        end_index = start_index + page_size
        page_cycle_ids = status_filtered_ids[start_index:end_index]

        # Step 5: load a lightweight trade slice for the cycles on this
        # page only.  We need trades for PnL/unit counting and grid
        # reconstruction, not for rendering — so we skip description /
        # metrics columns to keep the payload small.
        aggregates = _load_cycle_aggregates(
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=execution_id,
            cycle_ids=page_cycle_ids,
        )
        unrealized_pnl_by_position = _load_unrealized_pnl_map_for_position_ids(
            aggregates.still_open_position_ids
        )

        cycles = [
            _build_list_cycle(
                cycle_id=cid,
                aggregate=aggregates.per_cycle[cid],
                authoritative_status=cycle_status_map.get(cid),
                grid_state=cycle_grid_state_map.get(cid),
                unrealized_pnl_by_position=unrealized_pnl_by_position,
            )
            for cid in page_cycle_ids
        ]
        _attach_cycle_display_money(cycles, task=task, task_type=task_type)

        # Step 6: summary counts over the full filtered universe.  Counts
        # come from the same cycle universe we paginated over so numbers
        # stay self-consistent.
        summary = _build_filtered_summary(
            cycle_ids=status_filtered_ids,
            cycle_status_map=cycle_status_map,
            task_type=task_type,
            task_id=str(task.pk),
            execution_id=execution_id,
        )

        return {
            "execution_id": execution_id,
            "visualization": strategy_capabilities.get("visualization", {}),
            "cycles": cycles,
            "summary": summary,
            "pagination": {
                "page": safe_page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
            },
            "last_tick_timestamp": last_tick_ts,
            "strategy_type": strategy_type,
            "money_context": _task_money_context_dict(task=task, task_type=task_type),
        }

    def _empty_response(self, *, execution_id: str | None, strategy_type: str) -> dict[str, Any]:
        return {
            "execution_id": execution_id,
            "cycles": [],
            "summary": _empty_summary(),
            "pagination": None,
            "last_tick_timestamp": None,
            "strategy_type": strategy_type,
            "money_context": None,
        }


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------


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
    """Expose visualization-safe strategy state for non-grid strategy pages.

    Retained for external callers / tests; list responses no longer embed
    the raw strategy_state (it is only used server-side now).
    """
    if not isinstance(strategy_state, dict):
        return None
    return None


def _resolve_last_tick_timestamp(execution_state: dict[str, Any]) -> str | None:
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
    """Load minute-level metrics closest to each trade timestamp."""
    from apps.trading.models.metrics import Metrics

    if not trades:
        return {}

    minute_keys: set[str] = set()
    for t in trades:
        ts = t.get("timestamp")
        if ts:
            bucket = ts.replace(second=0, microsecond=0)
            minute_keys.add(bucket.isoformat())

    if not minute_keys:
        return {}

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


def _load_cycle_started_at_map(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
) -> list[tuple[str, Any]]:
    """Return [(cycle_id, started_at)] sorted by started_at ascending."""
    from django.db.models import Min

    from apps.trading.models.trades import Trade

    rows = (
        Trade.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_id__isnull=False,
        )
        .values("cycle_id")
        .annotate(started_at=Min("timestamp"))
        .order_by("started_at")
    )
    return [(str(row["cycle_id"]), row["started_at"]) for row in rows]


def _cycle_ids_with_position_id_like(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    needle: str,
) -> set[str]:
    from django.db.models import TextField
    from django.db.models.functions import Cast

    from apps.trading.models.trades import Trade

    rows = (
        Trade.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_id__isnull=False,
        )
        .annotate(position_id_text=Cast("position_id", output_field=TextField()))
        .filter(_position_id_icontains_q(needle))
        .values_list("cycle_id", flat=True)
    )
    return {str(cid) for cid in rows}


def _cycle_ids_with_trade_id_like(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    needle: str,
) -> set[str]:
    from django.db.models import TextField
    from django.db.models.functions import Cast

    from apps.trading.models.trades import Trade

    rows = (
        Trade.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_id__isnull=False,
        )
        .annotate(id_text=Cast("id", output_field=TextField()))
        .filter(_trade_id_icontains_q(needle))
        .values_list("cycle_id", flat=True)
    )
    return {str(cid) for cid in rows}


def _filter_cycle_ids_by_status(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    cycle_ids: list[str],
    cycle_status_map: dict[str, str],
    status_filter: str,
) -> list[str]:
    """Return the subset of ``cycle_ids`` whose resolved status matches.

    Cycles present in the authoritative map are resolved with a cheap
    dict lookup.  Cycles without an authoritative entry have their
    status derived from trade aggregates; those cycles are loaded in a
    single follow-up query.
    """
    authoritative_matches: list[str] = []
    unresolved_cycle_ids: list[str] = []
    for cid in cycle_ids:
        if cid in cycle_status_map:
            if cycle_status_map[cid] == status_filter:
                authoritative_matches.append(cid)
        else:
            unresolved_cycle_ids.append(cid)

    fallback_matches: list[str] = []
    if unresolved_cycle_ids:
        aggregates = _load_cycle_aggregates(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_ids=unresolved_cycle_ids,
        )
        for cid in unresolved_cycle_ids:
            status = _resolve_cycle_status(aggregates.per_cycle[cid], None)
            if status == status_filter:
                fallback_matches.append(cid)

    matched = set(authoritative_matches) | set(fallback_matches)
    return [cid for cid in cycle_ids if cid in matched]


def _position_id_icontains_q(needle: str) -> Q:
    """Build a Q object that matches Position IDs containing ``needle``.

    ``position_id`` is the UUID raw column that backs a ``ForeignKey`` so
    ``__icontains`` on it is rejected by Django.  We cast to text via an
    annotation instead (the caller is expected to do the cast).
    """
    return Q(position_id_text__icontains=needle)


def _trade_id_icontains_q(needle: str) -> Q:
    """Build a Q object that matches Trade IDs containing ``needle``."""
    return Q(id_text__icontains=needle)


class _CycleAggregates:
    """Lightweight container of per-cycle aggregate data for list mode."""

    __slots__ = ("per_cycle", "still_open_position_ids")

    def __init__(
        self,
        per_cycle: dict[str, dict[str, Any]],
        still_open_position_ids: set[str],
    ) -> None:
        self.per_cycle = per_cycle
        self.still_open_position_ids = still_open_position_ids


def _load_cycle_aggregates(
    *,
    task_type: str,
    task_id: str,
    execution_id: str,
    cycle_ids: list[str],
) -> _CycleAggregates:
    """Load the trade slice needed for list-mode aggregates.

    Returns a container holding per-cycle aggregate dicts ready for
    :func:`_build_list_cycle`.  Only the minimum set of columns is loaded
    since list rendering never displays individual trades.
    """
    from apps.trading.models.trades import Trade

    per_cycle: dict[str, dict[str, Any]] = {}
    still_open_position_ids: set[str] = set()

    if not cycle_ids:
        return _CycleAggregates(
            per_cycle=per_cycle, still_open_position_ids=still_open_position_ids
        )

    rows = list(
        Trade.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_id__in=cycle_ids,
        )
        .order_by("timestamp")
        .values(
            "id",
            "cycle_id",
            "direction",
            "units",
            "price",
            "execution_method",
            "timestamp",
            "position_id",
            "is_rebuild",
        )
    )

    by_cycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_cycle[str(row["cycle_id"])].append(row)

    for cid in cycle_ids:
        trades = by_cycle.get(cid, [])
        aggregate = _aggregate_cycle(cid, trades)
        per_cycle[cid] = aggregate
        still_open_position_ids.update(aggregate["still_open_position_ids"])

    return _CycleAggregates(
        per_cycle=per_cycle,
        still_open_position_ids=still_open_position_ids,
    )


def _aggregate_cycle(cycle_id: str, trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Fold a cycle's trade rows into the aggregate dict list mode needs."""
    if not trades:
        return {
            "cycle_id": cycle_id,
            "direction": "",
            "trade_count": 0,
            "open_count": 0,
            "close_count": 0,
            "open_units_total": 0,
            "position_ids": [],
            "realized_pnl": Decimal("0"),
            "rebuild_count": 0,
            "protection_count": 0,
            "has_protection": False,
            "started_at": None,
            "last_timestamp": None,
            "last_price": None,
            "still_open_position_ids": set(),
            "initial_is_closed": False,
            "has_unresolved_rebuilds": False,
            "has_open_remaining": False,
        }

    first = trades[0]
    last = trades[-1]
    direction = str(first.get("direction") or "").lower()

    open_price_by_pos: dict[str, Decimal] = {}
    open_ids: set[str] = set()
    close_ids: set[str] = set()
    rebuild_open_ids: set[str] = set()
    open_count = 0
    close_count = 0
    realized_pnl = Decimal("0")
    protection_count = 0
    rebuild_count = 0
    position_ids_seen: set[str] = set()
    units_by_open_pos: dict[str, int] = {}

    for trade in trades:
        pid = str(trade["position_id"]) if trade.get("position_id") else None
        if pid:
            position_ids_seen.add(pid)

        exec_method = trade["execution_method"]
        if exec_method in _OPEN_METHODS:
            open_count += 1
            if pid is not None:
                open_ids.add(pid)
                open_price_by_pos[pid] = Decimal(str(trade["price"]))
                units_by_open_pos[pid] = abs(int(trade["units"] or 0))
                if trade.get("is_rebuild") and exec_method == "rebuild_position":
                    rebuild_open_ids.add(pid)
        else:
            close_count += 1
            if pid is not None:
                close_ids.add(pid)
                entry_px = open_price_by_pos.get(pid)
                if entry_px is not None:
                    exit_px = Decimal(str(trade["price"]))
                    units = abs(int(trade["units"] or 0))
                    if direction == "long":
                        realized_pnl += (exit_px - entry_px) * units
                    else:
                        realized_pnl += (entry_px - exit_px) * units

        if trade.get("is_rebuild"):
            rebuild_count += 1
        if exec_method in _PROTECTION_METHODS or str(trade.get("description", "") or "").startswith(
            "[PROTECTION]"
        ):
            protection_count += 1

    still_open_position_ids = open_ids - close_ids
    has_open_remaining = bool(still_open_position_ids)
    has_unresolved_rebuilds = bool(rebuild_open_ids - close_ids)

    initial_trade = next(
        (t for t in trades if t["execution_method"] in _OPEN_METHODS and str(t["id"]) == cycle_id),
        first,
    )
    initial_pid = (
        str(initial_trade.get("position_id")) if initial_trade.get("position_id") else None
    )
    initial_is_closed = bool(initial_pid) and initial_pid in close_ids

    open_units_total = sum(units_by_open_pos.get(pid, 0) for pid in still_open_position_ids)

    return {
        "cycle_id": cycle_id,
        "direction": direction,
        "trade_count": len(trades),
        "open_count": open_count,
        "close_count": close_count,
        "open_units_total": open_units_total,
        "position_ids": sorted(position_ids_seen),
        "realized_pnl": realized_pnl,
        "rebuild_count": rebuild_count,
        "protection_count": protection_count,
        "has_protection": protection_count > 0,
        "started_at": first["timestamp"],
        "last_timestamp": last["timestamp"],
        "last_price": Decimal(str(last["price"])),
        "still_open_position_ids": still_open_position_ids,
        "initial_is_closed": initial_is_closed,
        "has_unresolved_rebuilds": has_unresolved_rebuilds,
        "has_open_remaining": has_open_remaining,
    }


def _build_list_cycle(
    *,
    cycle_id: str,
    aggregate: dict[str, Any],
    authoritative_status: str | None,
    grid_state: dict[str, Any] | None,
    unrealized_pnl_by_position: dict[str, Decimal],
) -> dict[str, Any]:
    """Shape a single aggregated cycle into the list-mode payload."""
    status = _resolve_cycle_status(aggregate, authoritative_status)

    unrealized_pnl = Decimal("0")
    for pid in aggregate["still_open_position_ids"]:
        unrealized_pnl += unrealized_pnl_by_position.get(pid, Decimal("0"))

    started_at = aggregate["started_at"]
    ended_at = aggregate["last_timestamp"] if status == "completed" else None
    return {
        "cycle_id": cycle_id,
        "direction": aggregate["direction"],
        "status": status,
        "started_at": started_at.isoformat() if started_at else None,
        "ended_at": ended_at.isoformat() if ended_at else None,
        "trade_count": aggregate["trade_count"],
        "open_count": aggregate["open_count"],
        "close_count": aggregate["close_count"],
        "open_units_total": aggregate["open_units_total"],
        "has_protection": aggregate["has_protection"],
        "protection_count": aggregate["protection_count"],
        "rebuild_count": aggregate["rebuild_count"],
        "position_ids": aggregate["position_ids"],
        "realized_pnl": str(aggregate["realized_pnl"]),
        "unrealized_pnl": str(unrealized_pnl),
        "_conversion_mid_price": str(aggregate.get("last_price") or ""),
        "grid_state": grid_state,
        "trades": [],
    }


def _resolve_cycle_status(aggregate: dict[str, Any], authoritative_status: str | None) -> str:
    """Pick the status for a cycle, preferring the authoritative map."""
    if authoritative_status is not None:
        return authoritative_status

    if (
        aggregate["initial_is_closed"]
        and not aggregate["has_open_remaining"]
        and not aggregate["has_unresolved_rebuilds"]
    ):
        return "completed"
    if aggregate["has_open_remaining"]:
        return "active"
    if not aggregate["has_open_remaining"] and aggregate["has_unresolved_rebuilds"]:
        return "pending"
    return "completed"


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
    """Detail-mode cycle builder that serialises every trade in the cycle."""
    aggregate = _aggregate_cycle(cycle_id, trades)
    status = _resolve_cycle_status(aggregate, authoritative_status)

    unrealized_pnl = Decimal("0")
    for pid in aggregate["still_open_position_ids"]:
        unrealized_pnl += (unrealized_pnl_by_position or {}).get(pid, Decimal("0"))

    open_price_by_pos: dict[str, Decimal] = {}
    for trade in trades:
        if trade["execution_method"] in _OPEN_METHODS and trade.get("position_id"):
            open_price_by_pos[str(trade["position_id"])] = Decimal(str(trade["price"]))

    started_at = aggregate["started_at"]
    ended_at = aggregate["last_timestamp"] if status == "completed" else None
    return {
        "cycle_id": cycle_id,
        "direction": aggregate["direction"],
        "status": status,
        "started_at": started_at.isoformat() if started_at else None,
        "ended_at": ended_at.isoformat() if ended_at else None,
        "trade_count": aggregate["trade_count"],
        "open_count": aggregate["open_count"],
        "close_count": aggregate["close_count"],
        "open_units_total": aggregate["open_units_total"],
        "has_protection": aggregate["has_protection"],
        "protection_count": aggregate["protection_count"],
        "rebuild_count": aggregate["rebuild_count"],
        "position_ids": aggregate["position_ids"],
        "realized_pnl": str(aggregate["realized_pnl"]),
        "unrealized_pnl": str(unrealized_pnl),
        "_conversion_mid_price": str(aggregate.get("last_price") or ""),
        "grid_state": grid_state,
        "trades": [
            _serialize_trade(t, metrics_by_minute, open_price_by_pos, aggregate["direction"])
            for t in trades
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

    trade_mr = t.get("margin_ratio")
    if trade_mr is not None:
        margin_ratio = f"{float(trade_mr):.3f}"

    pnl: str | None = None
    if t["execution_method"] not in _OPEN_METHODS and open_price_by_pos:
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


def _task_money_context_dict(*, task: Any, task_type: str) -> dict[str, Any]:
    from apps.trading.services.task_money_context import TASK_MONEY_CONTEXT

    task_type_label = "trading" if str(task_type) == "trading" else "backtest"
    return TASK_MONEY_CONTEXT.build(task, task_type=task_type_label).as_dict()


def _attach_cycle_display_money(
    cycles: list[dict[str, Any]],
    *,
    task: Any,
    task_type: str,
) -> None:
    if not cycles:
        return

    from apps.trading.money import Money
    from apps.trading.services.display_money import DISPLAY_MONEY
    from apps.trading.services.fx_rates import FX_CONVERSION
    from apps.trading.services.task_money_context import TASK_MONEY_CONTEXT
    from apps.trading.utils import Instrument

    task_type_label = "trading" if str(task_type) == "trading" else "backtest"
    money_context = TASK_MONEY_CONTEXT.build(task, task_type=task_type_label)
    target_currency = money_context.display_currency
    instrument = str(getattr(task, "instrument", "") or "").strip()
    quote_currency = Instrument(instrument).quote_currency
    if not target_currency or not quote_currency:
        for cycle in cycles:
            cycle.pop("_conversion_mid_price", None)
        return

    fx_conversion = FX_CONVERSION.with_cache()
    for cycle in cycles:
        realized = _decimal_or_none(cycle.get("realized_pnl")) or Decimal("0")
        unrealized = _decimal_or_none(cycle.get("unrealized_pnl")) or Decimal("0")
        total = realized + unrealized
        source_values = {
            "realized_pnl": Money.coerce(realized, quote_currency),
            "unrealized_pnl": Money.coerce(unrealized, quote_currency),
            "total_pnl": Money.coerce(total, quote_currency),
        }
        cycle["realized_pnl_money"] = source_values["realized_pnl"].as_dict()
        cycle["unrealized_pnl_money"] = source_values["unrealized_pnl"].as_dict()
        cycle["total_pnl_money"] = source_values["total_pnl"].as_dict()

        converted = DISPLAY_MONEY.convert_many(
            source_values,
            target_currency=target_currency,
            instrument=instrument,
            mid_price=_decimal_or_none(cycle.pop("_conversion_mid_price", None)),
            as_of=_cycle_pnl_as_of(cycle),
            fx_conversion=fx_conversion,
        )
        cycle["realized_pnl_display_money"] = converted.values.get("realized_pnl")
        cycle["unrealized_pnl_display_money"] = converted.values.get("unrealized_pnl")
        cycle["total_pnl_display_money"] = converted.values.get("total_pnl")
        if converted.conversion_context is not None:
            cycle["display_conversion_context"] = converted.conversion_context


def _cycle_pnl_as_of(cycle: dict[str, Any]) -> datetime | None:
    for key in ("ended_at", "started_at"):
        parsed = _datetime_or_none(cycle.get(key))
        if parsed is not None:
            return parsed
    return None


def _datetime_or_none(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


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


def _build_filtered_summary(
    *,
    cycle_ids: list[str],
    cycle_status_map: dict[str, str],
    task_type: str,
    task_id: str,
    execution_id: str,
) -> dict[str, int]:
    """Summary counts over the filtered cycle universe.

    Authoritative statuses from ``cycle_status_map`` are used where
    available; cycles without an entry fall back to the aggregate-based
    resolution used for list rendering.
    """
    from django.db.models import Count

    from apps.trading.models.trades import Trade

    cycle_count = len(cycle_ids)
    if cycle_count == 0:
        return _empty_summary()

    active_count = 0
    pending_count = 0
    completed_count = 0
    unresolved_cycle_ids: list[str] = []
    for cid in cycle_ids:
        status = cycle_status_map.get(cid)
        if status == "active":
            active_count += 1
        elif status == "pending":
            pending_count += 1
        elif status == "completed":
            completed_count += 1
        elif status is None:
            unresolved_cycle_ids.append(cid)

    if unresolved_cycle_ids:
        aggregates = _load_cycle_aggregates(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_ids=unresolved_cycle_ids,
        )
        for cid in unresolved_cycle_ids:
            status = _resolve_cycle_status(aggregates.per_cycle[cid], None)
            if status == "active":
                active_count += 1
            elif status == "pending":
                pending_count += 1
            else:
                completed_count += 1

    total_trades = (
        Trade.objects.filter(
            task_type=task_type,
            task_id=task_id,
            execution_id=execution_id,
            cycle_id__in=cycle_ids,
        )
        .aggregate(total=Count("id"))
        .get("total")
        or 0
    )

    return {
        "cycle_count": cycle_count,
        "active_count": active_count,
        "pending_count": pending_count,
        "completed_count": completed_count,
        "total_trades": total_trades,
    }


def _load_unrealized_pnl_map(trades: list[dict[str, Any]]) -> dict[str, Decimal]:
    """Load unrealized pnl for any position IDs referenced by open trades."""
    position_ids = {
        str(t["position_id"])
        for t in trades
        if t.get("position_id") and t.get("execution_method") in _OPEN_METHODS
    }
    return _load_unrealized_pnl_map_for_position_ids(position_ids)


def _load_unrealized_pnl_map_for_position_ids(
    position_ids: set[str],
) -> dict[str, Decimal]:
    from apps.trading.models.positions import Position

    if not position_ids:
        return {}

    return {
        str(position_id): Decimal(str(unrealized_pnl or "0"))
        for position_id, unrealized_pnl in Position.objects.filter(id__in=position_ids).values_list(
            "id", "unrealized_pnl"
        )
    }
