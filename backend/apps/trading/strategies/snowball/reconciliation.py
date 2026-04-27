"""Snowball broker reconciliation adapter."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from apps.trading.enums import Direction
from apps.trading.models import Position
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.models import SnowballStrategyState
from apps.trading.strategies.snowball.pricing import sync_entry_fill_price


def reconcile_broker_positions(
    *,
    state: Any,
    open_positions: list[Position],
    report: Any,
    strategy_config: Any | None = None,
) -> None:
    """Reconcile persisted Snowball entries against broker-backed positions."""
    snowball_state = SnowballStrategyState.from_strategy_state(state.strategy_state)
    config = _parse_config(strategy_config)
    by_id = {str(position.id): position for position in open_positions}
    assigned_ids: set[str] = set()

    for cycle in snowball_state.cycles:
        for layer in cycle.grid.layers:
            for slot in layer.slots:
                entry = slot.entry
                if entry is None:
                    continue

                matched = _match_position_for_entry(
                    entry=entry,
                    open_positions=open_positions,
                    by_id=by_id,
                    assigned_ids=assigned_ids,
                )
                if matched is None:
                    report.removed_open_entries += 1
                    report.blockers.append(
                        f"Snowball entry {entry.entry_id} "
                        f"(L{entry.layer_number}/R{entry.retracement_count}) "
                        "has no matching broker position. The position may have been "
                        "closed externally while the task was stopped. Use restart to "
                        "begin a fresh execution."
                    )
                    continue

                _apply_position_to_entry(
                    entry=entry,
                    layer=layer,
                    position=matched,
                    report=report,
                    config=config,
                )
                assigned_ids.add(str(matched.id))

        for entry in cycle.hedge_entries:
            matched = _match_position_for_entry(
                entry=entry,
                open_positions=open_positions,
                by_id=by_id,
                assigned_ids=assigned_ids,
            )
            if matched is None:
                report.removed_open_entries += 1
                report.blockers.append(
                    f"Snowball hedge entry {entry.entry_id} has no matching broker position. "
                    "The position may have been closed externally while the task was stopped. "
                    "Use restart to begin a fresh execution."
                )
                continue

            _apply_position_to_entry(
                entry=entry,
                layer=None,
                position=matched,
                report=report,
                config=config,
            )
            assigned_ids.add(str(matched.id))

    unmatched_positions = [
        position for position in open_positions if str(position.id) not in assigned_ids
    ]
    for position in unmatched_positions:
        report.synthesized_open_entries += 1
        report.blockers.append(
            "Snowball strategy state could not match open position "
            f"{position.id} (layer={position.layer_index}, "
            f"retracement={position.retracement_count})."
        )

    snowball_state.account_balance = _safe_decimal(state.current_balance)
    snowball_state.account_nav = snowball_state.account_balance + sum(
        (_safe_decimal(position.unrealized_pnl) for position in open_positions),
        Decimal("0"),
    )
    state.strategy_state = snowball_state.to_dict()


def _apply_position_to_entry(
    *,
    entry: Any,
    layer: Any,
    position: Position,
    report: Any,
    config: SnowballStrategyConfig,
) -> None:
    position_id = str(position.id)
    if entry.position_id != position_id:
        entry.position_id = position_id
        report.relinked_open_entries += 1

    entry.direction = Direction(str(position.direction).lower())
    entry.units = abs(int(position.units))
    sync_entry_fill_price(
        entry=entry,
        layer=layer,
        fill_price=_safe_decimal(position.entry_price),
        counter_tp_mode=config.counter_tp_mode,
    )
    entry.layer_number = int(position.layer_index or entry.layer_number or 1)
    entry.retracement_count = int(position.retracement_count or entry.retracement_count or 0)
    if position.entry_time is not None:
        entry.opened_at = position.entry_time


def _match_position_for_entry(
    *,
    entry: Any,
    open_positions: list[Position],
    by_id: dict[str, Position],
    assigned_ids: set[str],
) -> Position | None:
    position_id = str(getattr(entry, "position_id", "") or "").strip()
    if position_id:
        candidate = by_id.get(position_id)
        if candidate is not None and str(candidate.id) not in assigned_ids:
            return candidate

    entry_layer = int(getattr(entry, "layer_number", 0) or 0)
    entry_retracement = int(getattr(entry, "retracement_count", 0) or 0)
    entry_direction = str(getattr(entry, "direction", "") or "").lower()
    entry_units = abs(int(getattr(entry, "units", 0) or 0))
    entry_price = _safe_decimal(getattr(entry, "entry_price", None))

    best: Position | None = None
    best_price_diff: Decimal | None = None

    for candidate in open_positions:
        candidate_id = str(candidate.id)
        if candidate_id in assigned_ids:
            continue
        if entry_layer > 0 and int(candidate.layer_index or 0) != entry_layer:
            continue
        if int(candidate.retracement_count or 0) != entry_retracement:
            continue
        if (
            entry_direction in {Direction.LONG, Direction.SHORT}
            and str(candidate.direction) != entry_direction
        ):
            continue
        if entry_units > 0 and abs(int(candidate.units)) != entry_units:
            continue

        diff = abs(_safe_decimal(candidate.entry_price) - entry_price)
        if best is None or best_price_diff is None or diff < best_price_diff:
            best = candidate
            best_price_diff = diff

    return best


def _safe_decimal(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:  # nosec B110
        return Decimal(default)


def _parse_config(strategy_config: Any | None) -> SnowballStrategyConfig:
    if strategy_config is None:
        return SnowballStrategyConfig.from_dict({})
    return SnowballStrategyConfig.from_dict(getattr(strategy_config, "config_dict", {}) or {})
