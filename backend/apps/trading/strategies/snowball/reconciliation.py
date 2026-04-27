"""Snowball broker reconciliation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

from apps.trading.enums import Direction
from apps.trading.models import Position
from apps.trading.strategies.snowball.config import SnowballStrategyConfig
from apps.trading.strategies.snowball.models import Entry, Layer, SnowballStrategyState
from apps.trading.strategies.snowball.pricing import sync_entry_fill_price


class ReconciliationState(Protocol):
    strategy_state: dict[str, Any] | None
    current_balance: Any


class ReconciliationReport(Protocol):
    removed_open_entries: int
    relinked_open_entries: int
    synthesized_open_entries: int
    blockers: list[str]


class StrategyConfigLike(Protocol):
    config_dict: dict[str, Any]


@dataclass(frozen=True)
class PositionMatch:
    position: Position | None
    ambiguous: bool = False


def reconcile_broker_positions(
    *,
    state: ReconciliationState,
    open_positions: list[Position],
    report: ReconciliationReport,
    strategy_config: StrategyConfigLike | None = None,
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

                match = _match_position_for_entry(
                    entry=entry,
                    open_positions=open_positions,
                    by_id=by_id,
                    assigned_ids=assigned_ids,
                )
                matched = match.position
                if match.ambiguous:
                    report.blockers.append(
                        f"Snowball entry {entry.entry_id} "
                        f"(L{entry.layer_number}/R{entry.retracement_count}) "
                        "matches multiple broker positions. Reconciliation is blocked "
                        "to avoid relinking the wrong position."
                    )
                    continue
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
            match = _match_position_for_entry(
                entry=entry,
                open_positions=open_positions,
                by_id=by_id,
                assigned_ids=assigned_ids,
            )
            matched = match.position
            if match.ambiguous:
                report.blockers.append(
                    f"Snowball hedge entry {entry.entry_id} matches multiple broker positions. "
                    "Reconciliation is blocked to avoid relinking the wrong position."
                )
                continue
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

    snowball_state.account_balance = _strict_decimal(
        state.current_balance,
        field_name="state.current_balance",
    )
    snowball_state.account_nav = snowball_state.account_balance + sum(
        (
            _strict_decimal(position.unrealized_pnl, field_name="position.unrealized_pnl")
            for position in open_positions
        ),
        Decimal("0"),
    )
    state.strategy_state = snowball_state.to_dict()


def _apply_position_to_entry(
    *,
    entry: Entry,
    layer: Layer | None,
    position: Position,
    report: ReconciliationReport,
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
        fill_price=_strict_decimal(position.entry_price, field_name="position.entry_price"),
        counter_tp_mode=config.counter_tp_mode,
    )
    entry.layer_number = int(position.layer_index or entry.layer_number or 1)
    entry.retracement_count = int(position.retracement_count or entry.retracement_count or 0)
    if position.entry_time is not None:
        entry.opened_at = position.entry_time


def _match_position_for_entry(
    *,
    entry: Entry,
    open_positions: list[Position],
    by_id: dict[str, Position],
    assigned_ids: set[str],
) -> PositionMatch:
    position_id = str(getattr(entry, "position_id", "") or "").strip()
    if position_id:
        candidate = by_id.get(position_id)
        if candidate is not None and str(candidate.id) not in assigned_ids:
            return PositionMatch(position=candidate)

    entry_layer = int(getattr(entry, "layer_number", 0) or 0)
    entry_retracement = int(getattr(entry, "retracement_count", 0) or 0)
    entry_direction = str(getattr(entry, "direction", "") or "").lower()
    entry_units = abs(int(getattr(entry, "units", 0) or 0))
    candidates: list[Position] = []

    for candidate in open_positions:
        candidate_id = str(candidate.id)
        if candidate_id in assigned_ids:
            continue
        if entry_layer > 0 and int(candidate.layer_index or 0) != entry_layer:
            continue
        if int(candidate.retracement_count or 0) != entry_retracement:
            continue
        if entry_direction in {Direction.LONG.value, Direction.SHORT.value} and (
            str(candidate.direction).lower() != entry_direction
        ):
            continue
        if entry_units > 0 and abs(int(candidate.units)) != entry_units:
            continue

        candidates.append(candidate)

    if not candidates:
        return PositionMatch(position=None)
    if len(candidates) > 1:
        return PositionMatch(position=None, ambiguous=True)
    return PositionMatch(position=candidates[0])


def _strict_decimal(value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"Snowball reconciliation field {field_name} must be decimal") from exc


def _parse_config(strategy_config: StrategyConfigLike | None) -> SnowballStrategyConfig:
    if strategy_config is None:
        return SnowballStrategyConfig.from_dict({})
    return SnowballStrategyConfig.strict_from_dict(strategy_config.config_dict)
